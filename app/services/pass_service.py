from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import PASS_ALREADY_USED, PASS_EXPIRED, PASS_INVALID, PASS_REVOKED
from app.core.security import make_qr_token


async def generate_pass(*, db: AsyncSession, user: dict) -> dict:
    uid = user["id"]
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.qr_minutes)
    token = make_qr_token()
    await db.execute(
        text("update qr_passes set status = 'revoked', revoked_at = now() where user_id = :uid and status = 'active'"),
        {"uid": uid},
    )
    row_res = await db.execute(
        text(
            """
            insert into qr_passes(user_id, qr_token, status, expires_at)
            values(:uid, :token, 'active', :exp)
            returning qr_token, status, expires_at
            """
        ),
        {"uid": uid, "token": token, "exp": exp},
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


async def scan_pass(*, db: AsyncSession, data: dict) -> dict:
    token = data["qr_token"]
    row_res = await db.execute(
        text("select id, user_id, status, expires_at from qr_passes where qr_token = :token"),
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
    await db.commit()
    return {"ok": True, "status": "allowed", "msg": "Access granted"}
