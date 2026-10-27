"""HW8 Part 1 - Listing request/response over Kafka.

Shared by the worker (backend/listing_worker.py) and the FastAPI wrapper (backend/kafka_api.py).
Primary entity of domain 6 is Listing, so the operations are CREATE_LISTING and GET_LISTING.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

PREFIX = "s6758"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
REQUEST_TOPIC = f"{PREFIX}_listing_requests"
RESPONSE_TOPIC = f"{PREFIX}_listing_responses"

CATEGORIES = {"Apartment", "House", "Condo", "Studio", "Townhouse"}
TEXT_FIELDS = {"property_address": 255, "listing_description": 2000}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def log(component: str, event: str, **fields) -> None:
    """One timestamped line per event, so logs from all processes can be merged in order."""
    extra = " ".join(f"{k}={json.dumps(v, default=str)}" for k, v in fields.items())
    print(f"{now()} [{component}] {event} {extra}".rstrip(), flush=True)


def validate_listing(data) -> str | None:
    if not isinstance(data, dict):
        return "data must be an object"
    for field, limit in TEXT_FIELDS.items():
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return f"{field} is required"
        if len(value) > limit:
            return f"{field} must be at most {limit} characters"
    rent = data.get("monthly_rent")
    if rent is None or rent == "":
        return "monthly_rent is required"
    if isinstance(rent, bool) or not isinstance(rent, (int, float)) or rent <= 0:
        return "monthly_rent must be a number greater than 0"
    category = data.get("property_category")
    if not isinstance(category, str) or not category.strip():
        return "property_category is required"
    if category not in CATEGORIES:
        return f"property_category must be one of {sorted(CATEGORIES)}"
    return None


def process(listings: dict, operation, data) -> dict:
    """Business logic only: returns the response body without the correlation_id."""
    if operation == "CREATE_LISTING":
        error = validate_listing(data)
        if error:
            return {"success": False, "error": error}
        listing_id = str(uuid.uuid4())
        listings[listing_id] = {
            "listing_id": listing_id,
            "property_address": data["property_address"].strip(),
            "monthly_rent": data["monthly_rent"],
            "property_category": data["property_category"],
            "listing_description": data["listing_description"].strip(),
        }
        return {"success": True, "listing_id": listing_id, "message": "Listing created"}

    if operation == "GET_LISTING":
        listing_id = data.get("listing_id") if isinstance(data, dict) else None
        if not isinstance(listing_id, str) or not listing_id.strip():
            return {"success": False, "error": "listing_id is required"}
        if listing_id not in listings:
            return {"success": False, "error": "Listing not found"}
        return {"success": True, "listing": listings[listing_id]}

    return {"success": False, "error": "Unknown operation"}


def make_request(correlation_id: str, operation: str, data: dict) -> dict:
    return {"correlation_id": correlation_id, "reply_to": RESPONSE_TOPIC, "operation": operation, "data": data}


def make_response(correlation_id, result: dict) -> dict:
    return {"correlation_id": correlation_id, **result}
