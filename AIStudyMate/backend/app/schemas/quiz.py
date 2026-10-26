from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common import QuizDifficulty


class GeneratedSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1, max_length=255)


class GeneratedOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=1000)
    is_correct: bool


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question_text: str = Field(min_length=1, max_length=2000)
    options: list[GeneratedOption] = Field(min_length=4, max_length=4)
    explanation: str = Field(min_length=1, max_length=3000)
    source_references: list[GeneratedSourceReference] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_options(self) -> "GeneratedQuestion":
        if sum(option.is_correct for option in self.options) != 1:
            raise ValueError("Each question must have exactly one correct option")
        normalized = {option.text.casefold() for option in self.options}
        if len(normalized) != 4:
            raise ValueError("Answer options must be unique")
        return self


class GeneratedQuiz(BaseModel):
    model_config = ConfigDict(extra="forbid")

    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=20)


class QuizGenerateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    number_of_questions: int = Field(ge=1, le=20)
    difficulty: QuizDifficulty
    document_id: UUID


class QuizSourceReference(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int
    chunk_id: str


class QuizOptionResponse(BaseModel):
    id: UUID
    text: str
    order: int


class QuizQuestionResponse(BaseModel):
    id: UUID
    question_text: str
    order: int
    options: list[QuizOptionResponse]
    source_references: list[QuizSourceReference]


class QuizSummaryResponse(BaseModel):
    id: UUID
    document_id: UUID
    title: str
    description: str | None
    difficulty: QuizDifficulty
    question_count: int
    created_at: datetime


class QuizListResponse(BaseModel):
    items: list[QuizSummaryResponse]


class QuizDetailResponse(QuizSummaryResponse):
    questions: list[QuizQuestionResponse]


class QuizAttemptResponse(BaseModel):
    id: UUID
    quiz_id: UUID
    started_at: datetime
    completed_at: datetime | None
    total_questions: int
    quiz: QuizDetailResponse


class SubmittedAnswer(BaseModel):
    question_id: UUID
    selected_option_id: UUID


class SubmitAttemptRequest(BaseModel):
    answers: list[SubmittedAnswer] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_unique_questions(self) -> "SubmitAttemptRequest":
        if len({item.question_id for item in self.answers}) != len(self.answers):
            raise ValueError("Each question may be answered only once")
        return self


class QuestionResultResponse(BaseModel):
    question_id: UUID
    question_text: str
    selected_option_id: UUID
    correct_option_id: UUID
    is_correct: bool
    explanation: str
    source_references: list[QuizSourceReference]


class QuizResultResponse(BaseModel):
    attempt_id: UUID
    quiz_id: UUID
    score: int
    total_questions: int
    percentage: float
    completed_at: datetime
    questions: list[QuestionResultResponse]
