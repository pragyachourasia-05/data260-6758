import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from . import crud, schema
from .auth_jwt import (
    ACCESS_TOKEN_MINUTES,
    MODERATOR_ONLY,
    WRITER_OR_MODERATOR,
    create_access_token,
    get_current_claims,
)
from .database import Base, engine, get_db
from .hw5_entities import router as hw5_router
from .mongo_db import ping as mongo_ping
from .nplus1 import router as nplus1_router
from .routes_bikeshare import router as bikeshare_router
from .routes_listings_doc import router as listings_doc_router
from .routes_memory import router as memory_router

try:
    Base.metadata.create_all(bind=engine)
except OperationalError:
    # HW6 MongoDB routes do not need MySQL; keep them usable if it is down.
    logging.getLogger(__name__).warning("MySQL unavailable; relational routes will fail until it is up.")

app = FastAPI(title="Rental Housing Listings API (HW4-HW7)")
app.include_router(nplus1_router)
app.include_router(listings_doc_router)
app.include_router(memory_router)
app.include_router(bikeshare_router)


@app.middleware("http")
async def require_json_body(request: Request, call_next):
    """HW6: request bodies sent to /api/* must be JSON (FastAPI then parses them)."""
    if (
        request.url.path.startswith("/api/")
        and request.method in {"POST", "PUT", "PATCH"}
        and "application/json" not in request.headers.get("content-type", "")
    ):
        return JSONResponse(status_code=415, content={"detail": "Content-Type must be application/json."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8458", "http://127.0.0.1:8458"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "s6758_rel",
        "mongo_database": "s6758_doc",
        "mongo_ok": mongo_ping(),
    }


@app.get("/chat", include_in_schema=False)
def chat_page():
    """HW6 Part 2 mini chat page that calls POST /api/chat."""
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "chat.html")


@app.post("/users", response_model=schema.UserOut, status_code=201)
def register_user(
    payload: schema.UserCreate,
    db: Session = Depends(get_db),
):
    """Self-registration always creates a reader; roles are assigned by the seed/migration."""
    try:
        return crud.create_user(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username or email already exists",
        ) from None


@app.post("/auth/login", response_model=schema.TokenOut)
def login(
    payload: schema.LoginRequest,
    db: Session = Depends(get_db),
):
    """HW7: verify the hashed password from MySQL, then issue a JWT access token."""
    user = crud.get_user_by_username(db, payload.username)

    if not user or not crud.verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": create_access_token(user.username, user.role),
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_MINUTES * 60,
        "role": user.role,
    }


@app.get("/auth/me")
def current_user(
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_username(db, claims["sub"])

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "name": user.name,
        "token_expires": claims["exp"],
    }


@app.get(
    "/listings",
    response_model=list[schema.ListingOut],
)
def list_listings(
    _claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    return crud.get_listings(db)


@app.get(
    "/listings/{listing_id}",
    response_model=schema.ListingOut,
)
def get_listing(
    listing_id: int,
    _claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    listing = crud.get_listing(db, listing_id)

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Listing not found",
        )

    return listing


@app.post(
    "/listings",
    response_model=schema.ListingOut,
    status_code=201,
)
def create_listing(
    payload: schema.ListingCreate,
    _claims: dict = Depends(WRITER_OR_MODERATOR),
    db: Session = Depends(get_db),
):
    return crud.create_listing(db, payload)


@app.put(
    "/listings/{listing_id}",
    response_model=schema.ListingOut,
)
def update_listing(
    listing_id: int,
    payload: schema.ListingUpdate,
    _claims: dict = Depends(WRITER_OR_MODERATOR),
    db: Session = Depends(get_db),
):
    listing = crud.update_listing(db, listing_id, payload)

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Listing not found",
        )

    return crud.get_listing(db, listing_id)


@app.delete(
    "/listings/{listing_id}",
    response_model=schema.ListingOut,
)
def delete_listing(
    listing_id: int,
    _claims: dict = Depends(MODERATOR_ONLY),
    db: Session = Depends(get_db),
):
    listing = crud.delete_listing(db, listing_id)

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Listing not found",
        )

    return listing


@app.post(
    "/listing-details",
    response_model=schema.ListingDetailOut,
    status_code=201,
)
def create_listing_detail(
    payload: schema.RelatedDetailCreate,
    _claims: dict = Depends(WRITER_OR_MODERATOR),
    db: Session = Depends(get_db),
):
    listing = crud.get_listing(db, payload.listing_id)

    if not listing:
        raise HTTPException(
            status_code=404,
            detail="Listing not found",
        )

    return crud.create_listing_detail(db, payload)

@app.get(
    "/listing-details",
    response_model=list[schema.ListingDetailOut],
)
def list_listing_details(
    _claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    return crud.list_listing_details(db)


@app.get(
    "/listing-details/{detail_id}",
    response_model=schema.ListingDetailOut,
)
def get_listing_detail(
    detail_id: int,
    _claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    detail = crud.get_listing_detail(db, detail_id)

    if not detail:
        raise HTTPException(
            status_code=404,
            detail="Listing detail not found",
        )

    return detail


@app.put(
    "/listing-details/{detail_id}",
    response_model=schema.ListingDetailOut,
)
def update_listing_detail(
    detail_id: int,
    payload: schema.RelatedDetailUpdate,
    _claims: dict = Depends(WRITER_OR_MODERATOR),
    db: Session = Depends(get_db),
):
    detail = crud.update_listing_detail(db, detail_id, payload)

    if not detail:
        raise HTTPException(
            status_code=404,
            detail="Listing detail not found",
        )

    return detail


@app.delete(
    "/listing-details/{detail_id}",
    response_model=schema.ListingDetailOut,
)
def delete_listing_detail(
    detail_id: int,
    _claims: dict = Depends(MODERATOR_ONLY),
    db: Session = Depends(get_db),
):
    detail = crud.delete_listing_detail(db, detail_id)

    if not detail:
        raise HTTPException(
            status_code=404,
            detail="Listing detail not found",
        )

    return detail


@app.get(
    "/listing-details/{detail_name}/{detail_value}/listings",
    response_model=list[schema.ListingOut],
)
def get_listings_for_detail(
    detail_name: str,
    detail_value: str,
    _claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    return crud.get_listings_for_detail(
        db,
        detail_name,
        detail_value,
    )

app.include_router(hw5_router)
