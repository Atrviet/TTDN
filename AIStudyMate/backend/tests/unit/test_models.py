from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db.base import Base
from app.models.chat import ChatSession
from app.models.document import Document
from app.models.quiz import Question, Quiz, QuizAttempt
from app.models.user import User


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
}


def constraint_names(table_name: str, constraint_type: type) -> set[str | None]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if isinstance(constraint, constraint_type)}


def test_all_expected_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert all(table.primary_key.columns.keys() == ["id"] for table in Base.metadata.tables.values())


def test_mappers_and_required_relationships_are_configured() -> None:
    configure_mappers()

    assert {relationship.key for relationship in User.__mapper__.relationships} == {
        "documents",
        "chat_sessions",
        "quizzes",
        "quiz_attempts",
    }
    assert {relationship.key for relationship in Document.__mapper__.relationships} == {
        "user",
        "chunks",
        "quizzes",
    }
    assert {relationship.key for relationship in ChatSession.__mapper__.relationships} == {
        "user",
        "messages",
    }
    assert {relationship.key for relationship in Quiz.__mapper__.relationships} == {
        "user",
        "document",
        "questions",
        "attempts",
    }
    assert {relationship.key for relationship in Question.__mapper__.relationships} == {
        "quiz",
        "answer_options",
    }
    assert {relationship.key for relationship in QuizAttempt.__mapper__.relationships} == {
        "quiz",
        "user",
        "user_answers",
    }


def test_ordering_and_answer_uniqueness_constraints_exist() -> None:
    assert "uq_document_chunks_document_order" in constraint_names("document_chunks", UniqueConstraint)
    assert "uq_questions_quiz_order" in constraint_names("questions", UniqueConstraint)
    assert "uq_answer_options_question_order" in constraint_names("answer_options", UniqueConstraint)
    assert "uq_user_answers_attempt_question" in constraint_names("user_answers", UniqueConstraint)


def test_numeric_check_constraints_exist() -> None:
    expected = {
        "documents": {"ck_documents_file_size_non_negative", "ck_documents_page_count_positive"},
        "document_chunks": {
            "ck_document_chunks_index_non_negative",
            "ck_document_chunks_page_positive",
            "ck_document_chunks_token_count_non_negative",
        },
        "quiz_attempts": {
            "ck_quiz_attempts_score_non_negative",
            "ck_quiz_attempts_total_questions_positive",
            "ck_quiz_attempts_score_within_total",
            "ck_quiz_attempts_completion_after_start",
        },
    }
    for table_name, names in expected.items():
        assert names <= constraint_names(table_name, CheckConstraint)


def test_foreign_key_delete_behaviors_are_explicit() -> None:
    expected = {
        "documents": {"RESTRICT"},
        "document_chunks": {"CASCADE"},
        "chat_sessions": {"RESTRICT"},
        "chat_messages": {"CASCADE"},
        "quizzes": {"RESTRICT"},
        "questions": {"CASCADE"},
        "answer_options": {"CASCADE"},
        "quiz_attempts": {"RESTRICT"},
        "user_answers": {"CASCADE", "RESTRICT"},
    }
    for table_name, actions in expected.items():
        foreign_keys = {
            constraint.ondelete
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, ForeignKeyConstraint)
        }
        assert foreign_keys == actions


def test_unique_identity_indexes_exist() -> None:
    unique_indexes = {
        index.name
        for table in Base.metadata.tables.values()
        for index in table.indexes
        if index.unique
    }
    assert {"ix_users_username", "ix_users_email", "ix_document_chunks_chroma_id"} <= unique_indexes


def test_all_timestamps_are_timezone_aware() -> None:
    timestamp_names = {"created_at", "updated_at", "started_at", "completed_at", "answered_at"}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name in timestamp_names:
                assert column.type.timezone is True

