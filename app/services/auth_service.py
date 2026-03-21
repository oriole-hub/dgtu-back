from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ACCOUNT_EXPIRED, INVALID_CREDENTIALS, OFFICE_INACTIVE, OFFICE_NOT_FOUND, OFFICE_HEAD_EXISTS, USER_EXISTS
from app.core.security import hash_pwd, make_jwt, verify_pwd
from app.models import UserRole


def _normalize_create_data(data: dict) -> dict:
    normalized = {
        "full_name": data["full_name"].strip(),
        "email": data["email"].strip().lower(),
        "login": data["login"].strip().lower(),
        "pwd": data["pwd"],
    }
    for key in (
        "office_id",
        "role",
        "account_expires_at",
        "pass_limit_total",
        "office_name",
        "office_address",
        "office_city",
        "office_is_active",
    ):
        if key in data:
            normalized[key] = data[key]
    return normalized


async def _assert_login_or_email_not_taken(*, db: AsyncSession, login: str, email: str) -> None:
    has_user = await db.execute(
        text("select 1 from users where login = :login or email = :email"),
        {"login": login, "email": email},
    )
    if has_user.scalar_one_or_none():
        raise HTTPException(status_code=USER_EXISTS.status, detail={"code": USER_EXISTS.code, "msg": USER_EXISTS.msg})


async def _assert_login_or_email_not_taken_except(
    *, db: AsyncSession, login: str, email: str, except_user_id: int
) -> None:
    has_user = await db.execute(
        text(
            """
            select 1 from users
            where id != :uid and (login = :login or email = :email)
            """
        ),
        {"uid": except_user_id, "login": login, "email": email},
    )
    if has_user.scalar_one_or_none():
        raise HTTPException(status_code=USER_EXISTS.status, detail={"code": USER_EXISTS.code, "msg": USER_EXISTS.msg})


def _user_select_sql() -> str:
    return """
        returning id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                  passes_created_count, referral_count, created_by_user_id, created_at
    """


async def _assert_office_exists(*, db: AsyncSession, office_id: int | None) -> None:
    if office_id is None:
        return
    res = await db.execute(text("select 1 from offices where id = :oid"), {"oid": office_id})
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=OFFICE_NOT_FOUND.status, detail={"code": OFFICE_NOT_FOUND.code, "msg": OFFICE_NOT_FOUND.msg})


