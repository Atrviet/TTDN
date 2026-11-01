from datetime import UTC,datetime,timedelta
import pytest
from app.services.learning import combine_mastery,practice_score,recency_weight,weighted_score

def test_weighted_mastery_formula_and_missing_evidence():
    score,effective=combine_mastery({"quiz":.5,"flashcard":1.0,"practice":.5},{"quiz":.6,"flashcard":.3,"practice":.1})
    assert score==pytest.approx(.65);assert effective==pytest.approx({"quiz":.6,"flashcard":.3,"practice":.1})
    score,effective=combine_mastery({"quiz":.8,"flashcard":None,"practice":None},{"quiz":.6,"flashcard":.3,"practice":.1})
    assert score==pytest.approx(.8);assert effective["quiz"]==1
    with pytest.raises(ValueError):combine_mastery({"quiz":None},{"quiz":1})

def test_quiz_correctness_flashcard_recall_and_recency():
    now=datetime(2026,11,1,tzinfo=UTC);recent=now-timedelta(days=1);old=now-timedelta(days=60)
    assert recency_weight(now-timedelta(days=30),now,30)==pytest.approx(.5)
    score=weighted_score([(1,recent),(0,old)],now,30);assert score is not None and score>.7
    assert practice_score([old],now,30)==pytest.approx(.25)

def test_score_boundaries_are_stable():
    from app.services.learning import LearningService
    service=LearningService(None,quiz_weight=.6,flashcard_weight=.3,practice_weight=.1,half_life_days=30,needs_review_threshold=.5,strong_threshold=.75) # type: ignore[arg-type]
    assert service.level(.4999).value=="needs_review";assert service.level(.5).value=="developing";assert service.level(.75).value=="strong"
