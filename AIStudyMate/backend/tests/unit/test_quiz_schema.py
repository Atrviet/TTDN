import pytest
from pydantic import ValidationError

from app.schemas.quiz import GeneratedQuestion, GeneratedQuiz


def valid_question() -> dict:
    return {
        "question_text": "RAG combines which two stages?",
        "options": [
            {"text": "Retrieval and generation", "is_correct": True},
            {"text": "Sorting and caching", "is_correct": False},
            {"text": "Training and deployment", "is_correct": False},
            {"text": "Parsing and encryption", "is_correct": False},
        ],
        "explanation": "RAG retrieves evidence before generation.",
        "source_references": [{"chunk_id": "doc:0"}],
    }


def test_generated_quiz_accepts_complete_mcq() -> None:
    quiz = GeneratedQuiz.model_validate({"questions": [valid_question()]})
    assert len(quiz.questions[0].options) == 4
    assert sum(option.is_correct for option in quiz.questions[0].options) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["options"].pop(),
        lambda value: value["options"].__setitem__(1, {"text": "Second", "is_correct": True}),
        lambda value: value["source_references"].clear(),
        lambda value: value["options"].__setitem__(1, {"text": "Retrieval and generation", "is_correct": False}),
    ],
)
def test_generated_question_rejects_malformed_output(mutation) -> None:
    payload = valid_question()
    mutation(payload)
    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate(payload)
