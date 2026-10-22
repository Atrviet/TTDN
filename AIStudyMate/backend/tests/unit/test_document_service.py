from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError

from app.services.document import DocumentDatabaseError, DocumentService
from app.services.pdf_extractor import ExtractedPage, PDFExtractionResult
from app.services.storage import TemporaryUpload


@pytest.mark.asyncio
async def test_database_failure_removes_promoted_file() -> None:
    session = MagicMock()
    session.commit = AsyncMock(side_effect=SQLAlchemyError("database unavailable"))
    session.rollback = AsyncMock()
    storage = MagicMock()
    storage.save_temporary = AsyncMock(
        return_value=TemporaryUpload(Path("/tmp/upload.part"), 100, "lesson.pdf")
    )
    storage.promote = AsyncMock(return_value="user-id/document-id.pdf")
    storage.delete = AsyncMock()
    extractor = MagicMock()
    extractor.extract.return_value = PDFExtractionResult(
        pages=[ExtractedPage(page_number=1, text="Lesson")],
        page_count=1,
        metadata={},
        requires_ocr=False,
    )
    service = DocumentService(session, storage, extractor, max_upload_size=1024)

    with pytest.raises(DocumentDatabaseError):
        await service.upload(
            upload=MagicMock(spec=UploadFile),
            user_id=uuid4(),
            title="Lesson",
        )

    session.rollback.assert_awaited_once()
    storage.delete.assert_awaited_once_with("user-id/document-id.pdf")
