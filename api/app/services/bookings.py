"""Workflow 1: book a trip through sp_atomic_booking and prove what happened.

The procedure decides everything (balance, partial unique index, vehicle
state, fare validation). This module only reads the balance before and after,
calls the procedure, and translates its p_status into a reason code the UI can
turn into a friendly sentence.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from app.db import Postgres
from app.services.trips import ACTIVE_STATUSES, fetch_trip

# (substring of p_status, reason, HTTP status). Order matters: "is not active"
# must be tested before "not found".
REASONS: list[tuple[str, str, int]] = [
    ("insufficient wallet balance", "INSUFFICIENT_BALANCE", 409),
    ("already has an active trip", "ACTIVE_TRIP_EXISTS", 409),
    ("is not active", "VEHICLE_INACTIVE", 409),
    ("not found", "NOT_FOUND", 404),
    ("fare must be greater than", "INVALID_FARE", 400),
    ("concurrent update", "CONCURRENT_UPDATE", 409),
]


def classify(p_status: str) -> tuple[str | None, int]:
    if p_status == "COMMITTED":
        return None, 201
    for needle, reason, http_status in REASONS:
        if needle in p_status:
            return reason, http_status
    return "BOOKING_FAILED", 409


def _balance(conn, rider_id: UUID) -> float | None:
    row = conn.execute("SELECT wallet_balance FROM riders WHERE id = %s", (rider_id,)).fetchone()
    return row["wallet_balance"] if row else None


def book_trip(pg: Postgres, rider_id: UUID, vehicle_id: UUID, fare_amount: Decimal) -> tuple[int, dict[str, Any]]:
    with pg.connection() as conn:
        balance_before = _balance(conn, rider_id)
        result = conn.execute(
            "CALL sp_atomic_booking(%s, %s, %s, NULL, NULL)", (rider_id, vehicle_id, fare_amount)
        ).fetchone()
        balance_after = _balance(conn, rider_id)

        p_status: str = result["p_status"]
        trip_id = result["p_trip_id"]
        reason, http_status = classify(p_status)

        trip = audit_entry = active_trip_id = None
        if reason is None:
            trip = fetch_trip(conn, trip_id)
            # The trip INSERT and the trigger's audit INSERT ran in the same
            # transaction, so they share NOW(): that pins the exact audit row.
            audit_entry = conn.execute(
                """
                SELECT w.id, w."timestamp", w.action_type, w.amount_changed, w.balance_after
                FROM wallet_audit_logs w
                JOIN trips t ON t.id = %s
                WHERE w.rider_id = %s AND w."timestamp" = t.created_at
                ORDER BY w.id
                LIMIT 1
                """,
                (trip_id, rider_id),
            ).fetchone()
        elif reason == "ACTIVE_TRIP_EXISTS":
            row = conn.execute(
                "SELECT id FROM trips WHERE rider_id = %s AND status = ANY(%s)", (rider_id, list(ACTIVE_STATUSES))
            ).fetchone()
            active_trip_id = row["id"] if row else None

    requested = float(fare_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return http_status, {
        "status": "COMMITTED" if reason is None else "ROLLED_BACK",
        "reason": reason,
        "message": p_status,
        "fare_amount": trip["fare_amount"] if trip else requested,
        "trip": trip,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "audit_entry": audit_entry,
        "active_trip_id": active_trip_id,
    }
