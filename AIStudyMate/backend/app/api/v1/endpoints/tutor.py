import asyncio
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.ai.llm.base import LLMError
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import DocumentNotIndexableError, IndexConfigurationMismatchError, RAGDocumentNotFoundError
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.tutor import TutorServiceDependency
from app.schemas.tutor import TutorMessageRequest, TutorMessageResponse, TutorReplyResponse, TutorSessionCreate, TutorSessionDetail, TutorSessionList, TutorSessionResponse, TutorSessionUpdate
from app.services.tutor import TutorDocumentNotFoundError, TutorPersistenceError, TutorSessionNotFoundError


router = APIRouter(prefix="/tutor/sessions", tags=["AI Tutor"])


def view(item) -> TutorSessionResponse:
    return TutorSessionResponse(id=item.id, title=item.title, learning_objective=item.learning_objective, document_ids=[doc.id for doc in item.documents], created_at=item.created_at, updated_at=item.updated_at)


@router.post("", response_model=TutorSessionResponse, status_code=201)
async def create(payload: TutorSessionCreate, user: CurrentUser, service: TutorServiceDependency):
    try: return view(await service.create(user.id, payload.title, payload.learning_objective, payload.document_ids))
    except TutorDocumentNotFoundError as exc: raise HTTPException(404, "Document not found") from exc
    except TutorPersistenceError as exc: raise HTTPException(500, "Unable to save tutor session") from exc


@router.get("", response_model=TutorSessionList)
async def list_sessions(user: CurrentUser, service: TutorServiceDependency): return TutorSessionList(items=[view(item) for item in await service.list(user.id)])


@router.get("/{session_id}", response_model=TutorSessionDetail)
async def get_session(session_id: UUID, user: CurrentUser, service: TutorServiceDependency):
    try:
        item = await service.get(session_id, user.id)
        return TutorSessionDetail(**view(item).model_dump(), messages=[TutorMessageResponse.model_validate(msg) for msg in item.messages])
    except TutorSessionNotFoundError as exc: raise HTTPException(404, "Tutor session not found") from exc


@router.patch("/{session_id}", response_model=TutorSessionResponse)
async def update_session(session_id: UUID, payload: TutorSessionUpdate, user: CurrentUser, service: TutorServiceDependency):
    try: return view(await service.update(session_id, user.id, title=payload.title, objective=payload.learning_objective, document_ids=payload.document_ids, fields_set=payload.model_fields_set))
    except TutorSessionNotFoundError as exc: raise HTTPException(404, "Tutor session not found") from exc
    except TutorDocumentNotFoundError as exc: raise HTTPException(404, "Document not found") from exc


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: UUID, user: CurrentUser, service: TutorServiceDependency):
    try: await service.delete(session_id, user.id); return Response(status_code=204)
    except TutorSessionNotFoundError as exc: raise HTTPException(404, "Tutor session not found") from exc


@router.post("/{session_id}/messages", response_model=TutorReplyResponse)
async def send_message(session_id: UUID, payload: TutorMessageRequest, user: CurrentUser, service: TutorServiceDependency):
    try:
        user_msg, assistant, final = await service.send(session_id=session_id, user_id=user.id, message=payload.message, mode=payload.mode, difficulty=payload.difficulty, document_ids=payload.document_ids)
        return TutorReplyResponse(session_id=session_id, mode=payload.mode, difficulty=payload.difficulty, user_message=TutorMessageResponse.model_validate(user_msg), assistant_message=TutorMessageResponse.model_validate(assistant), model=service.llm.model_name, execution_steps=final["execution_steps"])
    except (TutorSessionNotFoundError, TutorDocumentNotFoundError, RAGDocumentNotFoundError) as exc: raise HTTPException(404, "Tutor session or document not found") from exc
    except (DocumentNotIndexableError, IndexConfigurationMismatchError) as exc: raise HTTPException(409, str(exc)) from exc
    except (LLMError, EmbeddingError, VectorStoreError, asyncio.TimeoutError, RuntimeError) as exc: raise HTTPException(503, "AI tutor is temporarily unavailable") from exc
    except TutorPersistenceError as exc: raise HTTPException(500, "Unable to save tutor interaction") from exc
