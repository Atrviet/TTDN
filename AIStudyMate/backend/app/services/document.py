from __future__ import annotations

from pathlib import Path
from uuid import UUID
from typing import TYPE_CHECKING

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.ai.rag.vector_store import VectorStoreError
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.services.pdf_extractor import PDFExtractionResult, PDFExtractor
from app.services.storage import LocalDocumentStorage

if TYPE_CHECKING:
    from app.ai.rag.vector_store import ChromaVectorStore


class DocumentNotFoundError(Exception):
    """Raised for both missing and non-owned documents to avoid existence leaks."""


class DocumentDatabaseError(Exception):
    """Raised when persistence fails after storage work has started."""


class DocumentVectorCleanupError(Exception):
    """Raised when a deleted document's vectors cannot be removed."""

class DocumentInUseError(Exception):
    def __init__(self,resource_types:list[str])->None:
        self.resource_types=resource_types
        super().__init__("Document is referenced by learning resources")


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        storage: LocalDocumentStorage,
        extractor: PDFExtractor,
        max_upload_size: int,
        vector_store: ChromaVectorStore | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.extractor = extractor
        self.max_upload_size = max_upload_size
        self.vector_store = vector_store
        self.documents = DocumentRepository(session)

    async def upload(
        self,
        *,
        upload: UploadFile,
        user_id: UUID,
        title: str | None,
    ) -> Document:
        temporary = await self.storage.save_temporary(upload, self.max_upload_size)
        try:
            extraction = await run_in_threadpool(self.extractor.extract, temporary.path)
        except Exception:
            await self.storage.remove_path(temporary.path)
            raise

        relative_path = await self.storage.promote(temporary.path, user_id)
        document = self._build_document(
            user_id=user_id,
            title=title,
            relative_path=relative_path,
            original_filename=temporary.original_filename,
            file_size=temporary.size,
            extraction=extraction,
        )
        self.documents.add(document)
        try:
            await self.session.commit()
            await self.session.refresh(document)
        except SQLAlchemyError as exc:
            await self.session.rollback()
            await self.storage.delete(relative_path)
            raise DocumentDatabaseError from exc
        return document

    async def list_owned(
        self,
        user_id: UUID,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[Document], int]:
        return await self.documents.list_owned(
            user_id,
            offset=(page - 1) * per_page,
            limit=per_page,
        )

    async def get_owned(self, document_id: UUID, user_id: UUID) -> Document:
        document = await self.documents.get_owned(document_id, user_id)
        if document is None:
            raise DocumentNotFoundError
        return document

    async def delete_owned(self, document_id: UUID, user_id: UUID) -> None:
        document = await self.get_owned(document_id, user_id)
        dependencies=await self.documents.dependent_resource_types(document_id)
        if dependencies:raise DocumentInUseError(dependencies)
        staged = await self.storage.stage_deletion(document.file_path)
        try:
            await self.documents.delete(document)
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            await self.storage.restore_deletion(staged)
            raise DocumentDatabaseError from exc
        try:
            if self.vector_store is not None and document.indexing_status == RAGIndexingStatus.INDEXED:
                await self.vector_store.delete_document(document.id, user_id)
        except VectorStoreError as exc:
            raise DocumentVectorCleanupError from exc
        finally:
            await self.storage.finalize_deletion(staged)

    @staticmethod
    def _build_document(
        *,
        user_id: UUID,
        title: str | None,
        relative_path: str,
        original_filename: str,
        file_size: int,
        extraction: PDFExtractionResult,
    ) -> Document:
        cleaned_title = " ".join((title or "").split())
        if not cleaned_title:
            metadata_title = str(extraction.metadata.get("title", "")).strip()
            cleaned_title = metadata_title or Path(original_filename).stem or "Untitled document"
        return Document(
            user_id=user_id,
            title=cleaned_title[:255],
            original_filename=original_filename,
            file_path=relative_path,
            file_size=file_size,
            mime_type="application/pdf",
            processing_status=DocumentProcessingStatus.READY,
            page_count=extraction.page_count,
            extracted_pages=[
                {"page_number": page.page_number, "text": page.text}
                for page in extraction.pages
            ],
            pdf_metadata=extraction.metadata,
            requires_ocr=extraction.requires_ocr,
            processing_error=None,
        )
