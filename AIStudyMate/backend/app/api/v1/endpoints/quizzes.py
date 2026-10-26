from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.ai.llm.base import LLMError
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import (
    DocumentNotIndexableError,
    IndexConfigurationMismatchError,
    RAGDocumentNotFoundError,
)
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.quiz import QuizServiceDependency
from app.models.quiz import Quiz, QuizAttempt
from app.schemas.quiz import (
    QuestionResultResponse,
    QuizAttemptResponse,
    QuizDetailResponse,
    QuizGenerateRequest,
    QuizListResponse,
    QuizOptionResponse,
    QuizQuestionResponse,
    QuizResultResponse,
    QuizSourceReference,
    QuizSummaryResponse,
    SubmitAttemptRequest,
)
from app.services.quiz import (
    AttemptNotCompletedError,
    DuplicateSubmissionError,
    EmptyQuizContextError,
    InvalidGeneratedQuizError,
    InvalidSubmissionError,
    QuizAttemptNotFoundError,
    QuizDocumentNotFoundError,
    QuizNotFoundError,
    QuizPersistenceError,
    QuizRequestValidationError,
)


router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


def quiz_summary(quiz: Quiz) -> QuizSummaryResponse:
    return QuizSummaryResponse(
        id=quiz.id,
        document_id=quiz.document_id,
        title=quiz.title,
        description=quiz.description,
        difficulty=quiz.difficulty,
        question_count=len(quiz.questions),
        created_at=quiz.created_at,
    )


def quiz_detail(quiz: Quiz) -> QuizDetailResponse:
    summary = quiz_summary(quiz)
    return QuizDetailResponse(
        **summary.model_dump(),
        questions=[
            QuizQuestionResponse(
                id=question.id,
                question_text=question.question_text,
                order=question.question_order,
                options=[
                    QuizOptionResponse(
                        id=option.id,
                        text=option.option_text,
                        order=option.option_order,
                    )
                    for option in question.answer_options
                ],
                source_references=[
                    QuizSourceReference.model_validate(item)
                    for item in (question.source_references or [])
                ],
            )
            for question in quiz.questions
        ],
    )


@router.post("/generate", response_model=QuizDetailResponse, status_code=status.HTTP_201_CREATED)
async def generate_quiz(
    request: QuizGenerateRequest,
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizDetailResponse:
    try:
        quiz = await service.generate(request, current_user.id)
    except (QuizDocumentNotFoundError, RAGDocumentNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except (DocumentNotIndexableError, IndexConfigurationMismatchError, EmptyQuizContextError) as exc:
        raise HTTPException(status_code=409, detail="Document has no usable indexed content") from exc
    except InvalidGeneratedQuizError as exc:
        raise HTTPException(status_code=502, detail="AI returned an invalid quiz") from exc
    except QuizRequestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (LLMError, EmbeddingError, VectorStoreError) as exc:
        raise HTTPException(status_code=503, detail="Quiz generation is temporarily unavailable") from exc
    except QuizPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save generated quiz") from exc
    return quiz_detail(quiz)


@router.get("", response_model=QuizListResponse)
async def list_quizzes(
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizListResponse:
    quizzes = await service.list_owned(current_user.id)
    return QuizListResponse(items=[quiz_summary(item) for item in quizzes])


@router.get("/{quiz_id}", response_model=QuizDetailResponse)
async def get_quiz(
    quiz_id: UUID,
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizDetailResponse:
    try:
        quiz = await service.get_owned(quiz_id, current_user.id)
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quiz not found") from exc
    return quiz_detail(quiz)


@router.post(
    "/{quiz_id}/attempts",
    response_model=QuizAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_quiz_attempt(
    quiz_id: UUID,
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizAttemptResponse:
    try:
        attempt = await service.start_attempt(quiz_id, current_user.id)
    except QuizNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quiz not found") from exc
    except InvalidSubmissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except QuizPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to start quiz attempt") from exc
    return QuizAttemptResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        total_questions=attempt.total_questions,
        quiz=quiz_detail(attempt.quiz),
    )


@router.post("/attempts/{attempt_id}/submit", response_model=QuizResultResponse)
async def submit_quiz_attempt(
    attempt_id: UUID,
    request: SubmitAttemptRequest,
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizResultResponse:
    try:
        attempt = await service.submit_attempt(attempt_id, current_user.id, request.answers)
    except QuizAttemptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quiz attempt not found") from exc
    except DuplicateSubmissionError as exc:
        raise HTTPException(status_code=409, detail="Quiz attempt was already submitted") from exc
    except InvalidSubmissionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except QuizPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save quiz submission") from exc
    return result_response(attempt)


@router.get("/attempts/{attempt_id}/results", response_model=QuizResultResponse)
async def get_quiz_results(
    attempt_id: UUID,
    current_user: CurrentUser,
    service: QuizServiceDependency,
) -> QuizResultResponse:
    try:
        attempt = await service.get_results(attempt_id, current_user.id)
    except QuizAttemptNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Quiz attempt not found") from exc
    except AttemptNotCompletedError as exc:
        raise HTTPException(status_code=409, detail="Quiz attempt has not been submitted") from exc
    return result_response(attempt)


def result_response(attempt: QuizAttempt) -> QuizResultResponse:
    answers = {answer.question_id: answer for answer in attempt.user_answers}
    questions = []
    for question in attempt.quiz.questions:
        user_answer = answers[question.id]
        correct_option = next(option for option in question.answer_options if option.is_correct)
        questions.append(
            QuestionResultResponse(
                question_id=question.id,
                question_text=question.question_text,
                selected_option_id=user_answer.selected_option_id,
                correct_option_id=correct_option.id,
                is_correct=user_answer.is_correct,
                explanation=question.explanation or "",
                source_references=[
                    QuizSourceReference.model_validate(item)
                    for item in (question.source_references or [])
                ],
            )
        )
    return QuizResultResponse(
        attempt_id=attempt.id,
        quiz_id=attempt.quiz_id,
        score=attempt.score,
        total_questions=attempt.total_questions,
        percentage=(attempt.score / attempt.total_questions) * 100,
        completed_at=attempt.completed_at,
        questions=questions,
    )
