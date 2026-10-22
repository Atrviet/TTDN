from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.common import RAGIndexingStatus


class IndexDocumentResponse(BaseModel):
    document_id: UUID
    status: RAGIndexingStatus
    chunk_count: int = Field(ge=0)
    already_indexed: bool
    embedding_provider: str
    embedding_model: str


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    document_ids: list[UUID] = Field(min_length=1, max_length=50)
    top_k: int = Field(default=5, ge=1)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Query must not be blank")
        return normalized


class RAGSearchResult(BaseModel):
    chunk_id: str
    text: str
    distance: float = Field(ge=0)
    document_id: UUID
    page_number: int = Field(ge=1)
    chunk_index: int = Field(ge=0)
    token_count: int = Field(ge=0)
    source_metadata: dict[str, str | int | float | bool]


class RAGSearchResponse(BaseModel):
    query: str
    distance_metric: str = "cosine"
    distance_interpretation: str = "Lower distance means greater semantic similarity."
    results: list[RAGSearchResult]
