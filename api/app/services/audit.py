"""Audit trail: read-only wallet_audit_logs for one rider with a running balance.

The running balance is computed in SQL from the amounts alone:
    opening balance (balance before the first entry in range)
      + SUM(amount_changed) OVER (ORDER BY timestamp, id)
and compared with the balance_after the trigger recorded on each row.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from app.db import Postgres
from app.db.sql import Filters
from app.errors import not_found
from app.pagination import PageParams


def wallet_audit(
    pg: Postgres,
    rider_id: UUID,
    page: PageParams,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    order: str = "asc",
) -> dict[str, Any]:
    f = Filters().add("rider_id = %(rider_id)s", rider_id=rider_id)
    if date_from:
        f.add('"timestamp" >= %(date_from)s', date_from=date_from)
    if date_to:
        f.add('"timestamp" < %(date_to_excl)s', date_to_excl=date_to + timedelta(days=1))
    ranged = f"""
        SELECT id, "timestamp", action_type, amount_changed, balance_after
        FROM wallet_audit_logs {f.where}
    """
    direction = "DESC" if order == "desc" else "ASC"

    with pg.connection() as conn:
        rider = conn.execute("SELECT id, name, wallet_balance FROM riders WHERE id = %s", (rider_id,)).fetchone()
        if rider is None:
            raise not_found("Rider", rider_id)

        summary = conn.execute(
            f"""
            WITH ranged AS ({ranged})
            SELECT
                COUNT(*) AS entries,
                (ARRAY_AGG(balance_after - amount_changed ORDER BY "timestamp", id))[1]  AS opening_balance,
                COALESCE(SUM(amount_changed) FILTER (WHERE action_type = 'CREDIT'), 0) AS credits_total,
                COUNT(*) FILTER (WHERE action_type = 'CREDIT')                          AS credits_count,
                COALESCE(SUM(amount_changed) FILTER (WHERE action_type = 'DEBIT'), 0)  AS debits_total,
                COUNT(*) FILTER (WHERE action_type = 'DEBIT')                           AS debits_count,
                (ARRAY_AGG(balance_after ORDER BY "timestamp" DESC, id DESC))[1]        AS closing_balance
            FROM ranged
            """,
            f.params,
        ).fetchone()

        rows = conn.execute(
            f"""
            WITH ranged AS ({ranged}),
            running AS (
                SELECT
                    r.*,
                    FIRST_VALUE(balance_after - amount_changed) OVER chronological
                      + SUM(amount_changed) OVER chronological AS running_balance
                FROM ranged r
                WINDOW chronological AS (ORDER BY "timestamp", id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
            )
            SELECT id, "timestamp", action_type, amount_changed, balance_after, running_balance,
                   running_balance = balance_after AS matches
            FROM running
            ORDER BY "timestamp" {direction}, id {direction}
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {**f.params, "limit": page.limit, "offset": page.offset},
        ).fetchall()

    return {
        **page.wrap(rows, summary["entries"]),
        "rider": rider,
        "date_from": date_from,
        "date_to": date_to,
        "order": "desc" if order == "desc" else "asc",
        "summary": summary,
    }
