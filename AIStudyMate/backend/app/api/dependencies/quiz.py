from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.quiz import QuizService


def get_quiz_service(
    session: SessionDependency,
    rag_service: RAGServiceDependency,
    llm_provider: LLMDependency,
) -> QuizService:
    settings = get_settings()
    return QuizService(
        session,
        rag_service,
        llm_provider,
        min_questions=settings.quiz_min_questions,
        max_questions=settings.quiz_max_questions,
        context_top_k=settings.quiz_context_top_k,
        context_max_chars=settings.quiz_context_max_chars,
        max_output_tokens=settings.quiz_max_output_tokens,
    )


QuizServiceDependency = Annotated[QuizService, Depends(get_quiz_service)]
