from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add(self, document: Document) -> None:
        self.session.add(document)

    async def get_owned(self, document_id: UUID, user_id: UUID) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )
        return await self.session.scalar(statement)

    async def list_owned(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Document], int]:
        filters = (Document.user_id == user_id,)
        total = await self.session.scalar(select(func.count(Document.id)).where(*filters))
        statement = (
            select(Document)
            .where(*filters)
            .order_by(Document.created_at.desc(), Document.id.desc())
            .offset(offset)
            .limit(limit)
        )
        documents = list((await self.session.scalars(statement)).all())
        return documents, total or 0

    async def delete(self, document: Document) -> None:
        await self.session.delete(document)
