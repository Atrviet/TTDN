from typing import Any, Literal, TypedDict


class TutorState(TypedDict):
    session_id: str
    user_id: str
    message: str
    mode: Literal["explain", "socratic", "practice", "hint", "review"]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    document_ids: list[str]
    history: list[dict[str, str]]
    learning_evidence: dict[str, Any]
    retrieved_context: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    answer: str
    execution_steps: int
    status: Literal["running", "completed", "failed", "limit_reached"]
    error: str | None

