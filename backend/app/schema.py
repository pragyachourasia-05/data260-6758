from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


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


class RelatedDetailUpdate(BaseModel):
    detail_name: str = Field(min_length=1, max_length=100)
    detail_value: str = Field(min_length=1, max_length=255)