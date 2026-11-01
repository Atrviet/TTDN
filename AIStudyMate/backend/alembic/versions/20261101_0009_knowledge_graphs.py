"""Group knowledge concepts and relations into owned graphs.

Revision ID: 20261101_0009
Revises: 20261031_0008
"""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261101_0009"
down_revision: str | None = "20261031_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("knowledge_graphs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_knowledge_graphs_user_id", "knowledge_graphs", ["user_id"])
    op.create_index("ix_knowledge_graphs_user_updated_at", "knowledge_graphs", ["user_id", "updated_at"])
    op.create_table("knowledge_graph_documents",
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["graph_id"], ["knowledge_graphs.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("graph_id", "document_id"))
    op.create_index("ix_knowledge_graph_documents_document_id", "knowledge_graph_documents", ["document_id"])
    op.create_table("knowledge_graph_concepts",
        sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("concept_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("document_chunk_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("page_number", sa.Integer(), nullable=False), sa.Column("confidence", sa.Numeric(4, 3), nullable=False), sa.Column("definition", sa.Text()), sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_knowledge_graph_concepts_confidence_range"), sa.CheckConstraint("page_number > 0", name="ck_knowledge_graph_concepts_page_positive"),
        sa.ForeignKeyConstraint(["concept_id"], ["knowledge_concepts.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["graph_id"], ["knowledge_graphs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("graph_id", "concept_id", "document_chunk_id", name="uq_knowledge_graph_concept_source"))
    op.create_index("ix_knowledge_graph_concepts_graph_concept", "knowledge_graph_concepts", ["graph_id", "concept_id"])
    op.drop_constraint("uq_knowledge_relations_edge_provenance", "knowledge_relations", type_="unique")
    op.add_column("knowledge_relations", sa.Column("graph_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("knowledge_relations", sa.Column("page_number", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_knowledge_relations_graph_id", "knowledge_relations", "knowledge_graphs", ["graph_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_knowledge_relations_graph_id", "knowledge_relations", ["graph_id"])
    op.create_unique_constraint("uq_knowledge_relations_graph_edge_source", "knowledge_relations", ["graph_id", "source_concept_id", "target_concept_id", "relation_type", "document_chunk_id"])


def downgrade() -> None:
    op.drop_constraint("uq_knowledge_relations_graph_edge_source", "knowledge_relations", type_="unique")
    op.drop_index("ix_knowledge_relations_graph_id", table_name="knowledge_relations")
    op.drop_constraint("fk_knowledge_relations_graph_id", "knowledge_relations", type_="foreignkey")
    op.drop_column("knowledge_relations", "page_number"); op.drop_column("knowledge_relations", "graph_id")
    op.create_unique_constraint("uq_knowledge_relations_edge_provenance", "knowledge_relations", ["source_concept_id", "target_concept_id", "relation_type", "document_id"])
    op.drop_table("knowledge_graph_concepts"); op.drop_index("ix_knowledge_graph_documents_document_id", table_name="knowledge_graph_documents"); op.drop_table("knowledge_graph_documents")
    op.drop_index("ix_knowledge_graphs_user_updated_at", table_name="knowledge_graphs"); op.drop_index("ix_knowledge_graphs_user_id", table_name="knowledge_graphs"); op.drop_table("knowledge_graphs")
