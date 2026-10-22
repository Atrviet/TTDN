from app.ai.rag.embeddings.base import EmbeddingProvider
from app.ai.rag.embeddings.gemini import GeminiEmbeddingProvider
from app.ai.rag.embeddings.local import LocalSentenceTransformerProvider
from app.core.config import Settings


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "gemini":
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_embedding_model,
            dimensions=settings.embedding_dimensions,
            batch_size=settings.embedding_batch_size,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_retries=settings.embedding_max_retries,
        )
    return LocalSentenceTransformerProvider(
        model_name=settings.local_embedding_model,
        batch_size=settings.embedding_batch_size,
    )
