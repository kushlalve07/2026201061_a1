"""Workflow 4: the $facet review summary, review lists, and a trip's review."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db import Mongo, Postgres
from app.pagination import PageParams
from app.services.vehicles import plates_by_id

TOP_TAGS = 10


def _match(vehicle_id: UUID | None) -> dict[str, Any]:
    # rating >= 1 is the Part A filter (lets the planner use an index).
    match: dict[str, Any] = {"rating": {"$gte": 1}}
    if vehicle_id is not None:
        match["vehicle_id"] = str(vehicle_id)
    return match


def summary(mongo: Mongo, vehicle_id: UUID | None = None) -> dict[str, Any]:
    pipeline = [
        {"$match": _match(vehicle_id)},
        {
            "$facet": {
                "rating_distribution": [
                    {"$group": {"_id": "$rating", "count": {"$sum": 1}}},
                    {"$sort": {"_id": 1}},
                ],
                "driver_feedback_tags": [
                    {"$unwind": "$tags"},
                    {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1, "_id": 1}},
                    {"$limit": TOP_TAGS},
                ],
                "overall_average": [
                    {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}, "total": {"$sum": 1}}},
                ],
            }
        },
    ]
    result = next(mongo.reviews.aggregate(pipeline))
    counts = {d["_id"]: d["count"] for d in result["rating_distribution"]}
    overall = result["overall_average"][0] if result["overall_average"] else None
    return {
        "vehicle_id": vehicle_id,
        "total": overall["total"] if overall else 0,
        "overall_average": round(overall["avg_rating"], 2) if overall else None,
        "rating_distribution": [{"rating": r, "count": counts.get(r, 0)} for r in range(1, 6)],
        "top_tags": [{"tag": d["_id"], "count": d["count"]} for d in result["driver_feedback_tags"]],
    }


def _review_item(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "trip_id": doc.get("trip_id"),
        "rider_id": doc.get("rider_id"),
        "vehicle_id": doc.get("vehicle_id"),
        "license_plate": None,
        "rating": doc.get("rating"),
        "tags": doc.get("tags", []),
        "comment": doc.get("comment"),
        "created_at": doc.get("created_at"),
    }


def list_reviews(
    mongo: Mongo,
    pg: Postgres,
    page: PageParams,
    *,
    vehicle_id: UUID | None = None,
    rating: int | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if vehicle_id is not None:
        query["vehicle_id"] = str(vehicle_id)
    if rating is not None:
        query["rating"] = rating
    total = mongo.reviews.count_documents(query)
    cursor = (
        mongo.reviews.find(query)
        .sort([("created_at", -1), ("_id", -1)])
        .skip(page.offset)
        .limit(page.limit)
    )
    items = [_review_item(d) for d in cursor]
    plates = plates_by_id(pg, [i["vehicle_id"] for i in items if i["vehicle_id"]])
    for item in items:
        item["license_plate"] = plates.get(item["vehicle_id"] or "", {}).get("license_plate")
    return page.wrap(items, total)


def review_for_trip(mongo: Mongo, trip_id: UUID) -> dict[str, Any] | None:
    doc = mongo.reviews.find_one({"trip_id": str(trip_id)})
    if doc is None:
        return None
    item = _review_item(doc)
    item.pop("license_plate")
    return item
