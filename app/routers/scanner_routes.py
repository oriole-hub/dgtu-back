from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_db
from app.schemas.pass_schema import ScanIn, ScanOut
from app.services.pass_service import scan_pass

scanner_router = APIRouter(prefix="/scanner", tags=["scanner"])


@scanner_router.post("/scan", response_model=ScanOut)
async def scan_route(
    body: ScanIn,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanOut:
    res = await scan_pass(db=db, data=body.model_dump())
    return ScanOut(**res)

