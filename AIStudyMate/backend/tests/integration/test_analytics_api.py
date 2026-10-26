import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.common import DocumentProcessingStatus, QuizDifficulty, UserRole
from app.models.document import Document
from app.models.quiz import AnswerOption, Question, Quiz, QuizAttempt, UserAnswer
from app.models.user import User


def safe_test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(value)
    if parsed.get_backend_name() != "postgresql" or not parsed.database or "test" not in parsed.database:
        pytest.fail("A dedicated PostgreSQL test database is required")
    return value


def document(user_id, suffix: str) -> Document:
    return Document(
        user_id=user_id,
        title=f"Analytics Document {suffix}",
        original_filename=f"analytics-{suffix}.pdf",
        file_path=f"{user_id}/analytics-{suffix}.pdf",
        file_size=100,
        mime_type="application/pdf",
        processing_status=DocumentProcessingStatus.READY,
        page_count=1,
        extracted_pages=[{"page_number": 1, "text": "analytics"}],
        pdf_metadata={},
        requires_ocr=False,
    )


def question(text: str, order: int) -> Question:
    item = Question(question_text=text, explanation="Explanation", question_order=order)
    item.answer_options = [
        AnswerOption(option_text="Correct", is_correct=True, option_order=0),
        AnswerOption(option_text="Wrong", is_correct=False, option_order=1),
        AnswerOption(option_text="Wrong 2", is_correct=False, option_order=2),
        AnswerOption(option_text="Wrong 3", is_correct=False, option_order=3),
    ]
    return item


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analytics_metrics_empty_filtering_isolation_and_pagination() -> None:
    engine = create_async_engine(safe_test_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_session():
        async with factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    owner, other, empty_user = [
        User(
            username=f"analytics_{label}_{suffix}",
            email=f"analytics_{label}_{suffix}@example.com",
            hashed_password=hash_password("SecurePassword123"),
            full_name=f"Analytics {label}",
            role=UserRole.STUDENT,
        )
        for label in ("owner", "other", "empty")
    ]
    async with factory() as session:
        session.add_all([owner, other, empty_user])
        await session.flush()
        owner_document = document(owner.id, suffix)
        other_document = document(other.id, f"other-{suffix}")
        session.add_all([owner_document, other_document])
        await session.flush()

        quiz_a = Quiz(
            user_id=owner.id,
            document_id=owner_document.id,
            title="RAG Basics",
            difficulty=QuizDifficulty.MEDIUM,
        )
        quiz_a.questions = [question("RAG Q1", 0), question("RAG Q2", 1)]
        quiz_b = Quiz(
            user_id=owner.id,
            document_id=owner_document.id,
            title="Vector Search",
            difficulty=QuizDifficulty.HARD,
        )
        quiz_b.questions = [question("Vector Q1", 0)]
        other_quiz = Quiz(
            user_id=other.id,
            document_id=other_document.id,
            title="Private Perfect Quiz",
            difficulty=QuizDifficulty.EASY,
        )
        other_quiz.questions = [question("Private Q1", 0)]
        session.add_all([quiz_a, quiz_b, other_quiz])
        await session.flush()

        attempts = [
            QuizAttempt(
                quiz_id=quiz_a.id,
                user_id=owner.id,
                score=2,
                total_questions=2,
                started_at=datetime(2026, 10, 20, 9, tzinfo=UTC),
                completed_at=datetime(2026, 10, 20, 9, 10, tzinfo=UTC),
            ),
            QuizAttempt(
                quiz_id=quiz_a.id,
                user_id=owner.id,
                score=1,
                total_questions=2,
                started_at=datetime(2026, 10, 21, 9, tzinfo=UTC),
                completed_at=datetime(2026, 10, 21, 9, 10, tzinfo=UTC),
            ),
            QuizAttempt(
                quiz_id=quiz_b.id,
                user_id=owner.id,
                score=0,
                total_questions=1,
                started_at=datetime(2026, 10, 21, 10, tzinfo=UTC),
                completed_at=datetime(2026, 10, 21, 10, 10, tzinfo=UTC),
            ),
            QuizAttempt(
                quiz_id=quiz_a.id,
                user_id=owner.id,
                score=0,
                total_questions=2,
                started_at=datetime(2026, 10, 22, 9, tzinfo=UTC),
                completed_at=None,
            ),
            QuizAttempt(
                quiz_id=other_quiz.id,
                user_id=other.id,
                score=1,
                total_questions=1,
                started_at=datetime(2026, 10, 21, 11, tzinfo=UTC),
                completed_at=datetime(2026, 10, 21, 11, 5, tzinfo=UTC),
            ),
        ]
        session.add_all(attempts)
        await session.flush()

        answer_rows = []
        outcomes = [
            [True, True],
            [True, False],
            [False],
            [],
            [True],
        ]
        quizzes = [quiz_a, quiz_a, quiz_b, quiz_a, other_quiz]
        for attempt, source_quiz, correctness in zip(attempts, quizzes, outcomes, strict=True):
            if not correctness:
                continue
            for source_question, is_correct in zip(source_quiz.questions, correctness, strict=True):
                selected = source_question.answer_options[0 if is_correct else 1]
                answer_rows.append(
                    UserAnswer(
                        attempt_id=attempt.id,
                        question_id=source_question.id,
                        selected_option_id=selected.id,
                        is_correct=is_correct,
                    )
                )
        session.add_all(answer_rows)
        await session.commit()

    users = [owner, other, empty_user]
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
        for user in users
    ]
    app.dependency_overrides[get_db_session] = override_session

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            overview = await client.get("/api/v1/analytics/overview", headers=headers[0])
            assert overview.status_code == 200, overview.text
            body = overview.json()
            assert body["total_quizzes_attempted"] == 3
            assert body["average_score_percentage"] == 50.0
            assert body["highest_score_percentage"] == 100.0
            assert body["total_correct_answers"] == 3
            assert body["total_answered_questions"] == 5
            assert [item["quiz_title"] for item in body["latest_results"]] == [
                "Vector Search",
                "RAG Basics",
                "RAG Basics",
            ]
            assert {item["quiz_title"] for item in body["accuracy_by_quiz"]} == {
                "RAG Basics",
                "Vector Search",
            }

            progress = await client.get("/api/v1/analytics/progress", headers=headers[0])
            assert progress.status_code == 200
            assert progress.json()["points"] == [
                {
                    "date": "2026-10-20",
                    "attempts": 1,
                    "average_score_percentage": 100.0,
                    "correct_answers": 2,
                    "total_questions": 2,
                },
                {
                    "date": "2026-10-21",
                    "attempts": 2,
                    "average_score_percentage": 25.0,
                    "correct_answers": 1,
                    "total_questions": 3,
                },
            ]

            filtered = await client.get(
                "/api/v1/analytics/overview?date_from=2026-10-21&date_to=2026-10-21",
                headers=headers[0],
            )
            assert filtered.status_code == 200
            assert filtered.json()["total_quizzes_attempted"] == 2
            assert filtered.json()["average_score_percentage"] == 25.0

            history_page_one = await client.get(
                "/api/v1/analytics/quiz-history?page=1&per_page=2", headers=headers[0]
            )
            history_page_two = await client.get(
                "/api/v1/analytics/quiz-history?page=2&per_page=2", headers=headers[0]
            )
            assert history_page_one.json()["total"] == 3
            assert history_page_one.json()["pages"] == 2
            assert len(history_page_one.json()["items"]) == 2
            assert len(history_page_two.json()["items"]) == 1

            weak = await client.get("/api/v1/analytics/weak-topics", headers=headers[0])
            assert weak.status_code == 200
            assert weak.json()["topic_basis"] == "quiz_title"
            assert [item["topic"] for item in weak.json()["items"]] == [
                "Vector Search",
                "RAG Basics",
            ]
            assert [item["accuracy_percentage"] for item in weak.json()["items"]] == [0.0, 75.0]

            isolated = await client.get("/api/v1/analytics/overview", headers=headers[1])
            assert isolated.json()["total_quizzes_attempted"] == 1
            assert isolated.json()["latest_results"][0]["quiz_title"] == "Private Perfect Quiz"

            empty = await client.get("/api/v1/analytics/overview", headers=headers[2])
            assert empty.json()["total_quizzes_attempted"] == 0
            assert empty.json()["average_score_percentage"] is None
            assert empty.json()["highest_score_percentage"] is None
            assert empty.json()["latest_results"] == []
            assert (await client.get(
                "/api/v1/analytics/progress", headers=headers[2]
            )).json()["points"] == []

            invalid = await client.get(
                "/api/v1/analytics/overview?date_from=2026-10-22&date_to=2026-10-20",
                headers=headers[0],
            )
            assert invalid.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        async with factory() as session:
            await session.execute(delete(QuizAttempt).where(QuizAttempt.user_id.in_([user.id for user in users])))
            await session.execute(delete(Quiz).where(Quiz.user_id.in_([user.id for user in users])))
            await session.execute(delete(Document).where(Document.user_id.in_([user.id for user in users])))
            await session.execute(delete(User).where(User.id.in_([user.id for user in users])))
            await session.commit()
        await engine.dispose()
