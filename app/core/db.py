from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.core import Base
from app.models import access_event_model, office_model, pass_model, user_model  # noqa: F401


async def _ensure_enum_value(conn, enum_type: str, enum_value: str) -> None:
    await conn.execute(
        text(
            f"""
            do $$
            begin
                if not exists (
                    select 1
                    from pg_enum e
                    join pg_type t on t.oid = e.enumtypid
                    where t.typname = '{enum_type}' and e.enumlabel = '{enum_value}'
                ) then
                    execute 'alter type {enum_type} add value ''{enum_value}''';
                end if;
            end
            $$;
            """
        )
    )


async def _ensure_legacy_enum_compatibility(conn) -> None:
    # user_role: support both legacy uppercase labels and lowercase labels used by app.
    for value in ("office_head", "admin", "employee", "guest"):
        await _ensure_enum_value(conn, "user_role", value)
    # pass_status: same approach to avoid runtime 500 on old schemas.
    for value in ("active", "used", "expired", "revoked"):
        await _ensure_enum_value(conn, "pass_status", value)
    for value in ("in", "out"):
        await _ensure_enum_value(conn, "access_direction", value)

    # PostgreSQL requires a commit before newly added enum values can be used.
    await conn.commit()

    # Normalize stored values to lowercase where legacy uppercase labels exist.
    await conn.execute(text("update users set role = 'office_head' where role::text = 'OFFICE_HEAD'"))
    await conn.execute(text("update users set role = 'admin' where role::text = 'ADMIN'"))
    await conn.execute(text("update users set role = 'employee' where role::text = 'EMPLOYEE'"))
    await conn.execute(text("update users set role = 'guest' where role::text = 'GUEST'"))
    await conn.execute(text("update qr_passes set status = 'active' where status::text = 'ACTIVE'"))
    await conn.execute(text("update qr_passes set status = 'used' where status::text = 'USED'"))
    await conn.execute(text("update qr_passes set status = 'expired' where status::text = 'EXPIRED'"))
    await conn.execute(text("update qr_passes set status = 'revoked' where status::text = 'REVOKED'"))
    await conn.execute(text("update access_events set direction = 'in' where direction::text = 'IN'"))
    await conn.execute(text("update access_events set direction = 'out' where direction::text = 'OUT'"))


async def _ensure_rbac_columns(conn) -> None:
    await _ensure_legacy_enum_compatibility(conn)
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
    await conn.execute(text("alter table users add column if not exists office_id integer"))
    await conn.execute(text("alter table offices add column if not exists address varchar(255)"))
    await conn.execute(text("alter table offices add column if not exists city varchar(128)"))
    await conn.execute(text("alter table offices add column if not exists is_active boolean"))
    await conn.execute(text("update offices set address = 'Не указан' where address is null"))
    await conn.execute(text("update offices set city = 'Не указан' where city is null"))
    await conn.execute(text("update offices set is_active = true where is_active is null"))
    await conn.execute(text("alter table offices alter column address set not null"))
    await conn.execute(text("alter table offices alter column city set not null"))
    await conn.execute(text("alter table offices alter column is_active set default true"))
    await conn.execute(text("alter table offices alter column is_active set not null"))
    await conn.execute(text("create index if not exists ix_offices_city on offices(city)"))
    await conn.execute(text("create index if not exists ix_offices_is_active on offices(is_active)"))
    await conn.execute(text("alter table qr_passes add column if not exists office_id integer"))
    await conn.execute(text("alter table access_events add column if not exists office_id integer"))
    await conn.execute(
        text(
            """
            update qr_passes p
            set office_id = u.office_id
            from users u
            where p.user_id = u.id and p.office_id is null
            """
        )
    )
    await conn.execute(
        text(
            """
            update access_events e
            set office_id = u.office_id
            from users u
            where e.user_id = u.id and e.office_id is null
            """
        )
    )
    await conn.execute(
        text(
            """
            do $$
            begin
                alter table users
                add constraint users_office_id_fkey
                foreign key (office_id) references offices(id) on delete set null;
            exception
                when duplicate_object then null;
            end
            $$;
            """
        )
    )
    await conn.execute(
        text(
            """
            do $$
            begin
                alter table qr_passes
                add constraint qr_passes_office_id_fkey
                foreign key (office_id) references offices(id) on delete cascade;
            exception
                when duplicate_object then null;
            end
            $$;
            """
        )
    )
    await conn.execute(
        text(
            """
            do $$
            begin
                alter table access_events
                add constraint access_events_office_id_fkey
                foreign key (office_id) references offices(id) on delete cascade;
            exception
                when duplicate_object then null;
            end
            $$;
            """
        )
    )
    await conn.execute(text("create index if not exists ix_users_office_id on users(office_id)"))
    await conn.execute(text("create index if not exists ix_qr_passes_office_id on qr_passes(office_id)"))
    await conn.execute(text("create index if not exists ix_access_events_office_id on access_events(office_id)"))
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
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_rbac_columns(conn)
        await conn.commit()
    app.state.db = session_factory
    try:
        yield
    finally:
        await engine.dispose()
