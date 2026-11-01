from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.common import (
    ChatMessageRole,
    FlashcardReviewRating,
    RecommendationStatus,
    StudyPlanStatus,
    StudyTaskStatus,
    QuizDifficulty,
)

if TYPE_CHECKING:
    from app.models.document import Document, DocumentChunk
    from app.models.user import User


tutor_session_documents = Table(
    "tutor_session_documents",
    Base.metadata,
    Column(
        "session_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "document_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_tutor_session_documents_document_id", "document_id"),
)


flashcard_deck_documents = Table(
    "flashcard_deck_documents",
    Base.metadata,
    Column(
        "deck_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("flashcard_decks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "document_id",
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Index("ix_flashcard_deck_documents_document_id", "document_id"),
)


study_plan_documents = Table(
    "study_plan_documents",
    Base.metadata,
    Column("plan_id", PostgreSQLUUID(as_uuid=True), ForeignKey("study_plans.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", PostgreSQLUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_study_plan_documents_document_id", "document_id"),
)

knowledge_graph_documents = Table(
    "knowledge_graph_documents",
    Base.metadata,
    Column("graph_id", PostgreSQLUUID(as_uuid=True), ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), primary_key=True),
    Column("document_id", PostgreSQLUUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_knowledge_graph_documents_document_id", "document_id"),
)


class FlashcardDeck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flashcard_decks"
    __table_args__ = (Index("ix_flashcard_decks_user_updated_at", "user_id", "updated_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="flashcard_decks")
    document: Mapped[Document | None] = relationship()
    documents: Mapped[list[Document]] = relationship(secondary=flashcard_deck_documents)
    flashcards: Mapped[list[Flashcard]] = relationship(
        back_populates="deck", cascade="all, delete-orphan", passive_deletes=True
    )


class Flashcard(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        UniqueConstraint("deck_id", "card_order", name="uq_flashcards_deck_order"),
        CheckConstraint("card_order >= 0", name="ck_flashcards_order_non_negative"),
        CheckConstraint(
            "source_page_number IS NULL OR source_page_number > 0",
            name="ck_flashcards_source_page_positive",
        ),
    )

    deck_id: Mapped[UUID] = mapped_column(
        ForeignKey("flashcard_decks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    front_text: Mapped[str] = mapped_column(Text, nullable=False)
    back_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    card_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    source_chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), index=True
    )
    source_page_number: Mapped[int | None] = mapped_column(Integer)

    deck: Mapped[FlashcardDeck] = relationship(back_populates="flashcards")
    source_document: Mapped[Document | None] = relationship(foreign_keys=[source_document_id])
    source_chunk: Mapped[DocumentChunk | None] = relationship(foreign_keys=[source_chunk_id])
    reviews: Mapped[list[FlashcardReview]] = relationship(
        back_populates="flashcard", cascade="all, delete-orphan", passive_deletes=True
    )


class FlashcardReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "flashcard_reviews"
    __table_args__ = (
        CheckConstraint("interval_days >= 0", name="ck_flashcard_reviews_interval_non_negative"),
        CheckConstraint("ease_factor >= 1.0", name="ck_flashcard_reviews_ease_factor_minimum"),
        CheckConstraint("repetition_count >= 0", name="ck_flashcard_reviews_repetition_non_negative"),
        Index("ix_flashcard_reviews_card_reviewed_at", "flashcard_id", "reviewed_at"),
        Index("ix_flashcard_reviews_next_review_at", "next_review_at"),
    )

    flashcard_id: Mapped[UUID] = mapped_column(
        ForeignKey("flashcards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rating: Mapped[FlashcardReviewRating] = mapped_column(
        Enum(
            FlashcardReviewRating,
            name="flashcard_review_rating",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
    )
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False)
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    repetition_count: Mapped[int] = mapped_column(Integer, nullable=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    flashcard: Mapped[Flashcard] = relationship(back_populates="reviews")


class StudyPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_plans"
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="ck_study_plans_date_order"),
        CheckConstraint("daily_available_minutes > 0", name="ck_study_plans_daily_minutes_positive"),
        CheckConstraint("preferred_session_minutes > 0", name="ck_study_plans_session_minutes_positive"),
        Index("ix_study_plans_user_status", "user_id", "status"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, server_default="General")
    difficulty: Mapped[QuizDifficulty] = mapped_column(
        Enum(QuizDifficulty, name="quiz_difficulty", values_callable=lambda enum: [item.value for item in enum], create_type=False),
        nullable=False, default=QuizDifficulty.MEDIUM, server_default=QuizDifficulty.MEDIUM.value,
    )
    daily_available_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="60")
    preferred_session_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    available_days: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default="[0,1,2,3,4]")
    status: Mapped[StudyPlanStatus] = mapped_column(
        Enum(
            StudyPlanStatus,
            name="study_plan_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=StudyPlanStatus.DRAFT,
        server_default=StudyPlanStatus.DRAFT.value,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Asia/Ho_Chi_Minh")

    user: Mapped[User] = relationship(back_populates="study_plans")
    tasks: Mapped[list[StudyTask]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )
    availability: Mapped[list[StudyAvailability]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list[Document]] = relationship(secondary=study_plan_documents)


class StudyTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_tasks"
    __table_args__ = (
        CheckConstraint("planned_duration_minutes > 0", name="ck_study_tasks_duration_positive"),
        CheckConstraint(
            "completed_at IS NULL OR status = 'completed'",
            name="ck_study_tasks_completion_requires_completed_status",
        ),
        Index("ix_study_tasks_plan_status_due", "plan_id", "status", "due_at"),
        CheckConstraint("actual_duration_minutes IS NULL OR actual_duration_minutes >= 0", name="ck_study_tasks_actual_duration_non_negative"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="ck_study_tasks_priority_range"),
    )

    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(255), nullable=False, server_default="General")
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default="study")
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="3")
    status: Mapped[StudyTaskStatus] = mapped_column(
        Enum(
            StudyTaskStatus,
            name="study_task_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=StudyTaskStatus.PENDING,
        server_default=StudyTaskStatus.PENDING.value,
    )
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[StudyPlan] = relationship(back_populates="tasks")
    document: Mapped[Document | None] = relationship()


class StudyAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "study_availability"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 0 AND 6", name="ck_study_availability_day_range"),
        CheckConstraint("end_time > start_time", name="ck_study_availability_time_order"),
        UniqueConstraint(
            "plan_id", "day_of_week", "start_time", "end_time",
            name="uq_study_availability_plan_window",
        ),
    )

    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    plan: Mapped[StudyPlan] = relationship(back_populates="availability")


class TutorSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tutor_sessions"
    __table_args__ = (Index("ix_tutor_sessions_user_updated_at", "user_id", "updated_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    learning_objective: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="tutor_sessions")
    documents: Mapped[list[Document]] = relationship(secondary=tutor_session_documents)
    messages: Mapped[list[TutorMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True,
        order_by="TutorMessage.created_at",
    )


class TutorMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "tutor_messages"
    __table_args__ = (Index("ix_tutor_messages_session_created_at", "session_id", "created_at"),)

    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[ChatMessageRole] = mapped_column(
        Enum(
            ChatMessageRole,
            name="chat_message_role",
            values_callable=lambda enum: [item.value for item in enum],
            create_type=False,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    token_usage: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[TutorSession] = relationship(back_populates="messages")


class KnowledgeGraph(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_graphs"
    __table_args__ = (Index("ix_knowledge_graphs_user_updated_at", "user_id", "updated_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship()
    documents: Mapped[list[Document]] = relationship(secondary=knowledge_graph_documents)
    concept_sources: Mapped[list[KnowledgeGraphConcept]] = relationship(back_populates="graph", cascade="all, delete-orphan", passive_deletes=True)
    relations: Mapped[list[KnowledgeRelation]] = relationship(back_populates="graph", cascade="all, delete-orphan", passive_deletes=True)


class KnowledgeGraphConcept(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_graph_concepts"
    __table_args__ = (
        UniqueConstraint("graph_id", "concept_id", "document_chunk_id", name="uq_knowledge_graph_concept_source"),
        CheckConstraint("page_number > 0", name="ck_knowledge_graph_concepts_page_positive"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_knowledge_graph_concepts_confidence_range"),
        Index("ix_knowledge_graph_concepts_graph_concept", "graph_id", "concept_id"),
    )

    graph_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), nullable=False)
    concept_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    document_chunk_id: Mapped[UUID] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    definition: Mapped[str | None] = mapped_column(Text)

    graph: Mapped[KnowledgeGraph] = relationship(back_populates="concept_sources")
    concept: Mapped[KnowledgeConcept] = relationship(back_populates="graph_sources")
    document: Mapped[Document] = relationship()
    document_chunk: Mapped[DocumentChunk] = relationship()


class KnowledgeConcept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_concepts"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_knowledge_concepts_user_name"),
        Index("ix_knowledge_concepts_user_updated_at", "user_id", "updated_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="knowledge_concepts")
    outgoing_relations: Mapped[list[KnowledgeRelation]] = relationship(
        back_populates="source_concept", foreign_keys="KnowledgeRelation.source_concept_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    incoming_relations: Mapped[list[KnowledgeRelation]] = relationship(
        back_populates="target_concept", foreign_keys="KnowledgeRelation.target_concept_id",
        cascade="all, delete-orphan", passive_deletes=True,
    )
    mastery_records: Mapped[list[TopicMastery]] = relationship(back_populates="concept")
    graph_sources: Mapped[list[KnowledgeGraphConcept]] = relationship(back_populates="concept", cascade="all, delete-orphan", passive_deletes=True)


class KnowledgeRelation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (
        CheckConstraint("source_concept_id <> target_concept_id", name="ck_knowledge_relations_distinct"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_knowledge_relations_confidence_range"),
        UniqueConstraint("graph_id", "source_concept_id", "target_concept_id", "relation_type", "document_chunk_id", name="uq_knowledge_relations_graph_edge_source"),
        Index("ix_knowledge_relations_source_type", "source_concept_id", "relation_type"),
        Index("ix_knowledge_relations_target_id", "target_concept_id"),
    )

    graph_id: Mapped[UUID | None] = mapped_column(ForeignKey("knowledge_graphs.id", ondelete="CASCADE"), index=True)
    source_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), nullable=False
    )
    target_concept_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    document_chunk_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), index=True
    )
    page_number: Mapped[int | None] = mapped_column(Integer)

    graph: Mapped[KnowledgeGraph | None] = relationship(back_populates="relations")
    source_concept: Mapped[KnowledgeConcept] = relationship(
        back_populates="outgoing_relations", foreign_keys=[source_concept_id]
    )
    target_concept: Mapped[KnowledgeConcept] = relationship(
        back_populates="incoming_relations", foreign_keys=[target_concept_id]
    )
    document: Mapped[Document | None] = relationship(foreign_keys=[document_id])
    document_chunk: Mapped[DocumentChunk | None] = relationship(foreign_keys=[document_chunk_id])


class TopicMastery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topic_mastery"
    __table_args__ = (
        CheckConstraint("mastery_score BETWEEN 0 AND 1", name="ck_topic_mastery_score_range"),
        CheckConstraint("evidence_count >= 0", name="ck_topic_mastery_evidence_non_negative"),
        UniqueConstraint("user_id", "topic_key", name="uq_topic_mastery_user_topic"),
        Index("ix_topic_mastery_user_score", "user_id", "mastery_score"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("knowledge_concepts.id", ondelete="SET NULL"), index=True
    )
    topic_key: Mapped[str] = mapped_column(String(255), nullable=False)
    topic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mastery_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="topic_mastery")
    concept: Mapped[KnowledgeConcept | None] = relationship(back_populates="mastery_records")
    recommendations: Mapped[list[LearningRecommendation]] = relationship(
        back_populates="topic_mastery", cascade="all, delete-orphan", passive_deletes=True
    )


class LearningRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_recommendations"
    __table_args__ = (Index("ix_learning_recommendations_mastery_status", "topic_mastery_id", "status"),)

    topic_mastery_id: Mapped[UUID] = mapped_column(
        ForeignKey("topic_mastery.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), index=True
    )
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RecommendationStatus] = mapped_column(
        Enum(
            RecommendationStatus,
            name="learning_recommendation_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=RecommendationStatus.PENDING,
        server_default=RecommendationStatus.PENDING.value,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    topic_mastery: Mapped[TopicMastery] = relationship(back_populates="recommendations")
    document: Mapped[Document | None] = relationship()
