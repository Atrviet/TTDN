import os
from pathlib import Path
from uuid import uuid4

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.dependencies.document import get_document_storage, get_max_pdf_size
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.common import UserRole
from app.models.document import Document
from app.models.user import User
from app.services.storage import LocalDocumentStorage, StorageError


def get_safe_test_database_url() -> str:
    test_url = os.getenv("TEST_DATABASE_URL")
    if not test_url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    parsed = make_url(test_url)
    development_url = os.getenv("DATABASE_URL")
    if parsed.get_backend_name() != "postgresql":
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if not parsed.database or "test" not in parsed.database.lower():
        pytest.fail("TEST_DATABASE_URL database name must contain 'test'")
    if development_url and make_url(development_url) == parsed:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL")
    return test_url


def make_pdf(*, text: str | None = None, image_only: bool = False) -> bytes:
    pdf = pymupdf.open()
    page = pdf.new_page()
    if text:
        page.insert_htmlbox(page.rect + (40, 40, -40, -40), f"<p>{text}</p>")
    if image_only:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
        pixmap.clear_with(180)
        page.insert_image(pymupdf.Rect(40, 40, 200, 200), pixmap=pixmap)
    content = pdf.tobytes()
    pdf.close()
    return content


class FailingStorage(LocalDocumentStorage):
    async def save_temporary(self, upload, max_size):
        raise StorageError("simulated filesystem failure")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_document_api_workflow(tmp_path: Path) -> None:
    engine = create_async_engine(get_safe_test_database_url())
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    storage = LocalDocumentStorage(tmp_path / "documents")

    async def override_session():
        async with session_factory() as session:
            yield session

    suffix = uuid4().hex[:10]
    user = User(
        username=f"document_owner_{suffix}",
        email=f"document_owner_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Document Owner",
        role=UserRole.STUDENT,
    )
    other_user = User(
        username=f"document_other_{suffix}",
        email=f"document_other_{suffix}@example.com",
        hashed_password=hash_password("SecurePassword123"),
        full_name="Other User",
        role=UserRole.STUDENT,
    )
    async with session_factory() as session:
        session.add_all([user, other_user])
        await session.commit()
        await session.refresh(user)
        await session.refresh(other_user)

    owner_headers = {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
    other_headers = {"Authorization": f"Bearer {create_access_token(other_user.id, other_user.role)}"}
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_document_storage] = lambda: storage
    app.dependency_overrides[get_max_pdf_size] = lambda: 1024 * 1024
    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            pdf_bytes = make_pdf(text="Giáo trình trí tuệ nhân tạo bằng tiếng Việt")

            missing_jwt = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("lesson.pdf", pdf_bytes, "application/pdf")},
            )
            assert missing_jwt.status_code == 401

            uploaded = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                data={"title": "Bài học AI"},
                files={"file": ("../../unsafe.pdf", pdf_bytes, "text/plain")},
            )
            assert uploaded.status_code == 201, uploaded.text
            document = uploaded.json()
            document_id = document["id"]
            assert document["original_filename"] == "unsafe.pdf"
            assert document["mime_type"] == "application/pdf"
            assert document["processing_status"] == "ready"
            assert document["requires_ocr"] is False
            assert "file_path" not in document

            stored_files = [path for path in (tmp_path / "documents").rglob("*.pdf")]
            assert len(stored_files) == 1
            assert stored_files[0].name != "unsafe.pdf"

            details = await client.get(f"/api/v1/documents/{document_id}", headers=owner_headers)
            assert details.status_code == 200
            assert details.json()["title"] == "Bài học AI"

            content = await client.get(
                f"/api/v1/documents/{document_id}/content",
                headers=owner_headers,
            )
            assert content.status_code == 200
            assert content.json()["pages"][0]["page_number"] == 1
            assert "tiếng Việt" in content.json()["pages"][0]["text"]

            second = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                files={"file": ("second.pdf", make_pdf(text="Second PDF"), "application/pdf")},
            )
            assert second.status_code == 201

            page_one = await client.get(
                "/api/v1/documents?page=1&per_page=1",
                headers=owner_headers,
            )
            page_two = await client.get(
                "/api/v1/documents?page=2&per_page=1",
                headers=owner_headers,
            )
            assert page_one.status_code == 200
            assert page_one.json()["total"] == 2
            assert len(page_one.json()["items"]) == 1
            assert len(page_two.json()["items"]) == 1

            for path in (
                f"/api/v1/documents/{document_id}",
                f"/api/v1/documents/{document_id}/content",
            ):
                isolated = await client.get(path, headers=other_headers)
                assert isolated.status_code == 404
            isolated_delete = await client.delete(
                f"/api/v1/documents/{document_id}", headers=other_headers
            )
            assert isolated_delete.status_code == 404

            scanned = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                files={"file": ("scan.pdf", make_pdf(image_only=True), "application/pdf")},
            )
            assert scanned.status_code == 201
            assert scanned.json()["requires_ocr"] is True

            for filename, payload in (
                ("invalid.pdf", b"not a pdf"),
                ("corrupt.pdf", b"%PDF-1.7\ncorrupted"),
                ("blank.pdf", make_pdf()),
            ):
                rejected = await client.post(
                    "/api/v1/documents/upload",
                    headers=owner_headers,
                    files={"file": (filename, payload, "application/pdf")},
                )
                assert rejected.status_code == 422

            empty = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                files={"file": ("empty.pdf", b"", "application/pdf")},
            )
            assert empty.status_code == 422

            app.dependency_overrides[get_max_pdf_size] = lambda: 10
            oversized = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                files={"file": ("large.pdf", pdf_bytes, "application/pdf")},
            )
            assert oversized.status_code == 413
            app.dependency_overrides[get_max_pdf_size] = lambda: 1024 * 1024

            app.dependency_overrides[get_document_storage] = lambda: FailingStorage(
                tmp_path / "failure"
            )
            filesystem_failure = await client.post(
                "/api/v1/documents/upload",
                headers=owner_headers,
                files={"file": ("failure.pdf", pdf_bytes, "application/pdf")},
            )
            assert filesystem_failure.status_code == 500
            app.dependency_overrides[get_document_storage] = lambda: storage

            deleted = await client.delete(
                f"/api/v1/documents/{document_id}", headers=owner_headers
            )
            assert deleted.status_code == 204
            missing = await client.get(f"/api/v1/documents/{document_id}", headers=owner_headers)
            assert missing.status_code == 404
            assert not stored_files[0].exists()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_document_storage, None)
        app.dependency_overrides.pop(get_max_pdf_size, None)
        async with session_factory() as session:
            await session.execute(
                delete(Document).where(Document.user_id.in_([user.id, other_user.id]))
            )
            await session.execute(delete(User).where(User.id.in_([user.id, other_user.id])))
            await session.commit()
        await engine.dispose()
