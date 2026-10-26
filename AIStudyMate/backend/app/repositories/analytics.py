from datetime import datetime
from uuid import UUID

from sqlalchemy import Float, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.quiz import Quiz, QuizAttempt, UserAnswer


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _attempt_filters(
        user_id: UUID, start: datetime | None, end_exclusive: datetime | None
    ) -> list:
        filters = [QuizAttempt.user_id == user_id, QuizAttempt.completed_at.is_not(None)]
        if start is not None:
            filters.append(QuizAttempt.completed_at >= start)
        if end_exclusive is not None:
            filters.append(QuizAttempt.completed_at < end_exclusive)
        return filters

    async def overview(
        self, user_id: UUID, start: datetime | None, end_exclusive: datetime | None
    ) -> dict:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        percentage = cast(QuizAttempt.score, Float) * 100.0 / QuizAttempt.total_questions
        row = (
            await self.session.execute(
                select(
                    func.count(QuizAttempt.id).label("attempts"),
                    func.avg(percentage).label("average_percentage"),
                    func.max(percentage).label("highest_percentage"),
                    func.coalesce(func.sum(QuizAttempt.score), 0).label("correct"),
                    func.coalesce(func.sum(QuizAttempt.total_questions), 0).label("questions"),
                ).where(*filters)
            )
        ).one()
        return dict(row._mapping)

    async def latest_results(
        self,
        user_id: UUID,
        start: datetime | None,
        end_exclusive: datetime | None,
        limit: int,
    ) -> list[dict]:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        rows = await self.session.execute(
            select(
                QuizAttempt.id.label("attempt_id"),
                Quiz.id.label("quiz_id"),
                Quiz.title.label("quiz_title"),
                Quiz.difficulty,
                QuizAttempt.score,
                QuizAttempt.total_questions,
                QuizAttempt.completed_at,
            )
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*filters)
            .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
            .limit(limit)
        )
        return [dict(row) for row in rows.mappings().all()]

    async def accuracy_by_quiz(
        self, user_id: UUID, start: datetime | None, end_exclusive: datetime | None
    ) -> list[dict]:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        rows = await self.session.execute(
            select(
                Quiz.id.label("quiz_id"),
                Quiz.title.label("quiz_title"),
                func.count(QuizAttempt.id).label("attempts"),
                func.sum(QuizAttempt.score).label("correct_answers"),
                func.sum(QuizAttempt.total_questions).label("total_answers"),
            )
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*filters)
            .group_by(Quiz.id, Quiz.title)
            .order_by(Quiz.title, Quiz.id)
        )
        return [dict(row) for row in rows.mappings().all()]

    async def progress(
        self, user_id: UUID, start: datetime | None, end_exclusive: datetime | None
    ) -> list[dict]:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        day = func.date(func.timezone("UTC", QuizAttempt.completed_at))
        percentage = cast(QuizAttempt.score, Float) * 100.0 / QuizAttempt.total_questions
        rows = await self.session.execute(
            select(
                day.label("date"),
                func.count(QuizAttempt.id).label("attempts"),
                func.avg(percentage).label("average_percentage"),
                func.sum(QuizAttempt.score).label("correct_answers"),
                func.sum(QuizAttempt.total_questions).label("total_questions"),
            )
            .where(*filters)
            .group_by(day)
            .order_by(day)
        )
        return [dict(row) for row in rows.mappings().all()]

    async def quiz_history(
        self,
        user_id: UUID,
        start: datetime | None,
        end_exclusive: datetime | None,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[dict], int]:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        total = await self.session.scalar(select(func.count(QuizAttempt.id)).where(*filters))
        rows = await self.session.execute(
            select(
                QuizAttempt.id.label("attempt_id"),
                Quiz.id.label("quiz_id"),
                Quiz.title.label("quiz_title"),
                Quiz.difficulty,
                QuizAttempt.score,
                QuizAttempt.total_questions,
                QuizAttempt.started_at,
                QuizAttempt.completed_at,
            )
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(*filters)
            .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return [dict(row) for row in rows.mappings().all()], int(total or 0)

    async def weak_topics(
        self, user_id: UUID, start: datetime | None, end_exclusive: datetime | None
    ) -> list[dict]:
        filters = self._attempt_filters(user_id, start, end_exclusive)
        incorrect = func.sum(case((UserAnswer.is_correct.is_(False), 1), else_=0))
        rows = await self.session.execute(
            select(
                Quiz.id.label("quiz_id"),
                Quiz.title.label("topic"),
                func.count(func.distinct(QuizAttempt.id)).label("attempts"),
                incorrect.label("incorrect_answers"),
                func.count(UserAnswer.id).label("total_answers"),
            )
            .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
            .join(UserAnswer, UserAnswer.attempt_id == QuizAttempt.id)
            .where(*filters)
            .group_by(Quiz.id, Quiz.title)
            .having(incorrect > 0)
            .order_by(
                (cast(incorrect, Float) / func.count(UserAnswer.id)).desc(), Quiz.title
            )
        )
        return [dict(row) for row in rows.mappings().all()]
