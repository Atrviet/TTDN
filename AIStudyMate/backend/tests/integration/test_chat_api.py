import os
from collections.abc import AsyncIterator
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.llm.base import LLMError, LLMProvider
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.rag import get_rag_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.common import UserRole
from app.models.user import User


class FakeRAGService:
    def __init__(self) -> None:
        self.results: list[VectorSearchResult] = []

    async def search(self, **kwargs) -> list[VectorSearchResult]:
        return self.results


class FakeLLM(LLMProvider):
    should_fail = False
    prompts: list[str] = []

    @property
    def model_name(self) -> str:
        return "mock-gemini"

    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        if self.should_fail:
            raise LLMError("simulated failure")
        self.prompts.append(prompt)
        return "Câu trả lời dựa trên tài liệu [SOURCE 1]."

    async def stream(self, *, system_instruction: str, prompt: str) -> AsyncIterator[str]:
        if self.should_fail:
            raise LLMError("simulated rate limit")
        self.prompts.append(prompt)
        yield "Câu trả lời "
        yield "được truyền dần [SOURCE 1]."


def safe_test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql" or not parsed.database or "test" not in parsed.database:
        pytest.fail("A dedicated PostgreSQL test database is required")
    return value


@pytest.mark.integration
@pytest.mark.asyncio
async def test_chat_lifecycle_grounding_isolation_no_evidence_and_failure() -> None:
    engine = create_async_engine(safe_test_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    owner = User(
        username=f"chat_owner_{suffix}",
        email=f"chat_owner_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Chat Owner",
        role=UserRole.STUDENT,
    )
    other = User(
        username=f"chat_other_{suffix}",
        email=f"chat_other_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Chat Other",
        role=UserRole.STUDENT,
    )
    async with factory() as session:
        session.add_all([owner, other])
        await session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id, owner.role)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    document_id = uuid4()
    rag = FakeRAGService()
    rag.results = [
        VectorSearchResult(
            chroma_id=f"{document_id}:3",
            text="Chương 2 mô tả retrieval-augmented generation.",
            distance=0.1,
            metadata={
                "document_id": str(document_id),
                "document_title": "Giáo trình RAG",
                "page_number": 7,
            },
        )
    ]
    llm = FakeLLM()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_llm_provider] = lambda: llm

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post(
                "/api/v1/chat/sessions", headers=owner_headers, json={"title": "RAG lesson"}
            )
            assert created.status_code == 201, created.text
            session_id = created.json()["id"]

            assert (await client.get("/api/v1/chat/sessions", headers=owner_headers)).json()["items"]
            isolated = await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=other_headers
            )
            assert isolated.status_code == 404
            unauthenticated_stream = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                json={"message": "Không có token", "document_ids": [str(document_id)]},
            )
            assert unauthenticated_stream.status_code == 401
            isolated_stream = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                headers=other_headers,
                json={"message": "Không thuộc phiên", "document_ids": [str(document_id)]},
            )
            assert isolated_stream.status_code == 404

            sent = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                headers=owner_headers,
                json={"message": "Tóm tắt chương 2", "document_ids": [str(document_id)]},
            )
            assert sent.status_code == 200, sent.text
            payload = sent.json()
            assert payload["model"] == "mock-gemini"
            assert payload["assistant_message"]["citations"] == [
                {
                    "document_id": str(document_id),
                    "document_title": "Giáo trình RAG",
                    "page_number": 7,
                    "chunk_id": f"{document_id}:3",
                }
            ]

            streamed = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                headers=owner_headers,
                json={"message": "Stream chương 2", "document_ids": [str(document_id)]},
            )
            assert streamed.status_code == 200
            assert streamed.headers["content-type"].startswith("text/event-stream")
            assert "event: citations" in streamed.text
            assert streamed.text.count("event: token") == 2
            assert "event: complete" in streamed.text
            assert "được truyền dần" in streamed.text

            history = await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=owner_headers
            )
            assert [item["role"] for item in history.json()["items"]] == [
                "user", "assistant", "user", "assistant"
            ]

            rag.results = []
            no_evidence = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                headers=owner_headers,
                json={"message": "Nội dung không có", "document_ids": [str(document_id)]},
            )
            assert no_evidence.status_code == 200
            assert no_evidence.json()["model"] is None
            assert no_evidence.json()["assistant_message"]["citations"] == []
            assert "chưa tìm thấy" in no_evidence.json()["assistant_message"]["content"]

            before_failure = len((await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=owner_headers
            )).json()["items"])
            rag.results = [SimpleNamespace(**vars(rag.results[0]))] if rag.results else [
                VectorSearchResult(
                    chroma_id=f"{document_id}:3",
                    text="Evidence",
                    distance=0.1,
                    metadata={"document_id": str(document_id), "document_title": "Doc", "page_number": 1},
                )
            ]
            llm.should_fail = True
            failed = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages",
                headers=owner_headers,
                json={"message": "Will fail", "document_ids": [str(document_id)]},
            )
            assert failed.status_code == 503
            after_failure = len((await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=owner_headers
            )).json()["items"])
            assert after_failure == before_failure

            failed_stream = await client.post(
                f"/api/v1/chat/sessions/{session_id}/messages/stream",
                headers=owner_headers,
                json={"message": "Rate limited stream", "document_ids": [str(document_id)]},
            )
            assert failed_stream.status_code == 200
            assert "event: error" in failed_stream.text
            assert "temporarily unavailable" in failed_stream.text
            after_stream_failure = len((await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=owner_headers
            )).json()["items"])
            assert after_stream_failure == after_failure

            renamed = await client.patch(
                f"/api/v1/chat/sessions/{session_id}",
                headers=owner_headers,
                json={"title": "Renamed"},
            )
            assert renamed.status_code == 200
            assert renamed.json()["title"] == "Renamed"
            assert (await client.delete(
                f"/api/v1/chat/sessions/{session_id}", headers=owner_headers
            )).status_code == 204
            assert (await client.get(
                f"/api/v1/chat/sessions/{session_id}/messages", headers=owner_headers
            )).status_code == 404

        async with factory() as session:
            assert await session.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)) == 0
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(ChatSession).where(ChatSession.user_id.in_([owner.id, other.id])))
            await session.execute(delete(User).where(User.id.in_([owner.id, other.id])))
            await session.commit()
        await engine.dispose()
