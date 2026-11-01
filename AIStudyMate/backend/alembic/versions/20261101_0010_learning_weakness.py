"""Add explainable topic mappings and mastery evidence.

Revision ID: 20261101_0010
Revises: 20261101_0009
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261101_0010"
down_revision: str | None = "20261101_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table("learning_topic_mappings",
        sa.Column("user_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("resource_type",sa.String(32),nullable=False),sa.Column("resource_id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("topic_key",sa.String(255),nullable=False),sa.Column("topic_name",sa.String(255),nullable=False),sa.Column("concept_id",postgresql.UUID(as_uuid=True)),sa.Column("provenance",sa.String(64),nullable=False),sa.Column("confidence",sa.Numeric(4,3),nullable=False),sa.Column("is_verified",sa.Boolean(),server_default="false",nullable=False),sa.Column("id",postgresql.UUID(as_uuid=True),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1",name="ck_learning_topic_mapping_confidence_range"),sa.ForeignKeyConstraint(["concept_id"],["knowledge_concepts.id"],ondelete="SET NULL"),sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),sa.PrimaryKeyConstraint("id"),sa.UniqueConstraint("user_id","resource_type","resource_id",name="uq_learning_topic_mapping_resource"))
    op.create_index("ix_learning_topic_mappings_user_id","learning_topic_mappings",["user_id"]);op.create_index("ix_learning_topic_mappings_concept_id","learning_topic_mappings",["concept_id"]);op.create_index("ix_learning_topic_mappings_user_topic","learning_topic_mappings",["user_id","topic_key"])
    op.add_column("topic_mastery",sa.Column("last_practiced_at",sa.DateTime(timezone=True)))
    op.add_column("topic_mastery",sa.Column("last_calculated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.add_column("topic_mastery",sa.Column("evidence_details",postgresql.JSONB(),server_default="{}",nullable=False))
    op.add_column("learning_recommendations",sa.Column("action_url",sa.String(1024)))
    op.add_column("learning_recommendations",sa.Column("recommendation_metadata",postgresql.JSONB(),server_default="{}",nullable=False))

def downgrade() -> None:
    op.drop_column("learning_recommendations","recommendation_metadata");op.drop_column("learning_recommendations","action_url")
    op.drop_column("topic_mastery","evidence_details");op.drop_column("topic_mastery","last_calculated_at");op.drop_column("topic_mastery","last_practiced_at")
    op.drop_index("ix_learning_topic_mappings_user_topic",table_name="learning_topic_mappings");op.drop_index("ix_learning_topic_mappings_concept_id",table_name="learning_topic_mappings");op.drop_index("ix_learning_topic_mappings_user_id",table_name="learning_topic_mappings");op.drop_table("learning_topic_mappings")
