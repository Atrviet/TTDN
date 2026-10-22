from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.ai.rag.chunker import DocumentChunker
from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.factory import create_embedding_provider
from app.ai.rag.service import RAGService
from app.ai.rag.vector_store import ChromaVectorStore
from app.api.dependencies.auth import SessionDependency
from app.core.config import get_settings


@lru_cache
def get_chunker() -> DocumentChunker:
    settings = get_settings()
    return DocumentChunker(settings.rag_chunk_size, settings.rag_chunk_overlap)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return create_embedding_provider(get_settings())


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    settings = get_settings()
    provider = get_embedding_provider()
    return ChromaVectorStore(
        path=settings.chroma_persist_dir,
        collection_prefix=settings.rag_collection_prefix,
        provider=provider.provider_name,
        model=provider.model_name,
    )


ChunkerDependency = Annotated[DocumentChunker, Depends(get_chunker)]
EmbeddingDependency = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
VectorStoreDependency = Annotated[ChromaVectorStore, Depends(get_vector_store)]


def get_rag_service(
    session: SessionDependency,
    chunker: ChunkerDependency,
    embedding_provider: EmbeddingDependency,
    vector_store: VectorStoreDependency,
) -> RAGService:
    return RAGService(session, chunker, embedding_provider, vector_store)


RAGServiceDependency = Annotated[RAGService, Depends(get_rag_service)]
