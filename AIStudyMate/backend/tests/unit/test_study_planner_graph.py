from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.ai.planner.graph import StudyPlannerGraph
from app.ai.rag.vector_store import VectorSearchResult
from app.ai.topics import IdentifiedTopics


class FakeRAG:
    async def search(self, **kwargs):
        return [VectorSearchResult(chroma_id="chunk-1", text="Python variables", distance=.1,
            metadata={"document_id": str(kwargs["document_ids"][0]), "document_title": "Python", "page_number": 1})]


class FakeTopics:
    async def identify(self, evidence):
        return IdentifiedTopics.model_validate({"topics":[{"name":"Variables","normalized_name":"variables","description":"Python variables","evidence_chunk_ids":["chunk-1"]}]})


def state(**overrides):
    today=datetime.now(UTC).date(); base={"user_id":uuid4(),"goal":"Pass exam","subject":"Python","exam_date":today+timedelta(days=14),"available_days":[0,1,2,3,4,5,6],"daily_available_minutes":60,"preferred_session_minutes":30,"difficulty":"medium","document_ids":[uuid4()],"timezone":"UTC","retrieved_evidence":[],"topics":[],"workload_minutes":0,"proposed_tasks":[],"status":"running","error":None,"execution_steps":0,"retry_count":0,"plan_id":None}; base.update(overrides); return base


def graph(max_steps=10):
    async def save(value): return SimpleNamespace(id=uuid4())
    return StudyPlannerGraph(rag_service=FakeRAG(),topic_identifier=FakeTopics(),save_plan=save,max_steps=max_steps,max_retries=1,context_top_k=5)


@pytest.mark.asyncio
async def test_planner_generates_non_overlapping_schedule_with_reviews():
    result=await graph().run(state())
    assert result["status"]=="saved"
    assert any(task["task_type"]=="review" for task in result["proposed_tasks"])
    assert graph().validate_tasks(result) is None


@pytest.mark.asyncio
async def test_planner_rejects_impossible_deadline():
    tomorrow=datetime.now(UTC).date()+timedelta(days=1)
    result=await graph().run(state(exam_date=tomorrow,available_days=[tomorrow.weekday()],daily_available_minutes=15,preferred_session_minutes=15,difficulty="hard"))
    assert result["status"]=="invalid" and "Impossible deadline" in result["error"]


@pytest.mark.asyncio
async def test_planner_enforces_step_limit():
    result=await graph(max_steps=2).run(state())
    assert result["status"]=="step_limit"


def test_validator_rejects_overlap_and_timezone_boundary():
    value=state(); start=datetime.now(UTC)+timedelta(days=1)
    value["exam_date"]=start.date()+timedelta(days=2); value["available_days"]=[start.weekday()]
    value["proposed_tasks"]=[{"title":"A","description":"","topic":"A","task_type":"study","priority":3,"planned_start_at":start,"due_at":start+timedelta(minutes=30),"planned_duration_minutes":30,"document_id":None},{"title":"B","description":"","topic":"B","task_type":"study","priority":3,"planned_start_at":start+timedelta(minutes=15),"due_at":start+timedelta(minutes=45),"planned_duration_minutes":30,"document_id":None}]
    assert graph().validate_tasks(value)=="Study tasks overlap"
