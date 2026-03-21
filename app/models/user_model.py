from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.core import Base


class UserRole(str, PyEnum):
    OFFICE_HEAD = "office_head"
    ADMIN = "admin"
    EMPLOYEE = "employee"
    GUEST = "guest"


_LEGACY_ROLE_LABELS = {
    "OFFICE_HEAD": UserRole.OFFICE_HEAD.value,
    "ADMIN": UserRole.ADMIN.value,
    "EMPLOYEE": UserRole.EMPLOYEE.value,
    "GUEST": UserRole.GUEST.value,
}


def normalize_db_role(raw) -> str:
    """Приводит значение role из БД/драйвера к строке, совпадающей с UserRole.value."""
    if raw is None:
        return ""
    if isinstance(raw, UserRole):
        return raw.value
    if isinstance(raw, PyEnum):
        ev = raw.value
        if isinstance(ev, str):
            s = ev.strip().strip('"').lower()
            if s in {r.value for r in UserRole}:
                return s
        s = str(ev).strip().strip('"')
        low = s.lower()
        if low in {r.value for r in UserRole}:
            return low
        return _LEGACY_ROLE_LABELS.get(s.upper(), low)
    v = getattr(raw, "value", raw)
    if isinstance(v, bytes):
        s = v.decode("utf-8", errors="replace").strip().strip('"')
    else:
        s = str(v).strip().strip('"')
    low = s.lower()
    if low in {r.value for r in UserRole}:
        return low
    return _LEGACY_ROLE_LABELS.get(s.upper(), low)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    login: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    pwd_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda enum: [item.value for item in enum]),
        default=UserRole.EMPLOYEE,
        nullable=False,
        index=True,
    )
    account_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pass_limit_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passes_created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    office_id: Mapped[int | None] = mapped_column(ForeignKey("offices.id", ondelete="SET NULL"), nullable=True, index=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_creation_purpose: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
