"""MongoDB access. The client connects lazily and fails fast (2 s) when the server is down."""
from __future__ import annotations

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database


class Mongo:
    def __init__(self, uri: str, database: str):
        self.client: MongoClient = MongoClient(
            uri,
            tz_aware=True,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            appname="ridesync-api",
        )
        self.db: Database = self.client[database]

    @property
    def pings(self) -> Collection:
        return self.db["TelemetryPings"]

    @property
    def reviews(self) -> Collection:
        return self.db["TripReviews"]

    @property
    def metadata(self) -> Collection:
        return self.db["VehicleMetadata"]

    def close(self) -> None:
        self.client.close()
