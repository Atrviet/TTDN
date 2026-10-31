from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.common import FlashcardReviewRating
from app.services.spaced_repetition import SchedulingState, schedule_sm2


NOW = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("rating", "expected_ease"),
    [
        (FlashcardReviewRating.AGAIN, Decimal("1.70")),
        (FlashcardReviewRating.HARD, Decimal("2.36")),
        (FlashcardReviewRating.GOOD, Decimal("2.50")),
        (FlashcardReviewRating.EASY, Decimal("2.60")),
    ],
)
def test_sm2_rating_mapping_is_deterministic(rating, expected_ease) -> None:
    result = schedule_sm2(SchedulingState(), rating, reviewed_at=NOW)
    assert result.ease_factor == expected_ease
    assert result.interval_days == 1


def test_sm2_success_progression_is_one_six_then_ease_scaled() -> None:
    first = schedule_sm2(
        SchedulingState(), FlashcardReviewRating.GOOD, reviewed_at=NOW
    )
    second = schedule_sm2(
        SchedulingState(first.interval_days, first.ease_factor, first.repetition_count),
        FlashcardReviewRating.GOOD,
        reviewed_at=NOW,
    )
    third = schedule_sm2(
        SchedulingState(second.interval_days, second.ease_factor, second.repetition_count),
        FlashcardReviewRating.EASY,
        reviewed_at=NOW,
    )
    assert (first.interval_days, second.interval_days, third.interval_days) == (1, 6, 16)
    assert third.repetition_count == 3


def test_again_resets_repetition_and_ease_has_floor() -> None:
    result = schedule_sm2(
        SchedulingState(30, Decimal("1.30"), 7),
        FlashcardReviewRating.AGAIN,
        reviewed_at=NOW,
    )
    assert result.repetition_count == 0
    assert result.interval_days == 1
    assert result.ease_factor == Decimal("1.30")


def test_sm2_requires_timezone_aware_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        schedule_sm2(
            SchedulingState(),
            FlashcardReviewRating.GOOD,
            reviewed_at=datetime(2026, 10, 31),
        )
