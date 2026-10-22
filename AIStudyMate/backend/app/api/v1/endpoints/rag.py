from fastapi import APIRouter, HTTPException, status

from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import (
    DocumentNotIndexableError,
    IndexConfigurationMismatchError,
    RAGDocumentNotFoundError,
)
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.schemas.rag import RAGSearchRequest, RAGSearchResponse, RAGSearchResult


router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post("/search", response_model=RAGSearchResponse)
async def semantic_search(
    request: RAGSearchRequest,
    current_user: CurrentUser,
    rag_service: RAGServiceDependency,
) -> RAGSearchResponse:
    if request.top_k > get_settings().rag_max_top_k:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"top_k must be at most {get_settings().rag_max_top_k}",
        )
    try:
        results = await rag_service.search(
            query=request.query,
            document_ids=request.document_ids,
            user_id=current_user.id,
            top_k=request.top_k,
        )
    except RAGDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    except (DocumentNotIndexableError, IndexConfigurationMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc) or "Document index is not compatible") from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Semantic search is temporarily unavailable") from exc

    return RAGSearchResponse(
        query=request.query,
        results=[
            RAGSearchResult(
                chunk_id=result.chroma_id,
                text=result.text,
                distance=result.distance,
                document_id=result.metadata["document_id"],
                page_number=result.metadata["page_number"],
                chunk_index=result.metadata["chunk_index"],
                token_count=result.metadata["token_count"],
                source_metadata=result.metadata,
            )
            for result in results
        ],
    )
