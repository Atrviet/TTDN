from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm.base import LLMProvider
from app.ai.rag.service import RAGService
from app.ai.tutor.graph import TutorGraph
from app.ai.tutor.state import TutorState
from app.models.advanced_learning import TutorMessage, TutorSession
from app.models.common import ChatMessageRole
from app.models.document import Document
from app.repositories.tutor import TutorRepository
from app.schemas.tutor import TutorDifficulty, TutorMode


class TutorSessionNotFoundError(Exception): pass
class TutorPersistenceError(Exception): pass
class TutorDocumentNotFoundError(Exception): pass


class TutorService:
    def __init__(self, session: AsyncSession, rag: RAGService, llm: LLMProvider, *, max_steps: int, timeout_seconds: float, history_messages: int, history_max_chars: int, context_top_k: int, context_max_chars: int) -> None:
        self.session = session
        self.rag = rag
        self.llm = llm
        self.repository = TutorRepository(session)
        self.graph = TutorGraph(llm, max_steps=max_steps, context_max_chars=context_max_chars)
        self.timeout_seconds = timeout_seconds
        self.history_messages = history_messages
        self.history_max_chars = history_max_chars
        self.context_top_k = context_top_k

    async def _documents(self, user_id: UUID, ids: list[UUID]) -> list[Document]:
        unique = list(dict.fromkeys(ids))
        if not unique: return []
        docs = list((await self.session.scalars(select(Document).where(Document.user_id == user_id, Document.id.in_(unique)))).all())
        if len(docs) != len(unique): raise TutorDocumentNotFoundError
        return docs

    async def create(self, user_id: UUID, title: str, objective: str | None, document_ids: list[UUID]) -> TutorSession:
        item = TutorSession(user_id=user_id, title=title, learning_objective=objective, documents=await self._documents(user_id, document_ids))
        self.session.add(item); await self._commit(); await self.session.refresh(item, ["documents"]); return item

    async def list(self, user_id: UUID) -> list[TutorSession]: return await self.repository.list_owned(user_id)

    async def get(self, session_id: UUID, user_id: UUID) -> TutorSession:
        item = await self.repository.get_owned(session_id, user_id, messages=True)
        if item is None: raise TutorSessionNotFoundError
        return item

    async def update(self, session_id: UUID, user_id: UUID, *, title: str | None, objective: str | None, document_ids: list[UUID] | None, fields_set: set[str]) -> TutorSession:
        item = await self.repository.get_owned(session_id, user_id)
        if item is None: raise TutorSessionNotFoundError
        if "title" in fields_set: item.title = title
        if "learning_objective" in fields_set: item.learning_objective = objective
        if document_ids is not None: item.documents = await self._documents(user_id, document_ids)
        item.updated_at = datetime.now(UTC); await self._commit(); return await self.get(session_id, user_id)

    async def delete(self, session_id: UUID, user_id: UUID) -> None:
        if not await self.repository.delete_owned(session_id, user_id): await self.session.rollback(); raise TutorSessionNotFoundError
        await self._commit()

    async def send(self, *, session_id: UUID, user_id: UUID, message: str, mode: TutorMode, difficulty: TutorDifficulty, document_ids: list[UUID]) -> tuple[TutorMessage, TutorMessage, TutorState]:
        tutor_session = await self.repository.get_owned(session_id, user_id)
        if tutor_session is None: raise TutorSessionNotFoundError
        selected = document_ids or [doc.id for doc in tutor_session.documents]
        await self._documents(user_id, selected)
        history_rows = await self.repository.recent_messages(session_id, self.history_messages)
        history: list[dict[str, str]] = []; used = 0
        for row in reversed(history_rows):
            remaining = self.history_max_chars - used
            if remaining <= 0: break
            content = row.content[:remaining]; history.append({"role": row.role.value, "content": content}); used += len(content)
        history.reverse()
        results = await self.rag.search(query=message, document_ids=selected, user_id=user_id, top_k=self.context_top_k) if selected else []
        context = [{"document_id": str(r.metadata["document_id"]), "document_title": str(r.metadata["document_title"]), "page_number": int(r.metadata["page_number"]), "chunk_id": r.chroma_id, "text": r.text, "distance": r.distance} for r in results]
        citations = [{key: item[key] for key in ("document_id", "document_title", "page_number", "chunk_id")} for item in context]
        state: TutorState = {"session_id": str(session_id), "user_id": str(user_id), "message": message, "mode": mode.value, "difficulty": difficulty.value, "document_ids": [str(i) for i in selected], "history": history, "learning_evidence": await self.repository.learning_evidence(user_id), "retrieved_context": context, "citations": citations, "answer": "", "execution_steps": 0, "status": "running", "error": None}
        final = await asyncio.wait_for(self.graph.run(state), timeout=self.timeout_seconds)
        if final["status"] != "completed" or not final["answer"]: raise RuntimeError(final.get("error") or "Tutor graph failed")
        locked = await self.repository.get_owned_for_update(session_id, user_id)
        if locked is None: raise TutorSessionNotFoundError
        now = datetime.now(UTC)
        user_message = TutorMessage(session_id=session_id, role=ChatMessageRole.USER, content=message, citations=None, created_at=now)
        assistant = TutorMessage(session_id=session_id, role=ChatMessageRole.ASSISTANT, content=final["answer"], citations=final["citations"], created_at=now + timedelta(microseconds=1))
        locked.updated_at = assistant.created_at; self.session.add_all([user_message, assistant]); await self._commit()
        return user_message, assistant, final

    async def _commit(self) -> None:
        try: await self.session.commit()
        except SQLAlchemyError as exc: await self.session.rollback(); raise TutorPersistenceError from exc

