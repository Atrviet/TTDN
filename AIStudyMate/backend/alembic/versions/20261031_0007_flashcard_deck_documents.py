"""Add multi-document sources for flashcard decks.

Revision ID: 20261031_0007
Revises: 20261031_0006
Create Date: 2026-10-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261031_0007"
down_revision: str | None = "20261031_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "flashcard_deck_documents",
        sa.Column("deck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["deck_id"], ["flashcard_decks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("deck_id", "document_id"),
    )
    op.create_index(
        "ix_flashcard_deck_documents_document_id",
        "flashcard_deck_documents",
        ["document_id"],
    )
    op.execute(
        "INSERT INTO flashcard_deck_documents (deck_id, document_id) "
        "SELECT id, document_id FROM flashcard_decks WHERE document_id IS NOT NULL "
        "ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("flashcard_deck_documents")
