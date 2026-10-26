from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from langgraph.errors import GraphRecursionError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents.graph import StudyAgentGraph
from app.ai.agents.state import StudyAgentState
from app.ai.agents.tools import StudyAgentTools
from app.ai.llm.base import LLMProvider
from app.ai.rag.service import RAGService
from app.models.chat import ChatMessage
from app.models.common import ChatMessageRole, RAGIndexingStatus
from app.repositories.chat import ChatRepository
from app.repositories.rag import RAGRepository


class AgentSessionNotFoundError(Exception):
    """Raised without revealing whether another user's session exists."""


class AgentDocumentNotFoundError(Exception):
    """Raised without revealing whether another user's document exists."""


class AgentDocumentNotReadyError(Exception):
    """Raised when selected documents are not indexed."""


class AgentTimeoutError(Exception):
    """Raised when the request exceeds its configured deadline."""


class AgentExecutionError(Exception):
    """Raised when graph execution cannot complete safely."""


class AgentPersistenceError(Exception):
    """Raised when the message pair cannot be committed atomically."""


class StudyAgentService:
    def __init__(
        self,
        session: AsyncSession,
        rag_service: RAGService,
        llm_provider: LLMProvider,
        *,
        max_steps: int,
        max_tool_calls: int,
        timeout_seconds: float,
        history_messages: int,
        context_max_chars: int,
    ) -> None:
        self.session = session
        self.rag_service = rag_service
        self.llm_provider = llm_provider
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.timeout_seconds = timeout_seconds
        self.history_messages = history_messages
        self.context_max_chars = context_max_chars
        self.chat_repository = ChatRepository(session)
        self.rag_repository = RAGRepository(session)

    async def chat(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        message: str,
        document_ids: list[UUID],
    ) -> StudyAgentState:
        chat_session = await self.chat_repository.get_owned_session(session_id, user_id)
        if chat_session is None:
            raise AgentSessionNotFoundError
        unique_document_ids = list(dict.fromkeys(document_ids))
        documents = await self.rag_repository.get_owned_documents(unique_document_ids, user_id)
        if len(documents) != len(unique_document_ids):
            raise AgentDocumentNotFoundError
        if any(item.indexing_status != RAGIndexingStatus.INDEXED for item in documents):
            raise AgentDocumentNotReadyError

        history = await self.chat_repository.recent_messages(session_id, self.history_messages)
        tools = StudyAgentTools(
            session=self.session,
            rag_service=self.rag_service,
            trusted_user_id=user_id,
            authorized_document_ids=frozenset(unique_document_ids),
        )
        graph = StudyAgentGraph(
            tools=tools,
            llm_provider=self.llm_provider,
            max_steps=self.max_steps,
            max_tool_calls=self.max_tool_calls,
            context_max_chars=self.context_max_chars,
        )
        initial_state: StudyAgentState = {
            "session_id": session_id,
            "user_id": user_id,
            "authorized_document_ids": unique_document_ids,
            "message": message.strip(),
            "conversation_history": [
                {"role": item.role.value, "content": item.content} for item in history
            ],
            "intent": "question",
            "planned_tools": [],
            "retrieved_context": [],
            "tool_call_history": [],
            "answer": "",
            "citations": [],
            "execution_status": "running",
            "execution_steps": 0,
            "error": None,
        }
        try:
            async with asyncio.timeout(self.timeout_seconds):
                result = await graph.run(initial_state)
        except TimeoutError as exc:
            raise AgentTimeoutError from exc
        except GraphRecursionError as exc:
            raise AgentExecutionError("Graph step limit reached") from exc

        await self._persist_exchange(session_id, user_id, message, result)
        return result

    async def _persist_exchange(
        self,
        session_id: UUID,
        user_id: UUID,
        message: str,
        state: StudyAgentState,
    ) -> None:
        chat_session = await self.chat_repository.get_owned_session_for_update(session_id, user_id)
        if chat_session is None:
            await self.session.rollback()
            raise AgentSessionNotFoundError
        now = datetime.now(UTC)
        assistant_time = now + timedelta(microseconds=1)
        citations = [dict(item) for item in state["citations"]]
        self.session.add_all(
            [
                ChatMessage(
                    session_id=session_id,
                    role=ChatMessageRole.USER,
                    content=message.strip(),
                    citations=None,
                    created_at=now,
                ),
                ChatMessage(
                    session_id=session_id,
                    role=ChatMessageRole.ASSISTANT,
                    content=state["answer"],
                    citations=citations,
                    created_at=assistant_time,
                ),
            ]
        )
        chat_session.updated_at = assistant_time
        try:
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise AgentPersistenceError from exc
