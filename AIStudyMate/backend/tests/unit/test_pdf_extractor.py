from pathlib import Path

import pymupdf
import pytest

from app.services.pdf_extractor import EmptyPDFError, EncryptedPDFError, InvalidPDFError, PDFExtractor


def save_pdf(path: Path, *, text: str | None = None, image_only: bool = False) -> None:
    pdf = pymupdf.open()
    page = pdf.new_page()
    if text:
        page.insert_htmlbox(page.rect + (40, 40, -40, -40), f"<p>{text}</p>")
    if image_only:
        pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 20), False)
        pixmap.clear_with(220)
        page.insert_image(pymupdf.Rect(40, 40, 200, 200), pixmap=pixmap)
    pdf.save(path)
    pdf.close()


def test_extracts_vietnamese_text_and_page_boundaries(tmp_path: Path) -> None:
    path = tmp_path / "vietnamese.pdf"
    save_pdf(path, text="Tài liệu học tập tiếng Việt")

    result = PDFExtractor().extract(path)

    assert result.page_count == 1
    assert result.pages[0].page_number == 1
    assert "Tài liệu học tập tiếng Việt" in result.pages[0].text
    assert result.requires_ocr is False


def test_image_only_pdf_is_marked_as_requiring_ocr(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    save_pdf(path, image_only=True)

    result = PDFExtractor().extract(path)

    assert result.pages[0].text == ""
    assert result.requires_ocr is True


def test_blank_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    save_pdf(path)

    with pytest.raises(EmptyPDFError):
        PDFExtractor().extract(path)


@pytest.mark.parametrize("content", [b"not a pdf", b"%PDF-1.7\ncorrupted content"])
def test_invalid_and_corrupted_pdf_are_rejected(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "invalid.pdf"
    path.write_bytes(content)

    with pytest.raises(InvalidPDFError):
        PDFExtractor().extract(path)


def test_encrypted_pdf_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Secret")
    pdf.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    pdf.close()

    with pytest.raises(EncryptedPDFError):
        PDFExtractor().extract(path)

