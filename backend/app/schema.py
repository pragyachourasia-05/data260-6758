from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    email: EmailStr
    role: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class ListingCreate(BaseModel):
    property_address: str = Field(min_length=1, max_length=255)
    monthly_rent: str = Field(min_length=1, max_length=100)
    submitter_email: EmailStr
    listing_description: str = Field(min_length=1)
    property_category: str = Field(min_length=1, max_length=100)


class ListingDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    detail_name: str
    detail_value: str


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    property_address: str
    monthly_rent: str
    submitter_email: EmailStr
    listing_description: str
    property_category: str
    details: list[ListingDetailOut] = []


class RelatedDetailCreate(BaseModel):
    listing_id: int
    detail_name: str = Field(min_length=1, max_length=100)
    detail_value: str = Field(min_length=1, max_length=255)


class RelatedDetailUpdate(BaseModel):
    detail_name: str = Field(min_length=1, max_length=100)
    detail_value: str = Field(min_length=1, max_length=255)

class ListingUpdate(BaseModel):
    property_address: str = Field(min_length=1, max_length=255)
    monthly_rent: str = Field(min_length=1, max_length=100)
    submitter_email: EmailStr
    listing_description: str = Field(min_length=1)
    property_category: str = Field(min_length=1, max_length=100)
