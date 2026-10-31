"""Add intelligent study planner fields.

Revision ID: 20261031_0008
Revises: 20261031_0007
Create Date: 2026-10-31
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261031_0008"
down_revision: str | None = "20261031_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE study_task_status ADD VALUE IF NOT EXISTS 'postponed'")
    op.add_column("study_plans", sa.Column("subject", sa.String(255), server_default="General", nullable=False))
    op.add_column("study_plans", sa.Column("difficulty", postgresql.ENUM("easy", "medium", "hard", name="quiz_difficulty", create_type=False), server_default="medium", nullable=False))
    op.add_column("study_plans", sa.Column("daily_available_minutes", sa.Integer(), server_default="60", nullable=False))
    op.add_column("study_plans", sa.Column("preferred_session_minutes", sa.Integer(), server_default="30", nullable=False))
    op.add_column("study_plans", sa.Column("available_days", postgresql.JSONB(), server_default="[0,1,2,3,4]", nullable=False))
    op.create_check_constraint("ck_study_plans_daily_minutes_positive", "study_plans", "daily_available_minutes > 0")
    op.create_check_constraint("ck_study_plans_session_minutes_positive", "study_plans", "preferred_session_minutes > 0")
    op.create_table(
        "study_plan_documents",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["study_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_id", "document_id"),
    )
    op.create_index("ix_study_plan_documents_document_id", "study_plan_documents", ["document_id"])
    op.add_column("study_tasks", sa.Column("topic", sa.String(255), server_default="General", nullable=False))
    op.add_column("study_tasks", sa.Column("task_type", sa.String(32), server_default="study", nullable=False))
    op.add_column("study_tasks", sa.Column("priority", sa.SmallInteger(), server_default="3", nullable=False))
    op.add_column("study_tasks", sa.Column("actual_duration_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_study_tasks_actual_duration_non_negative", "study_tasks", "actual_duration_minutes IS NULL OR actual_duration_minutes >= 0")
    op.create_check_constraint("ck_study_tasks_priority_range", "study_tasks", "priority BETWEEN 1 AND 5")


def downgrade() -> None:
    op.drop_constraint("ck_study_tasks_priority_range", "study_tasks", type_="check")
    op.drop_constraint("ck_study_tasks_actual_duration_non_negative", "study_tasks", type_="check")
    op.drop_column("study_tasks", "actual_duration_minutes")
    op.drop_column("study_tasks", "priority")
    op.drop_column("study_tasks", "task_type")
    op.drop_column("study_tasks", "topic")
    op.drop_table("study_plan_documents")
    op.drop_constraint("ck_study_plans_session_minutes_positive", "study_plans", type_="check")
    op.drop_constraint("ck_study_plans_daily_minutes_positive", "study_plans", type_="check")
    op.drop_column("study_plans", "available_days")
    op.drop_column("study_plans", "preferred_session_minutes")
    op.drop_column("study_plans", "daily_available_minutes")
    op.drop_column("study_plans", "difficulty")
    op.drop_column("study_plans", "subject")
