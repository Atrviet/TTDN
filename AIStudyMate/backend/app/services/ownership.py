from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.rag import RAGRepository


class OwnedResourceNotFoundError(Exception):
    """Does not reveal whether a resource exists for another user."""


class DocumentOwnershipService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = RAGRepository(session)

    async def require_documents(self, document_ids: list[UUID], user_id: UUID) -> list[Document]:
        unique_ids = list(dict.fromkeys(document_ids))
        documents = await self.repository.get_owned_documents(unique_ids, user_id)
        if len(documents) != len(unique_ids):
            raise OwnedResourceNotFoundError
        return documents
