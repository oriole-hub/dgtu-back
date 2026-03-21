from datetime import datetime

from pydantic import BaseModel, Field

from app.models import UserRole


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    login: str = Field(min_length=3, max_length=64)
    pwd: str = Field(min_length=6, max_length=128)


class BootstrapOfficeHeadIn(RegisterIn):
    office_name: str = Field(min_length=2, max_length=255)
    office_address: str = Field(min_length=3, max_length=255)
    office_city: str = Field(min_length=2, max_length=128)
    office_is_active: bool = True


class AdminCreateIn(RegisterIn):
    role: UserRole = Field(default=UserRole.ADMIN)
    office_id: int


class EmployeeCreateIn(RegisterIn):
    """Сотрудник создаётся в офисе текущего администратора; office_id должен совпадать."""

    office_id: int
    position: str = Field(min_length=1, max_length=255)
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)


class GuestCreateIn(RegisterIn):
    """Гостевой аккаунт офиса администратора; офис берётся из админа, цель обязательна."""

    account_purpose: str = Field(min_length=3, max_length=2000)
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=255)
    email: str | None = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    role: UserRole | None = None
    office_id: int | None = None
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)
    referral_count: int | None = Field(default=None, ge=0)
    position: str | None = Field(default=None, min_length=1, max_length=255)
    account_purpose: str | None = Field(default=None, min_length=3, max_length=2000)


class GuestSelfUpdateIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    login: str = Field(min_length=3, max_length=64)
    pwd: str | None = Field(default=None, min_length=6, max_length=128)


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
    referral_count: int
    position: str | None = None
    account_purpose: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime
