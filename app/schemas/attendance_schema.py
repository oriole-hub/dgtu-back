from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class AttendanceDayStatus(str, Enum):
    on_time = "on_time"
    late = "late"
    absent = "absent"


class AttendanceDayOut(BaseModel):
    date: date
    status: AttendanceDayStatus
    first_in_at: datetime | None = None


class AttendanceOut(BaseModel):
    iana_timezone: str
    work_start_time: str = Field(description="HH:MM:SS local office deadline")
    punctual_days_total: int
    days: list[AttendanceDayOut]
