from datetime import datetime

from pydantic import BaseModel, Field

from app.models import UserRole


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    login: str = Field(min_length=3, max_length=64)
    pwd: str = Field(min_length=6, max_length=128)


class AdminCreateIn(RegisterIn):
    role: UserRole = Field(default=UserRole.ADMIN)
    office_id: int


class StaffCreateIn(RegisterIn):
    role: UserRole
    office_id: int
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=255)
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    role: UserRole | None = None
    office_id: int | None = None
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)


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
    role: UserRole
    office_id: int | None = None
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = None
    passes_created_count: int
    created_by_user_id: int | None = None
    created_at: datetime
