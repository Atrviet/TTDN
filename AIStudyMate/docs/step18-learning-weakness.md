# STEP 18 — Learning Weakness Detection

## Deterministic baseline

For each normalized topic, available evidence is scored in `[0, 1]`:

- Quiz: recency-weighted mean of persisted `user_answers.is_correct` (`1` or `0`).
- Flashcard: recency-weighted mean of `again=0`, `hard=0.4`, `good=0.75`, `easy=1`.
- Practice: mean recency factor of completed study tasks.

Configured baseline weights are quiz `0.60`, flashcard `0.30`, and practice `0.10`. Missing sources
are excluded and remaining weights are normalized. Therefore no activity is not scored as zero.
Evidence decay is `0.5 ** (age_days / half_life_days)`; the default half-life is 30 days.

Default levels are:

- `needs_review`: score below `0.50`.
- `developing`: score from `0.50` to below `0.75`.
- `strong`: score from `0.75`.

These are explainable engineering defaults, not validated educational coefficients.

## Topic taxonomy

`learning_topic_mappings` maps `question`, `flashcard`, and `study_task` IDs to a normalized topic.
Initial labels come from quiz title, flashcard deck title, or study task topic with provenance and
confidence `0.7`; they are explicitly unverified. An exact normalized Knowledge Graph concept is
linked when available. `PATCH /learning/topic-mappings/{id}` records a user correction with
`provenance=user_corrected` and `is_verified=true`.

## API

- `GET /api/v1/learning/weak-topics`
- `GET /api/v1/learning/mastery`
- `GET /api/v1/learning/recommendations`
- `POST /api/v1/learning/mastery/recalculate`
- `GET /api/v1/learning/topic-mappings`
- `PATCH /api/v1/learning/topic-mappings/{mapping_id}`

Recommendations are deterministic links to relevant documents, flashcards, quizzes, Tutor, and
study plans when those owned resources exist. Gemini is not used for mastery scores.

## Limitations

Topic labels derived from titles may be broad and require correction. Recency decay, weights, rating
values, and thresholds are product defaults rather than validated psychometric parameters. A score
describes only observed evidence in this application and must not be interpreted as general ability.
