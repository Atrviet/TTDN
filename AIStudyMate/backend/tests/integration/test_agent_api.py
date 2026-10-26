import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.llm.base import LLMProvider
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.rag import get_rag_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document
from app.models.user import User


class ConcurrentFakeRAG:
    async def search(self, *, query, document_ids, user_id, top_k):
        await asyncio.sleep(0)
        document_id = document_ids[0]
        return [
            VectorSearchResult(
                chroma_id=f"{document_id}:0",
                text=f"Evidence for {document_id}",
                distance=0.1,
                metadata={
                    "document_id": str(document_id),
                    "document_title": f"Document {document_id}",
                    "page_number": 1,
                },
            )
        ]


class ConcurrentFakeLLM(LLMProvider):
    @property
    def model_name(self) -> str:
        return "mock-agent-gemini"

    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        await asyncio.sleep(0)
        return "Agent grounded answer"


def safe_test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql" or not parsed.database or "test" not in parsed.database:
        pytest.fail("A dedicated PostgreSQL test database is required")
    return value


def make_document(user_id, suffix: str) -> Document:
    return Document(
        user_id=user_id,
        title=f"Agent Doc {suffix}",
        original_filename=f"agent-{suffix}.pdf",
        file_path=f"{user_id}/agent-{suffix}.pdf",
        file_size=100,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.READY,
        page_count=1,
        extracted_pages=[{"page_number": 1, "text": "Agent test evidence"}],
        pdf_metadata={},
        requires_ocr=False,
        indexing_status=RAGIndexingStatus.INDEXED,
        embedding_provider="test",
        embedding_model="test-model",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_agent_persistence_authorization_and_concurrent_session_isolation() -> None:
    engine = create_async_engine(safe_test_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    users = [
        User(
            username=f"agent_{index}_{suffix}",
            email=f"agent_{index}_{suffix}@example.com",
            hashed_password=hash_password("SecurePassword123"),
            full_name=f"Agent User {index}",
            role=UserRole.STUDENT,
        )
        for index in range(2)
    ]
    async with factory() as session:
        session.add_all(users)
        await session.flush()
        documents = [make_document(user.id, f"{index}-{suffix}") for index, user in enumerate(users)]
        sessions = [ChatSession(user_id=user.id, title=f"Agent Session {index}") for index, user in enumerate(users)]
        session.add_all([*documents, *sessions])
        await session.commit()

    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"} for user in users
    ]
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_rag_service] = lambda: ConcurrentFakeRAG()
    app.dependency_overrides[get_llm_provider] = lambda: ConcurrentFakeLLM()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            foreign_session = await client.post(
                "/api/v1/agent/chat",
                headers=headers[0],
                json={
                    "session_id": str(sessions[1].id),
                    "message": "Explain",
                    "document_ids": [str(documents[0].id)],
                },
            )
            assert foreign_session.status_code == 404

            foreign_document = await client.post(
                "/api/v1/agent/chat",
                headers=headers[0],
                json={
                    "session_id": str(sessions[0].id),
                    "message": "Explain",
                    "document_ids": [str(documents[1].id)],
                },
            )
            assert foreign_document.status_code == 404

            async def send(index: int):
                return await client.post(
                    "/api/v1/agent/chat",
                    headers=headers[index],
                    json={
                        "session_id": str(sessions[index].id),
                        "message": "Giải thích và lập kế hoạch ôn tập",
                        "document_ids": [str(documents[index].id)],
                    },
                )

            responses = await asyncio.gather(send(0), send(1))
            for index, response in enumerate(responses):
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["execution_status"] == "completed"
                assert body["execution_steps"] == 4
                assert body["tools_used"] == ["search_documents", "get_learning_history"]
                assert body["citations"][0]["document_id"] == str(documents[index].id)

        async with factory() as session:
            for index, chat_session in enumerate(sessions):
                messages = list((await session.scalars(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == chat_session.id)
                    .order_by(ChatMessage.created_at, ChatMessage.id)
                )).all())
                assert [item.role.value for item in messages] == ["user", "assistant"]
                assert messages[1].citations[0]["document_id"] == str(documents[index].id)
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(ChatSession).where(ChatSession.user_id.in_([item.id for item in users])))
            await session.execute(delete(Document).where(Document.user_id.in_([item.id for item in users])))
            await session.execute(delete(User).where(User.id.in_([item.id for item in users])))
            await session.commit()
        await engine.dispose()
