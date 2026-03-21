from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import (
    OFFICE_NOT_FOUND,
    OFFICE_REQUIRED,
    OFFICE_SCOPE_VIOLATION,
    PASS_ALREADY_USED,
    PASS_EXPIRED,
    PASS_INVALID,
    PASS_LIMIT_REACHED,
    PASS_REVOKED,
)
from app.core.security import make_qr_token
from app.models import AccessDirection, UserRole


async def generate_pass(*, db: AsyncSession, user: dict) -> dict:
    if user["role"] not in (UserRole.EMPLOYEE.value, UserRole.GUEST.value):
        raise HTTPException(status_code=403, detail={"code": "forbidden", "msg": "Only employees/guests can create QR"})
    if user["pass_limit_total"] is not None and user["passes_created_count"] >= user["pass_limit_total"]:
        raise HTTPException(
            status_code=PASS_LIMIT_REACHED.status,
            detail={"code": PASS_LIMIT_REACHED.code, "msg": PASS_LIMIT_REACHED.msg},
        )
    if user["office_id"] is None:
        raise HTTPException(status_code=OFFICE_REQUIRED.status, detail={"code": OFFICE_REQUIRED.code, "msg": OFFICE_REQUIRED.msg})
    uid = user["id"]
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=5)
    token = make_qr_token()
    await db.execute(
        text("update qr_passes set status = 'revoked', revoked_at = now() where user_id = :uid and status = 'active'"),
        {"uid": uid},
    )
    row_res = await db.execute(
        text(
            """
            insert into qr_passes(user_id, office_id, qr_token, status, expires_at)
            values(:uid, :office_id, :token, 'active', :exp)
            returning qr_token, status, expires_at, office_id
            """
        ),
        {"uid": uid, "office_id": user["office_id"], "token": token, "exp": exp},
    )
    await db.execute(
        text("update users set passes_created_count = passes_created_count + 1 where id = :uid"),
        {"uid": uid},
    )
    await db.commit()
    row = row_res.mappings().first()
    return dict(row)


async def revoke_active_pass(*, db: AsyncSession, user: dict) -> dict:
    uid = user["id"]
    row_res = await db.execute(
        text(
            """
            update qr_passes
            set status = 'revoked', revoked_at = now()
            where user_id = :uid and status = 'active'
            returning qr_token, status, expires_at
            """
        ),
        {"uid": uid},
    )
    await db.commit()
    row = row_res.mappings().first()
    if row is None:
        return {"ok": True, "msg": "No active pass"}
    return {"ok": True, "msg": "Active pass revoked", "pass": dict(row)}


