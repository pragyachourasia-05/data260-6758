from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import crud, models, schema
from .database import Base, engine, get_db
from .session_crud import create_session, delete_session, get_session
from .nplus1 import router as nplus1_router


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Rental Housing Listings HW4 API")
app.include_router(nplus1_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_session(
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("session_id")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    session = get_session(db, token)

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    return session


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": "s6758_rel",
    }


@app.post("/users", response_model=schema.UserOut, status_code=201)
def register_user(
    payload: schema.UserCreate,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_user(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already exists",
        )


@app.post("/auth/login")
def login(
    payload: schema.LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = crud.get_user_by_email(db, str(payload.email))

    if not user or not crud.verify_password(
        payload.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    session = create_session(db, user.id)

    response.set_cookie(
        key="session_id",
        value=session.id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=30 * 60,
    )

    return {
        "message": "logged in",
        "user_id": user.id,
        "email": user.email,
    }


@app.get("/auth/me")
def current_user(
    session=Depends(require_session),
    db: Session = Depends(get_db),
):
    user = crud.get_user(db, session.user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    return {
        "logged_in": True,
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
    }


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("session_id")

    if token:
        delete_session(db, token)

    response.delete_cookie("session_id")

    return {
        "message": "logged out",
    }


@app.get(
    "/listings",
    response_model=list[schema.ListingOut],
)
def list_listings(
    _session=Depends(require_session),
    db: Session = Depends(get_db),
):
    return crud.get_listings(db)


@app.get(
    "/listings/{listing_id}",
    response_model=schema.ListingOut,
)
def get_listing(
    listing_id: int,
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
    db: Session = Depends(get_db),
):
    return crud.list_listing_details(db)


@app.get(
    "/listing-details/{detail_id}",
    response_model=schema.ListingDetailOut,
)
def get_listing_detail(
    detail_id: int,
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
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
    _session=Depends(require_session),
    db: Session = Depends(get_db),
):
    return crud.get_listings_for_detail(
        db,
        detail_name,
        detail_value,
    )