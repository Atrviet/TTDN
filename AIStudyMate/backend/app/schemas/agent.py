from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat import ChatCitation


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: UUID
    message: str = Field(min_length=1, max_length=10000)
    document_ids: list[UUID] = Field(min_length=1, max_length=20)


class AgentChatResponse(BaseModel):
    session_id: UUID
    answer: str
    tools_used: list[str]
    citations: list[ChatCitation]
    execution_steps: int
    execution_status: Literal["completed", "failed", "limit_reached"]
    model: str | None
