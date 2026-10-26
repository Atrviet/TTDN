from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.common import QuizDifficulty

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.user import User


class Quiz(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quizzes"
    __table_args__ = (Index("ix_quizzes_user_created_at", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[QuizDifficulty] = mapped_column(
        Enum(
            QuizDifficulty,
            name="quiz_difficulty",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=QuizDifficulty.MEDIUM,
        server_default=QuizDifficulty.MEDIUM.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="quizzes")
    document: Mapped[Document] = relationship(back_populates="quizzes")
    questions: Mapped[list[Question]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Question.question_order",
    )
    attempts: Mapped[list[QuizAttempt]] = relationship(back_populates="quiz", passive_deletes=True)


class Question(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("quiz_id", "question_order", name="uq_questions_quiz_order"),
        CheckConstraint("question_order >= 0", name="ck_questions_order_non_negative"),
    )

    quiz_id: Mapped[UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    source_references: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    question_order: Mapped[int] = mapped_column(Integer, nullable=False)

    quiz: Mapped[Quiz] = relationship(back_populates="questions")
    answer_options: Mapped[list[AnswerOption]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AnswerOption.option_order",
    )


class AnswerOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "answer_options"
    __table_args__ = (
        UniqueConstraint("question_id", "option_order", name="uq_answer_options_question_order"),
        CheckConstraint("option_order >= 0", name="ck_answer_options_order_non_negative"),
    )

    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    option_order: Mapped[int] = mapped_column(Integer, nullable=False)

    question: Mapped[Question] = relationship(back_populates="answer_options")


class QuizAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint("score >= 0", name="ck_quiz_attempts_score_non_negative"),
        CheckConstraint("total_questions > 0", name="ck_quiz_attempts_total_questions_positive"),
        CheckConstraint("score <= total_questions", name="ck_quiz_attempts_score_within_total"),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= started_at",
            name="ck_quiz_attempts_completion_after_start",
        ),
        Index("ix_quiz_attempts_user_started_at", "user_id", "started_at"),
        Index("ix_quiz_attempts_user_completed_at", "user_id", "completed_at"),
    )

    quiz_id: Mapped[UUID] = mapped_column(
        ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    quiz: Mapped[Quiz] = relationship(back_populates="attempts")
    user: Mapped[User] = relationship(back_populates="quiz_attempts")
    user_answers: Mapped[list[UserAnswer]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserAnswer(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id", name="uq_user_answers_attempt_question"),)

    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[UUID] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    selected_option_id: Mapped[UUID] = mapped_column(
        ForeignKey("answer_options.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    attempt: Mapped[QuizAttempt] = relationship(back_populates="user_answers")

