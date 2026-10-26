from datetime import UTC, date, datetime, time, timedelta
from math import ceil
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsProgressResponse,
    DateRangeResponse,
    LatestQuizResult,
    ProgressPoint,
    QuizAccuracy,
    QuizHistoryItem,
    QuizHistoryResponse,
    WeakTopic,
    WeakTopicsResponse,
)


class InvalidAnalyticsDateRangeError(Exception):
    """Raised when date_from is later than date_to."""


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = AnalyticsRepository(session)

    async def overview(
        self,
        user_id: UUID,
        date_from: date | None,
        date_to: date | None,
        latest_limit: int,
    ) -> AnalyticsOverviewResponse:
        start, end = self._bounds(date_from, date_to)
        metrics = await self.repository.overview(user_id, start, end)
        latest_rows = await self.repository.latest_results(
            user_id, start, end, latest_limit
        )
        accuracy_rows = await self.repository.accuracy_by_quiz(user_id, start, end)
        return AnalyticsOverviewResponse(
            date_range=self._range(date_from, date_to),
            total_quizzes_attempted=int(metrics["attempts"]),
            average_score_percentage=self._optional_percentage(metrics["average_percentage"]),
            highest_score_percentage=self._optional_percentage(metrics["highest_percentage"]),
            total_correct_answers=int(metrics["correct"]),
            total_answered_questions=int(metrics["questions"]),
            latest_results=[self._latest(item) for item in latest_rows],
            accuracy_by_quiz=[
                QuizAccuracy(
                    quiz_id=item["quiz_id"],
                    quiz_title=item["quiz_title"],
                    attempts=int(item["attempts"]),
                    correct_answers=int(item["correct_answers"]),
                    total_answers=int(item["total_answers"]),
                    accuracy_percentage=self._ratio(
                        item["correct_answers"], item["total_answers"]
                    ),
                )
                for item in accuracy_rows
            ],
        )

    async def progress(
        self, user_id: UUID, date_from: date | None, date_to: date | None
    ) -> AnalyticsProgressResponse:
        start, end = self._bounds(date_from, date_to)
        rows = await self.repository.progress(user_id, start, end)
        return AnalyticsProgressResponse(
            date_range=self._range(date_from, date_to),
            points=[
                ProgressPoint(
                    date=item["date"],
                    attempts=int(item["attempts"]),
                    average_score_percentage=round(float(item["average_percentage"]), 2),
                    correct_answers=int(item["correct_answers"]),
                    total_questions=int(item["total_questions"]),
                )
                for item in rows
            ],
        )

    async def quiz_history(
        self,
        user_id: UUID,
        date_from: date | None,
        date_to: date | None,
        page: int,
        per_page: int,
    ) -> QuizHistoryResponse:
        start, end = self._bounds(date_from, date_to)
        rows, total = await self.repository.quiz_history(
            user_id,
            start,
            end,
            offset=(page - 1) * per_page,
            limit=per_page,
        )
        return QuizHistoryResponse(
            date_range=self._range(date_from, date_to),
            items=[
                QuizHistoryItem(
                    **self._latest(item).model_dump(),
                    started_at=item["started_at"],
                )
                for item in rows
            ],
            total=total,
            page=page,
            per_page=per_page,
            pages=ceil(total / per_page) if total else 0,
        )

    async def weak_topics(
        self, user_id: UUID, date_from: date | None, date_to: date | None
    ) -> WeakTopicsResponse:
        start, end = self._bounds(date_from, date_to)
        rows = await self.repository.weak_topics(user_id, start, end)
        return WeakTopicsResponse(
            date_range=self._range(date_from, date_to),
            items=[
                WeakTopic(
                    quiz_id=item["quiz_id"],
                    topic=item["topic"],
                    attempts=int(item["attempts"]),
                    incorrect_answers=int(item["incorrect_answers"]),
                    total_answers=int(item["total_answers"]),
                    accuracy_percentage=self._ratio(
                        int(item["total_answers"]) - int(item["incorrect_answers"]),
                        item["total_answers"],
                    ),
                )
                for item in rows
            ],
        )

    @staticmethod
    def _bounds(
        date_from: date | None, date_to: date | None
    ) -> tuple[datetime | None, datetime | None]:
        if date_from and date_to and date_from > date_to:
            raise InvalidAnalyticsDateRangeError
        start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
        end = (
            datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
            if date_to
            else None
        )
        return start, end

    @staticmethod
    def _range(date_from: date | None, date_to: date | None) -> DateRangeResponse:
        return DateRangeResponse(date_from=date_from, date_to=date_to)

    @staticmethod
    def _optional_percentage(value) -> float | None:
        return round(float(value), 2) if value is not None else None

    @staticmethod
    def _ratio(numerator, denominator) -> float:
        return round(float(numerator) * 100.0 / float(denominator), 2) if denominator else 0.0

    @classmethod
    def _latest(cls, item: dict) -> LatestQuizResult:
        return LatestQuizResult(
            attempt_id=item["attempt_id"],
            quiz_id=item["quiz_id"],
            quiz_title=item["quiz_title"],
            difficulty=item["difficulty"],
            score=int(item["score"]),
            total_questions=int(item["total_questions"]),
            percentage=cls._ratio(item["score"], item["total_questions"]),
            completed_at=item["completed_at"],
        )
