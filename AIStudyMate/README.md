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
| `JWT_SECRET_KEY` | JWT signing secret; replace the development value before use |
| `JWT_ALGORITHM` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime in days |
| `JWT_ISSUER` | Expected JWT issuer claim |
| `JWT_AUDIENCE` | Expected JWT audience claim |
| `GEMINI_API_KEY` | Future Gemini credential; empty in STEP 02 |
| `CHROMA_PERSIST_DIR` | Future local ChromaDB persistence directory |
| `CORS_ORIGINS` | JSON array of allowed browser origins |
| `DOCUMENT_STORAGE_DIR` | Private local filesystem root for uploaded PDFs |
| `MAX_PDF_SIZE_MB` | Maximum streamed PDF upload size, default `20` MiB |
| `EMBEDDING_PROVIDER` | `local` or `gemini`; indexing and querying must use the same provider |
| `LOCAL_EMBEDDING_MODEL` | Sentence Transformers model used by the local provider |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model ID; availability and billing depend on the account |
| `EMBEDDING_DIMENSIONS` | Optional Gemini output vector dimensions |
| `EMBEDDING_BATCH_SIZE` | Number of texts sent to the embedding provider per batch |
| `EMBEDDING_TIMEOUT_SECONDS` | Gemini request timeout |
| `EMBEDDING_MAX_RETRIES` | Gemini attempts for timeout, 429, and retryable 5xx errors |
| `RAG_CHUNK_SIZE` | Approximate target tokens per chunk; default `500` |
| `RAG_CHUNK_OVERLAP` | Approximate repeated tokens between adjacent chunks; default `75` |
| `RAG_COLLECTION_PREFIX` | Stable Chroma collection prefix |
| `RAG_MAX_TOP_K` | Maximum search result count accepted by the API |

## Authentication

STEP 03 uses Argon2 password hashing and signed JWTs. Access and refresh tokens have distinct `type` claims and cannot be substituted for one another. Tokens also contain subject, role, JTI, issued-at, expiry, issuer, and audience claims.

Public registration always creates a `student`; the client cannot self-assign the `admin` role. Role dependencies are available for future admin-only endpoints. Password hashing and verification run in a worker thread so CPU-bound Argon2 work does not block FastAPI's event loop.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Register a student account |
| `POST` | `/api/v1/auth/login` | OAuth2 password-form login using username or email |
| `POST` | `/api/v1/auth/refresh` | Exchange a refresh token for a new token pair |
| `GET` | `/api/v1/users/me` | Return the authenticated user's profile |

Example registration:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"student1","email":"student1@example.com","password":"StrongPass123","full_name":"Student One"}'
```

OAuth2 login uses form data rather than JSON:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=student1&password=StrongPass123'
```

Use the returned access token:

```bash
curl http://127.0.0.1:8000/api/v1/users/me \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

Refresh tokens are currently stateless. Token revocation, logout, reuse detection, and refresh-token persistence are not part of STEP 03.

## PDF document management

STEP 04 stores private PDF files on the local filesystem and keeps ownership, extraction results, metadata, and processing state in PostgreSQL. Files are never served as public static assets, and API responses never expose server filesystem paths.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/documents/upload` | Stream, validate, extract, and store an authenticated user's PDF |
| `GET` | `/api/v1/documents` | List owned documents with `page` and `per_page` pagination |
| `GET` | `/api/v1/documents/{document_id}` | Return owned document metadata |
| `GET` | `/api/v1/documents/{document_id}/content` | Return extracted text grouped by PDF page |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete an owned document, its chunks, and its local file |

Upload example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents/upload \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -F 'title=Database fundamentals' \
  -F 'file=@/absolute/path/to/lesson.pdf;type=application/pdf'
```

List and read content:

```bash
curl 'http://127.0.0.1:8000/api/v1/documents?page=1&per_page=20' \
  -H 'Authorization: Bearer ACCESS_TOKEN'

curl http://127.0.0.1:8000/api/v1/documents/DOCUMENT_UUID/content \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

Delete a document:

