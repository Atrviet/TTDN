from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from app.ai.rag.embeddings.gemini import GeminiEmbeddingProvider
from app.ai.rag.embeddings.local import LocalSentenceTransformerProvider


class FakeSentenceTransformer:
    def encode(self, texts, **kwargs):
        assert kwargs["normalize_embeddings"] is True
        return np.asarray([[float(len(text)), 1.0] for text in texts])


@pytest.mark.asyncio
async def test_local_embedding_provider_runs_model_and_returns_vectors() -> None:
    provider = LocalSentenceTransformerProvider("fake-model", batch_size=2)
    provider._model = FakeSentenceTransformer()

    vectors = await provider.embed_documents(["xin chào", "Việt Nam"])

    assert vectors == [[8.0, 1.0], [8.0, 1.0]]
    assert await provider.embed_query("abc") == [3.0, 1.0]


@pytest.mark.asyncio
async def test_gemini_uses_distinct_retrieval_task_types() -> None:
    provider = GeminiEmbeddingProvider(
        api_key="test-key",
        model_name="gemini-embedding-001",
        dimensions=3,
        batch_size=10,
        timeout_seconds=5,
        max_retries=2,
    )
    embed_content = AsyncMock(
        side_effect=[
            SimpleNamespace(
                embeddings=[SimpleNamespace(values=[1.0, 0.0, 0.0])]
            ),
            SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.0, 1.0, 0.0])]
            ),
        ]
    )
    provider.client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(embed_content=embed_content))
    )

    await provider.embed_documents(["tài liệu"])
    await provider.embed_query("câu hỏi")

    assert embed_content.await_args_list[0].kwargs["config"]["task_type"] == "RETRIEVAL_DOCUMENT"
    assert embed_content.await_args_list[1].kwargs["config"]["task_type"] == "RETRIEVAL_QUERY"
    assert embed_content.await_args_list[0].kwargs["config"]["output_dimensionality"] == 3

