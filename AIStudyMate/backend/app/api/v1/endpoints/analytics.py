from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies.analytics import AnalyticsServiceDependency
from app.api.dependencies.auth import CurrentUser
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AnalyticsProgressResponse,
    QuizHistoryResponse,
    WeakTopicsResponse,
)
from app.services.analytics import InvalidAnalyticsDateRangeError


router = APIRouter(prefix="/analytics", tags=["Learning Analytics"])
DateFrom = Annotated[date | None, Query(description="Inclusive UTC start date")]
DateTo = Annotated[date | None, Query(description="Inclusive UTC end date")]


def invalid_range() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="date_from must be earlier than or equal to date_to",
    )


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def analytics_overview(
    current_user: CurrentUser,
    service: AnalyticsServiceDependency,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    latest_limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> AnalyticsOverviewResponse:
    try:
        return await service.overview(
            current_user.id, date_from, date_to, latest_limit
        )
    except InvalidAnalyticsDateRangeError as exc:
        raise invalid_range() from exc


@router.get("/progress", response_model=AnalyticsProgressResponse)
async def analytics_progress(
    current_user: CurrentUser,
    service: AnalyticsServiceDependency,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> AnalyticsProgressResponse:
    try:
        return await service.progress(current_user.id, date_from, date_to)
    except InvalidAnalyticsDateRangeError as exc:
        raise invalid_range() from exc


@router.get("/quiz-history", response_model=QuizHistoryResponse)
async def analytics_quiz_history(
    current_user: CurrentUser,
    service: AnalyticsServiceDependency,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> QuizHistoryResponse:
    try:
        return await service.quiz_history(
            current_user.id, date_from, date_to, page, per_page
        )
    except InvalidAnalyticsDateRangeError as exc:
        raise invalid_range() from exc


@router.get("/weak-topics", response_model=WeakTopicsResponse)
async def analytics_weak_topics(
    current_user: CurrentUser,
    service: AnalyticsServiceDependency,
    date_from: DateFrom = None,
    date_to: DateTo = None,
) -> WeakTopicsResponse:
    try:
        return await service.weak_topics(current_user.id, date_from, date_to)
    except InvalidAnalyticsDateRangeError as exc:
        raise invalid_range() from exc