```bash
curl -X DELETE http://127.0.0.1:8000/api/v1/documents/DOCUMENT_UUID \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

### Storage and extraction workflow

1. The multipart body is streamed to a private staging file in 1 MiB chunks. Reading stops immediately when `MAX_PDF_SIZE_MB` is exceeded.
2. PyMuPDF validates the real file structure, encryption state, page tree, images, and extractable text. Filename extensions and client MIME types are not trusted.
3. Text is normalized per page while preserving line and paragraph boundaries and Unicode Vietnamese content.
4. A UUID filename is atomically moved into a user-specific directory under `DOCUMENT_STORAGE_DIR`.
5. PostgreSQL stores only the relative path, extracted page JSON, sanitized metadata, page count, and processing state.
6. If database persistence fails, the promoted file is removed. Deletion first moves the file into a private trash area, commits the database deletion, and then removes the staged file; a failed database deletion restores it.

Image-only PDFs are accepted with `requires_ocr=true` and empty extracted text. OCR is intentionally not implemented or claimed in STEP 04. Blank PDFs without text or images, malformed PDFs, encrypted PDFs, empty uploads, and oversized files are rejected.

Document ownership always comes from the validated JWT. Requests for another user's document receive the same `404` as a missing document, preventing existence disclosure. UUID storage names and root-containment checks prevent path traversal.

## RAG indexing and semantic retrieval

STEP 05 indexes extracted PDF text and provides semantic retrieval only. It does not generate an AI answer.

```text
PostgreSQL extracted_pages
        │
        ▼
Unicode-aware page chunker (about 500 tokens, overlap 75)
        │
        ▼
EmbeddingProvider ── local sentence-transformers / Gemini embedding
        │
        ├──► ChromaDB: vector + chunk text + ownership/source metadata
        │
        └──► PostgreSQL document_chunks: Chroma ID, page, order, token count
```

PostgreSQL remains authoritative for users, ownership, document state, indexing state, and chunk references. ChromaDB contains retrieval-oriented vectors and duplicated chunk text/metadata. Every search first verifies ownership and indexing configuration in PostgreSQL, then applies ownership and document filters again in ChromaDB.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/documents/{document_id}/index` | Idempotently chunk, embed, and index an owned PDF |
| `POST` | `/api/v1/rag/search` | Search indexed chunks from explicitly selected owned documents |

Index a document:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/documents/DOCUMENT_UUID/index \
  -H 'Authorization: Bearer ACCESS_TOKEN'
```

Search indexed documents:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/search \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Giải thích nội dung chương 1",
    "document_ids": ["DOCUMENT_UUID"],
    "top_k": 5
  }'
```

Search results use cosine distance: lower values mean greater semantic similarity. Distance is not a probability or confidence percentage.

### Embedding providers

Local development defaults to a multilingual Sentence Transformers model:

```env
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

The model is downloaded from Hugging Face on first use and then cached locally. For Gemini:

```env
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=your-key
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSIONS=768
```

Gemini uses `RETRIEVAL_DOCUMENT` while indexing and `RETRIEVAL_QUERY` while searching. Confirm model availability, pricing, free-tier eligibility, and quota for the configured account before use; the application does not assume an embedding model is free. The implementation uses the official `google-genai` SDK with timeout and retry configuration for 408, 429, and retryable 5xx responses.

Changing the provider or model creates a deterministic new Chroma collection. Existing documents must be reindexed deliberately; the API rejects searching an index built with a different configuration.

### Retrieval evaluation

Automated tests verify chunking, metadata, isolation, idempotency, deterministic nearest-neighbor behavior, and failure cleanup. They do not measure production retrieval quality. Before claiming quality, build a representative Vietnamese evaluation set and report at least:

- Recall@k: whether a known relevant chunk appears in the first `k` results.
- Mean Reciprocal Rank (MRR): how early the first relevant chunk appears.
- nDCG@k: ranking quality when relevance has multiple grades.
- Indexing latency, query latency, and embedding API error/rate-limit rates.

## Database migrations

Alembic is configured for the async PostgreSQL URL in `.env`. To inspect SQL without connecting to PostgreSQL:

```bash
alembic upgrade head --sql
```
