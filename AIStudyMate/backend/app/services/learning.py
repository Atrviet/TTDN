from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import UTC,datetime
from decimal import Decimal
from uuid import UUID
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.advanced_learning import LearningRecommendation,LearningTopicMapping,TopicMastery
from app.models.common import FlashcardReviewRating
from app.repositories.learning import LearningRepository
from app.schemas.learning import MasteryLevel
from app.services.knowledge_graph import normalize_concept_name

class LearningMappingNotFoundError(Exception):pass
class LearningConceptNotFoundError(Exception):pass
class LearningPersistenceError(Exception):pass

RATING_SCORE={FlashcardReviewRating.AGAIN:0.0,FlashcardReviewRating.HARD:0.4,FlashcardReviewRating.GOOD:0.75,FlashcardReviewRating.EASY:1.0}

def recency_weight(at:datetime,now:datetime,half_life_days:float)->float:
    age=max(0.0,(now-at).total_seconds()/86400);return 0.5**(age/half_life_days)
def weighted_score(events:list[tuple[float,datetime]],now:datetime,half_life_days:float)->float|None:
    if not events:return None
    weights=[recency_weight(at,now,half_life_days) for _,at in events];return sum(value*w for (value,_),w in zip(events,weights,strict=True))/sum(weights)
def practice_score(events:list[datetime],now:datetime,half_life_days:float)->float|None:
    if not events:return None
    return sum(recency_weight(at,now,half_life_days) for at in events)/len(events)
def combine_mastery(scores:dict[str,float|None],weights:dict[str,float])->tuple[float,dict[str,float]]:
    available={key:value for key,value in scores.items() if value is not None}
    if not available:raise ValueError("At least one evidence source is required")
    total=sum(weights[key] for key in available);effective={key:(weights[key]/total if key in available else 0.0) for key in weights}
    return sum(float(available[key])*effective[key] for key in available),effective

@dataclass
class RecalculationResult:
    topics_calculated:int;mappings_created:int;recommendations_created:int

