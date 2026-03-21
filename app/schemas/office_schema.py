from datetime import datetime

from pydantic import BaseModel, Field


class OfficeCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    address: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=128)
    is_active: bool = True


class OfficeOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    is_active: bool
    created_by_user_id: int
    created_at: datetime
