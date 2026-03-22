from __future__ import annotations

import argparse
import asyncio
import os
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.security import hash_pwd


OFFICE_ID = 2

DEFAULT_LOGIN = "office2_present"
DEFAULT_PASSWORD = "SeedOffice2!"
DEFAULT_EMAIL = "office2_present@seed.local"


def _pick_ten_pair_days(*, today: date) -> list[date]:
    first = today.replace(day=1)
    prev: list[date] = []
    d = today - timedelta(days=1)
    while d >= first and len(prev) < 10:
        prev.append(d)
        d -= timedelta(days=1)
    prev.sort()
    if len(prev) >= 10:
        return prev[-10:]
    if len(prev) >= 1:
        return prev
    raise SystemExit(
        "В текущем месяце нет ни одного дня до «сегодня» — запустите скрипт не в первый день месяца "
        "или временно смените дату."
    )


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _build_today_shift_with_breaks_and_overtime(
    *,
    day: date,
    work_start: time,
    tz: ZoneInfo,
    late_minutes: int = 22,
    break1_minutes: int = 15,
    break2_minutes: int = 12,
    overtime_after_nominal: timedelta = timedelta(hours=1, minutes=30),
) -> tuple[list[tuple[datetime, str]], dict[str, object]]:
    """
    Один рабочий день: опоздание на late_minutes, два перекура (out/in), уход с переработкой
    относительно номинального окончания (8 ч после первого входа).
    """
    ws = datetime.combine(day, work_start, tzinfo=tz)
    first_in = ws + timedelta(minutes=late_minutes)

    b1_out = first_in + timedelta(hours=2)
    b1_in = b1_out + timedelta(minutes=break1_minutes)

    b2_out = b1_in + timedelta(hours=2, minutes=30)
    b2_in = b2_out + timedelta(minutes=break2_minutes)

    nominal_end = first_in + timedelta(hours=8)
    last_out = nominal_end + overtime_after_nominal

    local_seq = [
        (first_in, "in"),
        (b1_out, "out"),
        (b1_in, "in"),
        (b2_out, "out"),
        (b2_in, "in"),
        (last_out, "out"),
    ]
    meta: dict[str, object] = {
        "first_in_local": first_in,
        "last_out_local": last_out,
        "late_minutes": late_minutes,
        "break1_minutes": break1_minutes,
        "break2_minutes": break2_minutes,
        "overtime": overtime_after_nominal,
        "nominal_end_local": nominal_end,
    }
    return [(_to_utc(ts), d) for ts, d in local_seq], meta


async def _run(*, login: str, email: str, password: str) -> None:
    engine = create_async_engine(settings.sqlalchemy_dsn)
    pwd_hash = hash_pwd(pwd=password)

    async with engine.begin() as conn:
        r = await conn.execute(text("select 1 from offices where id = :oid"), {"oid": OFFICE_ID})
        if r.scalar_one_or_none() is None:
            raise SystemExit(f"Office id={OFFICE_ID} does not exist")

        r = await conn.execute(
            text("select work_start_time, iana_timezone from offices where id = :oid"),
            {"oid": OFFICE_ID},
        )
        sched = r.mappings().first()
        if sched is None:
            raise SystemExit(f"Office id={OFFICE_ID} has no schedule row")
        work_start: time = sched["work_start_time"] or time(9, 0)
        tz_name: str = sched["iana_timezone"] or "Europe/Moscow"
        tz = ZoneInfo(tz_name)

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

        today = date.today()
        pair_days = _pick_ten_pair_days(today=today)

        events: list[tuple[datetime, str]] = []

        for idx, d in enumerate(pair_days):
            ws = datetime.combine(d, work_start, tzinfo=tz)
            if idx % 2 == 0:
                in_local = ws + timedelta(hours=1, minutes=25)
            else:
                in_local = ws - timedelta(minutes=40)
            out_local = in_local + timedelta(hours=7, minutes=45)
            events.append((_to_utc(in_local), "in"))
            events.append((_to_utc(out_local), "out"))

        today_shift, today_meta = _build_today_shift_with_breaks_and_overtime(
            day=today,
            work_start=work_start,
            tz=tz,
            late_minutes=22,
            break1_minutes=15,
            break2_minutes=12,
            overtime_after_nominal=timedelta(hours=1, minutes=30),
        )
        events.extend(today_shift)

        events.sort(key=lambda x: x[0])

        for ts, direction in events:
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

    await engine.dispose()

    late_days = sum(1 for i in range(len(pair_days)) if i % 2 == 0)
    on_time_days = len(pair_days) - late_days

    if len(pair_days) < 10:
        print(
            f"Примечание: в месяце только {len(pair_days)} дней до «сегодня» — "
            f"создано столько же пар вход/выход (не 10).",
            flush=True,
        )

    fi = today_meta["first_in_local"]
    lo = today_meta["last_out_local"]
    ne = today_meta["nominal_end_local"]
    ot = today_meta["overtime"]
    assert isinstance(fi, datetime) and isinstance(lo, datetime) and isinstance(ne, datetime)
    assert isinstance(ot, timedelta)
    ot_h = int(ot.total_seconds() // 3600)
    ot_m = int((ot.total_seconds() % 3600) // 60)

    print()
    print("========== УЧЁТНАЯ ЗАПИСЬ ==========")
    print(f"  Логин:    {login}")
    print(f"  Пароль:   {password}")
    print(f"  Email:    {email}")
    print("====================================")
    print()
    print("========== СЕГОДНЯ (демо для календаря / API) ==========")
    print(f"  Локальная дата офиса: {today.isoformat()} ({tz_name})")
    print(f"  Начало рабочего дня (офис): {work_start.isoformat(timespec='minutes')}")
    print(f"  Приход (первый вход):     {fi.strftime('%H:%M')} — опоздание {today_meta['late_minutes']} мин → статус дня: late")
    print(f"  Перекур 1:                  {today_meta['break1_minutes']} мин (выход/вход в событиях)")
    print(f"  Перекур 2:                  {today_meta['break2_minutes']} мин")
    print(f"  Номинальный конец (8 ч):  {ne.strftime('%H:%M')}")
    print(f"  Уход:                       {lo.strftime('%H:%M')} — переработка {ot_h} ч {ot_m} мин после номинала")
    print("========================================================")
    print()
    print(
        f"OK: user id={user_id}, office_id={OFFICE_ID}, "
        f"дней с парами вход/выход (без сегодня): {len(pair_days)} "
        f"(~{late_days} с опозданием, ~{on_time_days} без), "
        f"+ сегодня: полный день с 2 перекурами и переработкой. "
        f"Таймзона офиса: {tz_name}, work_start: {work_start.isoformat(timespec='minutes')}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Seed user in office 2 with monthly attendance pattern")
    p.add_argument("--login", default=os.getenv("SEED_LOGIN", DEFAULT_LOGIN))
    p.add_argument("--email", default=os.getenv("SEED_EMAIL", DEFAULT_EMAIL))
    p.add_argument("--password", default=os.getenv("SEED_PASSWORD", DEFAULT_PASSWORD))
    args = p.parse_args()
    asyncio.run(_run(login=args.login, email=args.email, password=args.password))


if __name__ == "__main__":
    main()
