"""Add RAG indexing state to documents.

Revision ID: 20261022_0003
Revises: 20261022_0002
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261022_0003"
down_revision: str | None = "20261022_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


rag_indexing_status = postgresql.ENUM(
    "not_indexed",
    "indexing",
    "indexed",
    "failed",
    name="rag_indexing_status",
    create_type=False,
)


def upgrade() -> None:
    rag_indexing_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "indexing_status",
            rag_indexing_status,
            server_default="not_indexed",
            nullable=False,
        ),
    )
    op.add_column("documents", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("index_error", sa.String(500), nullable=True))
    op.add_column("documents", sa.Column("embedding_provider", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(255), nullable=True))
    op.create_index("ix_documents_indexing_status", "documents", ["indexing_status"])


def downgrade() -> None:
    op.drop_index("ix_documents_indexing_status", table_name="documents")
    op.drop_column("documents", "embedding_model")
    op.drop_column("documents", "embedding_provider")
    op.drop_column("documents", "index_error")
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "indexing_status")
    rag_indexing_status.drop(op.get_bind(), checkfirst=True)
