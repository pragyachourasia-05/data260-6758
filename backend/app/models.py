from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)

    sessions = relationship(
        "SessionToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="sessions")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    property_address = Column(String(255), nullable=False, index=True)
    monthly_rent = Column(String(100), nullable=False)
    submitter_email = Column(String(255), nullable=False)
    listing_description = Column(Text, nullable=False)
    property_category = Column(String(100), nullable=False, index=True)

    details = relationship(
        "ListingDetail",
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class ListingDetail(Base):
    __tablename__ = "listing_details"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    listing_id = Column(
        Integer,
        ForeignKey("listings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detail_name = Column(String(100), nullable=False)
    detail_value = Column(String(255), nullable=False)

    listing = relationship("Listing", back_populates="details")