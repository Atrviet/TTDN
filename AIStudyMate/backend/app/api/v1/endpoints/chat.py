from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.ai.llm.base import LLMError
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import (
    DocumentNotIndexableError,
    IndexConfigurationMismatchError,
    RAGDocumentNotFoundError,
)
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.chat import ChatServiceDependency
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionListResponse,
    ChatSessionRename,
    ChatSessionResponse,
    SendChatMessageRequest,
    SendChatMessageResponse,
)
from app.services.chat import ChatPersistenceError, ChatSessionNotFoundError


router = APIRouter(prefix="/chat/sessions", tags=["Chat"])


@router.post("", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    request: ChatSessionCreate,
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> ChatSessionResponse:
    try:
        chat_session = await service.create_session(current_user.id, request.title)
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save chat session") from exc
    return ChatSessionResponse.model_validate(chat_session)


@router.get("", response_model=ChatSessionListResponse)
async def list_chat_sessions(
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> ChatSessionListResponse:
    sessions = await service.list_sessions(current_user.id)
    return ChatSessionListResponse(items=[ChatSessionResponse.model_validate(item) for item in sessions])


@router.get("/{session_id}/messages", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> ChatHistoryResponse:
    try:
        messages = await service.get_messages(session_id, current_user.id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    return ChatHistoryResponse(
        session_id=session_id,
        items=[ChatMessageResponse.model_validate(item) for item in messages],
    )


@router.patch("/{session_id}", response_model=ChatSessionResponse)
async def rename_chat_session(
    session_id: UUID,
    request: ChatSessionRename,
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> ChatSessionResponse:
    try:
        chat_session = await service.rename_session(session_id, current_user.id, request.title)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to update chat session") from exc
    return ChatSessionResponse.model_validate(chat_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: UUID,
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> Response:
    try:
        await service.delete_session(session_id, current_user.id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to delete chat session") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{session_id}/messages", response_model=SendChatMessageResponse)
async def send_chat_message(
    session_id: UUID,
    request: SendChatMessageRequest,
    current_user: CurrentUser,
    service: ChatServiceDependency,
) -> SendChatMessageResponse:
    try:
        user_message, assistant_message, model = await service.send_message(
            session_id=session_id,
            user_id=current_user.id,
            message=request.message,
            document_ids=request.document_ids,
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    except RAGDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except (DocumentNotIndexableError, IndexConfigurationMismatchError) as exc:
        raise HTTPException(status_code=409, detail=str(exc) or "Document index is not compatible") from exc
    except (EmbeddingError, VectorStoreError, LLMError) as exc:
        raise HTTPException(status_code=503, detail="AI chat is temporarily unavailable") from exc
    except ChatPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save conversation") from exc
    return SendChatMessageResponse(
        session_id=session_id,
        user_message=ChatMessageResponse.model_validate(user_message),
        assistant_message=ChatMessageResponse.model_validate(assistant_message),
        model=model,
    )
