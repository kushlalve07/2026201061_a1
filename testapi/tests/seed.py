"""A small, fully known dataset so every expected value in the tests can be worked out by hand.

Completed trips (revenue):
    RS90001 (v1): 06-01 100.00, 06-03 50.00, 06-08 30.00  -> 180.00  rank 1
    RS90002 (v2): 06-02 180.00                            -> 180.00  rank 1 (tie)
    RS90004 (v4): 06-05 20.00                             ->  20.00  rank 2 (DENSE_RANK)
    RS90003 (v3) is inactive; RS90005 (v5) is reserved for booking tests.
Bob has one active (REQUESTED) trip on v4. Dora's wallet: 50 (opening) +25 -10.50 +5.25 = 69.75.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

ORIGIN = (-122.4194, 37.7749)  # Part A Workflow 3 origin

RIDERS = {
    "alice": ("Alice Free", 100.00),
    "bob": ("Bob Busy", 500.00),
    "carol": ("Carol Poor", 5.00),
    "dora": ("Dora Audit", 50.00),
}
PAGING_RIDERS = 30  # "Zed Paging 00".."Zed Paging 29", 10.00 each

VEHICLES = {
    "v1": ("RS90001", "ECONOMY", True),
    "v2": ("RS90002", "POOL", True),
    "v3": ("RS90003", "XL", False),
    "v4": ("RS90004", "PREMIUM", True),
    "v5": ("RS90005", "ECONOMY", True),
}

COMPLETED_TRIPS = {
    "t1": ("alice", "v1", "2026-06-01 10:00+00", 100.00),
    "t2": ("alice", "v1", "2026-06-03 12:00+00", 50.00),
    "t3": ("carol", "v1", "2026-06-08 09:00+00", 30.00),
    "t4": ("dora", "v2", "2026-06-02 15:00+00", 180.00),
    "t5": ("alice", "v4", "2026-06-05 08:00+00", 20.00),
}
ACTIVE_TRIP = ("bob", "v4", "2026-06-09 10:00+00", 15.00)

DORA_WALLET_CHANGES = [25.00, -10.50, 5.25]


def seed_postgres(conn) -> dict[str, Any]:
    ids: dict[str, Any] = {}
    for key, (name, balance) in RIDERS.items():
        ids[key] = conn.execute(
            "INSERT INTO riders (name, wallet_balance) VALUES (%s, %s) RETURNING id", (name, balance)
        ).fetchone()[0]
    for i in range(PAGING_RIDERS):
        conn.execute("INSERT INTO riders (name, wallet_balance) VALUES (%s, 10.00)", (f"Zed Paging {i:02d}",))
    for key, (plate, cls, active) in VEHICLES.items():
        ids[key] = conn.execute(
            "INSERT INTO vehicles (license_plate, class, is_active) VALUES (%s, %s, %s) RETURNING id",
            (plate, cls, active),
        ).fetchone()[0]
    for key, (rider, vehicle, created_at, fare) in COMPLETED_TRIPS.items():
        ids[key] = conn.execute(
            """INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at)
               VALUES (%s, %s, %s, 'COMPLETED', %s) RETURNING id""",
            (ids[rider], ids[vehicle], fare, created_at),
        ).fetchone()[0]
    rider, vehicle, created_at, fare = ACTIVE_TRIP
    ids["bob_trip"] = conn.execute(
        """INSERT INTO trips (rider_id, vehicle_id, fare_amount, status, created_at)
           VALUES (%s, %s, %s, 'REQUESTED', %s) RETURNING id""",
        (ids[rider], ids[vehicle], fare, created_at),
    ).fetchone()[0]
    # Autocommit: each UPDATE is its own transaction, so every audit row gets its own NOW().
    for delta in DORA_WALLET_CHANGES:
        conn.execute("UPDATE riders SET wallet_balance = wallet_balance + %s WHERE id = %s", (delta, ids["dora"]))
    conn.execute("SELECT refresh_vehicle_lifetime_stats()")
    return ids


def offset_point(dlat: float) -> list[float]:
    """A point due north of the origin; 0.0009 degrees of latitude is about 100 m."""
    return [ORIGIN[0], ORIGIN[1] + dlat]


def seed_mongo(db, ids: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)

    def ping(vehicle: str, dlat: float, available: bool = True) -> dict[str, Any]:
        return {
            "vehicle_id": str(ids[vehicle]),
            "location": {"type": "Point", "coordinates": offset_point(dlat)},
            "is_available": available,
            "speed_kmh": 10.0,
            "created_at": now,
        }

    db.TelemetryPings.insert_many(
        [
            ping("v1", 0.0009),          # ~100 m  (nearest ping of v1)
            ping("v1", 0.0027),          # ~300 m  (same vehicle, must be de-duplicated)
            ping("v2", 0.009),           # ~1 km
            ping("v4", 0.018, False),    # ~2 km but not available -> excluded
            ping("v3", 0.09),            # ~10 km -> outside the 5 km radius
        ]
    )

    def review(trip: str, vehicle: str, rider: str, rating: int, tags: list[str], day: str) -> dict[str, Any]:
        return {
            "trip_id": str(ids[trip]),
            "rider_id": str(ids[rider]),
            "vehicle_id": str(ids[vehicle]),
            "rating": rating,
            "tags": tags,
            "comment": f"Review of {trip}",
            "created_at": datetime.fromisoformat(f"{day}T12:00:00+00:00"),
        }

    db.TripReviews.insert_many(
        [
            review("t1", "v1", "alice", 5, ["Clean Car", "Polite"], "2026-06-01"),
            review("t2", "v1", "alice", 4, ["Clean Car"], "2026-06-03"),
            review("t4", "v2", "dora", 2, ["Late Pickup"], "2026-06-02"),
        ]
    )
    db.VehicleMetadata.insert_one(
        {
            "vehicle_id": str(ids["v1"]),
            "features": ["wifi", "child_seat"],
            "inspection_records": [
                {"passed": True, "inspected_at": datetime(2026, 5, 1, tzinfo=timezone.utc), "inspector": "Ann"},
                {"passed": False, "inspected_at": datetime(2026, 1, 2, tzinfo=timezone.utc), "inspector": "Ben"},
            ],
            "registration_city": "San Francisco",  # an extra, schema-less field
        }
    )
