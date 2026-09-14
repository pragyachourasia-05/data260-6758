from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import uvicorn

PORT_BASE = 8458  # SID4 = 6758 -> 8000 + (6758 mod 900)

app = FastAPI(title="Rental Housing Listings API", version="1.0.0")

# Mount static files directory for serving HTML/CSS/JS
app.mount("/static", StaticFiles(directory="static"), name="static")


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


# Serve the main HTML page
@app.get("/")
async def read_root():
    return FileResponse("static/index.html")


# ---- REST API endpoints ----

@app.get("/api/listings", response_model=List[Listing])
async def get_listings(q: Optional[str] = Query(default=None, description="Search primary/secondary field")):
    """
    Returns all listings, or a filtered subset when q is provided.
    Search matches (case-insensitively) against propertyAddress (primary field)
    or monthlyRent (secondary field), per the assignment's search requirement.
    """
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
    """Add a new listing. The frontend re-fetches the list and re-renders home after this succeeds."""
    new_id = max([l.id for l in listings], default=0) + 1
    new_listing = Listing(id=new_id, **data.model_dump())
    listings.append(new_listing)
    print(f"Created listing: {new_listing}")
    return new_listing


@app.delete("/api/listings/highest-id", response_model=Listing)
async def delete_highest_id_listing():
    """
    Convenience endpoint matching the assignment's specific requirement:
    delete the record with the highest ID currently in the list.
    Defined BEFORE the generic /api/listings/{listing_id} route below,
    since FastAPI matches path routes in registration order and an int
    path param would otherwise swallow this literal path first.
    """
    global listings
    if not listings:
        raise HTTPException(status_code=404, detail="No listings to delete")
    target = max(listings, key=lambda l: l.id)
    listings = [l for l in listings if l.id != target.id]
    print(f"Deleted highest-ID listing: {target}")
    return target


@app.put("/api/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: int, data: ListingUpdate):
    """Update an existing listing's fields (used generally, and specifically to update ID 1 per the assignment)."""
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


import webbrowser

if __name__ == "__main__":
    webbrowser.open(f"http://localhost:{PORT_BASE}")
    uvicorn.run(app, host="0.0.0.0", port=PORT_BASE)
