"""Add the advanced learning foundation schema.

Revision ID: 20261031_0006
Revises: 20261026_0005
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261031_0006"
down_revision: str | None = "20261026_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


flashcard_review_rating = postgresql.ENUM(
    "again", "hard", "good", "easy", name="flashcard_review_rating", create_type=False
)
study_plan_status = postgresql.ENUM(
    "draft", "active", "completed", "archived", name="study_plan_status", create_type=False
)
study_task_status = postgresql.ENUM(
    "pending", "in_progress", "completed", "skipped", name="study_task_status", create_type=False
)
learning_recommendation_status = postgresql.ENUM(
    "pending",
    "accepted",
    "dismissed",
    "completed",
    name="learning_recommendation_status",
    create_type=False,
)
chat_message_role = postgresql.ENUM(
    "user", "assistant", name="chat_message_role", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    flashcard_review_rating.create(bind, checkfirst=True)
    study_plan_status.create(bind, checkfirst=True)
    study_task_status.create(bind, checkfirst=True)
    learning_recommendation_status.create(bind, checkfirst=True)

    op.create_table(
        "flashcard_decks",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flashcard_decks_document_id", "flashcard_decks", ["document_id"])
    op.create_index("ix_flashcard_decks_user_id", "flashcard_decks", ["user_id"])
    op.create_index("ix_flashcard_decks_user_updated_at", "flashcard_decks", ["user_id", "updated_at"])

    op.create_table(
        "study_plans",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("status", study_plan_status, server_default="draft", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="Asia/Ho_Chi_Minh", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_study_plans_date_order"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_plans_user_id", "study_plans", ["user_id"])
    op.create_index("ix_study_plans_user_status", "study_plans", ["user_id", "status"])

    op.create_table(
        "tutor_sessions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("learning_objective", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tutor_sessions_user_id", "tutor_sessions", ["user_id"])
    op.create_index("ix_tutor_sessions_user_updated_at", "tutor_sessions", ["user_id", "updated_at"])

    op.create_table(
        "knowledge_concepts",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_knowledge_concepts_user_name"),
    )
    op.create_index("ix_knowledge_concepts_user_id", "knowledge_concepts", ["user_id"])
    op.create_index("ix_knowledge_concepts_user_updated_at", "knowledge_concepts", ["user_id", "updated_at"])

    op.create_table(
        "flashcards",
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("front_text", sa.Text(), nullable=False),
        sa.Column("back_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("card_order", sa.Integer(), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_page_number", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("card_order >= 0", name="ck_flashcards_order_non_negative"),
        sa.CheckConstraint(
            "source_page_number IS NULL OR source_page_number > 0",
            name="ck_flashcards_source_page_positive",
        ),
        sa.ForeignKeyConstraint(["deck_id"], ["flashcard_decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deck_id", "card_order", name="uq_flashcards_deck_order"),
    )
    op.create_index("ix_flashcards_deck_id", "flashcards", ["deck_id"])
    op.create_index("ix_flashcards_source_chunk_id", "flashcards", ["source_chunk_id"])
    op.create_index("ix_flashcards_source_document_id", "flashcards", ["source_document_id"])

    op.create_table(
        "study_tasks",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", study_task_status, server_default="pending", nullable=False),
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("planned_duration_minutes > 0", name="ck_study_tasks_duration_positive"),
        sa.CheckConstraint(
            "completed_at IS NULL OR status = 'completed'",
            name="ck_study_tasks_completion_requires_completed_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_study_tasks_document_id", "study_tasks", ["document_id"])
    op.create_index("ix_study_tasks_plan_id", "study_tasks", ["plan_id"])
    op.create_index("ix_study_tasks_plan_status_due", "study_tasks", ["plan_id", "status", "due_at"])

    op.create_table(
        "study_availability",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_study_availability_day_range"),
        sa.CheckConstraint("end_time > start_time", name="ck_study_availability_time_order"),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "plan_id", "day_of_week", "start_time", "end_time",
            name="uq_study_availability_plan_window",
        ),
    )
    op.create_index("ix_study_availability_plan_id", "study_availability", ["plan_id"])

    op.create_table(
        "tutor_session_documents",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["tutor_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "document_id"),
    )
    op.create_index("ix_tutor_session_documents_document_id", "tutor_session_documents", ["document_id"])

    op.create_table(
        "tutor_messages",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", chat_message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["tutor_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tutor_messages_session_created_at", "tutor_messages", ["session_id", "created_at"])

    op.create_table(
        "knowledge_relations",
        sa.Column("source_concept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_concept_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_knowledge_relations_confidence_range"),
        sa.CheckConstraint("source_concept_id <> target_concept_id", name="ck_knowledge_relations_distinct"),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_concept_id", "target_concept_id", "relation_type", "document_id",
            name="uq_knowledge_relations_edge_provenance",
        ),
    )
    op.create_index("ix_knowledge_relations_document_chunk_id", "knowledge_relations", ["document_chunk_id"])
    op.create_index("ix_knowledge_relations_document_id", "knowledge_relations", ["document_id"])
    op.create_index("ix_knowledge_relations_source_type", "knowledge_relations", ["source_concept_id", "relation_type"])
    op.create_index("ix_knowledge_relations_target_id", "knowledge_relations", ["target_concept_id"])

    op.create_table(
        "topic_mastery",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("concept_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("topic_key", sa.String(255), nullable=False),
        sa.Column("topic_name", sa.String(255), nullable=False),
        sa.Column("mastery_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("evidence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("evidence_count >= 0", name="ck_topic_mastery_evidence_non_negative"),
        sa.CheckConstraint("mastery_score BETWEEN 0 AND 1", name="ck_topic_mastery_score_range"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_concepts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "topic_key", name="uq_topic_mastery_user_topic"),
    )
    op.create_index("ix_topic_mastery_concept_id", "topic_mastery", ["concept_id"])
    op.create_index("ix_topic_mastery_user_id", "topic_mastery", ["user_id"])
    op.create_index("ix_topic_mastery_user_score", "topic_mastery", ["user_id", "mastery_score"])

    op.create_table(
        "flashcard_reviews",
        sa.Column("flashcard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", flashcard_review_rating, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("ease_factor", sa.Numeric(4, 2), nullable=False),
        sa.Column("repetition_count", sa.Integer(), nullable=False),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("ease_factor >= 1.0", name="ck_flashcard_reviews_ease_factor_minimum"),
        sa.CheckConstraint("interval_days >= 0", name="ck_flashcard_reviews_interval_non_negative"),
        sa.CheckConstraint("repetition_count >= 0", name="ck_flashcard_reviews_repetition_non_negative"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flashcard_reviews_card_reviewed_at", "flashcard_reviews", ["flashcard_id", "reviewed_at"])
    op.create_index("ix_flashcard_reviews_flashcard_id", "flashcard_reviews", ["flashcard_id"])
    op.create_index("ix_flashcard_reviews_next_review_at", "flashcard_reviews", ["next_review_at"])

    op.create_table(
        "learning_recommendations",
        sa.Column("topic_mastery_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recommendation_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", learning_recommendation_status, server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_mastery_id"], ["topic_mastery.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learning_recommendations_document_id", "learning_recommendations", ["document_id"])
    op.create_index("ix_learning_recommendations_mastery_status", "learning_recommendations", ["topic_mastery_id", "status"])
    op.create_index("ix_learning_recommendations_topic_mastery_id", "learning_recommendations", ["topic_mastery_id"])


def downgrade() -> None:
    op.drop_table("learning_recommendations")
    op.drop_table("flashcard_reviews")
    op.drop_table("topic_mastery")
    op.drop_table("knowledge_relations")
    op.drop_table("tutor_messages")
    op.drop_table("tutor_session_documents")
    op.drop_table("study_availability")
    op.drop_table("study_tasks")
    op.drop_table("flashcards")
    op.drop_table("knowledge_concepts")
    op.drop_table("tutor_sessions")
    op.drop_table("study_plans")
    op.drop_table("flashcard_decks")

    bind = op.get_bind()
    learning_recommendation_status.drop(bind, checkfirst=True)
    study_task_status.drop(bind, checkfirst=True)
    study_plan_status.drop(bind, checkfirst=True)
    flashcard_review_rating.drop(bind, checkfirst=True)
