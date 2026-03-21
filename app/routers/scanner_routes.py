from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db, require_roles
from app.models import UserRole
from app.schemas.pass_schema import AccessEventOut, ScanIn, ScanOut
from app.services.pass_service import list_access_events, list_access_events_by_user, scan_pass

scanner_router = APIRouter(prefix="/scanner", tags=["Сканер"])


@scanner_router.post(
    "/scan",
    response_model=ScanOut,
    summary="Сканировать QR",
    description="Проверяет QR и регистрирует событие входа/выхода.",
)
async def scan_route(
    body: ScanIn,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanOut:
    res = await scan_pass(db=db, data=body.model_dump(), scanner=admin)
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

