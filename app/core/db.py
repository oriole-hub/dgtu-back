from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.core import Base
from app.models import pass_model, user_model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.sqlalchemy_dsn, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.state.db = session_factory
    try:
        yield
    finally:
        await engine.dispose()
