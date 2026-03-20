from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    login: str = Field(min_length=3, max_length=64)
    pwd: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    pwd: str = Field(min_length=6, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    login: str
    created_at: datetime
