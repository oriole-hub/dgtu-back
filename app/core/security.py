import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt

from app.core.config import settings


def hash_pwd(*, pwd: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_pwd(*, pwd: str, pwd_hash: str) -> bool:
    try:
        salt_hex, digest_hex = pwd_hash.split(":")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", pwd.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(digest.hex(), digest_hex)


def make_jwt(*, sub: str, login: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "login": login,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def read_jwt(*, token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])


def make_qr_token() -> str:
    return uuid4().hex + uuid4().hex
