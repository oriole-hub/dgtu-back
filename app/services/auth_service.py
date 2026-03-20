from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import INVALID_CREDENTIALS, USER_EXISTS
from app.core.security import hash_pwd, make_jwt, verify_pwd


async def register_user(*, db: AsyncSession, data: dict) -> dict:
    full_name = data["full_name"].strip()
    email = data["email"].strip().lower()
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    has_user = await db.execute(
        text("select 1 from users where login = :login or email = :email"),
        {"login": login, "email": email},
    )
    is_taken = has_user.scalar_one_or_none()
    if is_taken:
        raise HTTPException(status_code=USER_EXISTS.status, detail={"code": USER_EXISTS.code, "msg": USER_EXISTS.msg})
    pwd_hash = hash_pwd(pwd=pwd)
    row_res = await db.execute(
        text(
            """
            insert into users(full_name, email, login, pwd_hash)
            values(:full_name, :email, :login, :pwd_hash)
            returning id, full_name, email, login, created_at
            """
        ),
        {"full_name": full_name, "email": email, "login": login, "pwd_hash": pwd_hash},
    )
    await db.commit()
    row = row_res.mappings().first()
    return dict(row)


async def login_user(*, db: AsyncSession, data: dict) -> dict:
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    row_res = await db.execute(
        text("select id, login, pwd_hash from users where login = :login"),
        {"login": login},
    )
    row = row_res.mappings().first()
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
