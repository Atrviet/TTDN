from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag.service import RAGService
from app.models.chat import ChatSession
from app.models.document import Document
from app.models.quiz import QuizAttempt
from app.repositories.document import DocumentRepository


class AgentToolError(Exception):
    """Safe tool failure whose internal details must not reach the model or client."""


class SearchDocumentsArguments(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    document_ids: list[UUID] = Field(min_length=1, max_length=20)
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentArguments(BaseModel):
    document_id: UUID


class LearningHistoryArguments(BaseModel):
    user_id: UUID


@dataclass
class StudyAgentTools:
    session: AsyncSession
    rag_service: RAGService
    trusted_user_id: UUID
    authorized_document_ids: frozenset[UUID]

    async def search_documents(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = self._validate(SearchDocumentsArguments, raw_arguments)
        requested = set(arguments.document_ids)
        if not requested <= self.authorized_document_ids:
            raise AgentToolError("Document access denied")
        results = await self.rag_service.search(
            query=arguments.query,
            document_ids=arguments.document_ids,
            user_id=self.trusted_user_id,
            top_k=arguments.top_k,
        )
        return {
            "query": arguments.query,
            "chunks": [self._serialize_result(item) for item in results],
        }

    async def get_document_summary(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = self._validate(DocumentArguments, raw_arguments)
        await self._require_authorized_document(arguments.document_id)
        results = await self.rag_service.search(
            query="Tóm tắt các ý chính và cấu trúc quan trọng của tài liệu",
            document_ids=[arguments.document_id],
            user_id=self.trusted_user_id,
            top_k=8,
        )
        return {
            "document_id": str(arguments.document_id),
            "summary_source_chunks": [self._serialize_result(item) for item in results],
        }

    async def get_document_metadata(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = self._validate(DocumentArguments, raw_arguments)
        document = await self._require_authorized_document(arguments.document_id)
        return {
            "document_id": str(document.id),
            "title": document.title,
            "original_filename": document.original_filename,
            "page_count": document.page_count,
            "processing_status": document.processing_status.value,
            "indexing_status": document.indexing_status.value,
            "requires_ocr": document.requires_ocr,
            "created_at": document.created_at.isoformat(),
        }

    async def get_learning_history(self, raw_arguments: dict[str, Any]) -> dict[str, Any]:
        arguments = self._validate(LearningHistoryArguments, raw_arguments)
        if arguments.user_id != self.trusted_user_id:
            raise AgentToolError("User access denied")
        total, completed, earned, possible = (
            await self.session.execute(
                select(
                    func.count(QuizAttempt.id),
                    func.count(QuizAttempt.completed_at),
                    func.coalesce(func.sum(QuizAttempt.score), 0),
                    func.coalesce(func.sum(QuizAttempt.total_questions), 0),
                ).where(QuizAttempt.user_id == self.trusted_user_id)
            )
        ).one()
        session_count = await self.session.scalar(
            select(func.count(ChatSession.id)).where(ChatSession.user_id == self.trusted_user_id)
        )
        accuracy = float(earned) / float(possible) if possible else None
        return {
            "user_id": str(self.trusted_user_id),
            "quiz_attempts": int(total),
            "completed_quiz_attempts": int(completed),
            "quiz_accuracy": accuracy,
            "chat_sessions": int(session_count or 0),
        }

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tools = {
            "search_documents": self.search_documents,
            "get_document_summary": self.get_document_summary,
            "get_document_metadata": self.get_document_metadata,
            "get_learning_history": self.get_learning_history,
        }
        tool = tools.get(name)
        if tool is None:
            raise AgentToolError("Unknown tool")
        try:
            return await tool(arguments)
        except AgentToolError:
            raise
        except Exception as exc:
            raise AgentToolError(f"{name} failed") from exc

    async def _require_authorized_document(self, document_id: UUID) -> Document:
        if document_id not in self.authorized_document_ids:
            raise AgentToolError("Document access denied")
        document = await DocumentRepository(self.session).get_owned(
            document_id, self.trusted_user_id
        )
        if document is None:
            raise AgentToolError("Document not found")
        return document

    @staticmethod
    def _validate(model: type[BaseModel], raw_arguments: dict[str, Any]) -> Any:
        try:
            return model.model_validate(raw_arguments)
        except ValidationError as exc:
            raise AgentToolError("Invalid tool arguments") from exc

    @staticmethod
    def _serialize_result(result: Any) -> dict[str, Any]:
        return {
            "chunk_id": result.chroma_id,
            "text": result.text,
            "distance": result.distance,
            "document_id": str(result.metadata["document_id"]),
            "document_title": str(result.metadata["document_title"]),
            "page_number": int(result.metadata["page_number"]),
        }
