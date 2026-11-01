from typing import Annotated
from fastapi import Depends
from app.api.dependencies.auth import SessionDependency
from app.core.config import get_settings
from app.services.learning import LearningService
def get_learning_service(session:SessionDependency)->LearningService:
    s=get_settings();return LearningService(session,quiz_weight=s.mastery_quiz_weight,flashcard_weight=s.mastery_flashcard_weight,practice_weight=s.mastery_practice_weight,half_life_days=s.mastery_recency_half_life_days,needs_review_threshold=s.mastery_needs_review_threshold,strong_threshold=s.mastery_strong_threshold)
LearningServiceDependency=Annotated[LearningService,Depends(get_learning_service)]
