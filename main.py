import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

from routers.auth import router as auth_router

PORT_BASE = 8458  # SID4 = 6758 -> 8000 + (6758 mod 900)

app = FastAPI(title="Rental Housing Listings API")

# Session support for Part 1 auth (HW3). SECRET_KEY should come from the
# environment in real deployment; a dev fallback is used here so the app
# still runs without extra setup for local testing/screenshots.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-key-change-me")
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True,   # Secure attribute on the session cookie
    same_site="lax",   # SameSite attribute
    max_age=3600,      # absolute cookie lifetime; idle timeout is enforced separately in routers/auth.py
)
# HttpOnly is on by default for Starlette's SessionMiddleware -- combined
# with https_only and same_site above, that's all three required Set-Cookie
# attributes (Secure, HttpOnly, SameSite).

# Mount static files (the rental listings SPA from HW1/HW2)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Auth routes: "/", "/login", "/dashboard", "/logout"
app.include_router(auth_router)


# ---- Domain model, matching DOMAIN_SCHEMA.md ----

class Listing(BaseModel):
    id: int
    propertyAddress: str
    monthlyRent: str
    submitterEmail: str
    listingDescription: str
    propertyCategory: str


class ListingCreate(BaseModel):
    propertyAddress: str = Field(..., min_length=1)
    monthlyRent: str = Field(..., min_length=1)
    submitterEmail: str = Field(..., min_length=1)
    listingDescription: str = Field(..., min_length=1)
    propertyCategory: str = Field(..., min_length=1)


class ListingUpdate(BaseModel):
    propertyAddress: str = Field(..., min_length=1)
    monthlyRent: str = Field(..., min_length=1)
    submitterEmail: str = Field(..., min_length=1)
    listingDescription: str = Field(..., min_length=1)
    propertyCategory: str = Field(..., min_length=1)


# In-memory storage, seeded with two example listings
listings: List[Listing] = [
    Listing(
        id=1,
        propertyAddress="385 River Oaks Parkway, San Jose, CA",
        monthlyRent="$3,500/month",
        submitterEmail="pragya.chourasia@sjsu.edu",
        listingDescription="Decent property, good community, close to downtown.",
        propertyCategory="Apartment",
    ),
    Listing(
        id=2,
        propertyAddress="212 Willow Creek Dr, San Jose, CA",
        monthlyRent="$4,200/month",
        submitterEmail="pragya.chourasia@sjsu.edu",
        listingDescription="Spacious house with a backyard, near light rail.",
        propertyCategory="House",
    ),
]


# ---- REST API endpoints (unchanged from HW2) ----

@app.get("/api/listings", response_model=List[Listing])
async def get_listings(q: Optional[str] = Query(default=None, description="Search primary/secondary field")):
    if not q:
        return listings
    needle = q.strip().lower()
    return [
        listing for listing in listings
        if needle in listing.propertyAddress.lower() or needle in listing.monthlyRent.lower()
    ]


@app.get("/api/listings/{listing_id}", response_model=Listing)
async def get_listing(listing_id: int):
    listing = next((l for l in listings if l.id == listing_id), None)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@app.post("/api/listings", response_model=Listing, status_code=201)
async def create_listing(data: ListingCreate):
    new_id = max([l.id for l in listings], default=0) + 1
    new_listing = Listing(id=new_id, **data.model_dump())
    listings.append(new_listing)
    print(f"Created listing: {new_listing}")
    return new_listing


@app.delete("/api/listings/highest-id", response_model=Listing)
async def delete_highest_id_listing():
    """Defined BEFORE /api/listings/{listing_id} -- see HW2 note on FastAPI route-matching order."""
    global listings
    if not listings:
        raise HTTPException(status_code=404, detail="No listings to delete")
    target = max(listings, key=lambda l: l.id)
    listings = [l for l in listings if l.id != target.id]
    print(f"Deleted highest-ID listing: {target}")
    return target


@app.put("/api/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: int, data: ListingUpdate):
    listing = next((l for l in listings if l.id == listing_id), None)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.propertyAddress = data.propertyAddress
    listing.monthlyRent = data.monthlyRent
    listing.submitterEmail = data.submitterEmail
    listing.listingDescription = data.listingDescription
    listing.propertyCategory = data.propertyCategory

    print(f"Updated listing: {listing}")
    return listing


@app.delete("/api/listings/{listing_id}", status_code=204)
async def delete_listing(listing_id: int):
    global listings
    index = next((i for i, l in enumerate(listings) if l.id == listing_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    deleted = listings.pop(index)
    print(f"Deleted listing: {deleted}")
    return None


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=PORT_BASE, reload=True)
