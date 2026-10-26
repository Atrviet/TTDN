from fastapi import APIRouter, HTTPException, status

from app.ai.agents.service import (
    AgentDocumentNotFoundError,
    AgentDocumentNotReadyError,
    AgentExecutionError,
    AgentPersistenceError,
    AgentSessionNotFoundError,
    AgentTimeoutError,
)
from app.ai.llm.base import LLMError
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import DocumentNotIndexableError, IndexConfigurationMismatchError
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.agent import AgentServiceDependency
from app.api.dependencies.auth import CurrentUser
from app.schemas.agent import AgentChatRequest, AgentChatResponse


router = APIRouter(prefix="/agent", tags=["Study Agent"])


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    current_user: CurrentUser,
    service: AgentServiceDependency,
) -> AgentChatResponse:
    try:
        result = await service.chat(
            session_id=request.session_id,
            user_id=current_user.id,
            message=request.message,
            document_ids=request.document_ids,
        )
    except AgentSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc
    except AgentDocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except (AgentDocumentNotReadyError, DocumentNotIndexableError, IndexConfigurationMismatchError) as exc:
        raise HTTPException(status_code=409, detail="Selected documents are not ready for the agent") from exc
    except AgentTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Study Agent timed out") from exc
    except (LLMError, EmbeddingError, VectorStoreError, AgentExecutionError) as exc:
        raise HTTPException(status_code=503, detail="Study Agent is temporarily unavailable") from exc
    except AgentPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save agent conversation") from exc

    tools_used = [
        item["name"] for item in result["tool_call_history"] if item["ok"]
    ]
    return AgentChatResponse(
        session_id=request.session_id,
        answer=result["answer"],
        tools_used=tools_used,
        citations=result["citations"],
        execution_steps=result["execution_steps"],
        execution_status=result["execution_status"],
        model=service.llm_provider.model_name if result["execution_status"] == "completed" else None,
    )
