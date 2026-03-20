from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.core import Base


class PassStatus(str, PyEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


class QrPass(Base):
    __tablename__ = "qr_passes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    qr_token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    status: Mapped[PassStatus] = mapped_column(
        Enum(PassStatus, name="pass_status"),
        default=PassStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
