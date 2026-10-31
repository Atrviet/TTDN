from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.advanced_learning import Flashcard, FlashcardDeck, FlashcardReview


DECK_LOAD_OPTIONS = (
    selectinload(FlashcardDeck.documents),
    selectinload(FlashcardDeck.flashcards).selectinload(Flashcard.source_document),
    selectinload(FlashcardDeck.flashcards).selectinload(Flashcard.source_chunk),
    selectinload(FlashcardDeck.flashcards).selectinload(Flashcard.reviews),
)


class FlashcardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def add_deck(self, deck: FlashcardDeck) -> None:
        self.session.add(deck)

    def add_review(self, review: FlashcardReview) -> None:
        self.session.add(review)

    async def list_decks(self, user_id: UUID) -> list[FlashcardDeck]:
        decks = await self.session.scalars(
            select(FlashcardDeck)
            .where(FlashcardDeck.user_id == user_id)
            .options(*DECK_LOAD_OPTIONS)
            .order_by(FlashcardDeck.updated_at.desc(), FlashcardDeck.id.desc())
        )
        return list(decks.unique().all())

    async def get_deck(self, deck_id: UUID, user_id: UUID) -> FlashcardDeck | None:
        return await self.session.scalar(
            select(FlashcardDeck)
            .where(FlashcardDeck.id == deck_id, FlashcardDeck.user_id == user_id)
            .options(*DECK_LOAD_OPTIONS)
        )

    async def get_card(
        self, card_id: UUID, user_id: UUID, *, for_update: bool = False
    ) -> Flashcard | None:
        statement = (
            select(Flashcard)
            .join(Flashcard.deck)
            .where(Flashcard.id == card_id, FlashcardDeck.user_id == user_id)
            .options(
                selectinload(Flashcard.source_document),
                selectinload(Flashcard.source_chunk),
                selectinload(Flashcard.reviews),
            )
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=Flashcard)
        return await self.session.scalar(statement)

    async def duplicate_front_exists(
        self, deck_id: UUID, front_text: str, *, excluding_card_id: UUID | None = None
    ) -> bool:
        filters = [
            Flashcard.deck_id == deck_id,
            func.lower(Flashcard.front_text) == front_text.casefold(),
        ]
        if excluding_card_id is not None:
            filters.append(Flashcard.id != excluding_card_id)
        return bool(await self.session.scalar(select(Flashcard.id).where(*filters).limit(1)))

    async def delete_card(self, card: Flashcard) -> None:
        await self.session.delete(card)

    async def due_cards(
        self, user_id: UUID, *, now: datetime, limit: int | None, deck_id: UUID | None = None
    ) -> list[Flashcard]:
        ranked = (
            select(
                FlashcardReview.flashcard_id.label("flashcard_id"),
                FlashcardReview.next_review_at.label("next_review_at"),
                func.row_number()
                .over(
                    partition_by=FlashcardReview.flashcard_id,
                    order_by=(FlashcardReview.reviewed_at.desc(), FlashcardReview.id.desc()),
                )
                .label("rank"),
            )
            .subquery()
        )
        filters = [
            FlashcardDeck.user_id == user_id,
            or_(ranked.c.flashcard_id.is_(None), ranked.c.next_review_at <= now),
            or_(ranked.c.rank.is_(None), ranked.c.rank == 1),
        ]
        if deck_id is not None:
            filters.append(Flashcard.deck_id == deck_id)
        statement = (
            select(Flashcard)
            .join(Flashcard.deck)
            .outerjoin(ranked, ranked.c.flashcard_id == Flashcard.id)
            .where(*filters)
            .options(
                selectinload(Flashcard.source_document),
                selectinload(Flashcard.source_chunk),
                selectinload(Flashcard.reviews),
            )
            .order_by(ranked.c.next_review_at.asc().nullsfirst(), Flashcard.created_at.asc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        cards = await self.session.scalars(statement)
        return list(cards.unique().all())

    async def total_due(
        self, user_id: UUID, *, now: datetime, deck_id: UUID | None = None
    ) -> int:
        return len(await self.due_cards(user_id, now=now, limit=None, deck_id=deck_id))

    async def stats(self, user_id: UUID, *, now: datetime) -> dict[str, object]:
        total_decks = await self.session.scalar(
            select(func.count(FlashcardDeck.id)).where(FlashcardDeck.user_id == user_id)
        )
        total_cards = await self.session.scalar(
            select(func.count(Flashcard.id))
            .join(Flashcard.deck)
            .where(FlashcardDeck.user_id == user_id)
        )
        reviewed_cards = await self.session.scalar(
            select(func.count(func.distinct(FlashcardReview.flashcard_id)))
            .join(FlashcardReview.flashcard)
            .join(Flashcard.deck)
            .where(FlashcardDeck.user_id == user_id)
        )
        rating_rows = await self.session.execute(
            select(FlashcardReview.rating, func.count(FlashcardReview.id))
            .join(FlashcardReview.flashcard)
            .join(Flashcard.deck)
            .where(FlashcardDeck.user_id == user_id)
            .group_by(FlashcardReview.rating)
        )
        rating_counts = {rating: count for rating, count in rating_rows.all()}
        return {
            "total_decks": total_decks or 0,
            "total_cards": total_cards or 0,
            "due_cards": await self.total_due(user_id, now=now),
            "reviewed_cards": reviewed_cards or 0,
            "total_reviews": sum(rating_counts.values()),
            "rating_counts": rating_counts,
        }
