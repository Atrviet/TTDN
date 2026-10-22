from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf


class InvalidPDFError(Exception):
    """Raised when uploaded bytes are not a readable PDF."""


class EncryptedPDFError(Exception):
    """Raised when a PDF requires a password."""


class EmptyPDFError(Exception):
    """Raised when a PDF has no pages or no text/image content."""


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class PDFExtractionResult:
    pages: list[ExtractedPage]
    page_count: int
    metadata: dict[str, Any]
    requires_ocr: bool


class PDFExtractor:
    @staticmethod
    def normalize_text(text: str) -> str:
        text = unicodedata.normalize("NFC", text).replace("\u00a0", " ")
        lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in text.splitlines()]
        normalized = "\n".join(lines).strip()
        return re.sub(r"\n{3,}", "\n\n", normalized)

    def extract(self, path: Path) -> PDFExtractionResult:
        try:
            with pymupdf.open(path) as pdf:
                if not pdf.is_pdf:
                    raise InvalidPDFError
                if pdf.needs_pass or pdf.is_encrypted:
                    raise EncryptedPDFError
                if pdf.page_count < 1:
                    raise EmptyPDFError

                pages: list[ExtractedPage] = []
                has_images = False
                has_text = False
                for page_index in range(pdf.page_count):
                    page = pdf.load_page(page_index)
                    text = self.normalize_text(page.get_text("text", sort=True))
                    has_text = has_text or bool(text)
                    has_images = has_images or bool(page.get_images(full=True))
                    pages.append(ExtractedPage(page_number=page_index + 1, text=text))

                if not has_text and not has_images:
                    raise EmptyPDFError

                metadata = {
                    key: str(value)[:2000]
                    for key, value in (pdf.metadata or {}).items()
                    if value not in (None, "")
                }
                return PDFExtractionResult(
                    pages=pages,
                    page_count=pdf.page_count,
                    metadata=metadata,
                    requires_ocr=not has_text and has_images,
                )
        except (EncryptedPDFError, EmptyPDFError):
            raise
        except (pymupdf.FileDataError, RuntimeError, ValueError) as exc:
            raise InvalidPDFError from exc
