from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common import FlashcardReviewRating, QuizDifficulty


class ManualFlashcardInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    front_text: str = Field(min_length=1, max_length=2000)
    back_text: str = Field(min_length=1, max_length=5000)
    explanation: str | None = Field(default=None, max_length=3000)


class CreateFlashcardDeckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=3000)
    cards: list[ManualFlashcardInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique_cards(self) -> "CreateFlashcardDeckRequest":
        fronts = [card.front_text.casefold() for card in self.cards]
        if len(fronts) != len(set(fronts)):
            raise ValueError("Flashcard fronts must be unique within a deck")
        return self


class GenerateFlashcardsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_ids: list[UUID] = Field(min_length=1, max_length=10)
    topic: str = Field(min_length=1, max_length=255)
    card_count: int = Field(ge=1, le=50)
    difficulty: QuizDifficulty = QuizDifficulty.MEDIUM
    title: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def unique_documents(self) -> "GenerateFlashcardsRequest":
        if len(self.document_ids) != len(set(self.document_ids)):
            raise ValueError("document_ids must be unique")
        return self


class GeneratedFlashcardSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=1, max_length=255)


class GeneratedFlashcard(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    front_text: str = Field(min_length=1, max_length=2000)
    back_text: str = Field(min_length=1, max_length=5000)
    explanation: str | None = Field(default=None, max_length=3000)
    source: GeneratedFlashcardSource


class GeneratedFlashcards(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[GeneratedFlashcard] = Field(min_length=1, max_length=50)


class UpdateFlashcardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    front_text: str | None = Field(default=None, min_length=1, max_length=2000)
    back_text: str | None = Field(default=None, min_length=1, max_length=5000)
    explanation: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateFlashcardRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class FlashcardSourceResponse(BaseModel):
    document_id: UUID
    document_title: str
    page_number: int | None
    chunk_id: str | None


class FlashcardResponse(BaseModel):
    id: UUID
    deck_id: UUID
    front_text: str
    back_text: str
    explanation: str | None
    card_order: int
    source: FlashcardSourceResponse | None
    created_at: datetime
    updated_at: datetime


class FlashcardDeckSummaryResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    card_count: int
    due_count: int
    document_ids: list[UUID]
    created_at: datetime
    updated_at: datetime


class FlashcardDeckResponse(FlashcardDeckSummaryResponse):
    cards: list[FlashcardResponse]


class FlashcardDeckListResponse(BaseModel):
    items: list[FlashcardDeckSummaryResponse]


class DueFlashcardsResponse(BaseModel):
    items: list[FlashcardResponse]
    total: int


class ReviewFlashcardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: FlashcardReviewRating


class FlashcardReviewResponse(BaseModel):
    id: UUID
    flashcard_id: UUID
    rating: FlashcardReviewRating
    reviewed_at: datetime
    next_review_at: datetime
    repetition_count: int
    ease_factor: float
    interval_days: int


class RatingCount(BaseModel):
    rating: FlashcardReviewRating
    count: int


class FlashcardStatsResponse(BaseModel):
    total_decks: int
    total_cards: int
    due_cards: int
    reviewed_cards: int
    total_reviews: int
    rating_counts: list[RatingCount]
