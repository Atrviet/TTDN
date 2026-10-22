"""Add PDF extraction fields and document processing states.

Revision ID: 20261022_0002
Revises: 20261021_0001
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261022_0002"
down_revision: str | None = "20261021_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE documents ALTER COLUMN processing_status DROP DEFAULT")
    op.execute(
        "ALTER TABLE documents ALTER COLUMN processing_status "
        "TYPE VARCHAR(32) USING processing_status::text"
    )
    op.execute("UPDATE documents SET processing_status = 'uploaded' WHERE processing_status = 'pending'")
    op.execute("UPDATE documents SET processing_status = 'ready' WHERE processing_status = 'completed'")
    op.execute("DROP TYPE document_processing_status")
    op.execute(
        "CREATE TYPE document_processing_status AS ENUM "
        "('uploaded', 'processing', 'ready', 'failed')"
    )
    op.execute(
        "ALTER TABLE documents ALTER COLUMN processing_status "
        "TYPE document_processing_status USING processing_status::document_processing_status"
    )
    op.execute("ALTER TABLE documents ALTER COLUMN processing_status SET DEFAULT 'uploaded'")

    op.add_column("documents", sa.Column("extracted_pages", postgresql.JSONB(), nullable=True))
    op.add_column("documents", sa.Column("pdf_metadata", postgresql.JSONB(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("requires_ocr", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("documents", sa.Column("processing_error", sa.String(500), nullable=True))
    op.create_index(
        "ix_documents_user_status",
        "documents",
        ["user_id", "processing_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_user_status", table_name="documents")
    op.drop_column("documents", "processing_error")
    op.drop_column("documents", "requires_ocr")
    op.drop_column("documents", "pdf_metadata")
    op.drop_column("documents", "extracted_pages")

    op.execute("ALTER TABLE documents ALTER COLUMN processing_status DROP DEFAULT")
    op.execute(
        "ALTER TABLE documents ALTER COLUMN processing_status "
        "TYPE VARCHAR(32) USING processing_status::text"
    )
    op.execute("UPDATE documents SET processing_status = 'pending' WHERE processing_status = 'uploaded'")
    op.execute("UPDATE documents SET processing_status = 'completed' WHERE processing_status = 'ready'")
    op.execute("UPDATE documents SET processing_status = 'pending' WHERE processing_status = 'processing'")
    op.execute("UPDATE documents SET processing_status = 'pending' WHERE processing_status = 'failed'")
    op.execute("DROP TYPE document_processing_status")
    op.execute(
        "CREATE TYPE document_processing_status AS ENUM "
        "('pending', 'processing', 'completed', 'failed')"
    )
    op.execute(
        "ALTER TABLE documents ALTER COLUMN processing_status "
        "TYPE document_processing_status USING processing_status::document_processing_status"
    )
    op.execute("ALTER TABLE documents ALTER COLUMN processing_status SET DEFAULT 'pending'")