async def _assert_office_active(*, db: AsyncSession, office_id: int) -> None:
    res = await db.execute(text("select is_active from offices where id = :oid"), {"oid": office_id})
    row = res.mappings().first()
    if row is None:
        raise HTTPException(status_code=OFFICE_NOT_FOUND.status, detail={"code": OFFICE_NOT_FOUND.code, "msg": OFFICE_NOT_FOUND.msg})
    if not row["is_active"]:
        raise HTTPException(status_code=OFFICE_INACTIVE.status, detail={"code": OFFICE_INACTIVE.code, "msg": OFFICE_INACTIVE.msg})


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
    created_head = await db.execute(
        text(
            """
            insert into users(full_name, email, login, pwd_hash, role, office_id, passes_created_count)
            values(:full_name, :email, :login, :pwd_hash, 'office_head', null, 0)
            returning id
            """
        ),
        {"full_name": data["full_name"], "email": data["email"], "login": data["login"], "pwd_hash": pwd_hash},
    )
    head_id = created_head.scalar_one()

    created_office = await db.execute(
        text(
            """
            insert into offices(name, address, city, is_active, created_by_user_id)
            values(:name, :address, :city, :is_active, :creator_id)
            returning id
            """
        ),
        {
            "name": data["office_name"].strip(),
            "address": data["office_address"].strip(),
            "city": data["office_city"].strip(),
            "is_active": data.get("office_is_active", True),
            "creator_id": head_id,
        },
    )
    office_id = created_office.scalar_one()

    row_res = await db.execute(
        text(
            """
            update users
            set office_id = :office_id
            where id = :uid
            """
            + _user_select_sql()
        ),
        {"uid": head_id, "office_id": office_id},
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def create_admin_by_office_head(*, db: AsyncSession, data: dict, creator: dict) -> dict:
    data = _normalize_create_data(data)
    await _assert_login_or_email_not_taken(db=db, login=data["login"], email=data["email"])
    pwd_hash = hash_pwd(pwd=data["pwd"])
    office_id = data.get("office_id")
    await _assert_office_exists(db=db, office_id=office_id)
    row_res = await db.execute(
        text(
            """
            insert into users(full_name, email, login, pwd_hash, role, office_id, passes_created_count, created_by_user_id)
            values(:full_name, :email, :login, :pwd_hash, 'admin', :office_id, 0, :creator_id)
            """
            + _user_select_sql()
        ),
        {
            "full_name": data["full_name"],
            "email": data["email"],
            "login": data["login"],
            "pwd_hash": pwd_hash,
            "office_id": office_id,
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
    office_id = creator["office_id"]
    if office_id is None:
        raise HTTPException(status_code=400, detail={"code": "office_required", "msg": "Admin must be assigned to office"})
    if data.get("office_id") != office_id:
        raise HTTPException(status_code=403, detail={"code": "office_scope_violation", "msg": "Admin can create users only in own office"})
    await _assert_office_active(db=db, office_id=office_id)
    await _assert_login_or_email_not_taken(db=db, login=data_core["login"], email=data_core["email"])
    pwd_hash = hash_pwd(pwd=data_core["pwd"])
    row_res = await db.execute(
        text(
            """
            insert into users(
                full_name, email, login, pwd_hash, role, account_expires_at,
                pass_limit_total, office_id, passes_created_count, created_by_user_id
            )
            values(
                :full_name, :email, :login, :pwd_hash, :role, :account_expires_at,
                :pass_limit_total, :office_id, 0, :creator_id
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
            "office_id": office_id,
            "creator_id": creator["id"],
        },
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def login_user(*, db: AsyncSession, data: dict) -> dict:
    login = data["login"].strip().lower()
    pwd = data["pwd"]
    row_res = await db.execute(
        text("select id, login, pwd_hash, role, office_id, account_expires_at from users where login = :login"),
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
            select id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                   passes_created_count, referral_count, created_by_user_id, created_at
            from users
            order by id
            """
        )
    )
    return [dict(row) for row in res.mappings().all()]


async def list_users_by_office_id(*, db: AsyncSession, office_id: int) -> list[dict]:
    res = await db.execute(
        text(
            """
            select id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                   passes_created_count, referral_count, created_by_user_id, created_at
            from users
            where office_id = :oid
            order by id
            """
        ),
        {"oid": office_id},
    )
    return [dict(row) for row in res.mappings().all()]


async def get_user_by_id(*, db: AsyncSession, user_id: int) -> dict | None:
    res = await db.execute(
        text(
            """
            select id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                   passes_created_count, referral_count, created_by_user_id, created_at
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
        "office_id": "office_id",
        "account_expires_at": "account_expires_at",
        "pass_limit_total": "pass_limit_total",
    }
    payload = {}
    set_parts = []
    if "referral_count" in data:
        payload["referral_count"] = int(data["referral_count"])
        set_parts.append("referral_count = :referral_count")
    for key, col in fields_map.items():
        if key in data and data[key] is not None:
            value = data[key]
            if key == "email":
                value = value.strip().lower()
            if key == "office_id":
                await _assert_office_exists(db=db, office_id=value)
            payload[key] = value
            set_parts.append(f"{col} = :{key}")
    if not set_parts:
        res = await db.execute(
            text(
                """
                select id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                       passes_created_count, referral_count, created_by_user_id, created_at
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
                      office_id, passes_created_count, referral_count, created_by_user_id, created_at
            """
        ),
        payload,
    )
    await db.commit()
    row = res.mappings().first()
    return dict(row) if row else None


async def update_guest_me(*, db: AsyncSession, user_id: int, data: dict) -> dict | None:
    login = data["login"].strip().lower()
    email = data["email"].strip().lower()
    await _assert_login_or_email_not_taken_except(db=db, login=login, email=email, except_user_id=user_id)
    pwd_hash = None
    if data.get("pwd"):
        pwd_hash = hash_pwd(pwd=data["pwd"])
    if pwd_hash:
        res = await db.execute(
            text(
                """
                update users
                set full_name = :full_name, email = :email, login = :login, pwd_hash = :pwd_hash
                where id = :uid
                returning id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                          passes_created_count, referral_count, created_by_user_id, created_at
                """
            ),
            {
                "uid": user_id,
                "full_name": data["full_name"].strip(),
                "email": email,
                "login": login,
                "pwd_hash": pwd_hash,
            },
        )
    else:
        res = await db.execute(
            text(
                """
                update users
                set full_name = :full_name, email = :email, login = :login
                where id = :uid
                returning id, full_name, email, login, role, office_id, account_expires_at, pass_limit_total,
                          passes_created_count, referral_count, created_by_user_id, created_at
                """
            ),
            {
                "uid": user_id,
                "full_name": data["full_name"].strip(),
                "email": email,
                "login": login,
            },
        )
    await db.commit()
    row = res.mappings().first()
    return dict(row) if row else None


async def delete_user(*, db: AsyncSession, user_id: int) -> bool:
    res = await db.execute(text("delete from users where id = :uid returning id"), {"uid": user_id})
    await db.commit()
    return res.scalar_one_or_none() is not None


async def update_office(*, db: AsyncSession, office_id: int, data: dict) -> dict | None:
    fields = []
    payload: dict = {"oid": office_id}
    if "work_start_time" in data and data["work_start_time"] is not None:
        fields.append("work_start_time = :work_start_time")
        payload["work_start_time"] = data["work_start_time"]
    if "iana_timezone" in data and data["iana_timezone"] is not None:
        tz_name = str(data["iana_timezone"]).strip()
        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            raise HTTPException(
                status_code=400,
                detail={"code": "invalid_timezone", "msg": f"Unknown IANA timezone: {tz_name}"},
            )
        fields.append("iana_timezone = :iana_timezone")
        payload["iana_timezone"] = tz_name
    if not fields:
        res = await db.execute(
            text(
                """
                select id, name, address, city, is_active, work_start_time, iana_timezone,
                       created_by_user_id, created_at
                from offices where id = :oid
                """
            ),
            {"oid": office_id},
        )
        row = res.mappings().first()
        return dict(row) if row else None
    res = await db.execute(
        text(
            f"""
            update offices
            set {", ".join(fields)}
            where id = :oid
            returning id, name, address, city, is_active, work_start_time, iana_timezone,
                      created_by_user_id, created_at
            """
        ),
        payload,
    )
    await db.commit()
    row = res.mappings().first()
    return dict(row) if row else None


async def create_office(*, db: AsyncSession, data: dict, creator_id: int) -> dict:
    row_res = await db.execute(
        text(
            """
            insert into offices(name, address, city, is_active, created_by_user_id)
            values(:name, :address, :city, :is_active, :creator_id)
            returning id, name, address, city, is_active, work_start_time, iana_timezone,
                      created_by_user_id, created_at
            """
        ),
        {
            "name": data["name"].strip(),
            "address": data["address"].strip(),
            "city": data["city"].strip(),
            "is_active": data["is_active"],
            "creator_id": creator_id,
        },
    )
    await db.commit()
    return dict(row_res.mappings().first())


async def list_offices(*, db: AsyncSession) -> list[dict]:
    res = await db.execute(
        text(
            """
            select id, name, address, city, is_active, work_start_time, iana_timezone,
                   created_by_user_id, created_at
            from offices order by id
            """
        )
    )
    return [dict(row) for row in res.mappings().all()]
