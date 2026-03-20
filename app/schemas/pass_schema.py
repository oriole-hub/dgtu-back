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
