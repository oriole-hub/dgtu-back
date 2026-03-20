from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.deps import get_current_user, get_db
from app.schemas.pass_schema import PassOut
from app.services.pass_service import generate_pass, revoke_active_pass

pass_router = APIRouter(prefix="/passes", tags=["passes"])


@pass_router.post("/generate", response_model=PassOut)
async def generate_pass_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PassOut:
    row = await generate_pass(db=db, user=user)
    return PassOut(**row)


@pass_router.post("/revoke")
async def revoke_pass_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await revoke_active_pass(db=db, user=user)
