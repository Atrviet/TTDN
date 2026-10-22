import os
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.rag.vector_store import ChromaVectorStore
from app.api.dependencies.document import get_document_storage
from app.api.dependencies.rag import get_chunker, get_embedding_provider, get_vector_store
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.services.storage import LocalDocumentStorage


class DeterministicEmbeddingProvider(EmbeddingProvider):
    @property
    def provider_name(self) -> str:
        return "test"

    @property
    def model_name(self) -> str:
        return "deterministic-v1"

    @staticmethod
    def vector(text: str) -> list[float]:
        lowered = text.lower()
        return [
            float(lowered.count("ai") + lowered.count("trí tuệ")),
            float(lowered.count("database") + lowered.count("cơ sở dữ liệu")),
            0.1,
        ]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self.vector(text)


class FailingEmbeddingProvider(DeterministicEmbeddingProvider):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("simulated provider failure")


def get_safe_test_database_url() -> str:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(test_url)
    development_url = os.getenv("DATABASE_URL")
    if parsed.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not parsed.database or "test" not in parsed.database.lower():
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")
    if development_url and make_url(development_url) == parsed:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL")
    return test_url


def make_document(user_id, relative_path: str, title: str, text: str) -> Document:
    return Document(
        user_id=user_id,
        title=title,
        original_filename=f"{title}.pdf",
        file_path=relative_path,
        file_size=100,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.READY,
        page_count=1,
        extracted_pages=[{"page_number": 1, "text": text}],
        pdf_metadata={},
        requires_ocr=False,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rag_index_search_ownership_idempotency_failure_and_deletion(tmp_path: Path) -> None:
    engine = create_async_engine(get_safe_test_database_url())
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    owner = User(
        username=f"rag_owner_{suffix}",
        email=f"rag_owner_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="RAG Owner",
        role=UserRole.STUDENT,
    )
    other = User(
        username=f"rag_other_{suffix}",
        email=f"rag_other_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="RAG Other",
        role=UserRole.STUDENT,
    )
    storage = LocalDocumentStorage(tmp_path / "documents")
    provider = DeterministicEmbeddingProvider()
    vector_store = ChromaVectorStore(
        tmp_path / "chroma", "integration_chunks", provider.provider_name, provider.model_name
    )

    async with session_factory() as session:
        session.add_all([owner, other])
        await session.flush()
        documents = [
            make_document(owner.id, f"{owner.id}/ai.pdf", "AI", "Trí tuệ nhân tạo AI hỗ trợ học tập."),
            make_document(owner.id, f"{owner.id}/db.pdf", "Database", "Cơ sở dữ liệu database lưu trữ thông tin."),
            make_document(owner.id, f"{owner.id}/failure.pdf", "Failure", "AI provider failure."),
            make_document(other.id, f"{other.id}/private.pdf", "Private", "Tài liệu riêng tư."),
        ]
        session.add_all(documents)
        await session.commit()
        for document in documents:
            await session.refresh(document)

    for document in documents:
        path = storage.resolve_relative_path(document.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test pdf placeholder")

    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id, owner.role)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_chunker] = lambda: DocumentChunker(20, 5)
    app.dependency_overrides[get_embedding_provider] = lambda: provider
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_document_storage] = lambda: storage
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            missing_jwt = await client.post(f"/api/v1/documents/{documents[0].id}/index")
            assert missing_jwt.status_code == 401

            indexed = await client.post(
                f"/api/v1/documents/{documents[0].id}/index", headers=owner_headers
            )
            assert indexed.status_code == 200, indexed.text
            assert indexed.json()["status"] == "indexed"
            assert indexed.json()["already_indexed"] is False
            assert indexed.json()["chunk_count"] > 0

            duplicate = await client.post(
                f"/api/v1/documents/{documents[0].id}/index", headers=owner_headers
            )
            assert duplicate.status_code == 200
            assert duplicate.json()["already_indexed"] is True

            await client.post(
                f"/api/v1/documents/{documents[1].id}/index", headers=owner_headers
            )

            ownership_index = await client.post(
                f"/api/v1/documents/{documents[3].id}/index", headers=owner_headers
            )
            assert ownership_index.status_code == 404

            search = await client.post(
                "/api/v1/rag/search",
                headers=owner_headers,
                json={
                    "query": "Giải thích trí tuệ nhân tạo AI",
                    "document_ids": [str(documents[0].id), str(documents[1].id)],
                    "top_k": 2,
                },
            )
            assert search.status_code == 200, search.text
            assert search.json()["distance_metric"] == "cosine"
            assert search.json()["results"][0]["document_id"] == str(documents[0].id)
            assert search.json()["results"][0]["page_number"] == 1

            isolated_search = await client.post(
                "/api/v1/rag/search",
                headers=owner_headers,
                json={
                    "query": "private",
                    "document_ids": [str(documents[3].id)],
                    "top_k": 1,
                },
            )
            assert isolated_search.status_code == 404

            app.dependency_overrides[get_embedding_provider] = lambda: FailingEmbeddingProvider()
            embedding_failure = await client.post(
                f"/api/v1/documents/{documents[2].id}/index", headers=owner_headers
            )
            assert embedding_failure.status_code == 503
            app.dependency_overrides[get_embedding_provider] = lambda: provider

            await vector_store.delete_document(documents[1].id, owner.id)
            empty = await client.post(
                "/api/v1/rag/search",
                headers=owner_headers,
                json={
                    "query": "database",
                    "document_ids": [str(documents[1].id)],
                    "top_k": 5,
                },
            )
            assert empty.status_code == 200
            assert empty.json()["results"] == []

            deleted = await client.delete(
                f"/api/v1/documents/{documents[0].id}", headers=owner_headers
            )
            assert deleted.status_code == 204
            assert await vector_store.count_document(documents[0].id, owner.id) == 0

        async with session_factory() as session:
            chunks = list(
                (await session.scalars(
                    select(DocumentChunk).where(DocumentChunk.document_id == documents[1].id)
                )).all()
            )
            failed_document = await session.get(Document, documents[2].id)
            assert chunks
            assert all(chunk.page_number == 1 for chunk in chunks)
            assert failed_document is not None
            assert failed_document.indexing_status == RAGIndexingStatus.FAILED
    finally:
        for dependency in (
            get_db_session,
            get_chunker,
            get_embedding_provider,
            get_vector_store,
            get_document_storage,
        ):
            app.dependency_overrides.pop(dependency, None)
        async with session_factory() as session:
            await session.execute(
                delete(Document).where(Document.user_id.in_([owner.id, other.id]))
            )
            await session.execute(delete(User).where(User.id.in_([owner.id, other.id])))
            await session.commit()
        await engine.dispose()
