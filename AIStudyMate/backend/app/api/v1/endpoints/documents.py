from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.document import DocumentServiceDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import (
    DocumentNotIndexableError,
    IndexConfigurationMismatchError,
    IndexingInProgressError,
    RAGDocumentNotFoundError,
    RAGPersistenceError,
)
from app.ai.rag.vector_store import VectorStoreError
from app.schemas.document import (
    DocumentContentResponse,
    DocumentListResponse,
    DocumentPageContent,
    DocumentResponse,
)
from app.schemas.rag import IndexDocumentResponse
from app.services.document import (
    DocumentDatabaseError,
    DocumentNotFoundError,
    DocumentVectorCleanupError,
)
from app.services.pdf_extractor import EmptyPDFError, EncryptedPDFError, InvalidPDFError
from app.services.storage import EmptyUploadError, FileTooLargeError, StorageError


router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/{document_id}/index", response_model=IndexDocumentResponse)
async def index_document(
    document_id: UUID,
    current_user: CurrentUser,
    rag_service: RAGServiceDependency,
) -> IndexDocumentResponse:
    try:
        result = await rag_service.index_document(document_id, current_user.id)
    except RAGDocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    except DocumentNotIndexableError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except (IndexingInProgressError, IndexConfigurationMismatchError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc) or "Indexing conflict") from exc
    except (EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document indexing is temporarily unavailable") from exc
    except RAGPersistenceError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Index metadata could not be persisted") from exc
    return IndexDocumentResponse(**result.__dict__)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: CurrentUser,
    document_service: DocumentServiceDependency,
    file: Annotated[UploadFile, File(description="PDF learning document")],
    title: Annotated[str | None, Form(max_length=255)] = None,
) -> DocumentResponse:
    try:
        document = await document_service.upload(
            upload=file,
            user_id=current_user.id,
            title=title,
        )
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="PDF is too large") from exc
    except EmptyUploadError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Uploaded file is empty") from exc
    except EncryptedPDFError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Encrypted PDFs are not supported") from exc
    except EmptyPDFError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="PDF contains no readable pages or content") from exc
    except InvalidPDFError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="File is not a valid PDF") from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document storage operation failed") from exc
    except DocumentDatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document could not be persisted") from exc
    return DocumentResponse.model_validate(document)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    current_user: CurrentUser,
    document_service: DocumentServiceDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DocumentListResponse:
    documents, total = await document_service.list_owned(
        current_user.id,
        page=page,
        per_page=per_page,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(document) for document in documents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: CurrentUser,
    document_service: DocumentServiceDependency,
) -> DocumentResponse:
    try:
        document = await document_service.get_owned(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: UUID,
    current_user: CurrentUser,
    document_service: DocumentServiceDependency,
) -> DocumentContentResponse:
    try:
        document = await document_service.get_owned(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    return DocumentContentResponse(
        document_id=document.id,
        title=document.title,
        page_count=document.page_count or 0,
        requires_ocr=document.requires_ocr,
        pages=[DocumentPageContent.model_validate(page) for page in document.extracted_pages or []],
        metadata=document.pdf_metadata or {},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    current_user: CurrentUser,
    document_service: DocumentServiceDependency,
) -> None:
    try:
        await document_service.delete_owned(document_id, current_user.id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document storage operation failed") from exc
    except DocumentDatabaseError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document could not be deleted") from exc
    except DocumentVectorCleanupError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document vectors could not be deleted") from exc
