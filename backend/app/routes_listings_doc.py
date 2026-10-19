"""CRUD route handlers for the MongoDB `listings` collection (HW6 Part 1)."""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, Query, Response, status
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError, WriteError

from .doc_schemas import ListingDocCreate, ListingDocOut, ListingDocUpdate
from .mongo_db import get_listings_collection

router = APIRouter(prefix="/api/listings", tags=["HW6 Listings (MongoDB)"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _object_id(listing_id: str) -> ObjectId:
    try:
        return ObjectId(listing_id)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid listing id '{listing_id}': expected a 24-character hex ObjectId.")


def _serialize(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["id"] = str(doc["_id"])
    return out


def _db_error(action: str, exc: Exception):
    if isinstance(exc, WriteError):
        # MongoDB $jsonSchema rejected the document.
        raise HTTPException(status_code=422, detail=f"Document failed database validation while {action}.")
    raise HTTPException(status_code=500, detail=f"Database error while {action}.")


@router.post("", response_model=ListingDocOut, status_code=status.HTTP_201_CREATED)
def create_listing(payload: ListingDocCreate):
    doc = payload.model_dump()
    ts = _now()
    doc["created_at"] = ts
    doc["updated_at"] = ts
    try:
        col = get_listings_collection()
        res = col.insert_one(doc)
        return _serialize(col.find_one({"_id": res.inserted_id}))
    except PyMongoError as exc:
        _db_error("creating listing", exc)


@router.get("", response_model=list[ListingDocOut])
def list_listings(
    status_filter: str | None = Query(None, alias="status"),
    property_type: str | None = None,
):
    query = {}
    if status_filter:
        query["status"] = status_filter
    if property_type:
        query["property_type"] = property_type
    try:
        docs = get_listings_collection().find(query).sort("created_at", -1)
        return [_serialize(d) for d in docs]
    except PyMongoError as exc:
        _db_error("fetching listings", exc)


@router.get("/{listing_id}", response_model=ListingDocOut)
def get_listing(listing_id: str):
    oid = _object_id(listing_id)
    try:
        doc = get_listings_collection().find_one({"_id": oid})
    except PyMongoError as exc:
        _db_error("fetching listing", exc)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found.")
    return _serialize(doc)


@router.put("/{listing_id}", response_model=ListingDocOut)
def update_listing(listing_id: str, payload: ListingDocUpdate):
    oid = _object_id(listing_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided to update.")
    updates["updated_at"] = _now()
    try:
        doc = get_listings_collection().find_one_and_update(
            {"_id": oid}, {"$set": updates}, return_document=ReturnDocument.AFTER
        )
    except PyMongoError as exc:
        _db_error("updating listing", exc)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found.")
    return _serialize(doc)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(listing_id: str):
    oid = _object_id(listing_id)
    try:
        res = get_listings_collection().delete_one({"_id": oid})
    except PyMongoError as exc:
        _db_error("deleting listing", exc)
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"Listing {listing_id} not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
