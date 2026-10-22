from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import UploadFile

from app.services.storage import (
    EmptyUploadError,
    FileTooLargeError,
    LocalDocumentStorage,
    StorageError,
)


@pytest.mark.asyncio
async def test_streams_upload_and_uses_safe_uuid_path(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / "storage")
    upload = UploadFile(filename="../../unsafe.pdf", file=BytesIO(b"%PDF-safe"))

    temporary = await storage.save_temporary(upload, max_size=1024)
    relative_path = await storage.promote(temporary.path, uuid4())

    assert temporary.original_filename == "unsafe.pdf"
    assert relative_path.endswith(".pdf")
    assert ".." not in relative_path
    assert storage.resolve_relative_path(relative_path).read_bytes() == b"%PDF-safe"


@pytest.mark.asyncio
async def test_oversized_upload_is_rejected_and_cleaned(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / "storage")
    upload = UploadFile(filename="large.pdf", file=BytesIO(b"12345"))

    with pytest.raises(FileTooLargeError):
        await storage.save_temporary(upload, max_size=4)

    assert list((tmp_path / "storage" / ".staging").iterdir()) == []


@pytest.mark.asyncio
async def test_empty_upload_is_rejected(tmp_path: Path) -> None:
    storage = LocalDocumentStorage(tmp_path / "storage")
    upload = UploadFile(filename="empty.pdf", file=BytesIO(b""))

    with pytest.raises(EmptyUploadError):
        await storage.save_temporary(upload, max_size=10)


@pytest.mark.asyncio
async def test_filesystem_failure_is_wrapped(tmp_path: Path) -> None:
    invalid_root = tmp_path / "file-not-directory"
    invalid_root.write_text("blocking directory creation")
    storage = LocalDocumentStorage(invalid_root)
    upload = UploadFile(filename="document.pdf", file=BytesIO(b"data"))

    with pytest.raises(StorageError):
        await storage.save_temporary(upload, max_size=10)

