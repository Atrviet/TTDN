"""Add AI generation idempotency records.

Revision ID: 20261101_0011
Revises: 20261101_0010
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision: str="20261101_0011";down_revision: str|None="20261101_0010";branch_labels: str|Sequence[str]|None=None;depends_on: str|Sequence[str]|None=None
def upgrade()->None:
    op.create_table("ai_generation_requests",sa.Column("user_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("operation",sa.String(64),nullable=False),sa.Column("idempotency_key",sa.String(128),nullable=False),sa.Column("request_hash",sa.String(64),nullable=False),sa.Column("status",sa.String(16),server_default="in_progress",nullable=False),sa.Column("resource_id",postgresql.UUID(as_uuid=True)),sa.Column("error_code",sa.String(64)),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("user_id","operation","idempotency_key",name="uq_ai_generation_request_key"))
    op.create_index("ix_ai_generation_requests_user_id","ai_generation_requests",["user_id"]);op.create_index("ix_ai_generation_requests_user_created","ai_generation_requests",["user_id","created_at"])
def downgrade()->None:
    op.drop_index("ix_ai_generation_requests_user_created",table_name="ai_generation_requests");op.drop_index("ix_ai_generation_requests_user_id",table_name="ai_generation_requests");op.drop_table("ai_generation_requests")
