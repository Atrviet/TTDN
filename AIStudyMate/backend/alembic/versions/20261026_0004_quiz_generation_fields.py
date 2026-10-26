"""Add AI quiz generation metadata.

Revision ID: 20261026_0004
Revises: 20261022_0003
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261026_0004"
down_revision: str | None = "20261022_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


quiz_difficulty = postgresql.ENUM(
    "easy", "medium", "hard", name="quiz_difficulty", create_type=False
)


def upgrade() -> None:
    quiz_difficulty.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "quizzes",
        sa.Column("difficulty", quiz_difficulty, server_default="medium", nullable=False),
    )
    op.add_column(
        "questions",
        sa.Column("source_references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("questions", "source_references")
    op.drop_column("quizzes", "difficulty")
    quiz_difficulty.drop(op.get_bind(), checkfirst=True)
