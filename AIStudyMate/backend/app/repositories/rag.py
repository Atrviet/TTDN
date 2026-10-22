from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk


class RAGRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned_document_for_update(
        self, document_id: UUID, user_id: UUID
    ) -> Document | None:
        statement = (
            select(Document)
            .where(Document.id == document_id, Document.user_id == user_id)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def get_owned_documents(self, document_ids: list[UUID], user_id: UUID) -> list[Document]:
        statement = select(Document).where(
            Document.id.in_(document_ids),
            Document.user_id == user_id,
        )
        return list((await self.session.scalars(statement)).all())

    async def count_chunks(self, document_id: UUID) -> int:
        count = await self.session.scalar(
            select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
        )
        return count or 0

    async def replace_chunks(self, document_id: UUID, chunks: list[DocumentChunk]) -> None:
        await self.session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        self.session.add_all(chunks)

