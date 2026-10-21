# AI StudyMate

AI StudyMate is an intelligent learning assistant. The current foundation includes FastAPI, versioned API routing, environment-based configuration, structured logging, an async PostgreSQL data model, Alembic migrations, and isolated unit/integration tests.

## Prerequisites

- Python 3.11 or newer
- Docker Desktop with Docker Compose

## Backend setup (macOS)

From the project root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

The values in `.env.example` are development-only. Replace `JWT_SECRET_KEY` and database credentials before using a non-local environment. Never commit `.env`.

## Start PostgreSQL

From the project root (`AIStudyMate/`):

```bash
docker compose --env-file backend/.env up -d postgres
docker compose ps
```

Stop it with:

```bash
docker compose --env-file backend/.env down
```

## Run the API

From `AIStudyMate/backend` with the virtual environment activated:

```bash
uvicorn app.main:app --reload
```

Open:

- API root: <http://127.0.0.1:8000/>
- Health endpoint: <http://127.0.0.1:8000/api/v1/health>
- Swagger UI: <http://127.0.0.1:8000/docs>

Expected health response:

```json
{"status":"ok"}
```

The health endpoint intentionally does not connect to PostgreSQL or Gemini.

## Database architecture

PostgreSQL is the system of record for users, document metadata, chats, quizzes, attempts, and citations. ChromaDB will be introduced later as a vector index for semantic retrieval. ChromaDB stores embeddings and points back to `document_chunks.chroma_id`; it does not replace PostgreSQL's transactional data, constraints, ownership, or quiz history.

| Table | Purpose |
| --- | --- |
| `users` | Account identity, role, and active state |
| `documents` | Uploaded-file metadata and processing state |
| `document_chunks` | Ordered PDF chunk metadata linked to future Chroma vectors |
| `chat_sessions` | User conversation containers |
| `chat_messages` | Ordered conversation content and optional JSONB citations |
| `quizzes` | Document-based quizzes owned by users |
| `questions` | Ordered quiz questions and explanations |
| `answer_options` | Ordered answer choices and correctness flags |
| `quiz_attempts` | A user's score and timing for one quiz attempt |
| `user_answers` | One selected option per question in an attempt |

All primary keys use UUID. Timestamps use PostgreSQL `TIMESTAMP WITH TIME ZONE`. Owned children use cascading deletion; account and completed quiz-history references use restrictive deletion. User removal should therefore be implemented as deactivation through `users.is_active`.

```mermaid
erDiagram
    USER ||--o{ DOCUMENT : owns
    USER ||--o{ CHAT_SESSION : starts
    USER ||--o{ QUIZ : owns
    USER ||--o{ QUIZ_ATTEMPT : takes
    DOCUMENT ||--o{ DOCUMENT_CHUNK : contains
    DOCUMENT ||--o{ QUIZ : sources
    CHAT_SESSION ||--o{ CHAT_MESSAGE : contains
    QUIZ ||--|{ QUESTION : contains
    QUIZ ||--o{ QUIZ_ATTEMPT : receives
    QUESTION ||--|{ ANSWER_OPTION : offers
    QUIZ_ATTEMPT ||--o{ USER_ANSWER : records
    QUESTION ||--o{ USER_ANSWER : answered_by
    ANSWER_OPTION ||--o{ USER_ANSWER : selected_as
```

The database enforces non-negative sizes/counts, valid attempt scores, unique question/option ordering, one answer per attempt/question, and explicit foreign-key deletion behavior. The service layer must additionally validate that a quiz and its document have the same owner, an attempt's question belongs to that attempt's quiz, a selected option belongs to that question, and at least one (normally exactly one) option is correct.

## Migrations

From `AIStudyMate/backend`:

```bash
alembic upgrade head
alembic current
alembic history
```

Generate a future migration only after changing ORM models:

```bash
alembic revision --autogenerate -m "describe change"
```

Inspect generated code before applying it. Only downgrade a disposable database:

```bash
alembic downgrade -1
```

## Run tests

From `AIStudyMate/backend` with the virtual environment activated:

```bash
pytest
```

Unit tests and the health test run without PostgreSQL. PostgreSQL integration tests require an explicitly separate database whose name contains `test`:

```bash
docker exec ai_studymate_postgres createdb \
  -U ai_studymate ai_studymate_test

export TEST_DATABASE_URL="postgresql+asyncpg://ai_studymate:ai_studymate_dev_password@localhost:5433/ai_studymate_test"
pytest -m integration
```

The migration integration test resets only `TEST_DATABASE_URL`, verifies all ten tables and foreign keys, performs a downgrade, and reapplies the migration. Never point it at a database containing important data.

Run only tests that do not need PostgreSQL:

```bash
pytest -m "not integration"
```

## Environment variables

| Variable | Description |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL URL used by the API and Alembic |
| `TEST_DATABASE_URL` | Optional isolated PostgreSQL database for destructive integration tests |
| `POSTGRES_DB` | Database created by the Docker image |
| `POSTGRES_USER` | Local PostgreSQL user |
| `POSTGRES_PASSWORD` | Local PostgreSQL password; replace outside development |
| `POSTGRES_PORT` | Host port mapped to PostgreSQL port 5432 |
| `JWT_SECRET_KEY` | Future JWT signing secret; must be replaced before authentication is used |
| `JWT_ALGORITHM` | Future JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Future access-token lifetime |
| `GEMINI_API_KEY` | Future Gemini credential; empty in STEP 02 |
| `CHROMA_PERSIST_DIR` | Future local ChromaDB persistence directory |
| `CORS_ORIGINS` | JSON array of allowed browser origins |

## Database migrations

Alembic is configured for the async PostgreSQL URL in `.env`. To inspect SQL without connecting to PostgreSQL:

```bash
alembic upgrade head --sql
```
