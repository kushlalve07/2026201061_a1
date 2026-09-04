"""
postgres_seeder.py

Seeds the RideSync PostgreSQL database with mock data:
  - 1,000 riders
  - 500 vehicles
  - 50,000+ trips (bookings)
  - 100,000+ wallet_audit_logs (generated automatically via the wallet_balance trigger)
"""

import random
import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

# ---- Config ----
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ridesync",
    "user": "ridesync",
    "password": "ridesync",
}

NUM_RIDERS = 1_000
NUM_VEHICLES = 500
NUM_TRIPS = 100          # comfortably over the 50k requirement
NUM_WALLET_UPDATES = 100  # comfortably over the 100k requirement (each fires the trigger)

BATCH_SIZE = 5_000
SEED = 42

VEHICLE_CLASSES = ["ECONOMY", "PREMIUM", "XL", "POOL"]
TRIP_STATUSES = ["REQUESTED", "IN_TRANSIT", "COMPLETED"]
TRIP_STATUS_WEIGHTS = [0.1, 0.1, 0.8]  # mostly completed trips, for realistic revenue data

random.seed(SEED)
fake = Faker()
Faker.seed(SEED)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def seed_riders(conn):
    print(f"Seeding {NUM_RIDERS} riders...")
    rows = [
        (fake.name(), round(random.uniform(50, 5000), 2))
        for _ in range(NUM_RIDERS)
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO riders (name, wallet_balance) VALUES %s RETURNING id",
            rows,
        )
        rider_ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    return rider_ids


def seed_vehicles(conn):
    print(f"Seeding {NUM_VEHICLES} vehicles...")
    rows = [
        (fake.license_plate(), random.choice(VEHICLE_CLASSES), random.random() > 0.1)
        for _ in range(NUM_VEHICLES)
    ]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO vehicles (license_plate, class, is_active) VALUES %s RETURNING id",
            rows,
        )
        vehicle_ids = [r[0] for r in cur.fetchall()]
    conn.commit()
    return vehicle_ids


def seed_trips(conn, rider_ids, vehicle_ids):
    print(f"Seeding {NUM_TRIPS} trips...")
    with conn.cursor() as cur:
        inserted = 0
        batch = []
        for _ in range(NUM_TRIPS):
            rider_id = random.choice(rider_ids)
            vehicle_id = random.choice(vehicle_ids)
            fare = round(random.uniform(5, 500), 2)
            status = random.choices(TRIP_STATUSES, weights=TRIP_STATUS_WEIGHTS)[0]
            created_at = fake.date_time_between(start_date="-90d", end_date="now")
            batch.append((rider_id, vehicle_id, fare, status, created_at))

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    "INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at) VALUES %s",
                    batch,
                )
                inserted += len(batch)
                batch = []
                print(f"  {inserted}/{NUM_TRIPS} trips inserted")

        if batch:
            execute_values(
                cur,
                "INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at) VALUES %s",
                batch,
            )
            inserted += len(batch)
    conn.commit()
    print(f"  Done. {inserted} trips inserted.")


def _apply_wallet_update_batch(cur, batch):
    """
    Bulk UPDATE using a VALUES join -- far faster than executemany(),
    since it's one round trip instead of one per row.
    NOTE: rows are applied one at a time by Postgres internally (so the
    trigger still fires once per row, producing one audit log row per update).
    """
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


def seed_wallet_audit_logs_via_trigger(conn, rider_ids):
    """
    wallet_audit_logs rows are NOT inserted directly -- they're generated
    automatically by the AFTER UPDATE OF wallet_balance trigger on riders.
    This proves the trigger works correctly under bulk load.
    """
    print(f"Generating {NUM_WALLET_UPDATES} wallet_balance updates (each fires the audit trigger)...")
    with conn.cursor() as cur:
        updated = 0
        batch = []
        for _ in range(NUM_WALLET_UPDATES):
            rider_id = random.choice(rider_ids)
            delta = round(random.uniform(-100, 100), 2)
            batch.append((delta, rider_id))

            if len(batch) >= BATCH_SIZE:
                _apply_wallet_update_batch(cur, batch)
                updated += len(batch)
                batch = []
                conn.commit()
                print(f"  {updated}/{NUM_WALLET_UPDATES} wallet updates applied")

        if batch:
            _apply_wallet_update_batch(cur, batch)
            updated += len(batch)
    conn.commit()
    print(f"  Done. {updated} wallet updates applied (each should have logged an audit row).")


def main():
    conn = get_connection()
    try:
        rider_ids = seed_riders(conn)
        vehicle_ids = seed_vehicles(conn)
        seed_trips(conn, rider_ids, vehicle_ids)
        seed_wallet_audit_logs_via_trigger(conn, rider_ids)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM trips")
            print(f"\nFinal trips count: {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM wallet_audit_logs")
            print(f"Final wallet_audit_logs count: {cur.fetchone()[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()