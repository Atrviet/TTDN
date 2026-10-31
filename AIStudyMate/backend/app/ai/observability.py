import logging
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __post_init__(self) -> None:
        if self.input_tokens < 0 or self.output_tokens < 0:
            raise ValueError("Token counts cannot be negative")


class AIObservability:
    """Structured AI telemetry that deliberately excludes prompts and secrets."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("app.ai")

    def generation_completed(
        self,
        *,
        operation: str,
        model: str,
        user_id: UUID,
        usage: TokenUsage,
        duration_ms: float,
    ) -> None:
        self.logger.info(
            "ai_generation_completed",
            extra={
                "operation": operation,
                "model": model,
                "user_id": str(user_id),
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "duration_ms": round(duration_ms, 2),
            },
        )

    def generation_failed(
        self, *, operation: str, model: str, user_id: UUID, error_type: str
    ) -> None:
        self.logger.warning(
            "ai_generation_failed",
            extra={
                "operation": operation,
                "model": model,
                "user_id": str(user_id),
                "error_type": error_type,
            },
        )
