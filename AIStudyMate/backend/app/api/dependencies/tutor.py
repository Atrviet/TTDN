from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.tutor import TutorService


def get_tutor_service(session: SessionDependency, rag: RAGServiceDependency, llm: LLMDependency) -> TutorService:
    settings = get_settings()
    return TutorService(session, rag, llm, max_steps=settings.tutor_max_steps, timeout_seconds=settings.tutor_timeout_seconds, history_messages=settings.tutor_history_messages, history_max_chars=settings.tutor_history_max_chars, context_top_k=settings.tutor_context_top_k, context_max_chars=settings.tutor_context_max_chars)


TutorServiceDependency = Annotated[TutorService, Depends(get_tutor_service)]

