"""HW9 Part 1 - Redis view counter for listings, synced to MySQL every 10 views."""
from __future__ import annotations

import logging
import os

import redis
from sqlalchemy import text

from app.database import engine

logger = logging.getLogger(__name__)
PREFIX = "s6758"
SYNC_EVERY = 10


class ListingCache:
    def __init__(self, host: str | None = None, port: int = 6379):
        self.redis_client = redis.Redis(host=host or os.getenv("REDIS_HOST", "localhost"), port=port,
                                        decode_responses=True)
        self.redis_client.ping()
        self.last_synced = False
        self.ensure_view_column()

    @staticmethod
    def ensure_view_column() -> None:
        with engine.begin() as conn:
            found = conn.execute(text("SHOW COLUMNS FROM listings LIKE 'view_count'")).first()
            if not found:
                conn.execute(text("ALTER TABLE listings ADD COLUMN view_count INT NOT NULL DEFAULT 0"))

    @staticmethod
    def views_key(listing_id: int) -> str:
        return f"{PREFIX}:views:listing:{listing_id}"

    def increment_listing_views(self, listing_id: int) -> int:
        """Count one view in Redis and write the count to MySQL on every 10th view."""
        count = self.redis_client.incr(self.views_key(listing_id))
        self.last_synced = count % SYNC_EVERY == 0
        if self.last_synced:
            with engine.begin() as conn:
                conn.execute(text("UPDATE listings SET view_count = :count WHERE id = :id"),
                             {"count": count, "id": listing_id})
            logger.info("Synced views to database: listing %s = %s", listing_id, count)
        return count

    @staticmethod
    def database_views(listing_id: int) -> int:
        with engine.connect() as conn:
            return conn.execute(text("SELECT view_count FROM listings WHERE id = :id"), {"id": listing_id}).scalar_one()
