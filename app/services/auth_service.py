import asyncpg
from fastapi import HTTPException

from app.core.errors import INVALID_CREDENTIALS, USER_EXISTS
from app.core.security import hash_pwd, make_jwt, verify_pwd


async def register_user(*, db: asyncpg.Pool, data: dict) -> dict:
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    has_user = await db.fetchval("select 1 from users where login = $1", login)
    if has_user:
        raise HTTPException(status_code=USER_EXISTS.status, detail={"code": USER_EXISTS.code, "msg": USER_EXISTS.msg})
    pwd_hash = hash_pwd(pwd=pwd)
    row = await db.fetchrow(
        "insert into users(login, pwd_hash) values($1, $2) returning id, login, created_at",
        login,
        pwd_hash,
    )
    return dict(row)


async def login_user(*, db: asyncpg.Pool, data: dict) -> dict:
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    row = await db.fetchrow("select id, login, pwd_hash from users where login = $1", login)
    if row is None:
        raise HTTPException(
            status_code=INVALID_CREDENTIALS.status,
            detail={"code": INVALID_CREDENTIALS.code, "msg": INVALID_CREDENTIALS.msg},
        )
    if not verify_pwd(pwd=pwd, pwd_hash=row["pwd_hash"]):
        raise HTTPException(
            status_code=INVALID_CREDENTIALS.status,
            detail={"code": INVALID_CREDENTIALS.code, "msg": INVALID_CREDENTIALS.msg},
        )
    token = make_jwt(sub=str(row["id"]), login=row["login"])
    return {"access_token": token, "token_type": "bearer"}
