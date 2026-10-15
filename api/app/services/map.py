"""Workflow 3: nearest available vehicles around an origin ($geoNear), plus demo pings."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from app.db import Mongo, Postgres
from app.services.vehicles import plates_by_id

# $geoNear returns pings nearest-first. Grouping only the nearest N pings is
# exact for the top vehicles: any vehicle whose nearest ping is outside the
# first N is farther than every vehicle found inside it. Each vehicle has
# hundreds of pings, so N grows until `limit` vehicles are found or the
# radius is exhausted.
FIRST_CANDIDATES = 25_000
MAX_CANDIDATES = 1_000_000

# Demo pings land within ~500 m of the origin.
SPREAD_LAT_DEG = 0.0045
SPREAD_LNG_DEG = 0.0057


def _nearest_per_vehicle(mongo: Mongo, lng: float, lat: float, radius_m: int, limit: int) -> list[dict[str, Any]]:
    candidates = FIRST_CANDIDATES
    while True:
        pipeline: list[dict[str, Any]] = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                    "distanceField": "distance_m",
                    "maxDistance": radius_m,
                    "query": {"is_available": True},
                    "spherical": True,
                }
            },
            {"$limit": candidates},
            {
                "$facet": {
                    "scanned": [{"$count": "n"}],
                    "vehicles": [
                        {
                            "$group": {
                                "_id": "$vehicle_id",
                                "distance_m": {"$first": "$distance_m"},
                                "location": {"$first": "$location"},
                                "last_ping_at": {"$first": "$created_at"},
                            }
                        },
                        {"$sort": {"distance_m": 1, "_id": 1}},
                        {"$limit": limit},
                    ],
                }
            },
        ]
        result = next(mongo.pings.aggregate(pipeline, allowDiskUse=True))
        scanned = result["scanned"][0]["n"] if result["scanned"] else 0
        vehicles = result["vehicles"]
        if len(vehicles) >= limit or scanned < candidates or candidates >= MAX_CANDIDATES:
            return vehicles
        candidates *= 4


def nearby_vehicles(
    mongo: Mongo, pg: Postgres, *, lng: float, lat: float, radius_m: int, limit: int
) -> dict[str, Any]:
    docs = _nearest_per_vehicle(mongo, lng, lat, radius_m, limit)
    plates = plates_by_id(pg, [d["_id"] for d in docs])
    items = []
    for d in docs:
        ref = plates.get(d["_id"], {})
        lng_, lat_ = d["location"]["coordinates"]
        items.append(
            {
                "vehicle_id": d["_id"],
                "license_plate": ref.get("license_plate"),
                "vehicle_class": ref.get("vehicle_class"),
                "distance_m": round(d["distance_m"], 1),
                "location": {"lng": lng_, "lat": lat_},
                "last_ping_at": d["last_ping_at"],
            }
        )
    return {
        "origin": {"lng": lng, "lat": lat},
        "radius_m": radius_m,
        "items": items,
        "generated_at": datetime.now(timezone.utc),
    }


def on_land(lng: float, lat: float) -> bool:
    """Rough San Francisco land mask (same rule as data_generation/mongo_seeder.py)."""
    if not (37.712 <= lat <= 37.805 and -122.505 <= lng):
        return False
    if lat >= 37.79:
        return lng <= -122.389 - (lat - 37.79) * 0.9
    return lng <= (-122.390 if lat >= 37.775 else -122.387)


def _demo_point(lng: float, lat: float) -> tuple[float, float]:
    for _ in range(50):
        p_lng = lng + random.gauss(0, SPREAD_LNG_DEG)
        p_lat = lat + random.gauss(0, SPREAD_LAT_DEG)
        if on_land(p_lng, p_lat):
            return p_lng, p_lat
    return lng, lat  # origin itself (outside San Francisco the mask never matches)


def simulate_pings(mongo: Mongo, pg: Postgres, *, lng: float, lat: float, count: int) -> dict[str, Any]:
    """Insert fresh, available pings for random active vehicles around the origin."""
    rows = pg.fetch_all(
        "SELECT id::text AS id FROM vehicles WHERE is_active ORDER BY random() LIMIT %s", (count,)
    )
    vehicle_ids = [r["id"] for r in rows]
    now = datetime.now(timezone.utc)
    docs = [
        {
            "vehicle_id": vid,
            "location": {
                "type": "Point",
                # floats -> BSON doubles, which the TelemetryPings validator requires
                "coordinates": [float(c) for c in _demo_point(lng, lat)],
            },
            "is_available": True,
            "speed_kmh": float(round(random.uniform(0, 60), 1)),
            "created_at": now,
        }
        for vid in vehicle_ids
    ]
    if docs:
        mongo.pings.insert_many(docs, ordered=False)
    return {"inserted": len(docs), "vehicle_ids": vehicle_ids}
