from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID


TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)


@dataclass(frozen=True)
class TextChunk:
    document_id: UUID
    page_number: int
    chunk_index: int
    text: str
    token_count: int


class DocumentChunker:
    def __init__(self, chunk_size: int = 500, overlap: int = 75) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFC", text).replace("\u00a0", " ")
        lines = [re.sub(r"[ \t]+", " ", line).rstrip() for line in normalized.splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

    @staticmethod
    def count_tokens(text: str) -> int:
        return len(TOKEN_PATTERN.findall(text))

    def chunk_pages(self, document_id: UUID, pages: list[dict[str, object]]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        chunk_index = 0
        step = self.chunk_size - self.overlap

        for page_data in pages:
            page_number = int(page_data["page_number"])
            text = self.normalize_text(str(page_data.get("text", "")))
            token_matches = list(TOKEN_PATTERN.finditer(text))
            if not token_matches:
                continue

            for start in range(0, len(token_matches), step):
                window = token_matches[start : start + self.chunk_size]
                if not window:
                    break
                chunk_text = text[window[0].start() : window[-1].end()].strip()
                chunks.append(
                    TextChunk(
                        document_id=document_id,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        token_count=len(window),
                    )
                )
                chunk_index += 1
                if start + self.chunk_size >= len(token_matches):
                    break
        return chunks

