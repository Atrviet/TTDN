from __future__ import annotations

import hashlib
import re
from threading import Lock
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import chromadb
from starlette.concurrency import run_in_threadpool

from app.ai.rag.chunker import TextChunk


class VectorStoreError(Exception):
    """Raised when ChromaDB cannot complete an operation."""


@dataclass(frozen=True)
class VectorSearchResult:
    chroma_id: str
    text: str
    distance: float
    metadata: dict[str, Any]


class ChromaVectorStore:
    def __init__(self, path: Path, collection_prefix: str, provider: str, model: str) -> None:
        self.path = path.expanduser().resolve()
        model_hash = hashlib.sha256(f"{provider}:{model}".encode()).hexdigest()[:12]
        safe_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", collection_prefix)[:40]
        self.collection_name = f"{safe_prefix}_{provider}_{model_hash}"[:63]
        self.provider = provider
        self.model = model
        self._client: Any = None
        self._collection: Any = None
        self._initialization_lock = Lock()

    def _get_collection(self) -> Any:
        if self._collection is None:
            with self._initialization_lock:
                if self._collection is None:
                    self.path.mkdir(parents=True, exist_ok=True)
                    self._client = chromadb.PersistentClient(path=str(self.path))
                    self._collection = self._client.get_or_create_collection(
                        name=self.collection_name,
                        embedding_function=None,
                        metadata={
                            "hnsw:space": "cosine",
                            "embedding_provider": self.provider,
                            "embedding_model": self.model,
                        },
                    )
        return self._collection

    async def upsert_chunks(
        self,
        chunks: list[TextChunk],
        embeddings: list[list[float]],
        user_id: UUID,
        document_title: str,
    ) -> list[str]:
        if len(chunks) != len(embeddings):
            raise VectorStoreError("Chunk and embedding counts do not match")
        ids = [f"{chunk.document_id}:{chunk.chunk_index}" for chunk in chunks]

        def operation() -> None:
            self._get_collection().upsert(
                ids=ids,
                embeddings=embeddings,
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "user_id": str(user_id),
                        "document_id": str(chunk.document_id),
                        "page_number": chunk.page_number,
                        "chunk_index": chunk.chunk_index,
                        "token_count": chunk.token_count,
                        "embedding_provider": self.provider,
                        "embedding_model": self.model,
                        "document_title": document_title,
                    }
                    for chunk in chunks
                ],
            )

        try:
            await run_in_threadpool(operation)
            return ids
        except Exception as exc:
            raise VectorStoreError("Unable to upsert vectors into ChromaDB") from exc

    async def search(
        self,
        *,
        query_embedding: list[float],
        user_id: UUID,
        document_ids: list[UUID],
        top_k: int,
    ) -> list[VectorSearchResult]:
        where: dict[str, Any] = {
            "$and": [
                {"user_id": {"$eq": str(user_id)}},
                {"document_id": {"$in": [str(value) for value in document_ids]}},
            ]
        }

        def operation() -> dict[str, Any]:
            return self._get_collection().query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        try:
            result = await run_in_threadpool(operation)
            ids = (result.get("ids") or [[]])[0]
            documents = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            return [
                VectorSearchResult(
                    chroma_id=chroma_id,
                    text=document or "",
                    distance=float(distance),
                    metadata=metadata or {},
                )
                for chroma_id, document, metadata, distance in zip(
                    ids, documents, metadatas, distances, strict=True
                )
            ]
        except Exception as exc:
            raise VectorStoreError("Unable to query ChromaDB") from exc

    async def delete_document(self, document_id: UUID, user_id: UUID) -> None:
        def operation() -> None:
            self._get_collection().delete(
                where={
                    "$and": [
                        {"document_id": {"$eq": str(document_id)}},
                        {"user_id": {"$eq": str(user_id)}},
                    ]
                }
            )

        try:
            await run_in_threadpool(operation)
        except Exception as exc:
            raise VectorStoreError("Unable to delete document vectors") from exc

    async def count_document(self, document_id: UUID, user_id: UUID) -> int:
        def operation() -> int:
            result = self._get_collection().get(
                where={
                    "$and": [
                        {"document_id": {"$eq": str(document_id)}},
                        {"user_id": {"$eq": str(user_id)}},
                    ]
                },
                include=[],
            )
            return len(result.get("ids") or [])

        try:
            return await run_in_threadpool(operation)
        except Exception as exc:
            raise VectorStoreError("Unable to inspect document vectors") from exc
