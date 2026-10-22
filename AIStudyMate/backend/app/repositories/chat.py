from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_owned_session(self, session_id: UUID, user_id: UUID) -> ChatSession | None:
        return await self.session.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )

    async def get_owned_session_for_update(
        self, session_id: UUID, user_id: UUID
    ) -> ChatSession | None:
        return await self.session.scalar(
            select(ChatSession)
            .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .with_for_update()
        )

    async def list_sessions(self, user_id: UUID) -> list[ChatSession]:
        result = await self.session.scalars(
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return list(result.all())

    async def list_messages(self, session_id: UUID) -> list[ChatMessage]:
        result = await self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return list(result.all())

    async def recent_messages(self, session_id: UUID, limit: int) -> list[ChatMessage]:
        if limit <= 0:
            return []
        result = await self.session.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(result.all()))

    async def delete_session(self, session_id: UUID, user_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )
        return bool(result.rowcount)
