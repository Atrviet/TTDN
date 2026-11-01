from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class MasteryLevel(StrEnum):
    NEEDS_REVIEW="needs_review"
    DEVELOPING="developing"
    STRONG="strong"

class EvidenceComponent(BaseModel):
    score: float | None
    evidence_count: int
    configured_weight: float
    effective_weight: float

class TopicMasteryResponse(BaseModel):
    id: UUID
    topic_id: UUID | None
    topic_key: str
    topic_name: str
    mastery_score: float
    mastery_percentage: float
    level: MasteryLevel
    evidence_count: int
    last_practiced_at: datetime | None
    last_calculated_at: datetime
    components: dict[str,EvidenceComponent]

class MasteryListResponse(BaseModel):
    items:list[TopicMasteryResponse]
    thresholds:dict[str,float]
    formula:str

class WeakTopicsResponse(MasteryListResponse): pass

class RecommendationResponse(BaseModel):
    id:UUID
    topic_key:str
    topic_name:str
    recommendation_type:str
    title:str
    rationale:str
    action_url:str|None
    metadata:dict[str,Any]

class RecommendationListResponse(BaseModel): items:list[RecommendationResponse]

class RecalculateResponse(BaseModel):
    topics_calculated:int
    mappings_created:int
    recommendations_created:int
    mastery:MasteryListResponse

class TopicMappingResponse(BaseModel):
    id:UUID
    resource_type:str
    resource_id:UUID
    topic_key:str
    topic_name:str
    topic_id:UUID|None
    provenance:str
    confidence:float
    is_verified:bool

class CorrectTopicMappingRequest(BaseModel):
    model_config=ConfigDict(str_strip_whitespace=True)
    topic_name:str=Field(min_length=1,max_length=255)
    concept_id:UUID|None=None

