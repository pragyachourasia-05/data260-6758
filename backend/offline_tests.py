"""Part 4 and Part 5 offline assert-based tests."""
from __future__ import annotations

import json

from app.execute_tool import execute_tool
from app.hw5_contracts import FixtureStore


def check(label, fn):
    try:
        fn()
        print(f"PASS | {label}")
        return True
    except AssertionError as exc:
        print(f"FAIL | {label} | {exc}")
        return False


def obj(raw):
    value = json.loads(raw)
    assert set(value) == {"ok", "data", "error"}
    return value


def main():
    store = FixtureStore()
    tests = [
        ("search valid", lambda: assert_ok(obj(execute_tool("search_listings", {"query": "Apartment"}, store)))),
        ("search invalid query", lambda: assert_error(obj(execute_tool("search_listings", {"query": ""}, store)), "query")),
        ("detail valid", lambda: assert_ok(obj(execute_tool("listing_detail", {"listing_id": 1}, store)))),
        ("detail invalid id", lambda: assert_error(obj(execute_tool("listing_detail", {"listing_id": -1}, store)), "positive")),
        ("summary valid", lambda: assert_ok(obj(execute_tool("listing_summary", {"category": "House"}, store)))),
        ("summary invalid category", lambda: assert_error(obj(execute_tool("listing_summary", {"category": ""}, store)), "non-empty")),
        ("safety block", lambda: assert_error(obj(execute_tool("listing_summary", {"include_private": True}, store)), "safety")),
        ("unknown tool", lambda: assert_error(obj(execute_tool("not_allowed", {}, store)), "unknown")),
    ]
    passed = sum(check(label, fn) for label, fn in tests)
    print(f"SUMMARY: {passed}/{len(tests)} PASS")
    return 0 if passed == len(tests) else 1


def assert_ok(value):
    assert value["ok"] is True and value["error"] is None


def assert_error(value, text):
    assert value["ok"] is False and text.lower() in value["error"].lower()


if __name__ == "__main__":
    raise SystemExit(main())
