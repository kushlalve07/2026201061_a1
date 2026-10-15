"""Runtime settings, read from the environment (same variable names as the seeders)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from psycopg.conninfo import make_conninfo


@dataclass(frozen=True)
class Settings:
    pg_host: str = "localhost"
    pg_port: int = 5433
    pg_database: str = "ridesync"
    pg_user: str = "ridesync"
    pg_password: str = "ridesync"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "ridesync"
    cors_origins: tuple[str, ...] = field(default=("http://localhost:5173",))

    @property
    def pg_conninfo(self) -> str:
        return make_conninfo(
            host=self.pg_host,
            port=self.pg_port,
            dbname=self.pg_database,
            user=self.pg_user,
            password=self.pg_password,
            application_name="ridesync-api",
        )

    @classmethod
    def from_env(cls) -> "Settings":
        origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
        return cls(
            pg_host=os.getenv("PGHOST", cls.pg_host),
            pg_port=int(os.getenv("PGPORT", str(cls.pg_port))),
            pg_database=os.getenv("PGDATABASE", cls.pg_database),
            pg_user=os.getenv("PGUSER", cls.pg_user),
            pg_password=os.getenv("PGPASSWORD", cls.pg_password),
            mongo_uri=os.getenv("MONGO_URI", cls.mongo_uri),
            mongo_database=os.getenv("MONGO_DB", cls.mongo_database),
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
