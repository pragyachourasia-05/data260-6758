from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import event
from sqlalchemy.orm import Session, joinedload
from contextvars import ContextVar

from .database import engine, get_db
from .models import Listing, ListingDetail


router = APIRouter(prefix="/bench", tags=["HW4 N+1 benchmark"])
sql_count = ContextVar("sql_count", default=None)


@event.listens_for(engine, "before_cursor_execute")
def count_sql_statements(
    conn,
    cursor,
    statement,
    parameters,
    context,
    executemany,
):
    current = sql_count.get()
    if current is not None:
        sql_count.set(current + 1)


def listing_payload(listing, details):
    return {
        "id": listing.id,
        "property_address": listing.property_address,
        "monthly_rent": listing.monthly_rent,
        "submitter_email": listing.submitter_email,
        "listing_description": listing.listing_description,
        "property_category": listing.property_category,
        "details": [
            {
                "id": detail.id,
                "detail_name": detail.detail_name,
                "detail_value": detail.detail_value,
            }
            for detail in details
        ],
    }


@router.get("/listings-naive")
def listings_naive(
    limit: int = Query(default=10, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    token = sql_count.set(0)
    try:
        listings = (
            db.query(Listing)
            .order_by(Listing.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for listing in listings:
            details = (
                db.query(ListingDetail)
                .filter(ListingDetail.listing_id == listing.id)
                .order_by(ListingDetail.id.asc())
                .all()
            )
            result.append(listing_payload(listing, details))

        count = sql_count.get()
        return JSONResponse(
            content=result,
            headers={"X-SQL-Count": str(count)},
        )
    finally:
        sql_count.reset(token)


@router.get("/listings-fixed")
def listings_fixed(
    limit: int = Query(default=10, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    token = sql_count.set(0)
    try:
        listings = (
            db.query(Listing)
            .options(joinedload(Listing.details))
            .order_by(Listing.id.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = [
            listing_payload(listing, listing.details)
            for listing in listings
        ]
        count = sql_count.get()
        return JSONResponse(
            content=result,
            headers={"X-SQL-Count": str(count)},
        )
    finally:
        sql_count.reset(token)
