import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "dgtu-back")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

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


settings = Settings()
