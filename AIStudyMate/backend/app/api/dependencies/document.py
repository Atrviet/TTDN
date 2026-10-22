from typing import Annotated

from fastapi import Depends

from app.api.dependencies.auth import SessionDependency
from app.core.config import get_settings
from app.services.document import DocumentService
from app.services.pdf_extractor import PDFExtractor
from app.services.storage import LocalDocumentStorage


def get_document_storage() -> LocalDocumentStorage:
    settings = get_settings()
    return LocalDocumentStorage(settings.document_storage_dir)


def get_pdf_extractor() -> PDFExtractor:
    return PDFExtractor()


def get_max_pdf_size() -> int:
    return get_settings().max_pdf_size_bytes


StorageDependency = Annotated[LocalDocumentStorage, Depends(get_document_storage)]
ExtractorDependency = Annotated[PDFExtractor, Depends(get_pdf_extractor)]
MaxPDFSizeDependency = Annotated[int, Depends(get_max_pdf_size)]


def get_document_service(
    session: SessionDependency,
    storage: StorageDependency,
    extractor: ExtractorDependency,
    max_upload_size: MaxPDFSizeDependency,
) -> DocumentService:
    return DocumentService(
        session=session,
        storage=storage,
        extractor=extractor,
        max_upload_size=max_upload_size,
    )


DocumentServiceDependency = Annotated[DocumentService, Depends(get_document_service)]
