"""Batch-compute last access times and today's smoke-break window from access_events."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _last_completed_break_today(events: list[dict]) -> tuple[datetime | None, datetime | None, int | None]:
    """
    events: rows sorted by created_at with keys direction ('in'|'out'), created_at (datetime).
    First IN starts the workday; subsequent OUT then IN pairs are breaks. Returns the last completed pair.
    """
    first_in_idx: int | None = None
    for i, e in enumerate(events):
        if e["direction"] == "in":
            first_in_idx = i
            break
    if first_in_idx is None:
        return None, None, None

    pending_out: datetime | None = None
    last_pair: tuple[datetime | None, datetime | None] = (None, None)

    for e in events[first_in_idx + 1 :]:
        d = e["direction"]
        ts = e["created_at"]
        if isinstance(ts, datetime):
            ts = _as_utc(ts)
        else:
            ts = datetime.fromtimestamp(float(ts), tz=UTC)

        if d == "out":
            pending_out = ts
        elif d == "in" and pending_out is not None:
            last_pair = (pending_out, ts)
            pending_out = None

    out_at, in_at = last_pair
    if out_at is None or in_at is None:
        return None, None, None
    sec = int((in_at - out_at).total_seconds())
    return out_at, in_at, sec if sec >= 0 else None


async def enrich_users_with_access_presence(*, db: AsyncSession, users: list[dict]) -> list[dict]:
    """Adds last_in_at, last_out_at, last_break_out_at, last_break_in_at, last_break_duration_seconds."""
    if not users:
        return users

    uids = [u["id"] for u in users]
    uid_set = set(uids)

    last_res = await db.execute(
        text(
            """
            select user_id,
                   max(created_at) filter (where direction = 'in') as last_in_at,
                   max(created_at) filter (where direction = 'out') as last_out_at
            from access_events
            where user_id = any(:uids)
            group by user_id
            """
        ),
        {"uids": uids},
    )
    last_by_uid: dict[int, dict[str, Any]] = {}
    for row in last_res.mappings().all():
        last_by_uid[int(row["user_id"])] = dict(row)

    today_res = await db.execute(
        text(
            """
            select e.user_id, e.direction::text as direction, e.created_at
            from access_events e
            inner join offices o on o.id = e.office_id
            where e.user_id = any(:uids)
              and (e.created_at at time zone o.iana_timezone)::date
                  = (current_timestamp at time zone o.iana_timezone)::date
            order by e.user_id, e.created_at
            """
        ),
        {"uids": uids},
    )
    events_by_uid: dict[int, list[dict]] = defaultdict(list)
    for row in today_res.mappings().all():
        uid = int(row["user_id"])
        if uid in uid_set:
            events_by_uid[uid].append({"direction": row["direction"], "created_at": row["created_at"]})

    out: list[dict] = []
    for u in users:
        row = dict(u)
        lid = u["id"]
        lr = last_by_uid.get(lid)
        row["last_in_at"] = lr.get("last_in_at") if lr else None
        row["last_out_at"] = lr.get("last_out_at") if lr else None

        evs = events_by_uid.get(lid, [])
        bout, bin_, bdur = _last_completed_break_today(evs)
        row["last_break_out_at"] = bout
        row["last_break_in_at"] = bin_
        row["last_break_duration_seconds"] = bdur
        out.append(row)

    return out
