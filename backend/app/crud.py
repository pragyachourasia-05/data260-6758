import hashlib
import hmac
import secrets

from sqlalchemy.orm import Session, joinedload

from . import models, schema


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        120_000,
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, digest_hex = stored_hash.split("$", 1)
        salt = bytes.fromhex(salt_hex)

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            120_000,
        )

        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_user(db: Session, payload: schema.UserCreate):
    user = models.User(
        name=payload.name,
        email=str(payload.email),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user(db: Session, user_id: int):
    return (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )


def get_user_by_email(db: Session, email: str):
    return (
        db.query(models.User)
        .filter(models.User.email == email)
        .first()
    )


def get_users(db: Session):
    return db.query(models.User).order_by(models.User.id.asc()).all()


def create_listing(db: Session, payload: schema.ListingCreate):
    listing = models.Listing(
        property_address=payload.property_address,
        monthly_rent=payload.monthly_rent,
        submitter_email=str(payload.submitter_email),
        listing_description=payload.listing_description,
        property_category=payload.property_category,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def get_listings(db: Session):
    return (
        db.query(models.Listing)
        .options(joinedload(models.Listing.details))
        .order_by(models.Listing.id.asc())
        .all()
    )


def get_listing(db: Session, listing_id: int):
    return (
        db.query(models.Listing)
        .options(joinedload(models.Listing.details))
        .filter(models.Listing.id == listing_id)
        .first()
    )


def update_listing(
    db: Session,
    listing_id: int,
    payload: schema.ListingUpdate,
):
    listing = (
        db.query(models.Listing)
        .filter(models.Listing.id == listing_id)
        .first()
    )

    if not listing:
        return None

    listing.property_address = payload.property_address
    listing.monthly_rent = payload.monthly_rent
    listing.submitter_email = str(payload.submitter_email)
    listing.listing_description = payload.listing_description
    listing.property_category = payload.property_category

    db.commit()
    db.refresh(listing)
    return listing


def delete_listing(db: Session, listing_id: int):
    listing = (
        db.query(models.Listing)
        .filter(models.Listing.id == listing_id)
        .first()
    )

    if not listing:
        return None

    db.delete(listing)
    db.commit()
    return listing


def create_listing_detail(
    db: Session,
    payload: schema.RelatedDetailCreate,
):
    detail = models.ListingDetail(
        listing_id=payload.listing_id,
        detail_name=payload.detail_name,
        detail_value=payload.detail_value,
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return detail