class LearningService:
    def __init__(self,session:AsyncSession,*,quiz_weight:float,flashcard_weight:float,practice_weight:float,half_life_days:float,needs_review_threshold:float,strong_threshold:float)->None:
        self.session=session;self.repo=LearningRepository(session);self.weights={"quiz":quiz_weight,"flashcard":flashcard_weight,"practice":practice_weight};self.half_life_days=half_life_days;self.needs_review_threshold=needs_review_threshold;self.strong_threshold=strong_threshold
    def level(self,score:float)->MasteryLevel:
        if score<self.needs_review_threshold:return MasteryLevel.NEEDS_REVIEW
        if score<self.strong_threshold:return MasteryLevel.DEVELOPING
        return MasteryLevel.STRONG
    async def ensure_mappings(self,user_id:UUID)->int:
        existing=await self.repo.mappings(user_id);concepts=await self.repo.concepts(user_id);created=0
        groups=[("question",await self.repo.question_resources(user_id),"quiz_title"),("flashcard",await self.repo.flashcard_resources(user_id),"flashcard_deck_title"),("study_task",await self.repo.task_resources(user_id),"study_task_topic")]
        for kind,resources,provenance in groups:
            for resource_id,label,_document_id in resources:
                if (kind,resource_id) in existing:continue
                key=normalize_concept_name(label or "")
                if not key:continue
                concept=concepts.get(key);mapping=LearningTopicMapping(user_id=user_id,resource_type=kind,resource_id=resource_id,topic_key=key,topic_name=concept.name if concept else label,concept_id=concept.id if concept else None,provenance=provenance,confidence=Decimal("0.700"),is_verified=False);self.session.add(mapping);existing[(kind,resource_id)]=mapping;created+=1
        try:await self.session.flush()
        except SQLAlchemyError as exc:await self.session.rollback();raise LearningPersistenceError from exc
        return created
    async def recalculate(self,user_id:UUID,*,now:datetime|None=None)->RecalculationResult:
        current=now or datetime.now(UTC);created=await self.ensure_mappings(user_id);topics:dict[str,dict]={}
        def topic(key,name,concept_id):return topics.setdefault(key,{"name":name,"concept_id":concept_id,"quiz":[],"flashcard":[],"practice":[]})
        for key,name,concept_id,correct,at in await self.repo.quiz_evidence(user_id):topic(key,name,concept_id)["quiz"].append((1.0 if correct else 0.0,at))
        for key,name,concept_id,rating,at in await self.repo.flashcard_evidence(user_id):topic(key,name,concept_id)["flashcard"].append((RATING_SCORE[rating],at))
        for key,name,concept_id,at in await self.repo.practice_evidence(user_id):topic(key,name,concept_id)["practice"].append(at)
        existing={item.topic_key:item for item in await self.repo.mastery(user_id)};active=set();recommendations=0
        for key,data in topics.items():
            scores={"quiz":weighted_score(data["quiz"],current,self.half_life_days),"flashcard":weighted_score(data["flashcard"],current,self.half_life_days),"practice":practice_score(data["practice"],current,self.half_life_days)}
            score,effective=combine_mastery(scores,self.weights);events=[at for values in (data["quiz"],data["flashcard"]) for _,at in values]+list(data["practice"]);count=sum(len(data[name]) for name in ("quiz","flashcard","practice"));item=existing.get(key)
            if item is None:item=TopicMastery(user_id=user_id,topic_key=key,topic_name=data["name"],mastery_score=Decimal("0"));self.session.add(item)
            item.topic_name=data["name"];item.concept_id=data["concept_id"];item.mastery_score=Decimal(str(round(score,4)));item.evidence_count=count;item.last_evidence_at=max(events);item.last_practiced_at=max(events);item.last_calculated_at=current;item.evidence_details={name:{"score":round(scores[name],4) if scores[name] is not None else None,"evidence_count":len(data[name]),"configured_weight":self.weights[name],"effective_weight":round(effective[name],4)} for name in self.weights};active.add(key)
            for old in list(item.recommendations):await self.session.delete(old)
            await self.session.flush()
            if self.level(score)!=MasteryLevel.STRONG:
                actions=await self.repo.topic_actions(user_id,key,item.concept_id);recommendations+=self._recommend(item,actions,score)
        for key,item in existing.items():
            if key not in active:await self.session.delete(item)
        try:await self.session.commit()
        except SQLAlchemyError as exc:await self.session.rollback();raise LearningPersistenceError from exc
        return RecalculationResult(len(topics),created,recommendations)
    def _recommend(self,item:TopicMastery,actions:dict,score:float)->int:
        level=self.level(score).value;metadata={"topic_key":item.topic_key,"mastery_score":round(score,4)};common={"topic_mastery_id":item.id,"rationale":f"Chủ đề {item.topic_name} đang ở mức {level}, dựa trên {item.evidence_count} bằng chứng thực tế."};items=[]
        if actions["document_sources"]:
            src=actions["document_sources"][0];items.append(LearningRecommendation(**common,recommendation_type="document_review",title=f"Đọc lại phần {item.topic_name}",document_id=UUID(src["document_id"]),action_url=f"/documents/{src['document_id']}?page={src['page_number']}",recommendation_metadata={**metadata,**src}))
        if actions["flashcard_ids"]:items.append(LearningRecommendation(**common,recommendation_type="flashcard_review",title=f"Ôn flashcard: {item.topic_name}",action_url="/flashcards/study",recommendation_metadata={**metadata,"flashcard_ids":actions["flashcard_ids"]}))
        if actions["quiz_ids"]:items.append(LearningRecommendation(**common,recommendation_type="practice_quiz",title=f"Luyện quiz: {item.topic_name}",action_url="/quizzes",recommendation_metadata={**metadata,"quiz_ids":actions["quiz_ids"]}))
        if actions["study_plan_ids"]:items.append(LearningRecommendation(**common,recommendation_type="study_plan",title=f"Tiếp tục kế hoạch: {item.topic_name}",action_url=f"/study-plans/{actions['study_plan_ids'][0]}",recommendation_metadata={**metadata,"study_plan_ids":actions["study_plan_ids"]}))
        items.append(LearningRecommendation(**common,recommendation_type="tutor",title=f"Học cùng AI Tutor: {item.topic_name}",action_url=f"/tutor?topic={item.topic_key}",recommendation_metadata=metadata));self.session.add_all(items);return len(items)
    async def mastery(self,user_id:UUID):return await self.repo.mastery(user_id)
    async def correct_mapping(self,mapping_id:UUID,user_id:UUID,topic_name:str,concept_id:UUID|None):
        mapping=await self.repo.mapping_owned(mapping_id,user_id)
        if mapping is None:raise LearningMappingNotFoundError
        concept=None
        if concept_id:
            concept=await self.repo.concept_owned(concept_id,user_id)
            if concept is None:raise LearningConceptNotFoundError
        mapping.topic_key=concept.normalized_name if concept else normalize_concept_name(topic_name);mapping.topic_name=concept.name if concept else topic_name;mapping.concept_id=concept.id if concept else None;mapping.provenance="user_corrected";mapping.confidence=Decimal("1.000");mapping.is_verified=True
        try:await self.session.commit()
        except SQLAlchemyError as exc:await self.session.rollback();raise LearningPersistenceError from exc
        return mapping
