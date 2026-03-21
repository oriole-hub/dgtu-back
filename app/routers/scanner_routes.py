from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db, require_roles
from app.core.errors import FORBIDDEN
from app.models import UserRole
from app.schemas.pass_schema import AccessEventOut, PresentInOfficeOut, ScanIn, ScanOut
from app.services.pass_service import (
    list_access_events,
    list_access_events_by_user,
    list_users_present_in_office,
    scan_pass,
)

scanner_router = APIRouter(prefix="/scanner", tags=["Сканер"])


@scanner_router.post(
    "/scan",
    response_model=ScanOut,
    summary="Сканировать QR",
    description=(
        "Проверяет QR и регистрирует событие входа/выхода в офисе сканирования. "
        "Доступно администратору и главному. Поле office_id — офис турникета; "
        "если не передано, используется office_id сканера (нужно явно указать, если у учётки нет офиса)."
    ),
)
async def scan_route(
    body: ScanIn,
    scanner: Annotated[dict, Depends(require_roles(UserRole.ADMIN, UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanOut:
    res = await scan_pass(db=db, data=body.model_dump(), scanner=scanner)
    return ScanOut(**res)


@scanner_router.get(
    "/events",
    response_model=list[AccessEventOut],
    summary="Журнал входов/выходов по офису",
    description="Показывает события только для офиса текущего администратора.",
)
async def events_route(
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AccessEventOut]:
    rows = await list_access_events(db=db, office_id=admin["office_id"])
    return [AccessEventOut(**row) for row in rows]


@scanner_router.get(
    "/events/users/{user_id}",
    response_model=list[AccessEventOut],
    summary="Журнал пользователя",
    description="Показывает входы/выходы выбранного пользователя в рамках офиса администратора.",
)
async def user_events_route(
    user_id: int,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AccessEventOut]:
    rows = await list_access_events_by_user(db=db, office_id=admin["office_id"], user_id=user_id)
    return [AccessEventOut(**row) for row in rows]


def _present_office_id(actor: dict, office_id: int | None) -> int:
    if actor["role"] == UserRole.ADMIN.value:
        oid = actor.get("office_id")
        if oid is None:
            raise HTTPException(status_code=400, detail={"code": "office_required", "msg": "Admin must be assigned to office"})
        if office_id is not None and office_id != oid:
            raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Admin can only view own office"})
        return oid
    if actor["role"] == UserRole.OFFICE_HEAD.value:
        if office_id is not None:
            return office_id
        head_oid = actor.get("office_id")
        if head_oid is None:
            raise HTTPException(
                status_code=400,
                detail={"code": "office_id_required", "msg": "Pass office_id query for this office head"},
            )
        return head_oid
    raise HTTPException(status_code=FORBIDDEN.status, detail={"code": FORBIDDEN.code, "msg": "Forbidden"})


@scanner_router.get(
    "/present",
    response_model=list[PresentInOfficeOut],
    summary="Кто сейчас в офисе",
    description=(
        "Пользователи, у которых последнее событие входа/выхода в выбранном офисе — вход (in). "
        "Администратор смотрит только свой офис (параметр office_id не нужен). "
        "Главный пользователь передаёт office_id или используется офис, привязанный к учётной записи."
    ),
)
async def present_in_office_route(
    actor: Annotated[dict, Depends(require_roles(UserRole.ADMIN, UserRole.OFFICE_HEAD))],
    db: Annotated[AsyncSession, Depends(get_db)],
    office_id: Annotated[int | None, Query(description="Офис (обязателен для главы без привязанного office_id)")] = None,
) -> list[PresentInOfficeOut]:
    oid = _present_office_id(actor, office_id)
    rows = await list_users_present_in_office(db=db, office_id=oid)
    return [PresentInOfficeOut(**row) for row in rows]

