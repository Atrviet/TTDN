from uuid import UUID
from fastapi import APIRouter,HTTPException
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.learning import LearningServiceDependency
from app.schemas.learning import CorrectTopicMappingRequest,EvidenceComponent,MasteryLevel,MasteryListResponse,RecalculateResponse,RecommendationListResponse,RecommendationResponse,TopicMappingResponse,TopicMasteryResponse,WeakTopicsResponse
from app.services.learning import LearningConceptNotFoundError,LearningMappingNotFoundError,LearningPersistenceError

router=APIRouter(prefix="/learning",tags=["Adaptive Learning"])
FORMULA="Available-source normalized baseline: quiz 60%, flashcard recall 30%, recent completed study tasks 10%; evidence is exponentially decayed with the configured half-life."
def thresholds(service):return {"needs_review_below":service.needs_review_threshold,"developing_below":service.strong_threshold,"strong_from":service.strong_threshold}
def mastery_item(item,service):
    score=float(item.mastery_score);details=item.evidence_details or {};components={name:EvidenceComponent(**details.get(name,{"score":None,"evidence_count":0,"configured_weight":service.weights[name],"effective_weight":0})) for name in service.weights}
    return TopicMasteryResponse(id=item.id,topic_id=item.concept_id,topic_key=item.topic_key,topic_name=item.topic_name,mastery_score=score,mastery_percentage=round(score*100,2),level=service.level(score),evidence_count=item.evidence_count,last_practiced_at=item.last_practiced_at,last_calculated_at=item.last_calculated_at,components=components)
async def mastery_response(user,service,weak=False):
    items=[mastery_item(x,service) for x in await service.mastery(user.id)];items=[x for x in items if x.level==MasteryLevel.NEEDS_REVIEW] if weak else items
    cls=WeakTopicsResponse if weak else MasteryListResponse;return cls(items=items,thresholds=thresholds(service),formula=FORMULA)
@router.get("/weak-topics",response_model=WeakTopicsResponse)
async def weak_topics(user:CurrentUser,service:LearningServiceDependency):return await mastery_response(user,service,True)
@router.get("/mastery",response_model=MasteryListResponse)
async def mastery(user:CurrentUser,service:LearningServiceDependency):return await mastery_response(user,service)
@router.get("/recommendations",response_model=RecommendationListResponse)
async def recommendations(user:CurrentUser,service:LearningServiceDependency):
    result=[]
    for item in await service.mastery(user.id):
        for rec in item.recommendations:result.append(RecommendationResponse(id=rec.id,topic_key=item.topic_key,topic_name=item.topic_name,recommendation_type=rec.recommendation_type,title=rec.title,rationale=rec.rationale,action_url=rec.action_url,metadata=rec.recommendation_metadata or {}))
    return RecommendationListResponse(items=result)
@router.post("/mastery/recalculate",response_model=RecalculateResponse)
async def recalculate(user:CurrentUser,service:LearningServiceDependency):
    try:result=await service.recalculate(user.id)
    except LearningPersistenceError as exc:raise HTTPException(500,"Unable to recalculate mastery") from exc
    view=await mastery_response(user,service);return RecalculateResponse(topics_calculated=result.topics_calculated,mappings_created=result.mappings_created,recommendations_created=result.recommendations_created,mastery=view)
@router.get("/topic-mappings",response_model=list[TopicMappingResponse])
async def mappings(user:CurrentUser,service:LearningServiceDependency):
    values=await service.repo.mappings(user.id);return [TopicMappingResponse(id=x.id,resource_type=x.resource_type,resource_id=x.resource_id,topic_key=x.topic_key,topic_name=x.topic_name,topic_id=x.concept_id,provenance=x.provenance,confidence=float(x.confidence),is_verified=x.is_verified) for x in values.values()]
@router.patch("/topic-mappings/{mapping_id}",response_model=TopicMappingResponse)
async def correct_mapping(mapping_id:UUID,payload:CorrectTopicMappingRequest,user:CurrentUser,service:LearningServiceDependency):
    try:x=await service.correct_mapping(mapping_id,user.id,payload.topic_name,payload.concept_id)
    except (LearningMappingNotFoundError,LearningConceptNotFoundError) as exc:raise HTTPException(404,"Topic mapping or concept not found") from exc
    return TopicMappingResponse(id=x.id,resource_type=x.resource_type,resource_id=x.resource_id,topic_key=x.topic_key,topic_name=x.topic_name,topic_id=x.concept_id,provenance=x.provenance,confidence=float(x.confidence),is_verified=x.is_verified)
