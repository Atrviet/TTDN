from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401
from app.db.base import Base
from app.models.chat import ChatSession
from app.models.advanced_learning import (
    Flashcard,
    FlashcardDeck,
    KnowledgeConcept,
    StudyPlan,
    TopicMastery,
    TutorSession,
)
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
    "flashcard_decks",
    "flashcards",
    "flashcard_reviews",
    "flashcard_deck_documents",
    "study_plan_documents",
    "study_plans",
    "study_tasks",
    "study_availability",
    "tutor_sessions",
    "tutor_session_documents",
    "tutor_messages",
    "knowledge_concepts",
    "knowledge_relations",
    "knowledge_graphs",
    "knowledge_graph_documents",
    "knowledge_graph_concepts",
    "topic_mastery",
    "learning_recommendations",
    "learning_topic_mappings",
    "ai_generation_requests",
}


def constraint_names(table_name: str, constraint_type: type) -> set[str | None]:
    table = Base.metadata.tables[table_name]
    return {constraint.name for constraint in table.constraints if isinstance(constraint, constraint_type)}


def test_all_expected_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert all(
        table.primary_key.columns.keys() == ["id"]
        for name, table in Base.metadata.tables.items()
        if name not in {"tutor_session_documents", "flashcard_deck_documents", "study_plan_documents", "knowledge_graph_documents"}
    )
    assert list(Base.metadata.tables["tutor_session_documents"].primary_key.columns.keys()) == [
        "session_id",
        "document_id",
    ]
    assert list(Base.metadata.tables["flashcard_deck_documents"].primary_key.columns.keys()) == [
        "deck_id",
        "document_id",
    ]
    assert list(Base.metadata.tables["study_plan_documents"].primary_key.columns.keys()) == ["plan_id", "document_id"]
    assert list(Base.metadata.tables["knowledge_graph_documents"].primary_key.columns.keys()) == ["graph_id", "document_id"]


def test_mappers_and_required_relationships_are_configured() -> None:
    configure_mappers()

    assert {relationship.key for relationship in User.__mapper__.relationships} == {
        "documents",
        "chat_sessions",
        "quizzes",
        "quiz_attempts",
        "flashcard_decks",
        "study_plans",
        "tutor_sessions",
        "knowledge_concepts",
        "topic_mastery",
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
    assert {relationship.key for relationship in FlashcardDeck.__mapper__.relationships} == {
        "user", "document", "documents", "flashcards"
    }
    assert {relationship.key for relationship in Flashcard.__mapper__.relationships} == {
        "deck", "source_document", "source_chunk", "reviews"
    }
    assert {relationship.key for relationship in StudyPlan.__mapper__.relationships} == {
        "user", "tasks", "availability", "documents"
    }
    assert {relationship.key for relationship in TutorSession.__mapper__.relationships} == {
        "user", "documents", "messages"
    }
    assert {relationship.key for relationship in KnowledgeConcept.__mapper__.relationships} == {
        "user", "outgoing_relations", "incoming_relations", "mastery_records", "graph_sources"
    }
    assert {relationship.key for relationship in TopicMastery.__mapper__.relationships} == {
        "user", "concept", "recommendations"
    }


def test_ordering_and_answer_uniqueness_constraints_exist() -> None:
    assert "uq_document_chunks_document_order" in constraint_names("document_chunks", UniqueConstraint)
    assert "uq_questions_quiz_order" in constraint_names("questions", UniqueConstraint)
    assert "uq_answer_options_question_order" in constraint_names("answer_options", UniqueConstraint)
    assert "uq_user_answers_attempt_question" in constraint_names("user_answers", UniqueConstraint)
    assert "uq_flashcards_deck_order" in constraint_names("flashcards", UniqueConstraint)
    assert "uq_study_availability_plan_window" in constraint_names(
        "study_availability", UniqueConstraint
    )
    assert "uq_knowledge_concepts_user_name" in constraint_names(
        "knowledge_concepts", UniqueConstraint
    )
    assert "uq_topic_mastery_user_topic" in constraint_names("topic_mastery", UniqueConstraint)


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
        "flashcard_decks": {"CASCADE", "SET NULL"},
        "flashcards": {"CASCADE", "SET NULL"},
        "flashcard_reviews": {"CASCADE"},
        "flashcard_deck_documents": {"CASCADE"},
        "study_plan_documents": {"CASCADE"},
        "study_plans": {"CASCADE"},
        "study_tasks": {"CASCADE", "SET NULL"},
        "study_availability": {"CASCADE"},
        "tutor_sessions": {"CASCADE"},
        "tutor_session_documents": {"CASCADE"},
        "tutor_messages": {"CASCADE"},
        "knowledge_concepts": {"CASCADE"},
        "knowledge_relations": {"CASCADE", "SET NULL"},
        "knowledge_graphs": {"CASCADE"},
        "knowledge_graph_documents": {"CASCADE"},
        "knowledge_graph_concepts": {"CASCADE"},
        "topic_mastery": {"CASCADE", "SET NULL"},
        "learning_recommendations": {"CASCADE", "SET NULL"},
        "learning_topic_mappings": {"CASCADE", "SET NULL"},
        "ai_generation_requests": {"CASCADE"},
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
    timestamp_names = {
        "created_at", "updated_at", "started_at", "completed_at", "answered_at",
        "reviewed_at", "next_review_at", "planned_start_at", "due_at", "last_evidence_at",
        "expires_at", "last_practiced_at", "last_calculated_at",
    }
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if column.name in timestamp_names:
                assert column.type.timezone is True

