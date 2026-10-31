from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.models.common import FlashcardReviewRating


QUALITY_BY_RATING = {
    FlashcardReviewRating.AGAIN: 0,
    FlashcardReviewRating.HARD: 3,
    FlashcardReviewRating.GOOD: 4,
    FlashcardReviewRating.EASY: 5,
}


@dataclass(frozen=True)
class SchedulingState:
    interval_days: int = 0
    ease_factor: Decimal = Decimal("2.50")
    repetition_count: int = 0


@dataclass(frozen=True)
class SchedulingResult:
    interval_days: int
    ease_factor: Decimal
    repetition_count: int
    next_review_at: datetime


def schedule_sm2(
    state: SchedulingState,
    rating: FlashcardReviewRating,
    *,
    reviewed_at: datetime,
) -> SchedulingResult:
    """Apply deterministic SM-2 with Again/Hard/Good/Easy mapped to 0/3/4/5."""
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    if state.interval_days < 0 or state.repetition_count < 0 or state.ease_factor < 1:
        raise ValueError("Invalid scheduling state")

    quality = QUALITY_BY_RATING[rating]
    difference = Decimal(5 - quality)
    ease_factor = state.ease_factor + Decimal("0.1") - difference * (
        Decimal("0.08") + difference * Decimal("0.02")
    )
    ease_factor = max(Decimal("1.30"), ease_factor).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    if quality < 3:
        repetition_count = 0
        interval_days = 1
    else:
        repetition_count = state.repetition_count + 1
        if repetition_count == 1:
            interval_days = 1
        elif repetition_count == 2:
            interval_days = 6
        else:
            interval_days = max(
                1,
                int(
                    (Decimal(state.interval_days) * ease_factor).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                ),
            )

    reviewed_at_utc = reviewed_at.astimezone(UTC)
    return SchedulingResult(
        interval_days=interval_days,
        ease_factor=ease_factor,
        repetition_count=repetition_count,
        next_review_at=reviewed_at_utc + timedelta(days=interval_days),
    )
