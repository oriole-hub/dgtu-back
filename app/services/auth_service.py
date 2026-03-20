from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ACCOUNT_EXPIRED, INVALID_CREDENTIALS, OFFICE_HEAD_EXISTS, USER_EXISTS
from app.core.security import hash_pwd, make_jwt, verify_pwd
from app.models import UserRole


def _normalize_create_data(data: dict) -> dict:
    return {
        "full_name": data["full_name"].strip(),
        "email": data["email"].strip().lower(),
        "login": data["login"].strip().lower(),
        "pwd": data["pwd"],
    }


async def _assert_login_or_email_not_taken(*, db: AsyncSession, login: str, email: str) -> None:
    has_user = await db.execute(
        text("select 1 from users where login = :login or email = :email"),
        {"login": login, "email": email},
    )
    if has_user.scalar_one_or_none():
        raise HTTPException(status_code=USER_EXISTS.status, detail={"code": USER_EXISTS.code, "msg": USER_EXISTS.msg})


def _user_select_sql() -> str:
    return """
        returning id, full_name, email, login, role, account_expires_at, pass_limit_total,
                  passes_created_count, created_by_user_id, created_at
    """


async def bootstrap_office_head(*, db: AsyncSession, data: dict) -> dict:
    data = _normalize_create_data(data)
    has_head = await db.execute(text("select 1 from users where role = 'office_head' limit 1"))
    if has_head.scalar_one_or_none():
        raise HTTPException(
            status_code=OFFICE_HEAD_EXISTS.status,
            detail={"code": OFFICE_HEAD_EXISTS.code, "msg": OFFICE_HEAD_EXISTS.msg},
        )
    await _assert_login_or_email_not_taken(db=db, login=data["login"], email=data["email"])
    pwd_hash = hash_pwd(pwd=data["pwd"])
    row_res = await db.execute(
        text(
            """
            insert into users(full_name, email, login, pwd_hash, role, passes_created_count)
            values(:full_name, :email, :login, :pwd_hash, 'office_head', 0)
            """
            + _user_select_sql()
        ),
        {"full_name": data["full_name"], "email": data["email"], "login": data["login"], "pwd_hash": pwd_hash},
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def create_admin_by_office_head(*, db: AsyncSession, data: dict, creator: dict) -> dict:
    data = _normalize_create_data(data)
    await _assert_login_or_email_not_taken(db=db, login=data["login"], email=data["email"])
    pwd_hash = hash_pwd(pwd=data["pwd"])
    row_res = await db.execute(
        text(
            """
            insert into users(full_name, email, login, pwd_hash, role, passes_created_count, created_by_user_id)
            values(:full_name, :email, :login, :pwd_hash, 'admin', 0, :creator_id)
            """
            + _user_select_sql()
        ),
        {
            "full_name": data["full_name"],
            "email": data["email"],
            "login": data["login"],
            "pwd_hash": pwd_hash,
            "creator_id": creator["id"],
        },
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def create_staff_by_admin(*, db: AsyncSession, data: dict, creator: dict) -> dict:
    data_core = _normalize_create_data(data)
    role = data["role"]
    if role not in (UserRole.EMPLOYEE.value, UserRole.GUEST.value):
        raise HTTPException(status_code=403, detail={"code": "invalid_role", "msg": "Admin can only create employee/guest"})
    await _assert_login_or_email_not_taken(db=db, login=data_core["login"], email=data_core["email"])
    pwd_hash = hash_pwd(pwd=data_core["pwd"])
    row_res = await db.execute(
        text(
            """
            insert into users(
                full_name, email, login, pwd_hash, role, account_expires_at,
                pass_limit_total, passes_created_count, created_by_user_id
            )
            values(
                :full_name, :email, :login, :pwd_hash, :role, :account_expires_at,
                :pass_limit_total, 0, :creator_id
            )
            """
            + _user_select_sql()
        ),
        {
            "full_name": data_core["full_name"],
            "email": data_core["email"],
            "login": data_core["login"],
            "pwd_hash": pwd_hash,
            "role": role,
            "account_expires_at": data.get("account_expires_at"),
            "pass_limit_total": data.get("pass_limit_total"),
            "creator_id": creator["id"],
        },
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def login_user(*, db: AsyncSession, data: dict) -> dict:
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    row_res = await db.execute(
        text("select id, login, pwd_hash, role, account_expires_at from users where login = :login"),
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
    if row["account_expires_at"] and row["account_expires_at"] < datetime.now(UTC):
        raise HTTPException(status_code=ACCOUNT_EXPIRED.status, detail={"code": ACCOUNT_EXPIRED.code, "msg": ACCOUNT_EXPIRED.msg})
    token = make_jwt(sub=str(row["id"]), login=row["login"], role=row["role"])
    return {"access_token": token, "token_type": "bearer"}


async def list_users(*, db: AsyncSession) -> list[dict]:
    res = await db.execute(
        text(
            """
            select id, full_name, email, login, role, account_expires_at, pass_limit_total,
                   passes_created_count, created_by_user_id, created_at
            from users
            order by id
            """
        )
    )
    return [dict(row) for row in res.mappings().all()]


async def get_user_by_id(*, db: AsyncSession, user_id: int) -> dict | None:
    res = await db.execute(
        text(
            """
            select id, full_name, email, login, role, account_expires_at, pass_limit_total,
                   passes_created_count, created_by_user_id, created_at
            from users where id = :uid
            """
        ),
        {"uid": user_id},
    )
    row = res.mappings().first()
    return dict(row) if row else None


async def update_user(*, db: AsyncSession, user_id: int, data: dict) -> dict | None:
    fields_map = {
        "full_name": "full_name",
        "email": "email",
        "role": "role",
        "account_expires_at": "account_expires_at",
        "pass_limit_total": "pass_limit_total",
    }
    payload = {}
    set_parts = []
    for key, col in fields_map.items():
        if key in data and data[key] is not None:
            value = data[key]
            if key == "email":
                value = value.strip().lower()
            payload[key] = value
            set_parts.append(f"{col} = :{key}")
    if not set_parts:
        res = await db.execute(
            text(
                """
                select id, full_name, email, login, role, account_expires_at, pass_limit_total,
                       passes_created_count, created_by_user_id, created_at
                from users where id = :uid
                """
            ),
            {"uid": user_id},
        )
        row = res.mappings().first()
        return dict(row) if row else None
    payload["uid"] = user_id
    res = await db.execute(
        text(
            f"""
            update users
            set {", ".join(set_parts)}
            where id = :uid
            returning id, full_name, email, login, role, account_expires_at, pass_limit_total,
                      passes_created_count, created_by_user_id, created_at
            """
        ),
        payload,
    )
    await db.commit()
    row = res.mappings().first()
    return dict(row) if row else None


async def delete_user(*, db: AsyncSession, user_id: int) -> bool:
    res = await db.execute(text("delete from users where id = :uid returning id"), {"uid": user_id})
    await db.commit()
    return res.scalar_one_or_none() is not None
