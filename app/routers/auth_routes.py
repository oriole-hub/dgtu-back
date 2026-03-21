from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_current_user, get_db, require_roles
from app.core.errors import FORBIDDEN, NOT_FOUND
from app.models import UserRole
from app.schemas.attendance_schema import AttendanceOut
from app.schemas.auth import (
    AdminCreateIn,
    BootstrapOfficeHeadIn,
    GuestSelfUpdateIn,
    LoginIn,
    StaffCreateIn,
    TokenOut,
    UserOut,
    UserUpdateIn,
)
from app.services.attendance_service import get_attendance_for_user
from app.services.auth_service import (
    bootstrap_office_head,
    create_admin_by_office_head,
    create_staff_by_admin,
    delete_user,
    get_user_by_id,
    list_users,
    list_users_by_office_id,
    login_user,
    update_guest_me,
    update_user,
)
from app.services.pass_service import revoke_active_pass

auth_router = APIRouter(prefix="/auth", tags=["Аутентификация и пользователи"])


@auth_router.post(
    "/bootstrap-office-head",
    response_model=UserOut,
    summary="Создать главного пользователя",
    description="Создает первого и единственного главного пользователя системы.",
)
async def bootstrap_office_head_route(
    body: BootstrapOfficeHeadIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await bootstrap_office_head(db=db, data=body.model_dump())
    return UserOut(**user)


@auth_router.post("/register", response_model=UserOut, include_in_schema=False)
async def register_legacy_route(
    body: BootstrapOfficeHeadIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Совместимость со старым фронтом: то же, что bootstrap-office-head."""
    user = await bootstrap_office_head(db=db, data=body.model_dump())
    return UserOut(**user)


@auth_router.post("/login", response_model=TokenOut, summary="Вход", description="Аутентификация пользователя.")
async def login_route(
    body: LoginIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    token = await login_user(db=db, data=body.model_dump())
    return TokenOut(**token)


@auth_router.get("/me", response_model=UserOut, summary="Текущий пользователь")
async def me_route(
    user: Annotated[dict, Depends(get_current_user)],
) -> UserOut:
    return UserOut(**user)


@auth_router.patch("/me", response_model=UserOut, summary="Изменить профиль (гость)")
async def patch_me_guest_route(
    body: GuestSelfUpdateIn,
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    if user["role"] != UserRole.GUEST.value:
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Only guests can use this endpoint"})
    updated = await update_guest_me(db=db, user_id=user["id"], data=body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return UserOut(**updated)


@auth_router.delete("/me", summary="Удалить свой аккаунт (гость)")
async def delete_me_guest_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if user["role"] != UserRole.GUEST.value:
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Only guests can delete own account"})
    ok = await delete_user(db=db, user_id=user["id"])
    if not ok:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return {"ok": True}


@auth_router.get(
    "/me/attendance",
    response_model=AttendanceOut,
    summary="Календарь посещаемости (себя)",
    description="Статусы дней и общий счётчик дней без опозданий для текущего пользователя.",
)
async def me_attendance_route(
    user: Annotated[dict, Depends(require_roles(UserRole.EMPLOYEE, UserRole.GUEST, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> AttendanceOut:
    raw = await get_attendance_for_user(
        db=db,
        user_id=user["id"],
        office_id=user.get("office_id"),
        date_from=date_from,
        date_to=date_to,
    )
    return AttendanceOut(**raw)


@auth_router.get(
    "/users/{user_id}/attendance",
    response_model=AttendanceOut,
    summary="Календарь посещаемости пользователя",
    description="Главный пользователь — любой сотрудник; администратор — только свой офис.",
)
async def user_attendance_route(
    user_id: int,
    actor: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
) -> AttendanceOut:
    target = await get_user_by_id(db=db, user_id=user_id)
    if not target:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    if actor["role"] == UserRole.ADMIN.value:
        if target.get("office_id") != actor.get("office_id"):
            raise HTTPException(
                status_code=FORBIDDEN.status,
                detail={"code": FORBIDDEN.code, "msg": "Admin can view attendance only for users in own office"},
            )
    raw = await get_attendance_for_user(
        db=db,
        user_id=user_id,
        office_id=target.get("office_id"),
        date_from=date_from,
        date_to=date_to,
    )
    return AttendanceOut(**raw)


@auth_router.post(
    "/admins",
    response_model=UserOut,
    summary="Создать администратора",
    description="Главный пользователь создает администратора и привязывает его к офису.",
)
async def create_admin_route(
    body: AdminCreateIn,
    office_head: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await create_admin_by_office_head(db=db, data=body.model_dump(), creator=office_head)
    return UserOut(**user)


@auth_router.post(
    "/staff",
    response_model=UserOut,
    summary="Создать сотрудника или гостя",
    description="Администратор может создавать только сотрудников/гостей в своем офисе.",
)
async def create_staff_route(
    body: StaffCreateIn,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await create_staff_by_admin(db=db, data=body.model_dump(), creator=admin)
    return UserOut(**user)


@auth_router.get("/users", response_model=list[UserOut], summary="Список пользователей")
async def list_users_route(
    _: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    rows = await list_users(db=db)
    return [UserOut(**row) for row in rows]


@auth_router.get(
    "/office-users",
    response_model=list[UserOut],
    summary="Пользователи офиса (админ)",
    description="Список учётных записей в офисе текущего администратора.",
)
async def list_office_users_route(
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    oid = admin.get("office_id")
    if oid is None:
        raise HTTPException(status_code=400, detail={"code": "office_required", "msg": "Admin must be assigned to office"})
    rows = await list_users_by_office_id(db=db, office_id=oid)
    return [UserOut(**row) for row in rows]


@auth_router.patch("/users/{user_id}", response_model=UserOut, summary="Изменить пользователя (главный)")
async def office_head_update_user_route(
    user_id: int,
    body: UserUpdateIn,
    _: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    updated = await update_user(db=db, user_id=user_id, data=body.model_dump(exclude_unset=True, mode="json"))
    if not updated:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return UserOut(**updated)


@auth_router.delete("/users/{user_id}", summary="Удалить пользователя (главный)")
async def office_head_delete_user_route(
    user_id: int,
    current_user: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if current_user["id"] == user_id:
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Office head cannot delete self"})
    ok = await delete_user(db=db, user_id=user_id)
    if not ok:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return {"ok": True}


@auth_router.patch(
    "/workers/{user_id}",
    response_model=UserOut,
    summary="Изменить сотрудника или гостя (админ)",
    description="Администратор может изменять сотрудников и гостей своего офиса, в том числе referral_count.",
)
@auth_router.patch(
    "/office-users/{user_id}",
    response_model=UserOut,
    summary="Изменить пользователя офиса (админ)",
    description="Алиас для PATCH /auth/workers/{user_id}.",
    include_in_schema=False,
)
async def admin_update_worker_route(
    user_id: int,
    body: UserUpdateIn,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    target = await get_user_by_id(db=db, user_id=user_id)
    if not target:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    if target["role"] not in (UserRole.EMPLOYEE.value, UserRole.GUEST.value):
        raise HTTPException(
            status_code=FORBIDDEN.status,
            detail={"code": FORBIDDEN.code, "msg": "Admin can update only employees and guests"},
        )
    if target["office_id"] != admin["office_id"]:
        raise HTTPException(
            status_code=FORBIDDEN.status,
            detail={"code": FORBIDDEN.code, "msg": "Admin can update only users in own office"},
        )
    incoming = body.model_dump(exclude_unset=True, mode="json")
    if "office_id" in incoming:
        incoming.pop("office_id")
    if "role" in incoming:
        allowed = {UserRole.EMPLOYEE.value, UserRole.GUEST.value}
        if incoming["role"] not in allowed or incoming["role"] != target["role"]:
            raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin cannot change role"})
    updated = await update_user(db=db, user_id=user_id, data=incoming)
    if not updated:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return UserOut(**updated)


@auth_router.post("/logout", summary="Выход")
async def logout_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await revoke_active_pass(db=db, user=user)

