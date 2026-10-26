from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.agents.tools import AgentToolError, StudyAgentTools


@pytest.mark.asyncio
async def test_tool_rejects_llm_supplied_user_and_document_identity() -> None:
    trusted_user = uuid4()
    authorized_document = uuid4()
    tools = StudyAgentTools(
        session=SimpleNamespace(),
        rag_service=SimpleNamespace(),
        trusted_user_id=trusted_user,
        authorized_document_ids=frozenset({authorized_document}),
    )

    with pytest.raises(AgentToolError, match="User access denied"):
        await tools.get_learning_history({"user_id": uuid4()})
    with pytest.raises(AgentToolError, match="Document access denied"):
        await tools.search_documents(
            {"query": "private", "document_ids": [uuid4()], "top_k": 1}
        )


@pytest.mark.asyncio
async def test_tool_argument_validation_is_bounded() -> None:
    tools = StudyAgentTools(
        session=SimpleNamespace(),
        rag_service=SimpleNamespace(),
        trusted_user_id=uuid4(),
        authorized_document_ids=frozenset(),
    )
    with pytest.raises(AgentToolError, match="Invalid tool arguments"):
        await tools.search_documents({"query": "", "document_ids": [], "top_k": 500})
