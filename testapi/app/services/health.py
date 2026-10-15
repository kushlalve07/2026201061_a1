"""Reachability of both stores, for the sidebar indicator."""
from __future__ import annotations

from app.db import Mongo, Postgres


def check(pg: Postgres, mongo: Mongo) -> dict[str, str]:
    try:
        with pg.connection(timeout=2) as conn:
            conn.execute("SELECT 1")
        postgres = "ok"
    except Exception:  # noqa: BLE001 - any failure means "down" here
        postgres = "down"
    try:
        mongo.client.admin.command("ping")
        mongo_state = "ok"
    except Exception:  # noqa: BLE001
        mongo_state = "down"
    status = "ok" if postgres == mongo_state == "ok" else "degraded"
    return {"status": status, "postgres": postgres, "mongo": mongo_state}
