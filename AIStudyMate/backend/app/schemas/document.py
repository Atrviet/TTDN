from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import DocumentProcessingStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    original_filename: str
    file_size: int
    mime_type: str
    processing_status: DocumentProcessingStatus
    page_count: int | None
    requires_ocr: bool
    processing_error: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)


class DocumentPageContent(BaseModel):
    page_number: int = Field(ge=1)
    text: str


class DocumentContentResponse(BaseModel):
    document_id: UUID
    title: str
    page_count: int
    requires_ocr: bool
    pages: list[DocumentPageContent]
    metadata: dict[str, str]

