"""Add completed-at index for learning analytics.

Revision ID: 20261026_0005
Revises: 20261026_0004
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20261026_0005"
down_revision: str | None = "20261026_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_quiz_attempts_user_completed_at",
        "quiz_attempts",
        ["user_id", "completed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_attempts_user_completed_at", table_name="quiz_attempts")
