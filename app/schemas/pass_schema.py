from datetime import datetime

from pydantic import BaseModel


class PassOut(BaseModel):
    qr_token: str
    status: str
    expires_at: datetime
    office_id: int


class ScanIn(BaseModel):
    qr_token: str


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
