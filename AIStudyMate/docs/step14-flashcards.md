# STEP 14 — AI Flashcards with Spaced Repetition

## Workflow

1. The authenticated user selects one or more indexed documents.
2. The backend validates ownership for the complete document set.
3. The existing RAG service retrieves authorized chunks from the existing
   ChromaDB collection.
4. Gemini receives a bounded context whose PDF text is explicitly marked as
   untrusted data.
5. Pydantic validates the structured cards. The service additionally rejects
   incorrect counts, duplicate fronts, and unknown chunk IDs.
6. The deck, cards, document links, and exact PostgreSQL chunk provenance are
   committed atomically.

No Gemini key is sent to the frontend. No new ChromaDB collection or Gemini
client is created.

## API

All routes require a bearer access token.

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/v1/flashcards/decks` | Create a manual deck, optionally with initial cards. |
| POST | `/api/v1/flashcards/generate` | Generate a grounded deck using RAG and Gemini. |
| GET | `/api/v1/flashcards/decks` | List the user's decks and due counts. |
| GET | `/api/v1/flashcards/decks/{deck_id}` | Get a deck, cards, and source metadata. |
| PATCH | `/api/v1/flashcards/{card_id}` | Edit a card owned through its deck. |
| DELETE | `/api/v1/flashcards/{card_id}` | Delete a card and its review history. |
| GET | `/api/v1/flashcards/due` | List due/new cards; supports `deck_id` and `limit`. |
| POST | `/api/v1/flashcards/{card_id}/review` | Record a grade and calculate the next review. |
| GET | `/api/v1/flashcards/stats` | Return deck, card, due, review, and grade counts. |

Generation example:

```json
{
  "document_ids": ["00000000-0000-0000-0000-000000000000"],
  "topic": "Python basics",
  "card_count": 15,
  "difficulty": "medium",
  "title": "Ôn tập Python"
}
```

Review example:

```json
{"rating": "good"}
```

## SM-2 scheduling

The implementation maps UI grades to original SM-2 quality values:

| Grade | Quality |
| --- | ---: |
| Again | 0 |
| Hard | 3 |
| Good | 4 |
| Easy | 5 |

Ease factor update:

```text
EF' = max(1.3, EF + 0.1 - (5-q) * (0.08 + (5-q) * 0.02))
```

- Quality below 3 resets repetition count and schedules one day later.
- The first successful review uses one day.
- The second successful review uses six days.
- Later intervals are `round(previous_interval * new_ease_factor)`.
- Rounding uses decimal half-up to make results deterministic.
- All timestamps are timezone-aware UTC values.

Every review creates a new `flashcard_reviews` row. Existing history is never
overwritten. The card row is locked with `SELECT ... FOR UPDATE` before reading
the latest state, so concurrent submissions are serialized and both reviews are
retained.

## Database

STEP 14 adds migration `20261031_0007`, which creates
`flashcard_deck_documents` for multi-document decks and backfills the legacy
single `document_id` relation. Existing flashcard tables from STEP 13 are reused:

- PostgreSQL owns deck/card/review state, scheduling, and source foreign keys.
- ChromaDB remains responsible only for semantic retrieval.
- `document_chunks` connects generated cards to stable Chroma IDs and page
  provenance.

## Configuration

```env
FLASHCARD_MIN_CARDS=1
FLASHCARD_MAX_CARDS=30
FLASHCARD_CONTEXT_TOP_K=20
FLASHCARD_CONTEXT_MAX_CHARS=50000
FLASHCARD_MAX_OUTPUT_TOKENS=6144
```

## Frontend

Routes:

- `/flashcards` — library, statistics, manual creation, and AI generation.
- `/flashcards/decks/{id}` — deck detail, flip interaction, grading, and delete.
- `/flashcards/study` — due-card review session and progress indicator.

## Verification

```bash
cd backend
alembic upgrade head
pytest

cd ../frontend
npm test
npm run build
```

Automated tests mock Gemini and cover structured generation, malformed output,
source integrity, document ownership, duplicate rejection, SM-2 transitions,
review history, due filtering, concurrent reviews, provider failures, and all
existing backend regressions.

## Limitations

- SM-2 is a deterministic baseline, not FSRS and not personalized from response
  latency.
- Duplicate detection normalizes whitespace/case but does not perform semantic
  paraphrase detection.
- Manual deck creation accepts initial cards; the requested API contract does
  not include a separate create-card endpoint.
- Background generation is synchronous for this step. Large generation jobs
  should use the durable worker boundary introduced in STEP 13.
- Retrieval and generation quality remain dependent on PDF extraction,
  embeddings, Gemini quota, and source material quality.
