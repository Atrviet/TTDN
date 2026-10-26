import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.agents.service import AgentTimeoutError, StudyAgentService
from app.models.common import RAGIndexingStatus


@pytest.mark.asyncio
async def test_agent_request_timeout_is_enforced(monkeypatch) -> None:
    user_id, session_id, document_id = uuid4(), uuid4(), uuid4()
    service = StudyAgentService(
        session=SimpleNamespace(),
        rag_service=SimpleNamespace(),
        llm_provider=SimpleNamespace(model_name="fake"),
        max_steps=8,
        max_tool_calls=4,
        timeout_seconds=0.01,
        history_messages=4,
        context_max_chars=1000,
    )

    async def owned_session(*args):
        return SimpleNamespace(id=session_id)

    async def owned_documents(*args):
        return [SimpleNamespace(id=document_id, indexing_status=RAGIndexingStatus.INDEXED)]

    async def history(*args):
        return []

    async def slow_run(*args):
        await asyncio.sleep(0.1)

    service.chat_repository.get_owned_session = owned_session
    service.chat_repository.recent_messages = history
    service.rag_repository.get_owned_documents = owned_documents
    monkeypatch.setattr("app.ai.agents.service.StudyAgentGraph.run", slow_run)

    with pytest.raises(AgentTimeoutError):
        await service.chat(
            session_id=session_id,
            user_id=user_id,
            message="Explain",
            document_ids=[document_id],
        )
