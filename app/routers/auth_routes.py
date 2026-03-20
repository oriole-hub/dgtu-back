from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from app.application.deps import get_current_user, get_db
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import login_user, register_user
from app.services.pass_service import revoke_active_pass

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserOut)
async def register_route(
    body: RegisterIn,
    db: Annotated[asyncpg.Pool, Depends(get_db)],
) -> UserOut:
    user = await register_user(db=db, data=body.model_dump())
    return UserOut(**user)


@auth_router.post("/login", response_model=TokenOut)
async def login_route(
    body: LoginIn,
    db: Annotated[asyncpg.Pool, Depends(get_db)],
) -> TokenOut:
    token = await login_user(db=db, data=body.model_dump())
    return TokenOut(**token)


@auth_router.get("/me", response_model=UserOut)
async def me_route(
    user: Annotated[dict, Depends(get_current_user)],
) -> UserOut:
    return UserOut(**user)


@auth_router.post("/logout")
async def logout_route(
    user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[asyncpg.Pool, Depends(get_db)],
) -> dict:
    return await revoke_active_pass(db=db, user=user)

