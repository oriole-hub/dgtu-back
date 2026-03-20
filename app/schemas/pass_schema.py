from datetime import datetime

from pydantic import BaseModel


class PassOut(BaseModel):
    qr_token: str
    status: str
    expires_at: datetime


class ScanIn(BaseModel):
    qr_token: str


class ScanOut(BaseModel):
    ok: bool
    status: str
    msg: str
    direction: str
    user_id: int
    user_full_name: str


class AccessEventOut(BaseModel):
    id: int
    user_id: int
    user_full_name: str
    direction: str
    scanned_by_user_id: int
    created_at: datetime
