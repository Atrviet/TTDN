from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.ai.agents.service import StudyAgentService


def get_agent_service(
    session: SessionDependency,
    rag_service: RAGServiceDependency,
    llm_provider: LLMDependency,
) -> StudyAgentService:
    settings = get_settings()
    return StudyAgentService(
        session,
        rag_service,
        llm_provider,
        max_steps=settings.agent_max_steps,
        max_tool_calls=settings.agent_max_tool_calls,
        timeout_seconds=settings.agent_timeout_seconds,
        history_messages=settings.agent_history_messages,
        context_max_chars=settings.agent_context_max_chars,
    )


AgentServiceDependency = Annotated[StudyAgentService, Depends(get_agent_service)]
