from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.flashcard import FlashcardService


def get_flashcard_service(
    session: SessionDependency,
    rag_service: RAGServiceDependency,
    llm_provider: LLMDependency,
) -> FlashcardService:
    settings = get_settings()
    return FlashcardService(
        session,
        rag_service,
        llm_provider,
        min_cards=settings.flashcard_min_cards,
        max_cards=settings.flashcard_max_cards,
        context_top_k=settings.flashcard_context_top_k,
        context_max_chars=settings.flashcard_context_max_chars,
        max_output_tokens=settings.flashcard_max_output_tokens,
    )


FlashcardServiceDependency = Annotated[FlashcardService, Depends(get_flashcard_service)]
