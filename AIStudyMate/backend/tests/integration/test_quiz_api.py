import os
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.ai.llm.base import LLMError, LLMProvider
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.rag import get_rag_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document
from app.models.quiz import Quiz, QuizAttempt
from app.models.user import User
from app.schemas.quiz import GeneratedQuiz


class FakeQuizRAG:
    empty = False

    async def search(self, *, query, document_ids, user_id, top_k):
        if self.empty:
            return []
        document_id = document_ids[0]
        return [
            VectorSearchResult(
                chroma_id=f"{document_id}:0",
                text="RAG retrieves relevant evidence before generating an answer.",
                distance=0.1,
                metadata={
                    "document_id": str(document_id),
                    "document_title": "RAG Fundamentals",
                    "page_number": 2,
                },
            )
        ]


class FakeQuizLLM(LLMProvider):
    mode = "valid"

    @property
    def model_name(self) -> str:
        return "mock-quiz-gemini"

    async def generate(self, *, system_instruction: str, prompt: str) -> str:
        return "unused"

    async def generate_structured(
        self, *, system_instruction, prompt, response_model, max_output_tokens=None
    ):
        if self.mode == "failure":
            raise LLMError("simulated Gemini outage")
        chunk_id = prompt.split('"chunk_id": "', 1)[1].split('"', 1)[0]
        question_count = 1 if self.mode == "wrong_count" else 2
        questions = []
        for index in range(question_count):
            questions.append(
                {
                    "question_text": f"Question {index + 1}: What does RAG do?",
                    "options": [
                        {"text": "Retrieves evidence before generation", "is_correct": True},
                        {"text": "Only sorts files", "is_correct": False},
                        {"text": "Deletes all context", "is_correct": False},
                        {"text": "Encrypts every answer", "is_correct": False},
                    ],
                    "explanation": "The source states that RAG retrieves evidence first.",
                    "source_references": [
                        {"chunk_id": "invented:99" if self.mode == "bad_source" else chunk_id}
                    ],
                }
            )
        return GeneratedQuiz.model_validate({"questions": questions})


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
        title="RAG Fundamentals",
        original_filename=f"rag-{suffix}.pdf",
        file_path=f"{user_id}/rag-{suffix}.pdf",
        file_size=100,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.READY,
        page_count=2,
        extracted_pages=[{"page_number": 2, "text": "RAG evidence"}],
        pdf_metadata={},
        requires_ocr=False,
        indexing_status=RAGIndexingStatus.INDEXED,
        embedding_provider="test",
        embedding_model="test-model",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_quiz_generation_attempt_grading_authorization_and_failures() -> None:
    engine = create_async_engine(safe_test_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    owner = User(
        username=f"quiz_owner_{suffix}",
        email=f"quiz_owner_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Quiz Owner",
        role=UserRole.STUDENT,
    )
    other = User(
        username=f"quiz_other_{suffix}",
        email=f"quiz_other_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Quiz Other",
        role=UserRole.STUDENT,
    )
    async with factory() as session:
        session.add_all([owner, other])
        await session.flush()
        document = make_document(owner.id, suffix)
        session.add(document)
        await session.commit()

    owner_headers = {"Authorization": f"Bearer {create_access_token(owner.id, owner.role)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.role)}"}
    rag, llm = FakeQuizRAG(), FakeQuizLLM()
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_rag_service] = lambda: rag
    app.dependency_overrides[get_llm_provider] = lambda: llm
    generated_quiz_id = None

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "title": "RAG Review",
                "number_of_questions": 2,
                "difficulty": "medium",
                "document_id": str(document.id),
            }
            generated = await client.post("/api/v1/quizzes/generate", headers=owner_headers, json=request)
            assert generated.status_code == 201, generated.text
            quiz_body = generated.json()
            generated_quiz_id = quiz_body["id"]
            assert quiz_body["difficulty"] == "medium"
            assert quiz_body["question_count"] == 2
            assert len(quiz_body["questions"]) == 2
            assert "is_correct" not in str(quiz_body)
            assert "explanation" not in str(quiz_body)

            listed = await client.get("/api/v1/quizzes", headers=owner_headers)
            assert listed.status_code == 200
            assert listed.json()["items"][0]["id"] == generated_quiz_id
            assert (await client.get(
                f"/api/v1/quizzes/{generated_quiz_id}", headers=other_headers
            )).status_code == 404

            attempt_response = await client.post(
                f"/api/v1/quizzes/{generated_quiz_id}/attempts", headers=owner_headers
            )
            assert attempt_response.status_code == 201, attempt_response.text
            attempt = attempt_response.json()
            attempt_id = attempt["id"]
            assert "is_correct" not in str(attempt)
            assert "explanation" not in str(attempt)

            assert (await client.get(
                f"/api/v1/quizzes/attempts/{attempt_id}/results", headers=owner_headers
            )).status_code == 409
            assert (await client.get(
                f"/api/v1/quizzes/attempts/{attempt_id}/results", headers=other_headers
            )).status_code == 404

            questions = attempt["quiz"]["questions"]
            submission = {
                "answers": [
                    {
                        "question_id": questions[0]["id"],
                        "selected_option_id": questions[0]["options"][0]["id"],
                    },
                    {
                        "question_id": questions[1]["id"],
                        "selected_option_id": questions[1]["options"][1]["id"],
                    },
                ]
            }
            submitted = await client.post(
                f"/api/v1/quizzes/attempts/{attempt_id}/submit",
                headers=owner_headers,
                json=submission,
            )
            assert submitted.status_code == 200, submitted.text
            result = submitted.json()
            assert result["score"] == 1
            assert result["total_questions"] == 2
            assert result["percentage"] == 50.0
            assert [item["is_correct"] for item in result["questions"]] == [True, False]
            assert all(item["explanation"] for item in result["questions"])
            assert (await client.post(
                f"/api/v1/quizzes/attempts/{attempt_id}/submit",
                headers=owner_headers,
                json=submission,
            )).status_code == 409

            stored_result = await client.get(
                f"/api/v1/quizzes/attempts/{attempt_id}/results", headers=owner_headers
            )
            assert stored_result.status_code == 200
            assert stored_result.json()["score"] == 1

            rag.empty = True
            assert (await client.post(
                "/api/v1/quizzes/generate", headers=owner_headers, json=request
            )).status_code == 409
            rag.empty = False
            llm.mode = "wrong_count"
            assert (await client.post(
                "/api/v1/quizzes/generate", headers=owner_headers, json=request
            )).status_code == 502
            llm.mode = "bad_source"
            assert (await client.post(
                "/api/v1/quizzes/generate", headers=owner_headers, json=request
            )).status_code == 502
            llm.mode = "failure"
            assert (await client.post(
                "/api/v1/quizzes/generate", headers=owner_headers, json=request
            )).status_code == 503

        async with factory() as session:
            quiz = await session.scalar(select(Quiz).where(Quiz.id == generated_quiz_id))
            assert quiz is not None
            assert len((await session.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id))).all()) == 1
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(QuizAttempt).where(QuizAttempt.user_id.in_([owner.id, other.id])))
            await session.execute(delete(Quiz).where(Quiz.user_id.in_([owner.id, other.id])))
            await session.execute(delete(Document).where(Document.user_id.in_([owner.id, other.id])))
            await session.execute(delete(User).where(User.id.in_([owner.id, other.id])))
            await session.commit()
        await engine.dispose()
