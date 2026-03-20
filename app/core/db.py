from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from app.core.config import settings


DDL = """
create table if not exists users (
  id bigserial primary key,
  login text not null unique,
  pwd_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists qr_passes (
  id bigserial primary key,
  user_id bigint not null references users(id) on delete cascade,
  qr_token text not null unique,
  status text not null check (status in ('active', 'used', 'expired', 'revoked')),
  expires_at timestamptz not null,
  used_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_qr_passes_user_status on qr_passes(user_id, status);
create index if not exists idx_qr_passes_token on qr_passes(qr_token);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(dsn=settings.db_dsn, min_size=2, max_size=10)
    async with pool.acquire() as conn:
        await conn.execute(DDL)
    app.state.db = pool
    try:
        yield
    finally:
        await pool.close()
