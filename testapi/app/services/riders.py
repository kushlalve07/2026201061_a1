"""Riders: browse, detail and the 'acting as' picker."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db import Postgres
from app.db.sql import Filters, like_pattern
from app.errors import not_found
from app.pagination import PageParams
from app.services.trips import TRIP_COLUMNS, TRIP_FROM, fetch_trip, trip_from_row

RIDER_FROM = """
    FROM riders r
    LEFT JOIN trips a ON a.rider_id = r.id AND a.status IN ('REQUESTED', 'IN_TRANSIT')
"""


def list_riders(
    pg: Postgres,
    page: PageParams,
    *,
    search: str | None = None,
    has_active_trip: bool | None = None,
) -> dict[str, Any]:
    # idx_active_rider_trip guarantees at most one active trip per rider, so
    # the LEFT JOIN never duplicates a rider.
    f = Filters()
    if search:
        f.add("r.name ILIKE %(q)s", q=like_pattern(search))
    if has_active_trip is True:
        f.add("a.id IS NOT NULL")
    elif has_active_trip is False:
        f.add("a.id IS NULL")

    with pg.connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n {RIDER_FROM} {f.where}", f.params).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT r.id, r.name, r.wallet_balance, a.id AS active_trip_id, a.status AS active_trip_status
            {RIDER_FROM} {f.where}
            ORDER BY r.name, r.id
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**f.params, "limit": page.limit, "offset": page.offset},
        ).fetchall()
    items = [
        {
            "id": r["id"],
            "name": r["name"],
            "wallet_balance": r["wallet_balance"],
            "active_trip": (
                {"id": r["active_trip_id"], "status": r["active_trip_status"]} if r["active_trip_id"] else None
            ),
        }
        for r in rows
    ]
    return page.wrap(items, total)


def get_rider(pg: Postgres, rider_id: UUID) -> dict[str, Any]:
    with pg.connection() as conn:
        rider = conn.execute(
            "SELECT id, name, wallet_balance FROM riders WHERE id = %s", (rider_id,)
        ).fetchone()
        if rider is None:
            raise not_found("Rider", rider_id)
        active = conn.execute(
            "SELECT id FROM trips WHERE rider_id = %s AND status IN ('REQUESTED', 'IN_TRANSIT')", (rider_id,)
        ).fetchone()
        recent = conn.execute(
            f"SELECT {TRIP_COLUMNS} {TRIP_FROM} WHERE t.rider_id = %s ORDER BY t.created_at DESC, t.id DESC LIMIT 5",
            (rider_id,),
        ).fetchall()
        audit_entries = conn.execute(
            "SELECT COUNT(*) AS n FROM wallet_audit_logs WHERE rider_id = %s", (rider_id,)
        ).fetchone()["n"]
        active_trip = fetch_trip(conn, active["id"]) if active else None
    return {
        **rider,
        "active_trip": active_trip,
        "recent_trips": [trip_from_row(r) for r in recent],
        "audit_entries": audit_entries,
    }
