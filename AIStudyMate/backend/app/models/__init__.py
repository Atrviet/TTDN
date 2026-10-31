"""SQLAlchemy models exported here for metadata and migration discovery."""

from app.models.chat import ChatMessage, ChatSession
from app.models.advanced_learning import (
    Flashcard,
    FlashcardDeck,
    FlashcardReview,
    KnowledgeConcept,
    KnowledgeRelation,
    LearningRecommendation,
    StudyAvailability,
    StudyPlan,
    StudyTask,
    TopicMastery,
    TutorMessage,
    TutorSession,
)
from app.models.document import Document, DocumentChunk
from app.models.quiz import AnswerOption, Question, Quiz, QuizAttempt, UserAnswer
from app.models.user import User

__all__ = [
    "AnswerOption",
    "Flashcard",
    "FlashcardDeck",
    "FlashcardReview",
    "ChatMessage",
    "ChatSession",
    "Document",
    "DocumentChunk",
    "KnowledgeConcept",
    "KnowledgeRelation",
    "LearningRecommendation",
    "Question",
    "Quiz",
    "QuizAttempt",
    "StudyAvailability",
    "StudyPlan",
    "StudyTask",
    "TopicMastery",
    "TutorMessage",
    "TutorSession",
    "User",
    "UserAnswer",
]

