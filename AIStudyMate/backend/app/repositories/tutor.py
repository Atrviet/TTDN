from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.advanced_learning import Flashcard, FlashcardDeck, FlashcardReview, TutorMessage, TutorSession
from app.models.quiz import QuizAttempt


class TutorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned(self, session_id: UUID, user_id: UUID, *, messages: bool = False) -> TutorSession | None:
        query = select(TutorSession).where(TutorSession.id == session_id, TutorSession.user_id == user_id)
        query = query.options(selectinload(TutorSession.documents), selectinload(TutorSession.messages)) if messages else query.options(selectinload(TutorSession.documents))
        return await self.session.scalar(query)

    async def get_owned_for_update(self, session_id: UUID, user_id: UUID) -> TutorSession | None:
        return await self.session.scalar(select(TutorSession).where(TutorSession.id == session_id, TutorSession.user_id == user_id).with_for_update())

    async def list_owned(self, user_id: UUID) -> list[TutorSession]:
        rows = await self.session.scalars(select(TutorSession).where(TutorSession.user_id == user_id).options(selectinload(TutorSession.documents)).order_by(TutorSession.updated_at.desc()))
        return list(rows.all())

    async def recent_messages(self, session_id: UUID, limit: int) -> list[TutorMessage]:
        if limit <= 0:
            return []
        rows = await self.session.scalars(select(TutorMessage).where(TutorMessage.session_id == session_id).order_by(TutorMessage.created_at.desc(), TutorMessage.id.desc()).limit(limit))
        return list(reversed(rows.all()))

    async def delete_owned(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(delete(TutorSession).where(TutorSession.id == session_id, TutorSession.user_id == user_id))
        return bool(result.rowcount)

    async def learning_evidence(self, user_id: UUID) -> dict[str, object]:
        quiz_row = (await self.session.execute(select(func.count(QuizAttempt.id), func.avg(QuizAttempt.score * 100.0 / QuizAttempt.total_questions)).where(QuizAttempt.user_id == user_id, QuizAttempt.completed_at.is_not(None)))).one()
        review_row = (await self.session.execute(select(func.count(FlashcardReview.id), func.count(func.distinct(FlashcardReview.flashcard_id))).join(FlashcardReview.flashcard).join(Flashcard.deck).where(FlashcardDeck.user_id == user_id))).one()
        return {"completed_quiz_attempts": quiz_row[0] or 0, "average_quiz_score_percent": round(float(quiz_row[1]), 2) if quiz_row[1] is not None else None, "flashcard_reviews": review_row[0] or 0, "reviewed_flashcards": review_row[1] or 0}

