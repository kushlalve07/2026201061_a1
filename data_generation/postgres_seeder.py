"""
RideSync Step 4 — PostgreSQL seeder.

Targets (assignment):
  - at least 50,000 trips
  - at least 100,000 wallet_audit_logs (via the wallet_balance trigger)

Usage:
  python data_generation/postgres_seeder.py
  python data_generation/postgres_seeder.py --reset
"""

from __future__ import annotations

import argparse
import os
import random
from datetime import timezone

import psycopg2
from faker import Faker
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "ridesync"),
    "user": os.getenv("PGUSER", "ridesync"),
    "password": os.getenv("PGPASSWORD", "ridesync"),
}

NUM_RIDERS = 1_000
NUM_VEHICLES = 500
NUM_TRIPS = 50_000
NUM_WALLET_UPDATES = 100_000
BATCH_SIZE = 5_000
SEED = 42

VEHICLE_CLASSES = ["ECONOMY", "PREMIUM", "XL", "POOL"]

random.seed(SEED)
fake = Faker()
Faker.seed(SEED)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def reset_tables(conn) -> None:
    print("Truncating PostgreSQL tables...")
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE wallet_audit_logs, trips, riders, vehicles RESTART IDENTITY CASCADE"
        )
    conn.commit()


def seed_riders(conn) -> list:
    print(f"Seeding {NUM_RIDERS} riders...")
    rows = [
        (fake.name()[:100], round(random.uniform(200, 5_000), 2))
        for _ in range(NUM_RIDERS)
    ]
    with conn.cursor() as cur:
        returned = execute_values(
            cur,
            "INSERT INTO riders (name, wallet_balance) VALUES %s RETURNING id",
            rows,
            fetch=True,
        )
    conn.commit()
    return [r[0] for r in returned]


def seed_vehicles(conn) -> list:
    print(f"Seeding {NUM_VEHICLES} vehicles...")
    rows = [
        (f"RS{i:05d}", random.choice(VEHICLE_CLASSES), random.random() > 0.1)
        for i in range(NUM_VEHICLES)
    ]
    with conn.cursor() as cur:
        returned = execute_values(
            cur,
            "INSERT INTO vehicles (license_plate, class, is_active) VALUES %s RETURNING id",
            rows,
            fetch=True,
        )
    conn.commit()
    return [r[0] for r in returned]


def seed_trips(conn, rider_ids: list, vehicle_ids: list) -> None:
    """
    At most one REQUESTED/IN_TRANSIT trip per rider so idx_active_rider_trip holds.
    Most trips are COMPLETED so Workflow 2 and the materialized view have revenue.
    """
    print(f"Seeding {NUM_TRIPS} trips...")
    active_riders: set = set()
    inserted = 0
    batch: list = []

    with conn.cursor() as cur:
        for _ in range(NUM_TRIPS):
            rider_id = random.choice(rider_ids)
            if rider_id not in active_riders and random.random() < 0.12:
                status = random.choice(["REQUESTED", "IN_TRANSIT"])
                active_riders.add(rider_id)
            else:
                status = "COMPLETED"

            batch.append(
                (
                    rider_id,
                    random.choice(vehicle_ids),
                    round(random.uniform(5, 250), 2),
                    status,
                    fake.date_time_between(
                        start_date="-90d", end_date="now", tzinfo=timezone.utc
                    ),
                )
            )

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    "INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at) VALUES %s",
                    batch,
                )
                inserted += len(batch)
                batch = []
                conn.commit()
                print(f"  {inserted}/{NUM_TRIPS} trips")

        if batch:
            execute_values(
                cur,
                "INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at) VALUES %s",
                batch,
            )
            inserted += len(batch)
            conn.commit()

    print(f"  Done. {inserted} trips (active riders with one open trip: {len(active_riders)})")


def seed_wallet_audit_logs_via_trigger(conn, rider_ids: list) -> None:
    """
    Do not INSERT into wallet_audit_logs. Each UPDATE of wallet_balance fires
    rider_wallet_audit. One unique rider per statement so Postgres applies
    every row (UPDATE ... FROM with duplicate keys can collapse updates).
    """
    print(f"Applying {NUM_WALLET_UPDATES} wallet updates (trigger writes audit rows)...")
    n_riders = len(rider_ids)
    rounds, leftover = divmod(NUM_WALLET_UPDATES, n_riders)
    applied = 0

    with conn.cursor() as cur:
        for _ in range(rounds):
            batch = [
                (round(random.uniform(-40, 80), 2), rider_id)
                for rider_id in rider_ids
            ]
            execute_values(
                cur,
                """
                UPDATE riders AS r
                SET wallet_balance = GREATEST(r.wallet_balance + v.delta, 0.01)
                FROM (VALUES %s) AS v(delta, rider_id)
                WHERE r.id = v.rider_id::uuid
                """,
                batch,
            )
            applied += len(batch)
            conn.commit()
            print(f"  {applied}/{NUM_WALLET_UPDATES} wallet updates")

        if leftover:
            batch = [
                (round(random.uniform(-40, 80), 2), rider_id)
                for rider_id in random.sample(rider_ids, leftover)
            ]
            execute_values(
                cur,
                """
                UPDATE riders AS r
                SET wallet_balance = GREATEST(r.wallet_balance + v.delta, 0.01)
                FROM (VALUES %s) AS v(delta, rider_id)
                WHERE r.id = v.rider_id::uuid
                """,
                batch,
            )
            applied += len(batch)
            conn.commit()

    print(f"  Done. {applied} wallet updates applied.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RideSync PostgreSQL data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="TRUNCATE riders/vehicles/trips/audit logs before inserting.",
    )
    args = parser.parse_args()

    conn = get_connection()
    try:
        if args.reset:
            reset_tables(conn)
        rider_ids = seed_riders(conn)
        vehicle_ids = seed_vehicles(conn)
        seed_trips(conn, rider_ids, vehicle_ids)
        seed_wallet_audit_logs_via_trigger(conn, rider_ids)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM riders")
            print(f"\nriders: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM vehicles")
            print(f"vehicles: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM trips")
            print(f"trips: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM wallet_audit_logs")
            print(f"wallet_audit_logs: {cur.fetchone()[0]}")
        print("Refresh the materialized view after this: SELECT refresh_vehicle_lifetime_stats();")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
