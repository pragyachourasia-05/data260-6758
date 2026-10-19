"""Pydantic schemas for the HW6 MongoDB document API (Part 1) and chat memory API (Part 2)."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ListingStatus = Literal["available", "pending", "rented"]
PropertyType = Literal["apartment", "house", "condo", "studio", "townhouse"]


class ListingDocCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    status: ListingStatus = "available"
    property_type: PropertyType
    monthly_rent: Optional[float] = Field(None, ge=0)
    available_from: datetime


class ListingDocUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[ListingStatus] = None
    property_type: Optional[PropertyType] = None
    monthly_rent: Optional[float] = Field(None, ge=0)
    available_from: Optional[datetime] = None


class ListingDocOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: ListingStatus
    property_type: PropertyType
    monthly_rent: Optional[float] = None
    available_from: datetime
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    session_id: Optional[str] = Field(None, min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)
    # Experiment overrides for Part 3; normal clients leave these unset.
    short_term_n: Optional[int] = Field(None, ge=0, le=100)
    policy: Optional[Literal["none", "compress_assistant"]] = None


class ChatResponse(BaseModel):
    user_id: str
    session_id: str
    reply: str
    memory_used: dict[str, Any]
    usage: dict[str, Any]
