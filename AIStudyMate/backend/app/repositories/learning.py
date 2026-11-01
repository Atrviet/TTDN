from datetime import datetime
from uuid import UUID
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.advanced_learning import Flashcard,FlashcardDeck,FlashcardReview,KnowledgeConcept,KnowledgeGraphConcept,LearningRecommendation,LearningTopicMapping,StudyPlan,StudyTask,TopicMastery
from app.models.quiz import Question,Quiz,QuizAttempt,UserAnswer

class LearningRepository:
    def __init__(self,session:AsyncSession)->None:self.session=session
    async def concepts(self,user_id:UUID):
        rows=await self.session.scalars(select(KnowledgeConcept).where(KnowledgeConcept.user_id==user_id));return {x.normalized_name:x for x in rows.all()}
    async def mappings(self,user_id:UUID):
        rows=await self.session.scalars(select(LearningTopicMapping).where(LearningTopicMapping.user_id==user_id));return {(x.resource_type,x.resource_id):x for x in rows.all()}
    async def question_resources(self,user_id:UUID):
        rows=await self.session.execute(select(Question.id,Quiz.title,Quiz.document_id).join(Quiz,Quiz.id==Question.quiz_id).where(Quiz.user_id==user_id));return list(rows.all())
    async def flashcard_resources(self,user_id:UUID):
        rows=await self.session.execute(select(Flashcard.id,FlashcardDeck.title,Flashcard.source_document_id).join(FlashcardDeck,FlashcardDeck.id==Flashcard.deck_id).where(FlashcardDeck.user_id==user_id));return list(rows.all())
    async def task_resources(self,user_id:UUID):
        rows=await self.session.execute(select(StudyTask.id,StudyTask.topic,StudyTask.document_id).join(StudyPlan,StudyPlan.id==StudyTask.plan_id).where(StudyPlan.user_id==user_id));return list(rows.all())
    async def quiz_evidence(self,user_id:UUID):
        rows=await self.session.execute(select(LearningTopicMapping.topic_key,LearningTopicMapping.topic_name,LearningTopicMapping.concept_id,UserAnswer.is_correct,UserAnswer.answered_at).join(UserAnswer,UserAnswer.question_id==LearningTopicMapping.resource_id).join(QuizAttempt,QuizAttempt.id==UserAnswer.attempt_id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="question",QuizAttempt.user_id==user_id,QuizAttempt.completed_at.is_not(None)));return list(rows.all())
    async def flashcard_evidence(self,user_id:UUID):
        rows=await self.session.execute(select(LearningTopicMapping.topic_key,LearningTopicMapping.topic_name,LearningTopicMapping.concept_id,FlashcardReview.rating,FlashcardReview.reviewed_at).join(FlashcardReview,FlashcardReview.flashcard_id==LearningTopicMapping.resource_id).join(Flashcard,Flashcard.id==FlashcardReview.flashcard_id).join(FlashcardDeck,FlashcardDeck.id==Flashcard.deck_id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="flashcard",FlashcardDeck.user_id==user_id));return list(rows.all())
    async def practice_evidence(self,user_id:UUID):
        rows=await self.session.execute(select(LearningTopicMapping.topic_key,LearningTopicMapping.topic_name,LearningTopicMapping.concept_id,StudyTask.completed_at).join(StudyTask,StudyTask.id==LearningTopicMapping.resource_id).join(StudyPlan,StudyPlan.id==StudyTask.plan_id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="study_task",StudyPlan.user_id==user_id,StudyTask.completed_at.is_not(None)));return list(rows.all())
    async def mastery(self,user_id:UUID):
        rows=await self.session.scalars(select(TopicMastery).where(TopicMastery.user_id==user_id).options(selectinload(TopicMastery.recommendations)).order_by(TopicMastery.mastery_score,TopicMastery.topic_name));return list(rows.unique().all())
    async def mapping_owned(self,mapping_id:UUID,user_id:UUID):return await self.session.scalar(select(LearningTopicMapping).where(LearningTopicMapping.id==mapping_id,LearningTopicMapping.user_id==user_id))
    async def concept_owned(self,concept_id:UUID,user_id:UUID):return await self.session.scalar(select(KnowledgeConcept).where(KnowledgeConcept.id==concept_id,KnowledgeConcept.user_id==user_id))
    async def topic_actions(self,user_id:UUID,topic_key:str,concept_id:UUID|None):
        flashcards=list((await self.session.scalars(select(Flashcard.id).join(LearningTopicMapping,LearningTopicMapping.resource_id==Flashcard.id).join(FlashcardDeck,FlashcardDeck.id==Flashcard.deck_id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="flashcard",LearningTopicMapping.topic_key==topic_key,FlashcardDeck.user_id==user_id).limit(20))).all())
        quizzes=list((await self.session.scalars(select(Quiz.id).join(Question,Question.quiz_id==Quiz.id).join(LearningTopicMapping,LearningTopicMapping.resource_id==Question.id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="question",LearningTopicMapping.topic_key==topic_key,Quiz.user_id==user_id).distinct().limit(10))).all())
        plans=list((await self.session.scalars(select(StudyPlan.id).join(StudyTask,StudyTask.plan_id==StudyPlan.id).join(LearningTopicMapping,LearningTopicMapping.resource_id==StudyTask.id).where(LearningTopicMapping.user_id==user_id,LearningTopicMapping.resource_type=="study_task",LearningTopicMapping.topic_key==topic_key,StudyPlan.user_id==user_id).distinct().limit(10))).all())
        sources=[]
        if concept_id:
            rows=await self.session.execute(select(KnowledgeGraphConcept.document_id,KnowledgeGraphConcept.page_number).join(KnowledgeConcept,KnowledgeConcept.id==KnowledgeGraphConcept.concept_id).where(KnowledgeGraphConcept.concept_id==concept_id,KnowledgeConcept.user_id==user_id).distinct().limit(10));sources=[{"document_id":str(r.document_id),"page_number":r.page_number} for r in rows]
        return {"flashcard_ids":[str(x) for x in flashcards],"quiz_ids":[str(x) for x in quizzes],"study_plan_ids":[str(x) for x in plans],"document_sources":sources}
    async def clear_calculated(self,user_id:UUID):
        ids=select(TopicMastery.id).where(TopicMastery.user_id==user_id)
        await self.session.execute(delete(LearningRecommendation).where(LearningRecommendation.topic_mastery_id.in_(ids)))
        await self.session.execute(delete(TopicMastery).where(TopicMastery.user_id==user_id))
