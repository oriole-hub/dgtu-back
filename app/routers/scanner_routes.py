from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db, require_roles
from app.models import UserRole
from app.schemas.pass_schema import AccessEventOut, ScanIn, ScanOut
from app.services.pass_service import list_access_events, scan_pass

scanner_router = APIRouter(prefix="/scanner", tags=["scanner"])


@scanner_router.post("/scan", response_model=ScanOut)
async def scan_route(
    body: ScanIn,
    admin: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanOut:
    res = await scan_pass(db=db, data=body.model_dump(), scanner=admin)
    return ScanOut(**res)


@scanner_router.get("/events", response_model=list[AccessEventOut])
async def events_route(
    _: Annotated[dict, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AccessEventOut]:
    rows = await list_access_events(db=db)
    return [AccessEventOut(**row) for row in rows]

