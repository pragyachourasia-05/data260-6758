"""HW9 Part 1 test: 25 accesses of one listing.

    python backend/run_hw09_counter.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.listing_cache import ListingCache  # noqa: E402

LISTING_ID = 4
RAW = Path(__file__).resolve().parent.parent / "reports" / "hw09" / "raw"


def main():
    cache = ListingCache()
    cache.redis_client.delete(cache.views_key(LISTING_ID))
    with engine.begin() as conn:
        conn.execute(text("UPDATE listings SET view_count = 0 WHERE id = :id"), {"id": LISTING_ID})

    print("=== Testing Counter ===\n")
    for access in range(1, 26):
        print(f"Access #{access}: Total = {cache.increment_listing_views(LISTING_ID)}", flush=True)
        if cache.last_synced:
            print("✓ Synced views to database", flush=True)

    result = {"listing_id": LISTING_ID, "redis_key": cache.views_key(LISTING_ID),
              "redis_count": int(cache.redis_client.get(cache.views_key(LISTING_ID))),
              "database_view_count": cache.database_views(LISTING_ID)}
    print(f"\nRedis key {result['redis_key']} = {result['redis_count']}")
    print(f"MySQL listings.view_count for listing {LISTING_ID} = {result['database_view_count']}")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part1_counter.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
