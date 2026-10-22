from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus

if TYPE_CHECKING:
    from app.models.quiz import Quiz
    from app.models.user import User


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_size >= 0", name="ck_documents_file_size_non_negative"),
        CheckConstraint("page_count IS NULL OR page_count > 0", name="ck_documents_page_count_positive"),
        Index("ix_documents_user_created_at", "user_id", "created_at"),
        Index("ix_documents_user_status", "user_id", "processing_status"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        Enum(
            DocumentProcessingStatus,
            name="document_processing_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED,
        server_default=DocumentProcessingStatus.UPLOADED.value,
        index=True,
    )
    page_count: Mapped[int | None] = mapped_column(Integer)
    extracted_pages: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    pdf_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requires_ocr: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    processing_error: Mapped[str | None] = mapped_column(String(500))
    indexing_status: Mapped[RAGIndexingStatus] = mapped_column(
        Enum(
            RAGIndexingStatus,
            name="rag_indexing_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=RAGIndexingStatus.NOT_INDEXED,
        server_default=RAGIndexingStatus.NOT_INDEXED.value,
        index=True,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    index_error: Mapped[str | None] = mapped_column(String(500))
    embedding_provider: Mapped[str | None] = mapped_column(String(32))
    embedding_model: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="documents")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )
    quizzes: Mapped[list[Quiz]] = relationship(back_populates="document", passive_deletes=True)


class DocumentChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_order"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_non_negative"),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="ck_document_chunks_page_positive"),
        CheckConstraint("token_count >= 0", name="ck_document_chunks_token_count_non_negative"),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chroma_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

