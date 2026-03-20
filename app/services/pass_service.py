from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import HTTPException

from app.core.config import settings
from app.core.errors import PASS_ALREADY_USED, PASS_EXPIRED, PASS_INVALID, PASS_REVOKED
from app.core.security import make_qr_token


async def generate_pass(*, db: asyncpg.Pool, user: dict) -> dict:
    uid = user["id"]
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.qr_minutes)
    token = make_qr_token()
    async with db.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "update qr_passes set status = 'revoked', revoked_at = now() where user_id = $1 and status = 'active'",
                uid,
            )
            row = await conn.fetchrow(
                """
                insert into qr_passes(user_id, qr_token, status, expires_at)
                values($1, $2, 'active', $3)
                returning qr_token, status, expires_at
                """,
                uid,
                token,
                exp,
            )
    return dict(row)


async def revoke_active_pass(*, db: asyncpg.Pool, user: dict) -> dict:
    uid = user["id"]
    row = await db.fetchrow(
        """
        update qr_passes
        set status = 'revoked', revoked_at = now()
        where user_id = $1 and status = 'active'
        returning qr_token, status, expires_at
        """,
        uid,
    )
    if row is None:
        return {"ok": True, "msg": "No active pass"}
    return {"ok": True, "msg": "Active pass revoked", "pass": dict(row)}


async def scan_pass(*, db: asyncpg.Pool, data: dict) -> dict:
    token = data["qr_token"]
    row = await db.fetchrow(
        "select id, user_id, status, expires_at from qr_passes where qr_token = $1",
        token,
    )
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
        await db.execute("update qr_passes set status = 'expired' where id = $1 and status = 'active'", row["id"])
        raise HTTPException(status_code=PASS_EXPIRED.status, detail={"code": PASS_EXPIRED.code, "msg": PASS_EXPIRED.msg})
    await db.execute("update qr_passes set status = 'used', used_at = now() where id = $1", row["id"])
    return {"ok": True, "status": "allowed", "msg": "Access granted"}
