from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.core import Base
from app.models import access_event_model, pass_model, user_model  # noqa: F401


async def _ensure_rbac_columns(conn) -> None:
    await conn.execute(text("alter table users add column if not exists role user_role"))
    await conn.execute(text("update users set role = 'employee' where role is null"))
    await conn.execute(text("alter table users alter column role set default 'employee'"))
    await conn.execute(text("alter table users alter column role set not null"))
    await conn.execute(text("alter table users add column if not exists account_expires_at timestamptz"))
    await conn.execute(text("alter table users add column if not exists pass_limit_total integer"))
    await conn.execute(text("alter table users add column if not exists passes_created_count integer"))
    await conn.execute(text("update users set passes_created_count = 0 where passes_created_count is null"))
    await conn.execute(text("alter table users alter column passes_created_count set default 0"))
    await conn.execute(text("alter table users alter column passes_created_count set not null"))
    await conn.execute(text("alter table users add column if not exists created_by_user_id integer"))
    await conn.execute(
        text(
            """
            do $$
            begin
                alter table users
                add constraint users_created_by_user_id_fkey
                foreign key (created_by_user_id) references users(id) on delete set null;
            exception
                when duplicate_object then null;
            end
            $$;
            """
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.sqlalchemy_dsn, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_rbac_columns(conn)
    app.state.db = session_factory
    try:
        yield
    finally:
        await engine.dispose()
