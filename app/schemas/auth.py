from datetime import datetime
from pydantic import BaseModel, Field, computed_field

from app.models import UserRole
from app.schemas.office_schema import OfficeOut


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
    office_id: int
    job_title: str = Field(min_length=1, max_length=255)
    account_expires_at: datetime | None = None
    pass_limit_total: int | None = Field(default=None, ge=1)


class GuestCreateIn(RegisterIn):
    office_id: int
    creation_purpose: str = Field(min_length=3, max_length=512, description="Цель создания гостевого аккаунта")
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
    job_title: str | None = Field(default=None, max_length=255)
    account_creation_purpose: str | None = Field(default=None, max_length=512)


class GuestSelfUpdateIn(BaseModel):
    full_name: str = Field(min_length=3, max_length=255)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    login: str = Field(min_length=3, max_length=64)
    pwd: str | None = Field(default=None, min_length=6, max_length=128)


class LoginIn(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    pwd: str = Field(min_length=6, max_length=128)


class ForgotPasswordIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)


class ForgotPasswordOut(BaseModel):
    ok: bool = True


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
    created_by_user_id: int | None = None
    created_at: datetime
    job_title: str | None = Field(default=None, description="Должность (сотрудник)")
    account_creation_purpose: str | None = None
    office: OfficeOut | None = None
    last_in_at: datetime | None = Field(
        default=None, description="Последнее событие входа (любой день, UTC)"
    )
    last_out_at: datetime | None = Field(
        default=None, description="Последнее событие выхода (любой день, UTC)"
    )
    last_break_out_at: datetime | None = Field(
        default=None,
        description="Начало последнего завершённого перекура сегодня (локальный день офиса события, UTC)",
    )
    last_break_in_at: datetime | None = Field(
        default=None,
        description="Возврат после последнего завершённого перекура сегодня (UTC)",
    )
    last_break_duration_seconds: int | None = Field(
        default=None,
        description="Длительность последнего завершённого перекура сегодня, секунды",
    )
    late_minutes_today: int | None = Field(
        default=None,
        description="Опоздание сегодня (локальный день офиса пользователя): минуты после work_start до первого входа",
    )
    overtime_minutes_today: int | None = Field(
        default=None,
        description="Переработка сегодня: минуты после окончания номинальной смены (work_start + 8 ч) до последнего выхода; null если выхода ещё не было",
    )

    @computed_field
    @property
    def position(self) -> str | None:
        return self.job_title
