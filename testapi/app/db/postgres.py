"""PostgreSQL access through a small connection pool.

Every pooled connection runs in **autocommit** mode:
  * ``sp_atomic_booking`` issues COMMIT/ROLLBACK itself, which PostgreSQL only
    allows when CALL is not inside an outer transaction block;
  * every other statement is a single read or a single function call, so it
    is already atomic on its own.
NUMERIC values are loaded as Python floats so they serialise as JSON numbers.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.numeric import FloatLoader
from psycopg_pool import ConnectionPool

Row = dict[str, Any]


def _configure(conn: Connection) -> None:
    conn.adapters.register_loader("numeric", FloatLoader)


class Postgres:
    def __init__(self, conninfo: str, *, min_size: int = 1, max_size: int = 10, timeout: float = 5.0):
        self.pool = ConnectionPool(
            conninfo,
            min_size=min_size,
            max_size=max_size,
            timeout=timeout,
            open=False,
            kwargs={"autocommit": True, "row_factory": dict_row},
            configure=_configure,
            check=ConnectionPool.check_connection,
        )

    def open(self) -> None:
        # wait=False: the API starts (and reports "down" on /api/health) even
        # if the database is not reachable yet; the pool keeps retrying.
        self.pool.open(wait=False)

    def close(self) -> None:
        self.pool.close()

    @contextmanager
    def connection(self, timeout: float | None = None) -> Iterator[Connection]:
        with self.pool.connection(timeout=timeout) as conn:
            yield conn

    def fetch_all(self, sql: str, params: Any = None) -> list[Row]:
        with self.connection() as conn:
            return conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: str, params: Any = None) -> Row | None:
        with self.connection() as conn:
            return conn.execute(sql, params).fetchone()

    def fetch_value(self, sql: str, params: Any = None) -> Any:
        row = self.fetch_one(sql, params)
        return None if row is None else next(iter(row.values()))
