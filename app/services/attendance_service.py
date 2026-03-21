from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import OFFICE_NOT_FOUND, OFFICE_REQUIRED


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _work_start_from_row(row_time: time | None) -> time:
    if row_time is None:
        return time(9, 0)
    return row_time


async def _load_office_schedule(*, db: AsyncSession, office_id: int | None) -> tuple[time, str]:
    if office_id is None:
        raise HTTPException(
            status_code=OFFICE_REQUIRED.status,
            detail={"code": OFFICE_REQUIRED.code, "msg": OFFICE_REQUIRED.msg},
        )
    res = await db.execute(
        text(
            """
            select work_start_time, iana_timezone
            from offices
            where id = :oid
            """
        ),
        {"oid": office_id},
    )
    row = res.mappings().first()
    if row is None:
        raise HTTPException(
            status_code=OFFICE_NOT_FOUND.status,
            detail={"code": OFFICE_NOT_FOUND.code, "msg": OFFICE_NOT_FOUND.msg},
        )
    tz_name = row["iana_timezone"]
    try:
        ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=500,
            detail={"code": "invalid_office_timezone", "msg": f"Office timezone is invalid: {tz_name}"},
        )
    return _work_start_from_row(row["work_start_time"]), tz_name


async def _fetch_first_in_by_local_date(
    *, db: AsyncSession, user_id: int, tz_name: str
) -> list[dict]:
    res = await db.execute(
        text(
            """
            select
              (e.created_at at time zone :tz)::date as local_date,
              min(e.created_at) as first_in
            from access_events e
            where e.user_id = :uid and e.direction = 'in'
            group by 1
            order by 1
            """
        ),
        {"uid": user_id, "tz": tz_name},
    )
    return [dict(r) for r in res.mappings().all()]


async def get_attendance_for_user(
    *,
    db: AsyncSession,
    user_id: int,
    office_id: int | None,
    date_from: date,
    date_to: date,
) -> dict:
    if date_to < date_from:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_range", "msg": "date_to must be >= date_from"},
        )
    work_start, tz_name = await _load_office_schedule(db=db, office_id=office_id)
    rows = await _fetch_first_in_by_local_date(db=db, user_id=user_id, tz_name=tz_name)
    by_first_in, punctual_days_total = _build_day_status_map(rows, tz_name=tz_name, work_start=work_start)

    days_out: list[dict] = []
    cur = date_from
    while cur <= date_to:
        if cur in by_first_in:
            st, fi = by_first_in[cur]
            days_out.append({"date": cur, "status": st, "first_in_at": fi})
        else:
            days_out.append({"date": cur, "status": "absent", "first_in_at": None})
        cur += timedelta(days=1)

    return {
        "iana_timezone": tz_name,
        "work_start_time": work_start.isoformat(timespec="seconds"),
        "punctual_days_total": punctual_days_total,
        "days": days_out,
    }


def _build_day_status_map(
    rows: list[dict], *, tz_name: str, work_start: time
) -> tuple[dict[date, tuple[str, datetime | None]], int]:
    """Returns map date -> (status, first_in_utc) and punctual day count (all history)."""
    tz = ZoneInfo(tz_name)
    by_date: dict[date, tuple[str, datetime | None]] = {}
    punctual = 0
    for r in rows:
        d = r["local_date"]
        first_in = r["first_in"]
        if isinstance(first_in, datetime):
            fi = _as_utc(first_in)
        else:
            fi = datetime.fromtimestamp(float(first_in), tz=UTC)
        local_t = fi.astimezone(tz).time()
        if local_t <= work_start:
            st = "on_time"
            punctual += 1
        else:
            st = "late"
        by_date[d] = (st, fi)
    return by_date, punctual
