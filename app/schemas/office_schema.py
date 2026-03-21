from datetime import datetime

from pydantic import BaseModel, Field


class OfficeCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)


class OfficeOut(BaseModel):
    id: int
    name: str
    created_by_user_id: int
    created_at: datetime
