from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
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
    login: str
    created_at: datetime
