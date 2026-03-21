from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db, require_roles
from app.models import UserRole
from app.schemas.office_schema import OfficeCreateIn, OfficeOut
from app.services.auth_service import create_office, list_offices

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
    description="Возвращает все офисы. Доступно главному пользователю и администраторам.",
)
async def list_offices_route(
    user: Annotated[dict, Depends(require_roles(UserRole.OFFICE_HEAD, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OfficeOut]:
    rows = await list_offices(db=db)
    if user["role"] == UserRole.ADMIN.value:
        rows = [row for row in rows if row["id"] == user["office_id"]]
    return [OfficeOut(**row) for row in rows]
