from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.quiz import AnswerOption, Question, Quiz, QuizAttempt, UserAnswer


QUIZ_LOAD_OPTIONS = (
    selectinload(Quiz.questions).selectinload(Question.answer_options),
)


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_owned(self, user_id: UUID) -> list[Quiz]:
        result = await self.session.scalars(
            select(Quiz)
            .where(Quiz.user_id == user_id)
            .options(*QUIZ_LOAD_OPTIONS)
            .order_by(Quiz.created_at.desc(), Quiz.id.desc())
        )
        return list(result.all())

    async def get_owned(self, quiz_id: UUID, user_id: UUID) -> Quiz | None:
        return await self.session.scalar(
            select(Quiz)
            .where(Quiz.id == quiz_id, Quiz.user_id == user_id)
            .options(*QUIZ_LOAD_OPTIONS)
        )

    async def get_attempt_owned(
        self, attempt_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> QuizAttempt | None:
        statement = (
            select(QuizAttempt)
            .where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user_id)
            .options(
                selectinload(QuizAttempt.quiz)
                .selectinload(Quiz.questions)
                .selectinload(Question.answer_options),
                selectinload(QuizAttempt.user_answers),
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    def add_quiz(self, quiz: Quiz) -> None:
        self.session.add(quiz)

    def add_attempt(self, attempt: QuizAttempt) -> None:
        self.session.add(attempt)

    def add_answers(self, answers: list[UserAnswer]) -> None:
        self.session.add_all(answers)
