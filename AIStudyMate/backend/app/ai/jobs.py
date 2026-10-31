from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class AIJobRequest:
    job_type: str
    user_id: UUID
    payload: dict[str, Any]
    job_id: UUID = field(default_factory=uuid4)


class AIJobDispatcher(Protocol):
    """Boundary for a durable worker implementation added by a later feature step."""

    async def enqueue(
        self,
        request: AIJobRequest,
        handler: Callable[[AIJobRequest], Awaitable[None]],
    ) -> UUID: ...


class BackgroundJobsUnavailableError(RuntimeError):
    """Raised when a deployment has no configured durable AI worker."""
