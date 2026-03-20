from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_current_user, get_db, require_roles
from app.core.errors import FORBIDDEN, NOT_FOUND
from app.models import UserRole
from app.schemas.auth import AdminCreateIn, LoginIn, RegisterIn, StaffCreateIn, TokenOut, UserOut, UserUpdateIn
from app.services.auth_service import (
    bootstrap_office_head,
    create_admin_by_office_head,
    create_staff_by_admin,
    delete_user,
    get_user_by_id,
    list_users,
    login_user,
    update_user,
)
from app.services.pass_service import revoke_active_pass

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/bootstrap-office-head", response_model=UserOut)
async def bootstrap_office_head_route(
    body: RegisterIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await bootstrap_office_head(db=db, data=body.model_dump())
    return UserOut(**user)


@auth_router.post("/login", response_model=TokenOut)
async def login_route(
    body: LoginIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenOut:
    token = await login_user(db=db, data=body.model_dump())
    return TokenOut(**token)


@auth_router.get("/me", response_model=UserOut)
async def me_route(
    user: Annotated[dict, Depends(get_current_user)],
) -> UserOut:
    return UserOut(**user)


@auth_router.post("/admins", response_model=UserOut)
async def create_admin_route(
    body: AdminCreateIn,
    office_head: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await create_admin_by_office_head(db=db, data=body.model_dump(), creator=office_head)
    return UserOut(**user)


@auth_router.post("/staff", response_model=UserOut)
async def create_staff_route(
    body: StaffCreateIn,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    user = await create_staff_by_admin(db=db, data=body.model_dump(mode="json"), creator=admin)
    return UserOut(**user)


@auth_router.get("/users", response_model=list[UserOut])
async def list_users_route(
    _: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    rows = await list_users(db=db)
    return [UserOut(**row) for row in rows]


@auth_router.patch("/users/{user_id}", response_model=UserOut)
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


@auth_router.delete("/users/{user_id}")
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


@auth_router.patch("/workers/{user_id}", response_model=UserOut)
async def admin_update_worker_route(
    user_id: int,
    body: UserUpdateIn,
    _: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    target = await get_user_by_id(db=db, user_id=user_id)
    if not target:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    if target["role"] != UserRole.EMPLOYEE.value:
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin can update only employees"})
    incoming = body.model_dump(exclude_unset=True, mode="json")
    if "role" in incoming and incoming["role"] != UserRole.EMPLOYEE.value:
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin cannot change role"})
    updated = await update_user(db=db, user_id=user_id, data=incoming)
    return UserOut(**updated)


@auth_router.post("/logout")
async def logout_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await revoke_active_pass(db=db, user=user)

