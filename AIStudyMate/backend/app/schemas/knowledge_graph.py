from datetime import datetime
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RelationType(StrEnum):
    PREREQUISITE_OF = "prerequisite_of"
    PART_OF = "part_of"
    RELATED_TO = "related_to"
    EXAMPLE_OF = "example_of"
    CONTRASTS_WITH = "contrasts_with"


class ExtractedConcept(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    definition: str = Field(min_length=1, max_length=3000)
    source_chunk_id: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0, le=1)


class ExtractedRelation(BaseModel):
    source: str = Field(min_length=1, max_length=255)
    target: str = Field(min_length=1, max_length=255)
    relation_type: RelationType
    source_chunk_id: str = Field(min_length=1, max_length=255)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def distinct(self):
        if self.source.casefold().strip() == self.target.casefold().strip():
            raise ValueError("Relation endpoints must differ")
        return self


class ExtractedKnowledge(BaseModel):
    concepts: list[ExtractedConcept] = Field(default_factory=list, max_length=100)
    relations: list[ExtractedRelation] = Field(default_factory=list, max_length=200)


class GenerateKnowledgeGraphRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    document_ids: list[UUID] = Field(min_length=1, max_length=20)

    @field_validator("document_ids")
    @classmethod
    def unique_documents(cls, value):
        if len(value) != len(set(value)): raise ValueError("document_ids must be unique")
        return value


class SourceReference(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: str
    page_number: int
    definition: str | None = None
    confidence: float


class GraphNode(BaseModel):
    id: UUID
    name: str
    normalized_name: str
    definition: str | None
    sources: list[SourceReference]
    ambiguous: bool = False


class GraphEdge(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    relation_type: RelationType
    confidence: float
    source_reference: SourceReference | None


class KnowledgeGraphSummary(BaseModel):
    id: UUID
    title: str
    description: str | None
    document_ids: list[UUID]
    node_count: int
    edge_count: int
    created_at: datetime
    updated_at: datetime


class KnowledgeGraphDetail(KnowledgeGraphSummary):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class KnowledgeGraphList(BaseModel):
    items: list[KnowledgeGraphSummary]


class GraphNodesResponse(BaseModel): nodes: list[GraphNode]
class GraphEdgesResponse(BaseModel): edges: list[GraphEdge]


class ConceptDetail(GraphNode):
    incoming_edges: list[GraphEdge]
    outgoing_edges: list[GraphEdge]
