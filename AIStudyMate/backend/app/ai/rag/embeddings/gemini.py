from __future__ import annotations

from google import genai
from google.genai import errors, types

from app.ai.rag.embeddings.base import EmbeddingError, EmbeddingProvider


class GeminiEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        dimensions: int | None,
        batch_size: int,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required")
        self._model_name = model_name
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=int(timeout_seconds * 1000),
                retry_options=types.HttpRetryOptions(
                    attempts=max_retries,
                    initial_delay=1.0,
                    max_delay=10.0,
                    exp_base=2.0,
                    jitter=0.5,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        try:
            for offset in range(0, len(texts), self.batch_size):
                batch = texts[offset : offset + self.batch_size]
                config: dict[str, object] = {"task_type": task_type}
                if self.dimensions is not None:
                    config["output_dimensionality"] = self.dimensions
                response = await self.client.aio.models.embed_content(
                    model=self._model_name,
                    contents=batch,
                    config=config,
                )
                if not response.embeddings or len(response.embeddings) != len(batch):
                    raise EmbeddingError("Gemini returned an incomplete embedding response")
                for embedding in response.embeddings:
                    if not embedding.values:
                        raise EmbeddingError("Gemini returned an empty embedding")
                    vectors.append([float(value) for value in embedding.values])
            return vectors
        except EmbeddingError:
            raise
        except (errors.APIError, TimeoutError, OSError) as exc:
            raise EmbeddingError("Gemini embedding request failed") from exc
        except Exception as exc:
            raise EmbeddingError("Gemini embedding request failed") from exc

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        return (await self._embed([text], "RETRIEVAL_QUERY"))[0]

