from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import INVALID_TOKEN, UNAUTHORIZED
from app.core.security import read_jwt


bearer = HTTPBearer(auto_error=False)


async def get_db(req: Request):
    session_factory: async_sessionmaker[AsyncSession] = req.app.state.db
    async with session_factory() as session:
        yield session


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if creds is None:
        raise HTTPException(status_code=UNAUTHORIZED.status, detail={"code": UNAUTHORIZED.code, "msg": UNAUTHORIZED.msg})
    token = creds.credentials
    try:
        payload = read_jwt(token=token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=INVALID_TOKEN.status, detail={"code": INVALID_TOKEN.code, "msg": INVALID_TOKEN.msg})
    uid = payload.get("sub")
    if not uid:
        raise HTTPException(status_code=INVALID_TOKEN.status, detail={"code": INVALID_TOKEN.code, "msg": INVALID_TOKEN.msg})
    res = await db.execute(
        text("select id, full_name, email, login, created_at from users where id = :uid"),
        {"uid": int(uid)},
    )
    row = res.mappings().first()
    if row is None:
        raise HTTPException(status_code=UNAUTHORIZED.status, detail={"code": UNAUTHORIZED.code, "msg": UNAUTHORIZED.msg})
    return dict(row)
