import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "users",
    "documents",
    "document_chunks",
    "chat_sessions",
    "chat_messages",
    "quizzes",
    "questions",
    "answer_options",
    "quiz_attempts",
    "user_answers",
    "flashcard_decks",
    "flashcards",
    "flashcard_reviews",
    "study_plans",
    "study_tasks",
    "study_availability",
    "tutor_sessions",
    "tutor_session_documents",
    "tutor_messages",
    "knowledge_concepts",
    "knowledge_relations",
    "topic_mastery",
    "learning_recommendations",
}


def get_safe_test_database_url() -> str:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    parsed_test_url = make_url(test_url)
    development_url = os.getenv("DATABASE_URL")
    if parsed_test_url.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not parsed_test_url.database or "test" not in parsed_test_url.database.lower():
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")
    if development_url and make_url(development_url) == parsed_test_url:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL")
    return test_url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgresql_connectivity() -> None:
    engine = create_async_engine(get_safe_test_database_url())
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_migration_upgrade_downgrade_and_foreign_keys() -> None:
    test_url = get_safe_test_database_url()
    environment = os.environ.copy()
    environment["DATABASE_URL"] = test_url
    environment["APP_ENV"] = "testing"

    def run_alembic(*arguments: str) -> None:
        subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=BACKEND_DIR,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

    # This test is intentionally destructive only for the explicitly named test database.
    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")

    engine = create_async_engine(test_url)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda sync_connection: set(inspect(sync_connection).get_table_names()))
            foreign_keys = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_foreign_keys("document_chunks")
            )
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert EXPECTED_TABLES <= tables
        assert version == "20261031_0006"
        assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    finally:
        await engine.dispose()

    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")

