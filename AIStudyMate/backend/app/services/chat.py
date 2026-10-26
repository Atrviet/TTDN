from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import LLMProvider
from app.ai.rag.prompt import SYSTEM_INSTRUCTION, build_grounded_prompt
from app.ai.rag.service import RAGService
from app.models.chat import ChatMessage, ChatSession
from app.models.common import ChatMessageRole
from app.repositories.chat import ChatRepository


class ChatSessionNotFoundError(Exception):
    """Raised without disclosing whether a non-owned session exists."""


class ChatPersistenceError(Exception):
    """Raised when a chat database transaction cannot be completed."""


class ChatService:
    NO_EVIDENCE_ANSWER = (
        "Tôi chưa tìm thấy thông tin phù hợp trong các tài liệu đã chọn để trả lời câu hỏi này."
    )

    def __init__(
        self,
        session: AsyncSession,
        rag_service: RAGService,
        llm_provider: LLMProvider,
        *,
        rag_top_k: int,
        history_messages: int,
        history_max_chars: int,
        context_max_chars: int,
    ) -> None:
        self.session = session
        self.repository = ChatRepository(session)
        self.rag_service = rag_service
        self.llm_provider = llm_provider
        self.rag_top_k = rag_top_k
        self.history_messages = history_messages
        self.history_max_chars = history_max_chars
        self.context_max_chars = context_max_chars

    async def create_session(self, user_id: UUID, title: str) -> ChatSession:
        chat_session = ChatSession(user_id=user_id, title=title.strip())
        self.session.add(chat_session)
        await self._commit()
        return chat_session

    async def list_sessions(self, user_id: UUID) -> list[ChatSession]:
        return await self.repository.list_sessions(user_id)

    async def get_messages(self, session_id: UUID, user_id: UUID) -> list[ChatMessage]:
        await self._require_owned_session(session_id, user_id)
        return await self.repository.list_messages(session_id)

    async def rename_session(
        self, session_id: UUID, user_id: UUID, title: str
    ) -> ChatSession:
        chat_session = await self._require_owned_session(session_id, user_id)
        chat_session.title = title.strip()
        chat_session.updated_at = datetime.now(UTC)
        await self._commit()
        return chat_session

    async def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        deleted = await self.repository.delete_session(session_id, user_id)
        if not deleted:
            await self.session.rollback()
            raise ChatSessionNotFoundError
        await self._commit()

    async def send_message(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        message: str,
        document_ids: list[UUID],
    ) -> tuple[ChatMessage, ChatMessage, str | None]:
        await self._require_owned_session(session_id, user_id)
        history = await self.repository.recent_messages(session_id, self.history_messages)
        results = await self.rag_service.search(
            query=message,
            document_ids=document_ids,
            user_id=user_id,
            top_k=self.rag_top_k,
        )
        prompt_context = build_grounded_prompt(
            message=message,
            history=history,
            results=results,
            history_max_chars=self.history_max_chars,
            context_max_chars=self.context_max_chars,
        )

        citations = [
            {
                "document_id": str(result.metadata["document_id"]),
                "document_title": str(result.metadata["document_title"]),
                "page_number": int(result.metadata["page_number"]),
                "chunk_id": result.chroma_id,
            }
            for result in prompt_context.included_results
        ]
        if prompt_context.included_results:
            answer = await self.llm_provider.generate(
                system_instruction=SYSTEM_INSTRUCTION,
                prompt=prompt_context.prompt,
            )
            model_name: str | None = self.llm_provider.model_name
        else:
            answer = self.NO_EVIDENCE_ANSWER
            model_name = None

        chat_session = await self.repository.get_owned_session_for_update(session_id, user_id)
        if chat_session is None:
            await self.session.rollback()
            raise ChatSessionNotFoundError
        now = datetime.now(UTC)
        assistant_time = now + timedelta(microseconds=1)
        user_message = ChatMessage(
            session_id=session_id,
            role=ChatMessageRole.USER,
            content=message.strip(),
            citations=None,
            created_at=now,
        )
        assistant_message = ChatMessage(
            session_id=session_id,
            role=ChatMessageRole.ASSISTANT,
            content=answer,
            citations=citations,
            created_at=assistant_time,
        )
        chat_session.updated_at = assistant_time
        self.session.add_all([user_message, assistant_message])
        await self._commit()
        return user_message, assistant_message, model_name

    async def _require_owned_session(self, session_id: UUID, user_id: UUID) -> ChatSession:
        chat_session = await self.repository.get_owned_session(session_id, user_id)
        if chat_session is None:
            raise ChatSessionNotFoundError
        return chat_session

    async def _commit(self) -> None:
        try:
            await self.session.commit()
        except SQLAlchemyError as exc:
            await self.session.rollback()
            raise ChatPersistenceError from exc
