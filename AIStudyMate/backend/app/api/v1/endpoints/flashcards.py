from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status
from typing import Annotated

from app.ai.llm.base import LLMError
from app.ai.rag.embeddings.base import EmbeddingError
from app.ai.rag.service import (
    DocumentNotIndexableError,
    IndexConfigurationMismatchError,
    RAGDocumentNotFoundError,
)
from app.ai.rag.vector_store import VectorStoreError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.flashcard import FlashcardServiceDependency
from app.api.dependencies.idempotency import IdempotencyServiceDependency
from app.services.idempotency import IdempotencyClaim,IdempotencyConflictError,IdempotencyInProgressError
from app.models.advanced_learning import Flashcard, FlashcardDeck, FlashcardReview
from app.models.common import FlashcardReviewRating
from app.schemas.flashcard import (
    CreateFlashcardDeckRequest,
    DueFlashcardsResponse,
    FlashcardDeckListResponse,
    FlashcardDeckResponse,
    FlashcardDeckSummaryResponse,
    FlashcardResponse,
    FlashcardReviewResponse,
    FlashcardSourceResponse,
    FlashcardStatsResponse,
    GenerateFlashcardsRequest,
    RatingCount,
    ReviewFlashcardRequest,
    UpdateFlashcardRequest,
)
from app.services.flashcard import (
    DuplicateFlashcardError,
    EmptyFlashcardContextError,
    FlashcardDeckNotFoundError,
    FlashcardLimitError,
    FlashcardNotFoundError,
    FlashcardPersistenceError,
    InvalidGeneratedFlashcardsError,
)


router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


def _latest_review(card: Flashcard) -> FlashcardReview | None:
    return max(card.reviews, key=lambda item: (item.reviewed_at, item.id), default=None)


def _is_due(card: Flashcard, now: datetime) -> bool:
    latest = _latest_review(card)
    return latest is None or latest.next_review_at <= now


