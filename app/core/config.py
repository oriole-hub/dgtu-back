import os
from dataclasses import dataclass


def _parse_cors_origins(raw: str) -> tuple[list[str], bool]:
    """
    Returns (origins, allow_credentials).
    If raw is "*", credentials must be False (browser requirement).
    """
    raw = raw.strip()
    if raw == "*":
        return ["*"], False
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins:
        return ["*"], False
    return origins, True


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "dgtu-back")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    # Comma-separated origins, or "*" for any (dev only; no cookies with *)
    cors_origins_raw: str = os.getenv("CORS_ORIGINS", "*")

    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "dgtu")
    db_user: str = os.getenv("DB_USER", "tapok")
    db_pass: str = os.getenv("DB_PASS", "chinazes778")

    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-prod")
    jwt_alg: str = os.getenv("JWT_ALG", "HS256")
    jwt_minutes: int = int(os.getenv("JWT_MINUTES", str(60 * 24)))
    qr_minutes: int = int(os.getenv("QR_MINUTES", "5"))

    @property
    def sqlalchemy_dsn(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def cors_origins(self) -> list[str]:
        return _parse_cors_origins(self.cors_origins_raw)[0]

    @property
    def cors_allow_credentials(self) -> bool:
        return _parse_cors_origins(self.cors_origins_raw)[1]


settings = Settings()
