from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.common import QuizDifficulty


class DateRangeResponse(BaseModel):
    date_from: date | None
    date_to: date | None


class LatestQuizResult(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    quiz_title: str
    difficulty: QuizDifficulty
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime


class QuizAccuracy(BaseModel):
    quiz_id: UUID
    quiz_title: str
    attempts: int
    correct_answers: int
    total_answers: int
    accuracy_percentage: float


class AnalyticsOverviewResponse(BaseModel):
    date_range: DateRangeResponse
    total_quizzes_attempted: int
    average_score_percentage: float | None
    highest_score_percentage: float | None
    total_correct_answers: int
    total_answered_questions: int
    latest_results: list[LatestQuizResult]
    accuracy_by_quiz: list[QuizAccuracy]


class ProgressPoint(BaseModel):
    date: date
    attempts: int
    average_score_percentage: float
    correct_answers: int
    total_questions: int


class AnalyticsProgressResponse(BaseModel):
    date_range: DateRangeResponse
    granularity: str = "day"
    points: list[ProgressPoint]


class QuizHistoryItem(LatestQuizResult):
    started_at: datetime


class QuizHistoryResponse(BaseModel):
    date_range: DateRangeResponse
    items: list[QuizHistoryItem]
    total: int
    page: int
    per_page: int
    pages: int


class WeakTopic(BaseModel):
    quiz_id: UUID
    topic: str
    attempts: int
    incorrect_answers: int
    total_answers: int
    accuracy_percentage: float


class WeakTopicsResponse(BaseModel):
    date_range: DateRangeResponse
    topic_basis: str = "quiz_title"
    items: list[WeakTopic]
