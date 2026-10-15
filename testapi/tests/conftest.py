"""Integration-test fixtures.

The tests never touch the real `ridesync` data: they build a throw-away
`ridesync_test` PostgreSQL database from the project's own sql/ scripts and a
`ridesync_test` MongoDB database, then load the small dataset in tests/seed.py.
Needs the docker-compose databases running (Postgres on 5433, Mongo on 27017).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from pymongo import ASCENDING, DESCENDING, GEOSPHERE, MongoClient

from app.config import Settings
from app.main import create_app
from tests import seed

ROOT = Path(__file__).resolve().parents[2]
SQL_FILES = [
    "01_schema_ddl.sql",
    "02_indexes.sql",
    "03_triggers_and_audit.sql",
    "04_stored_procedures.sql",
    "05_materialized_views.sql",
    "07_a2_frontend_support.sql",
]

PG = {
    "host": os.getenv("TEST_PGHOST", "localhost"),
    "port": int(os.getenv("TEST_PGPORT", "5433")),
    "user": os.getenv("TEST_PGUSER", "ridesync"),
    "password": os.getenv("TEST_PGPASSWORD", "ridesync"),
}
TEST_DB = "ridesync_test"
MONGO_URI = os.getenv("TEST_MONGO_URI", "mongodb://localhost:27017")


def _create_mongo_collections(db) -> None:
    """Same indexes as mongo/01 + mongo/04 (validators are not needed for the tests)."""
    db.TelemetryPings.create_index([("location", GEOSPHERE)])
    db.TelemetryPings.create_index([("created_at", ASCENDING)], expireAfterSeconds=7200)
    db.TripReviews.create_index([("rating", ASCENDING)])
    db.TripReviews.create_index([("vehicle_id", ASCENDING), ("rating", ASCENDING)])
    db.TripReviews.create_index([("trip_id", ASCENDING)])
    db.TripReviews.create_index([("created_at", DESCENDING)])
    db.VehicleMetadata.create_index([("vehicle_id", ASCENDING)], unique=True)


@pytest.fixture(scope="session")
def ids() -> dict[str, Any]:
    with psycopg.connect(dbname="postgres", autocommit=True, **PG) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TEST_DB)))
    with psycopg.connect(dbname=TEST_DB, autocommit=True, **PG) as conn:
        for name in SQL_FILES:
            conn.execute((ROOT / "sql" / name).read_text())
        seeded = seed.seed_postgres(conn)

    mongo = MongoClient(MONGO_URI, tz_aware=True)
    mongo.drop_database(TEST_DB)
    _create_mongo_collections(mongo[TEST_DB])
    seed.seed_mongo(mongo[TEST_DB], seeded)
    yield seeded
    mongo.drop_database(TEST_DB)
    mongo.close()
    with psycopg.connect(dbname="postgres", autocommit=True, **PG) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(TEST_DB)))


@pytest.fixture(scope="session")
def client(ids) -> TestClient:
    settings = Settings(
        pg_host=PG["host"],
        pg_port=PG["port"],
        pg_database=TEST_DB,
        pg_user=PG["user"],
        pg_password=PG["password"],
        mongo_uri=MONGO_URI,
        mongo_database=TEST_DB,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture()
def db(ids):
    """Direct connection to the test database, for setting up and checking state."""
    with psycopg.connect(dbname=TEST_DB, autocommit=True, **PG) as conn:
        yield conn


@pytest.fixture()
def new_rider(db):
    """Factory: a fresh rider with the given balance, so tests never share wallet state."""
    counter = {"n": 0}

    def make(balance: float = 100.00):
        counter["n"] += 1
        return db.execute(
            "INSERT INTO riders (name, wallet_balance) VALUES (%s, %s) RETURNING id",
            (f"Test Rider {counter['n']}", balance),
        ).fetchone()[0]

    return make
