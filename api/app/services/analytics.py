"""Workflow 2 (7-day moving average + DENSE_RANK) and the materialized view summary."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.db import Postgres
from app.errors import ApiError, not_found
from app.pagination import PageParams
from app.services.vehicles import VEHICLE_COLUMNS, VEHICLE_FROM, last_refresh


def fleet_summary(pg: Postgres) -> dict[str, Any]:
    with pg.connection() as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*)                                AS total_vehicles,
                COUNT(*) FILTER (WHERE is_active)       AS active_vehicles,
                COALESCE(SUM(lifetime_trip_count), 0)   AS lifetime_trips,
                COALESCE(SUM(total_earnings), 0)        AS total_earnings,
                COALESCE(ROUND(AVG(total_earnings), 2), 0) AS avg_earnings_per_vehicle
            FROM vehicle_lifetime_stats
            """
        ).fetchone()
        top = conn.execute(
            f"""
            SELECT {VEHICLE_COLUMNS} {VEHICLE_FROM}
            ORDER BY COALESCE(s.total_earnings, 0) DESC, v.license_plate
            LIMIT 5
            """
        ).fetchall()
    refresh = last_refresh(pg)
    return {
        **totals,
        "top_vehicles": top,
        "last_refreshed_at": refresh["refreshed_at"] if refresh else None,
        "last_refresh_duration_ms": refresh["duration_ms"] if refresh else None,
    }


def refresh_fleet_summary(pg: Postgres) -> dict[str, Any]:
    """REFRESH MATERIALIZED VIEW CONCURRENTLY via refresh_vehicle_lifetime_stats(), which logs the run."""
    with pg.connection() as conn:
        conn.execute("SELECT refresh_vehicle_lifetime_stats()")
    refresh = last_refresh(pg)
    if refresh is None:  # pragma: no cover - the function always logs
        raise ApiError(500, "REFRESH_NOT_LOGGED", "The refresh ran but was not logged.")
    return {"refreshed_at": refresh["refreshed_at"], "duration_ms": refresh["duration_ms"]}


def revenue_ranking(pg: Postgres, page: PageParams) -> dict[str, Any]:
    with pg.connection() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM v_vehicle_revenue_ranking").fetchone()["n"]
        rows = conn.execute(
            """
            SELECT revenue_rank, vehicle_id, license_plate, class AS vehicle_class, total_revenue
            FROM v_vehicle_revenue_ranking
            ORDER BY revenue_rank, license_plate
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"limit": page.limit, "offset": page.offset},
        ).fetchall()
    return page.wrap(rows, total)


def revenue_trend(pg: Postgres, vehicle_id: UUID, *, days: int, zero_fill: bool) -> dict[str, Any]:
    """The window ends on the vehicle's last day with a completed trip (or today)."""
    with pg.connection() as conn:
        vehicle = conn.execute(
            "SELECT id, license_plate, class AS vehicle_class FROM vehicles WHERE id = %s", (vehicle_id,)
        ).fetchone()
        if vehicle is None:
            raise not_found("Vehicle", vehicle_id)
        last_day = conn.execute(
            """
            SELECT COALESCE(MAX(DATE(created_at)), CURRENT_DATE) AS d
            FROM trips WHERE vehicle_id = %s AND status = 'COMPLETED'
            """,
            (vehicle_id,),
        ).fetchone()["d"]
        date_to: date = last_day
        date_from: date = date_to - timedelta(days=days - 1)
        rank = conn.execute(
            "SELECT revenue_rank, total_revenue FROM v_vehicle_revenue_ranking WHERE vehicle_id = %s", (vehicle_id,)
        ).fetchone()
        points = conn.execute(
            """
            SELECT revenue_date AS day, daily_total, moving_avg_7day, has_trips
            FROM fn_vehicle_revenue_trend(%s, %s, %s, %s)
            """,
            (vehicle_id, date_from, date_to, zero_fill),
        ).fetchall()
    return {
        "vehicle": vehicle,
        "revenue_rank": rank["revenue_rank"] if rank else None,
        "total_revenue": rank["total_revenue"] if rank else None,
        "date_from": date_from,
        "date_to": date_to,
        "days": days,
        "zero_fill": zero_fill,
        "points": points,
    }
