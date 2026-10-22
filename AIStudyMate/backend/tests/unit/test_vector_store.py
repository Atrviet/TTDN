from pathlib import Path
from uuid import uuid4

import pytest

from app.ai.rag.chunker import TextChunk
from app.ai.rag.vector_store import ChromaVectorStore


@pytest.mark.asyncio
async def test_vector_insert_semantic_search_and_delete(tmp_path: Path) -> None:
    user_id = uuid4()
    document_id = uuid4()
    store = ChromaVectorStore(tmp_path / "chroma", "test_chunks", "test", "deterministic-v1")
    chunks = [
        TextChunk(document_id, 1, 0, "apple fruit", 2),
        TextChunk(document_id, 2, 1, "database systems", 2),
    ]

    ids = await store.upsert_chunks(
        chunks,
        [[1.0, 0.0], [0.0, 1.0]],
        user_id,
        "Test document",
    )
    results = await store.search(
        query_embedding=[1.0, 0.0],
        user_id=user_id,
        document_ids=[document_id],
        top_k=2,
    )

    assert ids == [f"{document_id}:0", f"{document_id}:1"]
    assert results[0].text == "apple fruit"
    assert results[0].distance <= results[1].distance
    assert await store.count_document(document_id, user_id) == 2

    await store.delete_document(document_id, user_id)
    assert await store.count_document(document_id, user_id) == 0

