from typing import Any, Literal, TypedDict
from uuid import UUID


AgentIntent = Literal["question", "summary", "explanation", "outline", "learning_plan"]
AgentStatus = Literal["running", "completed", "failed", "limit_reached"]


class ConversationTurn(TypedDict):
    role: Literal["user", "assistant"]
    content: str


class AgentToolCall(TypedDict):
    name: str
    arguments: dict[str, Any]
    ok: bool
    output: dict[str, Any]


class AgentCitation(TypedDict):
    document_id: str
    document_title: str
    page_number: int
    chunk_id: str


class StudyAgentState(TypedDict):
    session_id: UUID
    user_id: UUID
    authorized_document_ids: list[UUID]
    message: str
    conversation_history: list[ConversationTurn]
    intent: AgentIntent
    planned_tools: list[str]
    retrieved_context: list[dict[str, Any]]
    tool_call_history: list[AgentToolCall]
    answer: str
    citations: list[AgentCitation]
    execution_status: AgentStatus
    execution_steps: int
    error: str | None
