"""
Usage:
  python data_generation/mongo_seeder.py
  python data_generation/mongo_seeder.py --reset
"""

from __future__ import annotations

import argparse
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from faker import Faker
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

try:
    import psycopg2
except ImportError:
    psycopg2 = None

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "ridesync"

PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "ridesync"),
    "user": os.getenv("PGUSER", "ridesync"),
    "password": os.getenv("PGPASSWORD", "ridesync"),
}

NUM_PINGS = 500_000
NUM_REVIEWS = 25_000
BATCH_SIZE = 5_000
SEED = 42

# Same point as mongo/02_workflow3_geonear.js (San Francisco)
GEO_NEAR_LNG = -122.4194
GEO_NEAR_LAT = 37.7749

FEEDBACK_TAGS = [
    "Smooth Driving",
    "Clean Car",
    "Polite",
    "On Time",
    "Safe",
    "Music Too Loud",
    "Late Pickup",
    "Helpful",
]
VEHICLE_FEATURES = [
    "sunroof",
    "child_seat",
    "usb_charger",
    "wifi",
    "wheelchair_access",
    "premium_audio",
]

random.seed(SEED)
fake = Faker()
Faker.seed(SEED)


def load_vehicle_ids() -> list[str]:
    if psycopg2 is None:
        print("psycopg2 not available; generating synthetic vehicle_ids.")
        return [str(uuid.uuid4()) for _ in range(500)]
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id::text FROM vehicles")
                ids = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
        if ids:
            print(f"Using {len(ids)} vehicle_id values from PostgreSQL.")
            return ids
        print("No vehicles in PostgreSQL; generating synthetic vehicle_ids.")
    except Exception as exc:
        print(f"Could not read vehicles from PostgreSQL ({exc}); using synthetic ids.")
    return [str(uuid.uuid4()) for _ in range(500)]


def load_trip_ids() -> list[tuple[str, str, str]]:
    """Return (trip_id, rider_id, vehicle_id) from Postgres when available."""
    if psycopg2 is None:
        return []
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, rider_id::text, vehicle_id::text
                    FROM trips
                    WHERE status = 'COMPLETED'
                    LIMIT 25000
                    """
                )
                rows = cur.fetchall()
        finally:
            conn.close()
        print(f"Using {len(rows)} completed trips from PostgreSQL for reviews.")
        return rows
    except Exception as exc:
        print(f"Could not read trips from PostgreSQL ({exc}).")
        return []


def random_point_near_sf() -> dict:
    lng = GEO_NEAR_LNG + random.gauss(0, 0.012)
    lat = GEO_NEAR_LAT + random.gauss(0, 0.010)
    return {"type": "Point", "coordinates": [float(lng), float(lat)]}


def seed_vehicle_metadata(coll, vehicle_ids: list[str], reset: bool) -> None:
    if reset:
        coll.delete_many({})
    now = datetime.now(timezone.utc)
    docs = []
    for vid in vehicle_ids:
        n_insp = random.randint(1, 4)
        docs.append(
            {
                "vehicle_id": vid,
                "features": random.sample(VEHICLE_FEATURES, k=random.randint(1, 3)),
                "inspection_records": [
                    {
                        "passed": random.random() > 0.1,
                        "inspected_at": now - timedelta(days=random.randint(1, 400)),
                        "inspector": fake.name(),
                    }
                    for _ in range(n_insp)
                ],
            }
        )
    if docs:
        coll.insert_many(docs, ordered=False)
    print(f"VehicleMetadata: {len(docs)} documents")


def seed_reviews(coll, vehicle_ids: list[str], trip_rows: list, reset: bool) -> None:
    if reset:
        coll.delete_many({})
    now = datetime.now(timezone.utc)
    docs = []
    for i in range(NUM_REVIEWS):
        if trip_rows:
            trip_id, rider_id, vehicle_id = trip_rows[i % len(trip_rows)]
        else:
            trip_id = str(uuid.uuid4())
            rider_id = str(uuid.uuid4())
            vehicle_id = random.choice(vehicle_ids)
        n_tags = random.randint(1, 3)
        docs.append(
            {
                "trip_id": trip_id,
                "rider_id": rider_id,
                "vehicle_id": vehicle_id,
                "rating": int(random.choices([1, 2, 3, 4, 5], weights=[4, 6, 15, 35, 40])[0]),
                "tags": random.sample(FEEDBACK_TAGS, k=n_tags),
                "comment": fake.sentence(nb_words=10),
                "created_at": now - timedelta(days=random.randint(0, 29)),
            }
        )
        if len(docs) >= BATCH_SIZE:
            coll.insert_many(docs, ordered=False)
            print(f"  TripReviews {i + 1}/{NUM_REVIEWS}")
            docs = []
    if docs:
        coll.insert_many(docs, ordered=False)
    print(f"TripReviews: {NUM_REVIEWS} documents")


def seed_pings(coll, vehicle_ids: list[str], reset: bool) -> None:
    if reset:
        coll.delete_many({})
    now = datetime.now(timezone.utc)
    inserted = 0
    batch = []
    for i in range(NUM_PINGS):
        created = now - timedelta(minutes=random.uniform(0, 90))
        batch.append(
            InsertOne(
                {
                    "vehicle_id": random.choice(vehicle_ids),
                    "location": random_point_near_sf(),
                    "is_available": random.random() > 0.25,
                    "speed_kmh": float(round(random.uniform(0, 90), 1)),
                    "created_at": created,
                }
            )
        )
        if len(batch) >= BATCH_SIZE:
            try:
                coll.bulk_write(batch, ordered=False)
            except BulkWriteError as exc:
                inserted += exc.details.get("nInserted", 0)
                raise
            inserted += len(batch)
            batch = []
            if inserted % 50_000 == 0:
                print(f"  TelemetryPings {inserted}/{NUM_PINGS}")
    if batch:
        coll.bulk_write(batch, ordered=False)
        inserted += len(batch)
    print(f"TelemetryPings: {inserted} documents")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed RideSync MongoDB data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing documents in the three collections first.",
    )
    args = parser.parse_args()

    vehicle_ids = load_vehicle_ids()
    trip_rows = load_trip_ids()

    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    try:
        seed_vehicle_metadata(db["VehicleMetadata"], vehicle_ids, args.reset)
        seed_reviews(db["TripReviews"], vehicle_ids, trip_rows, args.reset)
        seed_pings(db["TelemetryPings"], vehicle_ids, args.reset)

        print("\nCollection counts:")
        for name in ("VehicleMetadata", "TripReviews", "TelemetryPings"):
            print(f"  {name}: {db[name].count_documents({})}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
