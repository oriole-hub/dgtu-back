from typing import Annotated

import asyncpg
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import INVALID_TOKEN, UNAUTHORIZED
from app.core.security import read_jwt


bearer = HTTPBearer(auto_error=False)


def get_db(req: Request) -> asyncpg.Pool:
    return req.app.state.db


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[asyncpg.Pool, Depends(get_db)],
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
    row = await db.fetchrow("select id, login, created_at from users where id = $1", int(uid))
    if row is None:
        raise HTTPException(status_code=UNAUTHORIZED.status, detail={"code": UNAUTHORIZED.code, "msg": UNAUTHORIZED.msg})
    return dict(row)
