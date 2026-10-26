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
    gemini_chat_model: str = "gemini-2.5-flash-lite"
    gemini_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    gemini_max_retries: int = Field(default=3, ge=1, le=10)
    gemini_max_output_tokens: int = Field(default=1024, ge=64, le=8192)
    chroma_persist_dir: Path = Path("./chroma_data")
    embedding_provider: Literal["local", "gemini"] = "local"
    local_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    gemini_embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int | None = Field(default=768, gt=0, le=3072)
    embedding_batch_size: int = Field(default=32, gt=0, le=100)
    embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    embedding_max_retries: int = Field(default=3, ge=1, le=10)
    rag_chunk_size: int = Field(default=500, ge=50, le=2000)
    rag_chunk_overlap: int = Field(default=75, ge=0, le=500)
    rag_collection_prefix: str = Field(default="ai_studymate_chunks_v1", pattern=r"^[a-zA-Z0-9_-]+$")
    rag_max_top_k: int = Field(default=20, ge=1, le=100)
    chat_rag_top_k: int = Field(default=5, ge=1, le=20)
    chat_history_messages: int = Field(default=8, ge=0, le=50)
    chat_history_max_chars: int = Field(default=12000, ge=0, le=100000)
    chat_context_max_chars: int = Field(default=24000, ge=1000, le=200000)
    agent_max_steps: int = Field(default=8, ge=4, le=50)
    agent_max_tool_calls: int = Field(default=4, ge=1, le=20)
    agent_timeout_seconds: float = Field(default=60.0, gt=0, le=300)
    agent_history_messages: int = Field(default=8, ge=0, le=50)
    agent_context_max_chars: int = Field(default=30000, ge=1000, le=200000)
    quiz_min_questions: int = Field(default=1, ge=1, le=20)
    quiz_max_questions: int = Field(default=10, ge=1, le=20)
    quiz_context_top_k: int = Field(default=12, ge=1, le=20)
    quiz_context_max_chars: int = Field(default=40000, ge=1000, le=200000)
    quiz_max_output_tokens: int = Field(default=4096, ge=512, le=8192)
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
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
        if self.embedding_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini")
        if self.quiz_min_questions > self.quiz_max_questions:
            raise ValueError("QUIZ_MIN_QUESTIONS must not exceed QUIZ_MAX_QUESTIONS")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

