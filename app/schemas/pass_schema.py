from datetime import datetime
from pydantic import BaseModel, Field

class PassOut(BaseModel):
    qr_token: str
    status: str
    expires_at: datetime
    office_id: int


class ScanIn(BaseModel):
    qr_token: str
    office_id: int | None = Field(
        default=None,
        description="Офис, в котором выполняется сканирование. Если не указан — берётся office_id сканера.",
    )


class ScanOut(BaseModel):
    ok: bool
    status: str
    msg: str
    direction: str
    user_id: int
    user_full_name: str
    office_id: int


class AccessEventOut(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    office_id: int
    direction: str
    scanned_by_user_id: int
    created_at: datetime


class PresentInOfficeOut(BaseModel):
    user_id: int
    user_full_name: str
    last_event_at: datetime

#1