"""
Создаёт пользователя в офисе id=2 с историей 10 входов и 10 выходов (20 событий)
и финальным входом (21-е событие), чтобы пользователь считался «сейчас в офисе».

Запуск из корня репозитория:
  python -m app.scripts.seed_office2_present_user

В Docker:
  docker compose exec api python -m app.scripts.seed_office2_present_user

Переменные окружения (опционально):
  SEED_LOGIN, SEED_EMAIL, SEED_PASSWORD — учётка создаваемого пользователя
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.security import hash_pwd


OFFICE_ID = 2


async def _run(*, login: str, email: str, password: str) -> None:
    engine = create_async_engine(settings.sqlalchemy_dsn)
    pwd_hash = hash_pwd(pwd=password)

    async with engine.begin() as conn:
        r = await conn.execute(text("select 1 from offices where id = :oid"), {"oid": OFFICE_ID})
        if r.scalar_one_or_none() is None:
            raise SystemExit(f"Office id={OFFICE_ID} does not exist")

        r = await conn.execute(
            text("select id from users where office_id = :oid order by id limit 1"),
            {"oid": OFFICE_ID},
        )
        scanner_id = r.scalar_one_or_none()
        if scanner_id is None:
            raise SystemExit(f"No users in office {OFFICE_ID} to use as scanned_by_user_id; create one first")

        r = await conn.execute(
            text("select 1 from users where login = :login or email = :email"),
            {"login": login, "email": email},
        )
        if r.scalar_one_or_none():
            raise SystemExit(f"User with login={login!r} or email={email!r} already exists")

        r = await conn.execute(
            text(
                """
                insert into users(
                    full_name, email, login, pwd_hash, role, office_id,
                    passes_created_count, referral_count
                )
                values (
                    :full_name, :email, :login, :pwd_hash, 'employee', :office_id, 0, 0
                )
                returning id
                """
            ),
            {
                "full_name": f"Seed user office {OFFICE_ID}",
                "email": email,
                "login": login,
                "pwd_hash": pwd_hash,
                "office_id": OFFICE_ID,
            },
        )
        user_id = r.scalar_one()

        base_time = datetime.now(UTC) - timedelta(hours=24)

        for i in range(20):
            direction = "in" if i % 2 == 0 else "out"
            ts = base_time + timedelta(minutes=i * 3)
            await conn.execute(
                text(
                    """
                    insert into access_events(
                        user_id, office_id, pass_id, direction, scanned_by_user_id, created_at
                    )
                    values (
                        :uid, :oid, null, cast(:dir as access_direction), :scanner, :ts
                    )
                    """
                ),
                {"uid": user_id, "oid": OFFICE_ID, "dir": direction, "scanner": scanner_id, "ts": ts},
            )

        final_in_ts = base_time + timedelta(minutes=20 * 3 + 1)
        await conn.execute(
            text(
                """
                insert into access_events(
                    user_id, office_id, pass_id, direction, scanned_by_user_id, created_at
                )
                values (
                    :uid, :oid, null, cast(:dir as access_direction), :scanner, :ts
                )
                """
            ),
            {"uid": user_id, "oid": OFFICE_ID, "dir": "in", "scanner": scanner_id, "ts": final_in_ts},
        )

    await engine.dispose()
    print(
        f"OK: user id={user_id} office_id={OFFICE_ID} "
        f"login={login!r} — 10 входов + 10 выходов + финальный вход (в офисе сейчас)"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Seed user in office 2 with access history")
    p.add_argument("--login", default=os.getenv("SEED_LOGIN", "office2_present"))
    p.add_argument("--email", default=os.getenv("SEED_EMAIL", "office2_present@seed.local"))
    p.add_argument("--password", default=os.getenv("SEED_PASSWORD", "SeedOffice2!"))
    args = p.parse_args()
    asyncio.run(_run(login=args.login, email=args.email, password=args.password))


if __name__ == "__main__":
    main()
