from functools import lru_cache
from pydantic import BaseSettings, field_validator
from typing import Any

class Settings(BaseSettings):
    app_name: str = "GEMCODEX API"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "gemcodex"
    postgres_user: str = "gemcodex"
    postgres_password: str = "gemcodex"
    redis_url: str | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    rate_limit_per_minute: int = 120

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @field_validator("cors_origins", mode="before")
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

@lru_cache(1)
def get_settings() -> Settings:
    return Settings()
