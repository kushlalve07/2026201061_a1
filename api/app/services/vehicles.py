"""Vehicles: browse with lifetime stats (materialized view), detail, catalog document."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.db import Mongo, Postgres
from app.db.sql import Filters, like_pattern
from app.errors import not_found
from app.pagination import PageParams

# Whitelisted ORDER BY fragments; the client only chooses the key.
VEHICLE_SORTS = {
    "earnings": "COALESCE(s.total_earnings, 0) DESC, v.license_plate",
    "trips": "COALESCE(s.lifetime_trip_count, 0) DESC, v.license_plate",
    "plate": "v.license_plate",
}

VEHICLE_COLUMNS = """
    v.id, v.license_plate, v.class AS vehicle_class, v.is_active,
    COALESCE(s.lifetime_trip_count, 0) AS lifetime_trip_count,
    COALESCE(s.total_earnings, 0)      AS total_earnings
"""
VEHICLE_FROM = """
    FROM vehicles v
    LEFT JOIN vehicle_lifetime_stats s ON s.vehicle_id = v.id
"""


def last_refresh(pg: Postgres) -> dict[str, Any] | None:
    return pg.fetch_one(
        """
        SELECT refreshed_at, duration_ms FROM mv_refresh_log
        WHERE view_name = 'vehicle_lifetime_stats'
        ORDER BY refreshed_at DESC LIMIT 1
        """
    )


def stats_as_of(pg: Postgres) -> datetime | None:
    row = last_refresh(pg)
    return row["refreshed_at"] if row else None


def list_vehicles(
    pg: Postgres,
    page: PageParams,
    *,
    search: str | None = None,
    vehicle_class: str | None = None,
    is_active: bool | None = None,
    sort: str = "plate",
) -> dict[str, Any]:
    f = Filters()
    if search:
        f.add("v.license_plate ILIKE %(q)s", q=like_pattern(search))
    if vehicle_class:
        f.add("v.class = %(vehicle_class)s", vehicle_class=vehicle_class)
    if is_active is not None:
        f.add("v.is_active = %(is_active)s", is_active=is_active)
    order_by = VEHICLE_SORTS[sort]

    with pg.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n {VEHICLE_FROM} {f.where}", f.params).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT {VEHICLE_COLUMNS} {VEHICLE_FROM} {f.where}
            ORDER BY {order_by}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**f.params, "limit": page.limit, "offset": page.offset},
        ).fetchall()
    return {**page.wrap(rows, total), "stats_as_of": stats_as_of(pg)}


def vehicle_classes(pg: Postgres) -> list[str]:
    return [r["class"] for r in pg.fetch_all("SELECT DISTINCT class FROM vehicles ORDER BY class")]


def get_vehicle(pg: Postgres, vehicle_id: UUID) -> dict[str, Any]:
    with pg.connection() as conn:
        row = conn.execute(f"SELECT {VEHICLE_COLUMNS} {VEHICLE_FROM} WHERE v.id = %s", (vehicle_id,)).fetchone()
        if row is None:
            raise not_found("Vehicle", vehicle_id)
        rank = conn.execute(
            "SELECT revenue_rank FROM v_vehicle_revenue_ranking WHERE vehicle_id = %s", (vehicle_id,)
        ).fetchone()
        ranked = conn.execute("SELECT COUNT(*) AS n FROM v_vehicle_revenue_ranking").fetchone()["n"]
    return {
        **row,
        "revenue_rank": rank["revenue_rank"] if rank else None,
        "ranked_vehicles": ranked,
        "stats_as_of": stats_as_of(pg),
    }


def plates_by_id(pg: Postgres, vehicle_ids: list[str]) -> dict[str, dict[str, str]]:
    """license_plate/class for vehicle ids stored as strings in MongoDB."""
    valid: list[UUID] = []
    for vid in set(vehicle_ids):
        try:
            valid.append(UUID(vid))
        except (ValueError, TypeError):
            continue
    if not valid:
        return {}
    rows = pg.fetch_all(
        "SELECT id::text AS id, license_plate, class AS vehicle_class FROM vehicles WHERE id = ANY(%s)",
        (valid,),
    )
    return {r["id"]: r for r in rows}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items() if k != "_id"}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)  # ObjectId, Decimal128, ... shown as text


def get_metadata(pg: Postgres, mongo: Mongo, vehicle_id: UUID) -> dict[str, Any]:
    """The flexible VehicleMetadata document, returned as-is (minus _id) for generic rendering."""
    doc = mongo.metadata.find_one({"vehicle_id": str(vehicle_id)})
    if doc is None:
        if pg.fetch_one("SELECT 1 FROM vehicles WHERE id = %s", (vehicle_id,)) is None:
            raise not_found("Vehicle", vehicle_id)
        raise not_found("Catalog document for vehicle", vehicle_id)
    return _jsonable(doc)
