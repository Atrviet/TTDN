import asyncio
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from langgraph.errors import GraphRecursionError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm.base import LLMProvider
from app.ai.planner.graph import StudyPlannerGraph
from app.ai.planner.state import StudyPlannerState
from app.ai.rag.service import RAGService
from app.ai.topics import LearningTopicIdentifier
from app.models.advanced_learning import StudyAvailability, StudyPlan, StudyTask, TopicMastery
from app.models.common import RAGIndexingStatus, StudyPlanStatus, StudyTaskStatus
from app.repositories.study_plan import StudyPlanRepository
from app.services.ownership import DocumentOwnershipService, OwnedResourceNotFoundError
from app.schemas.study_plan import GenerateStudyPlanRequest, UpdateStudyPlanRequest, UpdateStudyTaskRequest
from app.services.knowledge_graph import normalize_concept_name


class StudyPlanNotFoundError(Exception): pass
class StudyTaskNotFoundError(Exception): pass
class StudyPlanDocumentError(Exception): pass
class ImpossibleScheduleError(Exception): pass
class StudyPlannerTimeoutError(Exception): pass
class StudyPlanPersistenceError(Exception): pass


class StudyPlanService:
    def __init__(self, session: AsyncSession, rag_service: RAGService, llm: LLMProvider, *, max_steps: int, max_retries: int, timeout_seconds: float, context_top_k: int, needs_review_threshold: float=0.5):
        self.session=session; self.rag_service=rag_service; self.llm=llm; self.max_steps=max_steps; self.max_retries=max_retries; self.timeout_seconds=timeout_seconds; self.context_top_k=context_top_k; self.needs_review_threshold=needs_review_threshold
        self.repository=StudyPlanRepository(session); self.ownership=DocumentOwnershipService(session)

    async def generate(self, request: GenerateStudyPlanRequest, user_id: UUID):
        return await self._run(request, user_id, None)

    async def _run(self, request, user_id, plan_id):
        try: documents = await self.ownership.require_documents(request.document_ids, user_id)
        except OwnedResourceNotFoundError as exc: raise StudyPlanDocumentError from exc
        if any(doc.indexing_status != RAGIndexingStatus.INDEXED for doc in documents): raise StudyPlanDocumentError
        async def save(state): return await self._persist(state, documents)
        graph=StudyPlannerGraph(rag_service=self.rag_service, topic_identifier=LearningTopicIdentifier(self.llm), save_plan=save, max_steps=self.max_steps, max_retries=self.max_retries, context_top_k=self.context_top_k)
        initial: StudyPlannerState={"user_id":user_id,"goal":request.goal,"subject":request.subject,"exam_date":request.exam_date,"available_days":request.available_days,"daily_available_minutes":request.daily_available_minutes,"preferred_session_minutes":request.preferred_session_minutes,"difficulty":request.difficulty.value,"document_ids":request.document_ids,"timezone":request.timezone,"retrieved_evidence":[],"topics":[],"workload_minutes":0,"proposed_tasks":[],"status":"running","error":None,"execution_steps":0,"retry_count":0,"plan_id":plan_id}
        try:
            async with asyncio.timeout(self.timeout_seconds): result=await graph.run(initial)
        except (TimeoutError, GraphRecursionError) as exc: raise StudyPlannerTimeoutError from exc
        if result["status"] != "saved": raise ImpossibleScheduleError(result.get("error") or "Unable to build schedule")
        return await self.get(result["plan_id"], user_id)

    async def _persist(self, state, documents):
        if state["plan_id"]:
            plan=await self.repository.get_owned(state["plan_id"], state["user_id"], for_update=True)
            if not plan: raise StudyPlanNotFoundError
            await self.repository.delete_incomplete_tasks(plan.id); await self.session.flush()
            plan.updated_at=datetime.now(UTC)
        else:
            plan=StudyPlan(user_id=state["user_id"],title=state["subject"],goal=state["goal"],subject=state["subject"],difficulty=state["difficulty"],status=StudyPlanStatus.ACTIVE,start_date=datetime.now(ZoneInfo(state["timezone"])).date(),end_date=state["exam_date"],timezone=state["timezone"],daily_available_minutes=state["daily_available_minutes"],preferred_session_minutes=state["preferred_session_minutes"],available_days=state["available_days"])
            plan.documents=documents; plan.tasks=[]; plan.availability=[StudyAvailability(day_of_week=day,start_time=time(18),end_time=(datetime.combine(datetime.today(), time(18))+timedelta(minutes=state["daily_available_minutes"])).time()) for day in state["available_days"]]
            self.repository.add(plan); await self.session.flush()
        weak_keys=set((await self.session.scalars(select(TopicMastery.topic_key).where(TopicMastery.user_id==state["user_id"],TopicMastery.mastery_score<self.needs_review_threshold))).all())
        tasks=[]
        for item in state["proposed_tasks"]:
            weak=normalize_concept_name(item["topic"]) in weak_keys
            description=item["description"]
            if weak:description=f"Ưu tiên ôn tập từ Weakness Detection. {description or ''}".strip()
            tasks.append(StudyTask(document_id=item["document_id"],title=item["title"],description=description,topic=item["topic"],task_type=item["task_type"],priority=1 if weak else item["priority"],status=StudyTaskStatus.PENDING,planned_start_at=item["planned_start_at"],due_at=item["due_at"],planned_duration_minutes=item["planned_duration_minutes"]))
        plan.tasks.extend(tasks)
        await self._commit(); return plan

    async def list(self,user_id): return await self.repository.list_owned(user_id)
    async def get(self,plan_id,user_id):
        plan=await self.repository.get_owned(plan_id,user_id)
        if not plan: raise StudyPlanNotFoundError
        return plan
    async def update_plan(self,plan_id,user_id,request:UpdateStudyPlanRequest):
        plan=await self.get(plan_id,user_id)
        for field in request.model_fields_set: setattr(plan,field,getattr(request,field))
        await self._commit(); return await self.get(plan_id,user_id)
    async def delete(self,plan_id,user_id):
        plan=await self.get(plan_id,user_id); await self.repository.delete(plan); await self._commit()
    async def update_task(self,task_id,user_id,request:UpdateStudyTaskRequest):
        task=await self.repository.get_task_owned(task_id,user_id,for_update=True)
        if not task: raise StudyTaskNotFoundError
        if request.status==StudyTaskStatus.POSTPONED:
            if request.planned_start_at is None: raise ImpossibleScheduleError("postponed tasks require planned_start_at")
            duration=timedelta(minutes=task.planned_duration_minutes); task.planned_start_at=request.planned_start_at.astimezone(UTC); task.due_at=task.planned_start_at+duration
            local_start=task.planned_start_at.astimezone(ZoneInfo(task.plan.timezone))
            if local_start.date()>task.plan.end_date: raise ImpossibleScheduleError("Task cannot be postponed after exam")
            if local_start.weekday() not in task.plan.available_days: raise ImpossibleScheduleError("Task must use an available study day")
            plan=await self.repository.get_owned(task.plan_id,user_id)
            if any(other.id!=task.id and other.status!=StudyTaskStatus.COMPLETED and other.planned_start_at and other.due_at and task.planned_start_at < other.due_at and task.due_at > other.planned_start_at for other in plan.tasks): raise ImpossibleScheduleError("Postponed task overlaps another task")
        task.status=request.status; task.actual_duration_minutes=request.actual_duration_minutes
        task.completed_at=datetime.now(UTC) if request.status==StudyTaskStatus.COMPLETED else None
        await self._commit(); return await self.repository.get_task_owned(task.id,user_id)
    async def replan(self,plan_id,user_id):
        plan=await self.get(plan_id,user_id)
        req=GenerateStudyPlanRequest(goal=plan.goal or plan.title,subject=plan.subject,exam_date=plan.end_date,available_days=plan.available_days,daily_available_minutes=plan.daily_available_minutes,preferred_session_minutes=plan.preferred_session_minutes,difficulty=plan.difficulty,document_ids=[doc.id for doc in plan.documents],timezone=plan.timezone)
        return await self._run(req,user_id,plan.id)
    async def _commit(self):
        try: await self.session.commit()
        except SQLAlchemyError as exc: await self.session.rollback(); raise StudyPlanPersistenceError from exc
