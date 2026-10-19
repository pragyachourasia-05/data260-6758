"""PyMongo connection for the s6758_doc database.

The listings collection gets a $jsonSchema validator so MongoDB itself rejects
documents that bypass the Pydantic layer. The memory collections (messages,
summaries, episodes) are created in the same database with light validators
and the indexes the chat endpoints query on.
"""
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure

from .mongo_config import MONGODB_DB, MONGODB_URI

LISTING_STATUSES = ["available", "pending", "rented"]
PROPERTY_TYPES = ["apartment", "house", "condo", "studio", "townhouse"]

LISTINGS_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["title", "status", "property_type", "available_from", "created_at", "updated_at"],
        "properties": {
            "title": {"bsonType": "string", "minLength": 1, "maxLength": 100},
            "description": {"bsonType": ["string", "null"], "maxLength": 2000},
            "status": {"enum": LISTING_STATUSES},
            "property_type": {"enum": PROPERTY_TYPES},
            "monthly_rent": {"bsonType": ["int", "long", "double", "null"], "minimum": 0},
            "available_from": {"bsonType": "date"},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

MESSAGES_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "role", "content", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": "string"},
            "role": {"enum": ["user", "assistant"]},
            "content": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

SUMMARIES_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "scope", "text", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": ["string", "null"]},
            "scope": {"enum": ["session", "user"]},
            "text": {"bsonType": "string"},
            "created_at": {"bsonType": "date"},
        },
    }
}

EPISODES_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "session_id", "fact", "importance", "embedding", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string"},
            "session_id": {"bsonType": "string"},
            "fact": {"bsonType": "string", "maxLength": 300},
            "importance": {"bsonType": "double", "minimum": 0, "maximum": 1},
            "embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
            "created_at": {"bsonType": "date"},
        },
    }
}

_client = None
_initialized = False


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=15000, tz_aware=True)
    return _client


def get_db():
    return get_client()[MONGODB_DB]


def _ensure_collection(db, name: str, validator: dict) -> None:
    try:
        db.create_collection(name, validator=validator, validationLevel="strict")
    except CollectionInvalid:
        # Already exists: keep the validator in sync with the code.
        db.command("collMod", name, validator=validator, validationLevel="strict")


def init_db() -> None:
    """Create collections, validators and indexes once per process."""
    global _initialized
    if _initialized:
        return
    db = get_db()
    _ensure_collection(db, "listings", LISTINGS_VALIDATOR)
    _ensure_collection(db, "messages", MESSAGES_VALIDATOR)
    _ensure_collection(db, "summaries", SUMMARIES_VALIDATOR)
    _ensure_collection(db, "episodes", EPISODES_VALIDATOR)

    db.listings.create_index([("status", ASCENDING), ("property_type", ASCENDING)])
    db.messages.create_index([("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)])
    db.summaries.create_index([("user_id", ASCENDING), ("scope", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)])
    db.episodes.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    _initialized = True


def get_listings_collection():
    init_db()
    return get_db()["listings"]


def get_memory_collections():
    init_db()
    db = get_db()
    return db["messages"], db["summaries"], db["episodes"]


def ping() -> bool:
    try:
        get_client().admin.command("ping")
        return True
    except (OperationFailure, Exception):
        return False
