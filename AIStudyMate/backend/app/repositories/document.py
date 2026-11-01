from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.quiz import Quiz
from app.models.advanced_learning import Flashcard,FlashcardDeck,StudyTask,flashcard_deck_documents,study_plan_documents,tutor_session_documents,knowledge_graph_documents


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

    async def dependent_resource_types(self,document_id:UUID)->list[str]:
        checks={"quizzes":select(Quiz.id).where(Quiz.document_id==document_id),"flashcards":select(Flashcard.id).where(Flashcard.source_document_id==document_id),"flashcard_decks":select(FlashcardDeck.id).where(FlashcardDeck.document_id==document_id),"flashcard_deck_documents":select(flashcard_deck_documents.c.deck_id).where(flashcard_deck_documents.c.document_id==document_id),"study_tasks":select(StudyTask.id).where(StudyTask.document_id==document_id),"study_plans":select(study_plan_documents.c.plan_id).where(study_plan_documents.c.document_id==document_id),"tutor_sessions":select(tutor_session_documents.c.session_id).where(tutor_session_documents.c.document_id==document_id),"knowledge_graphs":select(knowledge_graph_documents.c.graph_id).where(knowledge_graph_documents.c.document_id==document_id)}
        found=[]
        for name,query in checks.items():
            if await self.session.scalar(query.limit(1)) is not None:found.append(name)
        return found
