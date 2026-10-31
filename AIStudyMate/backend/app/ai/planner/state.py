from datetime import date, datetime
from typing import Any, Literal, TypedDict
from uuid import UUID


PlannerStatus = Literal["running", "valid", "invalid", "saved", "step_limit"]


class PlannedTask(TypedDict):
    title: str
    description: str
    topic: str
    task_type: str
    priority: int
    planned_start_at: datetime
    due_at: datetime
    planned_duration_minutes: int
    document_id: UUID | None


class StudyPlannerState(TypedDict):
    user_id: UUID
    goal: str
    subject: str
    exam_date: date
    available_days: list[int]
    daily_available_minutes: int
    preferred_session_minutes: int
    difficulty: str
    document_ids: list[UUID]
    timezone: str
    retrieved_evidence: list[dict[str, Any]]
    topics: list[dict[str, Any]]
    workload_minutes: int
    proposed_tasks: list[PlannedTask]
    status: PlannerStatus
    error: str | None
    execution_steps: int
    retry_count: int
    plan_id: UUID | None
