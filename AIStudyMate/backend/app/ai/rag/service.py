from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.rag.vector_store import ChromaVectorStore, VectorSearchResult, VectorStoreError
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus
from app.models.document import Document, DocumentChunk
from app.repositories.rag import RAGRepository


class RAGDocumentNotFoundError(Exception):
    """Raised without distinguishing missing and non-owned documents."""


class DocumentNotIndexableError(Exception):
    """Raised when extracted document content cannot be indexed."""


class IndexingInProgressError(Exception):
    """Raised when the same document is currently being indexed."""


class IndexConfigurationMismatchError(Exception):
    """Raised when indexed vectors use another embedding configuration."""


class RAGPersistenceError(Exception):
    """Raised when PostgreSQL metadata cannot be committed."""


@dataclass(frozen=True)
class IndexingResult:
    document_id: UUID
    status: RAGIndexingStatus
    chunk_count: int
    already_indexed: bool
    embedding_provider: str
    embedding_model: str


class RAGService:
    def __init__(
        self,
        session: AsyncSession,
        chunker: DocumentChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: ChromaVectorStore,
    ) -> None:
        self.session = session
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.repository = RAGRepository(session)

    async def index_document(self, document_id: UUID, user_id: UUID) -> IndexingResult:
        document = await self.repository.get_owned_document_for_update(document_id, user_id)
        if document is None:
            raise RAGDocumentNotFoundError
        self._ensure_indexable(document)

        if document.indexing_status == RAGIndexingStatus.INDEXING:
            raise IndexingInProgressError
        if document.indexing_status == RAGIndexingStatus.INDEXED:
            self._ensure_matching_configuration(document)
            database_count = await self.repository.count_chunks(document.id)
            vector_count = await self.vector_store.count_document(document.id, user_id)
            if database_count > 0 and database_count == vector_count:
                return self._result(document, database_count, already_indexed=True)

        document.indexing_status = RAGIndexingStatus.INDEXING
        document.index_error = None
        document.embedding_provider = self.embedding_provider.provider_name
        document.embedding_model = self.embedding_provider.model_name
        try:
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise RAGPersistenceError from exc

        try:
            chunks = await run_in_threadpool(
                self.chunker.chunk_pages,
                document.id,
                document.extracted_pages or [],
            )
            if not chunks:
                raise DocumentNotIndexableError("Document contains no extractable text")
            embeddings = await self.embedding_provider.embed_documents(
                [chunk.text for chunk in chunks]
            )
            self._validate_embeddings(embeddings, len(chunks))
            await self.vector_store.delete_document(document.id, user_id)
            chroma_ids = await self.vector_store.upsert_chunks(
                chunks,
                embeddings,
                user_id,
                document.title,
            )

            await self.repository.replace_chunks(
                document.id,
                [
                    DocumentChunk(
                        document_id=document.id,
                        chroma_id=chroma_id,
                        chunk_index=chunk.chunk_index,
                        page_number=chunk.page_number,
                        token_count=chunk.token_count,
                    )
                    for chunk, chroma_id in zip(chunks, chroma_ids, strict=True)
                ],
            )
            document.indexing_status = RAGIndexingStatus.INDEXED
            document.indexed_at = datetime.now(UTC)
            document.index_error = None
            await self.session.commit()
            return self._result(document, len(chunks), already_indexed=False)
        except (EmbeddingError, VectorStoreError, DocumentNotIndexableError):
            await self.session.rollback()
            await self._cleanup_failed_index(document.id, user_id)
            await self._mark_failed(document.id, user_id, "Indexing pipeline failed")
            raise
        except SQLAlchemyError as exc:
            await self.session.rollback()
            await self._cleanup_failed_index(document.id, user_id)
            await self._mark_failed(document.id, user_id, "Index metadata persistence failed")
            raise RAGPersistenceError from exc

    async def search(
        self,
        *,
        query: str,
        document_ids: list[UUID],
        user_id: UUID,
        top_k: int,
    ) -> list[VectorSearchResult]:
        unique_ids = list(dict.fromkeys(document_ids))
        documents = await self.repository.get_owned_documents(unique_ids, user_id)
        if len(documents) != len(unique_ids):
            raise RAGDocumentNotFoundError
        for document in documents:
            if document.indexing_status != RAGIndexingStatus.INDEXED:
                raise DocumentNotIndexableError("All documents must be indexed before search")
            self._ensure_matching_configuration(document)

        query_embedding = await self.embedding_provider.embed_query(query)
        self._validate_embeddings([query_embedding], 1)
        return await self.vector_store.search(
            query_embedding=query_embedding,
            user_id=user_id,
            document_ids=unique_ids,
            top_k=top_k,
        )

    async def get_authorized_indexed_chunks(
        self, *, document_ids: list[UUID], user_id: UUID
    ) -> list[VectorSearchResult]:
        """Return all indexed chunk texts for bounded offline AI pipelines.

        Text is deterministically reconstructed with the same configured chunker while PostgreSQL
        remains authoritative for which chunk IDs currently belong to the index.
        """
        unique_ids = list(dict.fromkeys(document_ids))
        documents = await self.repository.get_owned_documents(unique_ids, user_id)
        if len(documents) != len(unique_ids):
            raise RAGDocumentNotFoundError
        output: list[VectorSearchResult] = []
        for document in documents:
            if document.indexing_status != RAGIndexingStatus.INDEXED:
                raise DocumentNotIndexableError("All documents must be indexed before extraction")
            self._ensure_matching_configuration(document)
            chunks = await run_in_threadpool(self.chunker.chunk_pages, document.id, document.extracted_pages or [])
            persisted = await self.repository.get_chunks_by_chroma_ids(
                [f"{document.id}:{chunk.chunk_index}" for chunk in chunks]
            )
            persisted_by_id = {chunk.chroma_id: chunk for chunk in persisted}
            for chunk in chunks:
                chroma_id = f"{document.id}:{chunk.chunk_index}"
                db_chunk = persisted_by_id.get(chroma_id)
                if db_chunk is None:
                    continue
                output.append(VectorSearchResult(chroma_id=chroma_id, text=chunk.text, distance=0.0, metadata={"document_id": str(document.id), "document_title": document.title, "page_number": db_chunk.page_number or chunk.page_number, "chunk_index": chunk.chunk_index}))
        return output

    def _ensure_indexable(self, document: Document) -> None:
        if document.processing_status != DocumentProcessingStatus.READY:
            raise DocumentNotIndexableError("Document extraction is not ready")
        if document.requires_ocr:
            raise DocumentNotIndexableError("Document requires OCR before indexing")
        if not document.extracted_pages:
            raise DocumentNotIndexableError("Document contains no extracted pages")

    def _ensure_matching_configuration(self, document: Document) -> None:
        if (
            document.embedding_provider != self.embedding_provider.provider_name
            or document.embedding_model != self.embedding_provider.model_name
        ):
            raise IndexConfigurationMismatchError

    @staticmethod
    def _validate_embeddings(embeddings: list[list[float]], expected_count: int) -> None:
        if len(embeddings) != expected_count or not embeddings:
            raise EmbeddingError("Embedding count does not match chunk count")
        dimensions = len(embeddings[0])
        if dimensions == 0 or any(len(vector) != dimensions for vector in embeddings):
            raise EmbeddingError("Embedding dimensions are inconsistent")
        if any(not math.isfinite(value) for vector in embeddings for value in vector):
            raise EmbeddingError("Embedding contains non-finite values")

    async def _cleanup_failed_index(self, document_id: UUID, user_id: UUID) -> None:
        try:
            await self.vector_store.delete_document(document_id, user_id)
        except VectorStoreError:
            pass

    async def _mark_failed(self, document_id: UUID, user_id: UUID, message: str) -> None:
        document = await self.repository.get_owned_document_for_update(document_id, user_id)
        if document is None:
            return
        document.indexing_status = RAGIndexingStatus.FAILED
        document.index_error = message[:500]
        try:
            await self.session.commit()
        except SQLAlchemyError:
            await self.session.rollback()

    def _result(
        self, document: Document, chunk_count: int, *, already_indexed: bool
    ) -> IndexingResult:
        return IndexingResult(
            document_id=document.id,
            status=document.indexing_status,
            chunk_count=chunk_count,
            already_indexed=already_indexed,
            embedding_provider=self.embedding_provider.provider_name,
            embedding_model=self.embedding_provider.model_name,
        )