async def scan_pass(*, db: AsyncSession, data: dict, scanner: dict) -> dict:
    token = data["qr_token"]
    row_res = await db.execute(
        text(
            """
            select p.id, p.user_id, p.office_id, p.status, p.expires_at,
                   u.full_name as user_full_name, u.office_id as user_office_id
            from qr_passes p
            join users u on u.id = p.user_id
            where p.qr_token = :token
            """
        ),
        {"token": token},
    )
    row = row_res.mappings().first()
    if row is None:
        raise HTTPException(status_code=PASS_INVALID.status, detail={"code": PASS_INVALID.code, "msg": PASS_INVALID.msg})
    if row["status"] == "used":
        raise HTTPException(
            status_code=PASS_ALREADY_USED.status,
            detail={"code": PASS_ALREADY_USED.code, "msg": PASS_ALREADY_USED.msg},
        )
    if row["status"] == "revoked":
        raise HTTPException(status_code=PASS_REVOKED.status, detail={"code": PASS_REVOKED.code, "msg": PASS_REVOKED.msg})
    if row["status"] == "expired":
        raise HTTPException(status_code=PASS_EXPIRED.status, detail={"code": PASS_EXPIRED.code, "msg": PASS_EXPIRED.msg})
    if scanner.get("office_id") is None:
        raise HTTPException(status_code=OFFICE_REQUIRED.status, detail={"code": OFFICE_REQUIRED.code, "msg": OFFICE_REQUIRED.msg})
    if row["office_id"] != scanner["office_id"] or row["office_id"] != row["user_office_id"]:
        raise HTTPException(
            status_code=OFFICE_SCOPE_VIOLATION.status,
            detail={"code": OFFICE_SCOPE_VIOLATION.code, "msg": OFFICE_SCOPE_VIOLATION.msg},
        )
    is_exp = row["expires_at"] < datetime.now(UTC)
    if is_exp:
        await db.execute(
            text("update qr_passes set status = 'expired' where id = :pid and status = 'active'"),
            {"pid": row["id"]},
        )
        await db.commit()
        raise HTTPException(status_code=PASS_EXPIRED.status, detail={"code": PASS_EXPIRED.code, "msg": PASS_EXPIRED.msg})
    await db.execute(
        text("update qr_passes set status = 'used', used_at = now() where id = :pid"),
        {"pid": row["id"]},
    )
    last_event = await db.execute(
        text("select direction from access_events where user_id = :uid order by id desc limit 1"),
        {"uid": row["user_id"]},
    )
    prev = last_event.scalar_one_or_none()
    direction = AccessDirection.OUT.value if prev == AccessDirection.IN.value else AccessDirection.IN.value
    await db.execute(
        text(
            """
            insert into access_events(user_id, office_id, pass_id, direction, scanned_by_user_id)
            values(:user_id, :office_id, :pass_id, :direction, :scanner_id)
            """
        ),
        {
            "user_id": row["user_id"],
            "office_id": row["office_id"],
            "pass_id": row["id"],
            "direction": direction,
            "scanner_id": scanner["id"],
        },
    )
    await db.commit()
    return {
        "ok": True,
        "status": "allowed",
        "msg": "Access granted",
        "direction": direction,
        "user_id": row["user_id"],
        "user_full_name": row["user_full_name"],
        "office_id": row["office_id"],
    }


async def list_access_events(*, db: AsyncSession, office_id: int, limit: int = 200) -> list[dict]:
    res = await db.execute(
        text(
            """
            select e.id, e.user_id, u.full_name as user_full_name, e.office_id,
                   e.direction, e.scanned_by_user_id, e.created_at
            from access_events e
            join users u on u.id = e.user_id
            where e.office_id = :office_id
            order by e.id desc
            limit :limit
            """
        ),
        {"office_id": office_id, "limit": limit},
    )
    return [dict(row) for row in res.mappings().all()]


async def list_access_events_by_user(*, db: AsyncSession, office_id: int, user_id: int, limit: int = 200) -> list[dict]:
    res = await db.execute(
        text(
            """
            select e.id, e.user_id, u.full_name as user_full_name, e.office_id,
                   e.direction, e.scanned_by_user_id, e.created_at
            from access_events e
            join users u on u.id = e.user_id
            where e.office_id = :office_id and e.user_id = :user_id
            order by e.id desc
            limit :limit
            """
        ),
        {"office_id": office_id, "user_id": user_id, "limit": limit},
    )
    return [dict(row) for row in res.mappings().all()]


async def list_users_present_in_office(*, db: AsyncSession, office_id: int) -> list[dict]:
    exists = await db.execute(text("select 1 from offices where id = :oid"), {"oid": office_id})
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=OFFICE_NOT_FOUND.status, detail={"code": OFFICE_NOT_FOUND.code, "msg": OFFICE_NOT_FOUND.msg})
    res = await db.execute(
        text(
            """
            with last_ev as (
                select distinct on (e.user_id)
                    e.user_id,
                    e.direction,
                    e.created_at as last_event_at
                from access_events e
                where e.office_id = :office_id
                order by e.user_id, e.id desc
            )
            select le.user_id, u.full_name as user_full_name, le.last_event_at
            from last_ev le
            join users u on u.id = le.user_id
            where le.direction = 'in'
            order by u.full_name
            """
        ),
        {"office_id": office_id},
    )
    return [dict(row) for row in res.mappings().all()]
