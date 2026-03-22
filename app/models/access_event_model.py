from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.core import Base

class AccessDirection(str, PyEnum):
    IN = "in"
    OUT = "out"

class AccessEvent(Base):
    __tablename__ = "access_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    office_id: Mapped[int] = mapped_column(ForeignKey("offices.id", ondelete="CASCADE"), index=True, nullable=False)
    pass_id: Mapped[int] = mapped_column(ForeignKey("qr_passes.id", ondelete="SET NULL"), index=True, nullable=True)
    direction: Mapped[AccessDirection] = mapped_column(
        Enum(AccessDirection, name="access_direction", values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        index=True,
    )
    scanned_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
