"""HW5 relational extension for the existing rental-listing service.

The router uses the existing MySQL `listings` table and adds an `owners` table.
Run `ensure_hw5_schema` once at startup before including this router.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db

router = APIRouter(prefix="/hw5", tags=["HW5 rental entities"])


class OwnerCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr


class OwnerUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None


class ListingCreateHW5(BaseModel):
    property_address: str = Field(min_length=1, max_length=255)
    listing_code: str = Field(pattern=r"^L-\d{4}-\d{3}$")
    monthly_rent: float = Field(gt=0)
    available_units: int = Field(default=1, ge=0)
    owner_id: int = Field(gt=0)


class ListingUpdateHW5(BaseModel):
    property_address: str | None = Field(default=None, min_length=1, max_length=255)
    monthly_rent: float | None = Field(default=None, gt=0)
    available_units: int | None = Field(default=None, ge=0)
    owner_id: int | None = Field(default=None, gt=0)


def ensure_hw5_schema(db: Session) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS owners (
          id INT PRIMARY KEY AUTO_INCREMENT,
          first_name VARCHAR(100) NOT NULL,
          last_name VARCHAR(100) NOT NULL,
          email VARCHAR(255) NOT NULL UNIQUE,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """))
    for ddl in (
        "ALTER TABLE listings ADD COLUMN listing_code VARCHAR(20) NULL UNIQUE",
        "ALTER TABLE listings ADD COLUMN available_units INT NOT NULL DEFAULT 1",
        "ALTER TABLE listings ADD COLUMN owner_id INT NULL",
        "ALTER TABLE listings ADD COLUMN created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE listings ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    ):
        try:
            db.execute(text(ddl))
        except Exception as exc:
            # MySQL reports duplicate-column/index errors when migration was already run.
            if "duplicate" not in str(exc).lower() and "exists" not in str(exc).lower():
                raise
    db.commit()


def rows(db: Session, statement: str, params: dict[str, Any] | None = None):
    return [dict(row._mapping) for row in db.execute(text(statement), params or {}).mappings().all()]


@router.post("/owners", status_code=status.HTTP_201_CREATED)
def create_owner(payload: OwnerCreate, db: Session = Depends(get_db)):
    try:
        row = db.execute(text("INSERT INTO owners(first_name,last_name,email) VALUES (:first,:last,:email)"), payload.model_dump() | {"first": payload.first_name, "last": payload.last_name}).lastrowid
        db.commit()
        return rows(db, "SELECT * FROM owners WHERE id=:id", {"id": row})[0]
    except Exception as exc:
        db.rollback()
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "Owner email must be unique.")
        raise


@router.get("/owners")
def list_owners(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return rows(db, "SELECT * FROM owners ORDER BY id LIMIT :limit OFFSET :skip", {"limit": limit, "skip": skip})


@router.get("/owners/{owner_id}")
def get_owner(owner_id: int, db: Session = Depends(get_db)):
    found = rows(db, "SELECT * FROM owners WHERE id=:id", {"id": owner_id})
    if not found:
        raise HTTPException(404, "Owner not found.")
    return found[0]


@router.put("/owners/{owner_id}")
def update_owner(owner_id: int, payload: OwnerUpdate, db: Session = Depends(get_db)):
    get_owner(owner_id, db)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_owner(owner_id, db)
    assignments = ", ".join(f"{key}=:{key}" for key in data)
    data["id"] = owner_id
    try:
        db.execute(text(f"UPDATE owners SET {assignments} WHERE id=:id"), data)
        db.commit()
    except Exception as exc:
        db.rollback()
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "Owner email must be unique.")
        raise
    return get_owner(owner_id, db)


@router.delete("/owners/{owner_id}", status_code=204)
def delete_owner(owner_id: int, db: Session = Depends(get_db)):
    get_owner(owner_id, db)
    count = db.execute(text("SELECT COUNT(*) FROM listings WHERE owner_id=:id"), {"id": owner_id}).scalar_one()
    if count:
        raise HTTPException(409, "Cannot delete owner while listings reference this owner.")
    db.execute(text("DELETE FROM owners WHERE id=:id"), {"id": owner_id})
    db.commit()


@router.post("/listings", status_code=201)
def create_listing(payload: ListingCreateHW5, db: Session = Depends(get_db)):
    get_owner(payload.owner_id, db)
    try:
        result = db.execute(text("INSERT INTO listings(property_address,listing_code,monthly_rent,available_units,owner_id) VALUES (:address,:code,:rent,:units,:owner)"), {"address": payload.property_address, "code": payload.listing_code, "rent": payload.monthly_rent, "units": payload.available_units, "owner": payload.owner_id})
        db.commit()
        return get_listing(result.lastrowid, db)
    except Exception as exc:
        db.rollback()
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(409, "listing_code must be unique.")
        raise


@router.get("/listings")
def list_listings(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return rows(db, "SELECT * FROM listings ORDER BY id LIMIT :limit OFFSET :skip", {"limit": limit, "skip": skip})


def get_listing(listing_id: int, db: Session):
    found = rows(db, "SELECT * FROM listings WHERE id=:id", {"id": listing_id})
    if not found:
        raise HTTPException(404, "Listing not found.")
    return found[0]


@router.get("/listings/{listing_id}")
def listing_by_id(listing_id: int, db: Session = Depends(get_db)):
    return get_listing(listing_id, db)


@router.put("/listings/{listing_id}")
def update_listing(listing_id: int, payload: ListingUpdateHW5, db: Session = Depends(get_db)):
    get_listing(listing_id, db)
    data = payload.model_dump(exclude_unset=True)
    if "owner_id" in data:
        get_owner(data["owner_id"], db)
    if not data:
        return get_listing(listing_id, db)
    mapping = {"property_address": "property_address", "monthly_rent": "monthly_rent", "available_units": "available_units", "owner_id": "owner_id"}
    assignments = ", ".join(f"{mapping[key]}=:{key}" for key in data)
    data["id"] = listing_id
    db.execute(text(f"UPDATE listings SET {assignments} WHERE id=:id"), data)
    db.commit()
    return get_listing(listing_id, db)


@router.delete("/listings/{listing_id}", status_code=204)
def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    get_listing(listing_id, db)
    db.execute(text("DELETE FROM listings WHERE id=:id"), {"id": listing_id})
    db.commit()


@router.get("/owners/{owner_id}/listings")
def listings_for_owner(owner_id: int, db: Session = Depends(get_db)):
    get_owner(owner_id, db)
    return rows(db, "SELECT * FROM listings WHERE owner_id=:id ORDER BY id", {"id": owner_id})
