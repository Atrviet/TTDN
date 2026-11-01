from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import ChatMessageRole


class TutorMode(StrEnum):
    EXPLAIN = "explain"
    SOCRATIC = "socratic"
    PRACTICE = "practice"
    HINT = "hint"
    REVIEW = "review"


class TutorDifficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TutorSessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(default="Phiên gia sư mới", min_length=1, max_length=255)
    learning_objective: str | None = Field(default=None, max_length=2000)
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)


class TutorSessionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    learning_objective: str | None = Field(default=None, max_length=2000)
    document_ids: list[UUID] | None = Field(default=None, max_length=20)


class TutorMessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=10000)
    mode: TutorMode = TutorMode.EXPLAIN
    difficulty: TutorDifficulty = TutorDifficulty.BEGINNER
    document_ids: list[UUID] = Field(default_factory=list, max_length=20)


class TutorCitation(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int
    chunk_id: str


class TutorMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    role: ChatMessageRole
    content: str
    citations: list[TutorCitation] | None
    created_at: datetime


class TutorSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    learning_objective: str | None
    document_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class TutorSessionDetail(TutorSessionResponse):
    messages: list[TutorMessageResponse]


class TutorSessionList(BaseModel):
    items: list[TutorSessionResponse]


class TutorReplyResponse(BaseModel):
    session_id: UUID
    mode: TutorMode
    difficulty: TutorDifficulty
    user_message: TutorMessageResponse
    assistant_message: TutorMessageResponse
    model: str | None
    execution_steps: int

