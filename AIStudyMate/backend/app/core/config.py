from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI StudyMate"
    app_env: Literal["development", "testing", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    database_url: str = "postgresql+asyncpg://ai_studymate:ai_studymate_dev_password@localhost:5433/ai_studymate"

    jwt_secret_key: str = "replace-with-a-long-random-secret"
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)
    jwt_issuer: str = "ai-studymate"
    jwt_audience: str = "ai-studymate-api"

    gemini_api_key: str = ""
    chroma_persist_dir: Path = Path("./chroma_data")
    document_storage_dir: Path = Path("./document_storage")
    max_pdf_size_mb: int = Field(default=20, gt=0, le=100)
    cors_origins: list[AnyHttpUrl] = [AnyHttpUrl("http://localhost:5173")]

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env == "production" and (
            self.jwt_secret_key == "replace-with-a-long-random-secret"
            or len(self.jwt_secret_key) < 32
        ):
            raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

