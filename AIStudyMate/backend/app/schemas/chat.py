from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import ChatMessageRole


class ChatSessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="New conversation", min_length=1, max_length=255)


class ChatSessionRename(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionResponse]


class ChatCitation(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int
    chunk_id: str


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: ChatMessageRole
    content: str
    citations: list[ChatCitation] | None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: UUID
    items: list[ChatMessageResponse]


class SendChatMessageRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=10000)
    document_ids: list[UUID] = Field(min_length=1, max_length=20)


class SendChatMessageResponse(BaseModel):
    session_id: UUID
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse
    model: str | None = None
