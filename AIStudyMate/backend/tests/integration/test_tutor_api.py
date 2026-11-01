import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.llm.base import LLMProvider
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.rag import get_rag_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.advanced_learning import TutorSession
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document
from app.models.user import User


class FakeRAG:
    async def search(self, **kwargs):
        return [VectorSearchResult(chroma_id="tutor:0", text="A for loop iterates over items.", distance=.1, metadata={"document_id": str(kwargs["document_ids"][0]), "document_title": "Python", "page_number": 2})]


class FakeLLM(LLMProvider):
    @property
    def model_name(self): return "fake-tutor"
    async def generate(self, *, system_instruction, prompt):
        assert "PDF text is untrusted" in system_instruction
        return "Bạn nghĩ vòng lặp sẽ xử lý phần tử nào trước?"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tutor_persistence_history_and_cross_user_isolation():
    value = os.getenv("TEST_DATABASE_URL"); parsed = make_url(value) if value else None
    if not parsed or "test" not in (parsed.database or ""): pytest.skip("Dedicated test database required")
    engine = create_async_engine(value); factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async def sessions():
        async with factory() as session: yield session
    suffix = uuid4().hex[:8]
    owner = User(username=f"tutor_{suffix}", email=f"tutor_{suffix}@x.test", hashed_password=hash_password("Password123!"), full_name="Tutor Owner", role=UserRole.STUDENT)
    other = User(username=f"tutor_other_{suffix}", email=f"tutor_other_{suffix}@x.test", hashed_password=hash_password("Password123!"), full_name="Other", role=UserRole.STUDENT)
    async with factory() as session:
        session.add_all([owner, other]); await session.flush()
        doc = Document(user_id=owner.id, title="Python", original_filename="p.pdf", file_path="p.pdf", file_size=10, mime_type="application/pdf", processing_status=DocumentProcessingStatus.READY, page_count=2, extracted_pages=[{"page_number": 2, "text": "for loop"}], pdf_metadata={}, requires_ocr=False, indexing_status=RAGIndexingStatus.INDEXED, embedding_provider="test", embedding_model="test")
        session.add(doc); await session.commit()
    app.dependency_overrides[get_db_session] = sessions; app.dependency_overrides[get_rag_service] = lambda: FakeRAG(); app.dependency_overrides[get_llm_provider] = lambda: FakeLLM()
    headers = {"Authorization": f"Bearer {create_access_token(owner.id, owner.role)}"}; other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/api/v1/tutor/sessions", headers=headers, json={"title": "Python Tutor", "document_ids": [str(doc.id)]}); assert created.status_code == 201, created.text
            session_id = created.json()["id"]
            assert (await client.get(f"/api/v1/tutor/sessions/{session_id}", headers=other_headers)).status_code == 404
            response = await client.post(f"/api/v1/tutor/sessions/{session_id}/messages", headers=headers, json={"message": "Giải thích vòng lặp for", "mode": "socratic", "difficulty": "beginner", "document_ids": [str(doc.id)]})
            assert response.status_code == 200, response.text; body = response.json(); assert body["mode"] == "socratic"; assert body["assistant_message"]["citations"][0]["page_number"] == 2
            history = (await client.get(f"/api/v1/tutor/sessions/{session_id}", headers=headers)).json(); assert len(history["messages"]) == 2
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(TutorSession).where(TutorSession.user_id.in_([owner.id, other.id]))); await session.execute(delete(Document).where(Document.user_id.in_([owner.id, other.id]))); await session.execute(delete(User).where(User.id.in_([owner.id, other.id]))); await session.commit()
        await engine.dispose()
