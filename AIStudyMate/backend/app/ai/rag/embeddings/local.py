from __future__ import annotations

from threading import Lock
from typing import Any

from starlette.concurrency import run_in_threadpool

from app.ai.rag.embeddings.base import EmbeddingError, EmbeddingProvider


class LocalSentenceTransformerProvider(EmbeddingProvider):
    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        self._model_name = model_name
        self.batch_size = batch_size
        self._model: Any = None
        self._model_lock = Lock()

    @property
    def provider_name(self) -> str:
        return "local"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_model(self) -> Any:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self._model_name)
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        try:
            vectors = self._get_model().encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return vectors.tolist()
        except Exception as exc:
            raise EmbeddingError("Local embedding model failed") from exc

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await run_in_threadpool(self._encode, texts)

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self.embed_documents([text])
        return vectors[0]

