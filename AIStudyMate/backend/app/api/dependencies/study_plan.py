from typing import Annotated
from fastapi import Depends
from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.study_plan import StudyPlanService


def get_study_plan_service(session:SessionDependency,rag_service:RAGServiceDependency,llm:LLMDependency):
    s=get_settings(); return StudyPlanService(session,rag_service,llm,max_steps=s.planner_max_steps,max_retries=s.planner_max_retries,timeout_seconds=s.planner_timeout_seconds,context_top_k=s.planner_context_top_k)
StudyPlanServiceDependency=Annotated[StudyPlanService,Depends(get_study_plan_service)]
