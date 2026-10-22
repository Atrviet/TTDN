from abc import ABC, abstractmethod


class EmbeddingError(Exception):
    """Raised when an embedding provider cannot produce vectors."""


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...

