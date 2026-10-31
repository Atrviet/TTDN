import asyncio
import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
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
from app.models.advanced_learning import FlashcardDeck, FlashcardReview
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document, DocumentChunk
from app.models.user import User
from app.schemas.flashcard import GeneratedFlashcards


def safe_test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql" or not parsed.database or "test" not in parsed.database:
        pytest.fail("A dedicated PostgreSQL test database is required")
    return value


class FakeFlashcardRAG:
    def __init__(self, document_id, chroma_id) -> None:
        self.document_id = document_id
        self.chroma_id = chroma_id

    async def search(self, *, query, document_ids, user_id, top_k):
        return [
            VectorSearchResult(
                chroma_id=self.chroma_id,
                text="Python variables bind names to values and functions package reusable behavior.",
                distance=0.05,
                metadata={
                    "document_id": str(self.document_id),
                    "document_title": "Python Basics",
                    "page_number": 3,
                },
            )
        ]


class FakeFlashcardLLM(LLMProvider):
    mode = "valid"

    @property
    def model_name(self) -> str:
        return "mock-gemini"

    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        return "unused"

    async def generate_structured(self, *, prompt, response_model, **kwargs):
        if self.mode == "failure":
            raise LLMError("simulated outage")
        if self.mode == "malformed":
            try:
                return response_model.model_validate({"cards": [{"front_text": "missing"}]})
            except ValidationError:
                raise
        chunk_id = prompt.split('"chunk_id": "', 1)[1].split('"', 1)[0]
        fronts = ["Biến Python là gì?", "Hàm Python dùng để làm gì?"]
        if self.mode == "duplicate":
            fronts[1] = fronts[0]
        if self.mode == "bad_source":
            chunk_id = "unknown-source"
        return GeneratedFlashcards.model_validate(
            {
                "cards": [
                    {
                        "front_text": front,
                        "back_text": f"Câu trả lời {index + 1}",
                        "explanation": "Dựa trên nội dung tài liệu.",
                        "source": {"chunk_id": chunk_id},
                    }
                    for index, front in enumerate(fronts)
                ]
            }
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_flashcard_generation_review_due_stats_and_isolation() -> None:
    engine = create_async_engine(safe_test_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    owner = User(
        username=f"flash_owner_{suffix}", email=f"flash_owner_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"), full_name="Flash Owner",
        role=UserRole.STUDENT,
    )
    other = User(
        username=f"flash_other_{suffix}", email=f"flash_other_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"), full_name="Flash Other",
        role=UserRole.STUDENT,
    )
    async with factory() as session:
        session.add_all([owner, other])
        await session.flush()
        document = Document(
            user_id=owner.id, title="Python Basics", original_filename="python.pdf",
            file_path=f"{owner.id}/python.pdf", file_size=100, mime_type="application/pdf",
            processing_status=DocumentProcessingStatus.READY, page_count=3,
            extracted_pages=[{"page_number": 3, "text": "Python variables and functions"}],
            pdf_metadata={}, requires_ocr=False, indexing_status=RAGIndexingStatus.INDEXED,
            embedding_provider="test", embedding_model="test-model",
        )
        session.add(document)
        await session.flush()
        chunk = DocumentChunk(
            document_id=document.id, chroma_id=f"flash-{suffix}-0", chunk_index=0,
            page_number=3, token_count=8,
        )
        session.add(chunk)
        await session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id, owner.role)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    rag = FakeFlashcardRAG(document.id, chunk.chroma_id)
    llm = FakeFlashcardLLM()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_llm_provider] = lambda: llm

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            manual = await client.post(
                "/api/v1/flashcards/decks", headers=owner_headers,
                json={
                    "title": "Manual",
                    "cards": [{"front_text": "Câu hỏi tay", "back_text": "Câu trả lời tay"}],
                },
            )
            assert manual.status_code == 201, manual.text

            request = {
                "document_ids": [str(document.id)], "topic": "Python basics",
                "card_count": 2, "difficulty": "medium",
            }
            generated = await client.post(
                "/api/v1/flashcards/generate", headers=owner_headers, json=request
            )
            assert generated.status_code == 201, generated.text
            deck = generated.json()
            deck_id = deck["id"]
            card_id = deck["cards"][0]["id"]
            assert len(deck["cards"]) == 2
            assert deck["cards"][0]["source"] == {
                "document_id": str(document.id), "document_title": "Python Basics",
                "page_number": 3, "chunk_id": chunk.chroma_id,
            }

            assert (await client.get(
                f"/api/v1/flashcards/decks/{deck_id}", headers=other_headers
            )).status_code == 404
            unauthorized = await client.post(
                "/api/v1/flashcards/generate", headers=other_headers, json=request
            )
            assert unauthorized.status_code == 404

            due = await client.get("/api/v1/flashcards/due", headers=owner_headers)
            assert due.status_code == 200
            assert due.json()["total"] == 3

            first_review = await client.post(
                f"/api/v1/flashcards/{card_id}/review", headers=owner_headers,
                json={"rating": "good"},
            )
            assert first_review.status_code == 200, first_review.text
            assert first_review.json()["interval_days"] == 1
            assert first_review.json()["repetition_count"] == 1
            due_after_review = await client.get(
                "/api/v1/flashcards/due", headers=owner_headers
            )
            assert due_after_review.json()["total"] == 2
            assert card_id not in {item["id"] for item in due_after_review.json()["items"]}

            concurrent = await asyncio.gather(
                client.post(
                    f"/api/v1/flashcards/{card_id}/review", headers=owner_headers,
                    json={"rating": "good"},
                ),
                client.post(
                    f"/api/v1/flashcards/{card_id}/review", headers=owner_headers,
                    json={"rating": "easy"},
                ),
            )
            assert [response.status_code for response in concurrent] == [200, 200]
            assert sorted(response.json()["repetition_count"] for response in concurrent) == [2, 3]

            updated = await client.patch(
                f"/api/v1/flashcards/{deck['cards'][1]['id']}", headers=owner_headers,
                json={"front_text": deck["cards"][0]["front_text"]},
            )
            assert updated.status_code == 409

            stats = await client.get("/api/v1/flashcards/stats", headers=owner_headers)
            assert stats.status_code == 200
            assert stats.json()["total_decks"] == 2
            assert stats.json()["total_cards"] == 3
            assert stats.json()["total_reviews"] == 3
            assert stats.json()["reviewed_cards"] == 1

            for mode, expected in (("duplicate", 502), ("bad_source", 502), ("malformed", 502), ("failure", 503)):
                llm.mode = mode
                response = await client.post(
                    "/api/v1/flashcards/generate", headers=owner_headers, json=request
                )
                assert response.status_code == expected, (mode, response.text)
            llm.mode = "valid"

            deleted = await client.delete(
                f"/api/v1/flashcards/{deck['cards'][1]['id']}", headers=owner_headers
            )
            assert deleted.status_code == 204

        async with factory() as session:
            history_count = await session.scalar(
                select(func.count(FlashcardReview.id)).where(FlashcardReview.flashcard_id == card_id)
            )
            assert history_count == 3
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(FlashcardDeck).where(FlashcardDeck.user_id.in_([owner.id, other.id])))
            await session.execute(delete(Document).where(Document.user_id.in_([owner.id, other.id])))
            await session.execute(delete(User).where(User.id.in_([owner.id, other.id])))
            await session.commit()
        await engine.dispose()
