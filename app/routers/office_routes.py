from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db, require_roles
from app.core.errors import FORBIDDEN, NOT_FOUND
from app.models import UserRole
from app.schemas.office_schema import OfficeCreateIn, OfficeOut, OfficeUpdateIn
from app.services.auth_service import create_office, get_office_by_id, list_offices, update_office

office_router = APIRouter(prefix="/offices", tags=["Офисы"])


@office_router.post(
    "",
    response_model=OfficeOut,
    summary="Создать офис",
    description="Главный пользователь создает новый офис.",
)
async def create_office_route(
    body: OfficeCreateIn,
    office_head: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OfficeOut:
    row = await create_office(db=db, data=body.model_dump(), creator_id=office_head["id"])
    return OfficeOut(**row)


@office_router.get(
    "",
    response_model=list[OfficeOut],
    summary="Список офисов",
    description="Главный видит все офисы; администратор — только свой.",
)
async def list_offices_route(
    user: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OfficeOut]:
    rows = await list_offices(db=db)
    if user["role"] == UserRole.ADMIN.value:
        rows = [row for row in rows if row["id"] == user["office_id"]]
    return [OfficeOut(**row) for row in rows]


@office_router.get(
    "/{office_id}",
    response_model=OfficeOut,
    summary="Офис по id",
    description="Главный — любой офис; администратор — только свой.",
)
async def get_office_route(
    office_id: int,
    user: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OfficeOut:
    row = await get_office_by_id(db=db, office_id=office_id)
    if not row:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    if user["role"] == UserRole.ADMIN.value and row["id"] != user.get("office_id"):
        raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin can view only own office"})
    return OfficeOut(**row)


@office_router.patch(
    "/{office_id}",
    response_model=OfficeOut,
    summary="Изменить настройки офиса (расписание)",
    description="Главный и администратор могут менять расписание своего офиса (админ — только своего).",
)
async def patch_office_route(
    office_id: int,
    body: OfficeUpdateIn,
    user: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OfficeOut:
    if user["role"] == UserRole.OFFICE_HEAD.value:
        if user.get("office_id") != office_id:
            raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Office head can update only own office"})
    elif user["role"] == UserRole.ADMIN.value:
        if user.get("office_id") != office_id:
            raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin can update only own office"})
    updated = await update_office(db=db, office_id=office_id, data=body.model_dump(exclude_unset=True, mode="json"))
    if not updated:
        raise HTTPException(status_code=NOT_FOUND.status, detail={"code": NOT_FOUND.code, "msg": NOT_FOUND.msg})
    return OfficeOut(**updated)
