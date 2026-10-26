from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.services.analytics import AnalyticsService


def get_analytics_service(session: SessionDependency) -> AnalyticsService:
    return AnalyticsService(session)


AnalyticsServiceDependency = Annotated[AnalyticsService, Depends(get_analytics_service)]