def card_response(card: Flashcard) -> FlashcardResponse:
    source = None
    if card.source_document_id is not None and card.source_document is not None:
        source = FlashcardSourceResponse(
            document_id=card.source_document_id,
            document_title=card.source_document.title,
            page_number=card.source_page_number,
            chunk_id=card.source_chunk.chroma_id if card.source_chunk else None,
        )
    return FlashcardResponse(
        id=card.id,
        deck_id=card.deck_id,
        front_text=card.front_text,
        back_text=card.back_text,
        explanation=card.explanation,
        card_order=card.card_order,
        source=source,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


def deck_summary(deck: FlashcardDeck) -> FlashcardDeckSummaryResponse:
    now = datetime.now(UTC)
    document_ids = [document.id for document in deck.documents]
    if not document_ids and deck.document_id is not None:
        document_ids = [deck.document_id]
    return FlashcardDeckSummaryResponse(
        id=deck.id,
        title=deck.title,
        description=deck.description,
        card_count=len(deck.flashcards),
        due_count=sum(_is_due(card, now) for card in deck.flashcards),
        document_ids=document_ids,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
    )


def deck_response(deck: FlashcardDeck) -> FlashcardDeckResponse:
    return FlashcardDeckResponse(
        **deck_summary(deck).model_dump(),
        cards=[card_response(card) for card in sorted(deck.flashcards, key=lambda item: item.card_order)],
    )


@router.post("/decks", response_model=FlashcardDeckResponse, status_code=status.HTTP_201_CREATED)
async def create_deck(
    request: CreateFlashcardDeckRequest,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
) -> FlashcardDeckResponse:
    try:
        return deck_response(await service.create_deck(request, current_user.id))
    except FlashcardPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save flashcard deck") from exc


@router.post("/generate", response_model=FlashcardDeckResponse, status_code=status.HTTP_201_CREATED)
async def generate_flashcards(
    request: GenerateFlashcardsRequest,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
    idempotency: IdempotencyServiceDependency,
    idempotency_key:Annotated[str|None,Header(alias="Idempotency-Key",max_length=128)]=None,
) -> FlashcardDeckResponse:
    claim=IdempotencyClaim(None,None)
    try:
        claim=await idempotency.claim(current_user.id,"flashcards.generate",idempotency_key,request)
        if claim.completed_resource_id:return deck_response(await service.get_deck(claim.completed_resource_id,current_user.id))
        deck=await service.generate(request,current_user.id);await idempotency.complete(claim,deck.id);return deck_response(deck)
    except IdempotencyConflictError as exc:raise HTTPException(409,"Idempotency-Key was already used with another request") from exc
    except IdempotencyInProgressError as exc:raise HTTPException(409,"An identical generation request is already in progress") from exc
    except (FlashcardDeckNotFoundError, RAGDocumentNotFoundError) as exc:
        await idempotency.fail(claim,"document_not_found")
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except (DocumentNotIndexableError, IndexConfigurationMismatchError, EmptyFlashcardContextError) as exc:
        await idempotency.fail(claim,"invalid_context")
        raise HTTPException(status_code=409, detail="Documents have no usable indexed content") from exc
    except (InvalidGeneratedFlashcardsError,) as exc:
        await idempotency.fail(claim,"invalid_ai_output")
        raise HTTPException(status_code=502, detail="AI returned invalid flashcards") from exc
    except FlashcardLimitError as exc:
        await idempotency.fail(claim,"request_limit")
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (LLMError, EmbeddingError, VectorStoreError) as exc:
        await idempotency.fail(claim,"ai_unavailable")
        raise HTTPException(status_code=503, detail="Flashcard generation is temporarily unavailable") from exc
    except FlashcardPersistenceError as exc:
        await idempotency.fail(claim,"persistence_error")
        raise HTTPException(status_code=500, detail="Unable to save generated flashcards") from exc


@router.get("/decks", response_model=FlashcardDeckListResponse)
async def list_decks(
    current_user: CurrentUser, service: FlashcardServiceDependency
) -> FlashcardDeckListResponse:
    decks = await service.list_decks(current_user.id)
    return FlashcardDeckListResponse(items=[deck_summary(deck) for deck in decks])


@router.get("/due", response_model=DueFlashcardsResponse)
async def due_cards(
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
    deck_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> DueFlashcardsResponse:
    try:
        cards, total = await service.due_cards(
            current_user.id, deck_id=deck_id, limit=limit
        )
    except FlashcardDeckNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Flashcard deck not found") from exc
    return DueFlashcardsResponse(items=[card_response(card) for card in cards], total=total)


@router.get("/stats", response_model=FlashcardStatsResponse)
async def flashcard_stats(
    current_user: CurrentUser, service: FlashcardServiceDependency
) -> FlashcardStatsResponse:
    stats = await service.stats(current_user.id)
    counts = stats.pop("rating_counts")
    return FlashcardStatsResponse(
        **stats,
        rating_counts=[
            RatingCount(rating=rating, count=int(counts.get(rating, 0)))
            for rating in FlashcardReviewRating
        ],
    )


@router.get("/decks/{deck_id}", response_model=FlashcardDeckResponse)
async def get_deck(
    deck_id: UUID,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
) -> FlashcardDeckResponse:
    try:
        return deck_response(await service.get_deck(deck_id, current_user.id))
    except FlashcardDeckNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Flashcard deck not found") from exc


@router.patch("/{card_id}", response_model=FlashcardResponse)
async def update_flashcard(
    card_id: UUID,
    request: UpdateFlashcardRequest,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
) -> FlashcardResponse:
    try:
        return card_response(await service.update_card(card_id, current_user.id, request))
    except FlashcardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Flashcard not found") from exc
    except DuplicateFlashcardError as exc:
        raise HTTPException(status_code=409, detail="A card with this front already exists") from exc
    except FlashcardPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to update flashcard") from exc


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(
    card_id: UUID,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
) -> None:
    try:
        await service.delete_card(card_id, current_user.id)
    except FlashcardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Flashcard not found") from exc
    except FlashcardPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to delete flashcard") from exc


@router.post("/{card_id}/review", response_model=FlashcardReviewResponse)
async def review_flashcard(
    card_id: UUID,
    request: ReviewFlashcardRequest,
    current_user: CurrentUser,
    service: FlashcardServiceDependency,
) -> FlashcardReviewResponse:
    try:
        review = await service.review(card_id, current_user.id, request.rating)
    except FlashcardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Flashcard not found") from exc
    except FlashcardPersistenceError as exc:
        raise HTTPException(status_code=500, detail="Unable to save flashcard review") from exc
    return FlashcardReviewResponse(
        id=review.id,
        flashcard_id=review.flashcard_id,
        rating=review.rating,
        reviewed_at=review.reviewed_at,
        next_review_at=review.next_review_at,
        repetition_count=review.repetition_count,
        ease_factor=float(review.ease_factor),
        interval_days=review.interval_days,
    )
