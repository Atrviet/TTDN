from uuid import UUID
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.advanced_learning import KnowledgeConcept, KnowledgeGraph, KnowledgeGraphConcept, KnowledgeRelation


class KnowledgeGraphRepository:
    def __init__(self, session: AsyncSession) -> None: self.session = session

    async def get_owned(self, graph_id: UUID, user_id: UUID, *, detailed: bool = False) -> KnowledgeGraph | None:
        query = select(KnowledgeGraph).where(KnowledgeGraph.id == graph_id, KnowledgeGraph.user_id == user_id).options(selectinload(KnowledgeGraph.documents))
        if detailed:
            query = query.options(selectinload(KnowledgeGraph.concept_sources).selectinload(KnowledgeGraphConcept.concept), selectinload(KnowledgeGraph.concept_sources).selectinload(KnowledgeGraphConcept.document), selectinload(KnowledgeGraph.concept_sources).selectinload(KnowledgeGraphConcept.document_chunk), selectinload(KnowledgeGraph.relations).selectinload(KnowledgeRelation.source_concept), selectinload(KnowledgeGraph.relations).selectinload(KnowledgeRelation.target_concept), selectinload(KnowledgeGraph.relations).selectinload(KnowledgeRelation.document), selectinload(KnowledgeGraph.relations).selectinload(KnowledgeRelation.document_chunk))
        return await self.session.scalar(query)

    async def list_owned(self, user_id: UUID) -> list[KnowledgeGraph]:
        rows = await self.session.scalars(select(KnowledgeGraph).where(KnowledgeGraph.user_id == user_id).options(selectinload(KnowledgeGraph.documents), selectinload(KnowledgeGraph.concept_sources), selectinload(KnowledgeGraph.relations)).order_by(KnowledgeGraph.updated_at.desc()))
        return list(rows.unique().all())

    async def concepts_by_names(self, user_id: UUID, names: set[str]) -> dict[str, KnowledgeConcept]:
        if not names: return {}
        rows = await self.session.scalars(select(KnowledgeConcept).where(KnowledgeConcept.user_id == user_id, KnowledgeConcept.normalized_name.in_(names)))
        return {item.normalized_name: item for item in rows.all()}

    async def delete_owned(self, graph_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(delete(KnowledgeGraph).where(KnowledgeGraph.id == graph_id, KnowledgeGraph.user_id == user_id))
        return bool(result.rowcount)
