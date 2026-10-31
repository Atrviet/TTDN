from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.ai.llm.base import LLMProvider
from app.ai.llm.gemini import GeminiLLMProvider
from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.chat import ChatService


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return GeminiLLMProvider(
        api_key=settings.gemini_api_key,
        model_name=settings.gemini_chat_model,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
        max_output_tokens=settings.gemini_max_output_tokens,
        max_concurrent_requests=settings.gemini_max_concurrent_requests,
    )


LLMDependency = Annotated[LLMProvider, Depends(get_llm_provider)]


def get_chat_service(
    session: SessionDependency,
    rag_service: RAGServiceDependency,
    llm_provider: LLMDependency,
) -> ChatService:
    settings = get_settings()
    return ChatService(
        session,
        rag_service,
        llm_provider,
        rag_top_k=settings.chat_rag_top_k,
        history_messages=settings.chat_history_messages,
        history_max_chars=settings.chat_history_max_chars,
        context_max_chars=settings.chat_context_max_chars,
    )


ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
