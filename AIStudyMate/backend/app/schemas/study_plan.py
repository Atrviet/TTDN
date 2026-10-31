from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.common import QuizDifficulty, StudyPlanStatus, StudyTaskStatus


class GenerateStudyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    goal: str = Field(min_length=1, max_length=2000)
    subject: str = Field(min_length=1, max_length=255)
    exam_date: date
    available_days: list[int] = Field(min_length=1, max_length=7)
    daily_available_minutes: int = Field(ge=15, le=720)
    preferred_session_minutes: int = Field(ge=15, le=180)
    difficulty: QuizDifficulty
    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_availability(self):
        if len(set(self.available_days)) != len(self.available_days) or any(day not in range(7) for day in self.available_days):
            raise ValueError("available_days must contain unique values from 0 to 6")
        if self.preferred_session_minutes > self.daily_available_minutes:
            raise ValueError("preferred session cannot exceed daily availability")
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("document_ids must be unique")
        return self


class UpdateStudyPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = Field(default=None, min_length=1, max_length=2000)
    status: StudyPlanStatus | None = None


class UpdateStudyTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: StudyTaskStatus
    actual_duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    planned_start_at: datetime | None = None


class ReplanRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class StudyTaskResponse(BaseModel):
    id: UUID; plan_id: UUID; document_id: UUID | None; title: str; description: str | None
    topic: str; task_type: str; priority: int; status: StudyTaskStatus
    planned_start_at: datetime | None; due_at: datetime | None
    planned_duration_minutes: int; actual_duration_minutes: int | None; completed_at: datetime | None


class StudyPlanSummaryResponse(BaseModel):
    id: UUID; title: str; goal: str | None; subject: str; difficulty: QuizDifficulty
    status: StudyPlanStatus; start_date: date; exam_date: date; timezone: str
    daily_available_minutes: int; preferred_session_minutes: int; available_days: list[int]
    document_ids: list[UUID]; task_count: int; completed_count: int; progress_percentage: float
    planned_minutes: int; actual_minutes: int; created_at: datetime; updated_at: datetime


class StudyPlanDetailResponse(StudyPlanSummaryResponse):
    tasks: list[StudyTaskResponse]


class StudyPlanListResponse(BaseModel):
    items: list[StudyPlanSummaryResponse]


class StudyTaskListResponse(BaseModel):
    items: list[StudyTaskResponse]
