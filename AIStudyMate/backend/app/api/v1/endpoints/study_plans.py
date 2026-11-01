from uuid import UUID
from fastapi import APIRouter, Header, HTTPException, status
from typing import Annotated
from app.ai.llm.base import LLMError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.study_plan import StudyPlanServiceDependency
from app.models.advanced_learning import StudyPlan, StudyTask
from app.models.common import StudyTaskStatus
from app.schemas.study_plan import *
from app.services.study_plan import *
from app.api.dependencies.idempotency import IdempotencyServiceDependency
from app.services.idempotency import IdempotencyClaim,IdempotencyConflictError,IdempotencyInProgressError

router=APIRouter(tags=["Study Planner"])

def task_response(t:StudyTask): return StudyTaskResponse(id=t.id,plan_id=t.plan_id,document_id=t.document_id,title=t.title,description=t.description,topic=t.topic,task_type=t.task_type,priority=t.priority,status=t.status,planned_start_at=t.planned_start_at,due_at=t.due_at,planned_duration_minutes=t.planned_duration_minutes,actual_duration_minutes=t.actual_duration_minutes,completed_at=t.completed_at)
def summary(p:StudyPlan):
    completed=sum(t.status==StudyTaskStatus.COMPLETED for t in p.tasks); count=len(p.tasks)
    return StudyPlanSummaryResponse(id=p.id,title=p.title,goal=p.goal,subject=p.subject,difficulty=p.difficulty,status=p.status,start_date=p.start_date,exam_date=p.end_date,timezone=p.timezone,daily_available_minutes=p.daily_available_minutes,preferred_session_minutes=p.preferred_session_minutes,available_days=p.available_days,document_ids=[d.id for d in p.documents],task_count=count,completed_count=completed,progress_percentage=(completed/count*100 if count else 0),planned_minutes=sum(t.planned_duration_minutes for t in p.tasks),actual_minutes=sum(t.actual_duration_minutes or 0 for t in p.tasks),created_at=p.created_at,updated_at=p.updated_at)
def detail(p): return StudyPlanDetailResponse(**summary(p).model_dump(),tasks=[task_response(t) for t in sorted(p.tasks,key=lambda x:x.planned_start_at or x.created_at)])

def map_error(exc):
    if isinstance(exc,(StudyPlanNotFoundError,StudyTaskNotFoundError,StudyPlanDocumentError)): return HTTPException(404,"Study plan resource not found")
    if isinstance(exc,ImpossibleScheduleError): return HTTPException(409,str(exc))
    if isinstance(exc,StudyPlannerTimeoutError): return HTTPException(504,"Study planner timed out")
    if isinstance(exc,LLMError): return HTTPException(503,"Study planner AI is temporarily unavailable")
    return HTTPException(500,"Unable to persist study plan")

@router.post("/study-plans/generate",response_model=StudyPlanDetailResponse,status_code=201)
async def generate(r:GenerateStudyPlanRequest,u:CurrentUser,s:StudyPlanServiceDependency,i:IdempotencyServiceDependency,idempotency_key:Annotated[str|None,Header(alias="Idempotency-Key",max_length=128)]=None):
    claim=IdempotencyClaim(None,None)
    try:
        claim=await i.claim(u.id,"study_plans.generate",idempotency_key,r)
        if claim.completed_resource_id:return detail(await s.get(claim.completed_resource_id,u.id))
        plan=await s.generate(r,u.id);await i.complete(claim,plan.id);return detail(plan)
    except IdempotencyConflictError as exc:raise HTTPException(409,"Idempotency-Key was already used with another request") from exc
    except IdempotencyInProgressError as exc:raise HTTPException(409,"An identical generation request is already in progress") from exc
    except Exception as exc:
        if isinstance(exc,(StudyPlanNotFoundError,StudyTaskNotFoundError,StudyPlanDocumentError,ImpossibleScheduleError,StudyPlannerTimeoutError,StudyPlanPersistenceError,LLMError)):
            await i.fail(claim,type(exc).__name__);raise map_error(exc) from exc
        raise
@router.get("/study-plans",response_model=StudyPlanListResponse)
async def list_plans(u:CurrentUser,s:StudyPlanServiceDependency): return StudyPlanListResponse(items=[summary(p) for p in await s.list(u.id)])
@router.get("/study-plans/{plan_id}",response_model=StudyPlanDetailResponse)
async def get_plan(plan_id:UUID,u:CurrentUser,s:StudyPlanServiceDependency):
    try:return detail(await s.get(plan_id,u.id))
    except StudyPlanNotFoundError as exc: raise map_error(exc) from exc
@router.patch("/study-plans/{plan_id}",response_model=StudyPlanDetailResponse)
async def update_plan(plan_id:UUID,r:UpdateStudyPlanRequest,u:CurrentUser,s:StudyPlanServiceDependency):
    try:return detail(await s.update_plan(plan_id,u.id,r))
    except (StudyPlanNotFoundError,StudyPlanPersistenceError) as exc: raise map_error(exc) from exc
@router.delete("/study-plans/{plan_id}",status_code=204)
async def delete_plan(plan_id:UUID,u:CurrentUser,s:StudyPlanServiceDependency):
    try:await s.delete(plan_id,u.id)
    except (StudyPlanNotFoundError,StudyPlanPersistenceError) as exc: raise map_error(exc) from exc
@router.get("/study-plans/{plan_id}/tasks",response_model=StudyTaskListResponse)
async def tasks(plan_id:UUID,u:CurrentUser,s:StudyPlanServiceDependency):
    try:return StudyTaskListResponse(items=[task_response(t) for t in (await s.get(plan_id,u.id)).tasks])
    except StudyPlanNotFoundError as exc: raise map_error(exc) from exc
@router.patch("/study-tasks/{task_id}",response_model=StudyTaskResponse)
async def update_task(task_id:UUID,r:UpdateStudyTaskRequest,u:CurrentUser,s:StudyPlanServiceDependency):
    try:return task_response(await s.update_task(task_id,u.id,r))
    except (StudyTaskNotFoundError,ImpossibleScheduleError,StudyPlanPersistenceError) as exc: raise map_error(exc) from exc
@router.post("/study-plans/{plan_id}/replan",response_model=StudyPlanDetailResponse)
async def replan(plan_id:UUID,r:ReplanRequest,u:CurrentUser,s:StudyPlanServiceDependency):
    try:return detail(await s.replan(plan_id,u.id))
    except (StudyPlanNotFoundError,StudyPlanDocumentError,ImpossibleScheduleError,StudyPlannerTimeoutError,StudyPlanPersistenceError,LLMError) as exc: raise map_error(exc) from exc
