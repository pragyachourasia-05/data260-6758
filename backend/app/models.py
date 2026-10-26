
from sqlalchemy import (
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    # HW7: JWT login is by username; role drives authorization.
    username = Column(String(100), nullable=False, unique=True, index=True)
    role = Column(Enum("reader", "writer", "moderator", name="user_role"), nullable=False, default="reader")


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