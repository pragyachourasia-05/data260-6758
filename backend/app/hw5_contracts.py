"""Pure domain-tool contracts used by the MCP server and offline tests.

The store is deliberately dependency-injected.  The production adapter can be
replaced by a SQLAlchemy adapter, while the included fixture store makes the
contract tests deterministic and offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def envelope(ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data if ok else None, "error": None if ok else error}


@dataclass
class FixtureStore:
    listings: list[dict[str, Any]] = field(default_factory=lambda: [
        {"id": 1, "listing_code": "L-6758-001", "address": "100 Research Avenue, San Jose, CA", "category": "Apartment", "monthly_rent": 1800, "available_units": 1, "owner_id": 1},
        {"id": 2, "listing_code": "L-6758-002", "address": "101 Research Avenue, San Jose, CA", "category": "House", "monthly_rent": 2400, "available_units": 2, "owner_id": 1},
        {"id": 3, "listing_code": "L-6758-003", "address": "102 Research Avenue, San Jose, CA", "category": "Apartment", "monthly_rent": 2100, "available_units": 0, "owner_id": 2},
    ])
    owners: list[dict[str, Any]] = field(default_factory=lambda: [
        {"id": 1, "first_name": "Pragya", "last_name": "Chourasia", "email": "owner1@example.com"},
        {"id": 2, "first_name": "Alex", "last_name": "Rivera", "email": "owner2@example.com"},
    ])


def search_listings(store: FixtureStore, query: str, limit: int = 10) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        return envelope(False, error="query must be a non-empty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        return envelope(False, error="limit must be an integer from 1 to 50")
    needle = query.strip().lower()
    rows = [r for r in store.listings if needle in r["address"].lower() or needle in r["category"].lower() or needle in r["listing_code"].lower()]
    return envelope(True, rows[:limit])


def listing_detail(store: FixtureStore, listing_id: int) -> dict[str, Any]:
    if not isinstance(listing_id, int) or isinstance(listing_id, bool) or listing_id <= 0:
        return envelope(False, error="listing_id must be a positive integer")
    row = next((r for r in store.listings if r["id"] == listing_id), None)
    if row is None:
        return envelope(False, error="listing not found")
    owner = next((o for o in store.owners if o["id"] == row["owner_id"]), None)
    return envelope(True, {**row, "owner": owner})


def listing_summary(store: FixtureStore, category: str | None = None) -> dict[str, Any]:
    if category is not None and (not isinstance(category, str) or not category.strip()):
        return envelope(False, error="category must be a non-empty string when supplied")
    rows = store.listings if category is None else [r for r in store.listings if r["category"].lower() == category.strip().lower()]
    if not rows:
        return envelope(True, {"count": 0, "average_monthly_rent": None, "category": category})
    return envelope(True, {
        "count": len(rows),
        "average_monthly_rent": round(sum(r["monthly_rent"] for r in rows) / len(rows), 2),
        "category": category,
    })
