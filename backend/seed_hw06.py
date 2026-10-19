"""HW6 Part 1: seed the MongoDB `listings` collection through the running API.

Run from the repository root while the backend is up on port 8458:
    python backend/seed_hw06.py
Posting through the API (not straight into MongoDB) means every sample
document passes the same Pydantic + $jsonSchema validation as real clients.
"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8458/api/listings"

SAMPLES = [
    {"title": "Sunny 2BR near Diridon Station", "description": "Second floor, in-unit laundry, one covered parking spot.",
     "status": "available", "property_type": "apartment", "monthly_rent": 2850, "available_from": "2026-11-01T00:00:00Z"},
    {"title": "Downtown San Jose studio", "description": "Walk to SJSU, utilities included.",
     "status": "available", "property_type": "studio", "monthly_rent": 1950, "available_from": "2026-11-15T00:00:00Z"},
    {"title": "3BR house in Willow Glen", "description": "Backyard, pets allowed with deposit.",
     "status": "pending", "property_type": "house", "monthly_rent": 4200, "available_from": "2026-12-01T00:00:00Z"},
    {"title": "Santa Clara condo with EV charger",
     "status": "available", "property_type": "condo", "monthly_rent": 3100, "available_from": "2026-11-20T00:00:00Z"},
    {"title": "Sunnyvale townhouse near Caltrain", "description": "Two-car garage, quiet street.",
     "status": "rented", "property_type": "townhouse", "monthly_rent": 3650, "available_from": "2026-10-01T00:00:00Z"},
]


def post(payload: dict) -> dict:
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main() -> None:
    for sample in SAMPLES:
        try:
            created = post(sample)
            print(f"created {created['id']}  {created['title']}  ({created['status']}, {created['property_type']})")
        except urllib.error.HTTPError as exc:
            print(f"failed {sample['title']}: HTTP {exc.code} {exc.read().decode()[:200]}")


if __name__ == "__main__":
    main()
