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
| `GEMINI_API_KEY` | Gemini credential for AI chat and optional Gemini embeddings |
| `GEMINI_CHAT_MODEL` | Gemini generation model available to the configured API project |
| `GEMINI_TIMEOUT_SECONDS` | Generation request timeout |
| `GEMINI_MAX_RETRIES` | Bounded attempts for 408, 429, and retryable 5xx responses |
| `GEMINI_MAX_OUTPUT_TOKENS` | Maximum generated answer tokens |
| `CHROMA_PERSIST_DIR` | Local ChromaDB persistence directory |
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
| `CHAT_RAG_TOP_K` | Retrieved chunks considered for one grounded answer |
| `CHAT_HISTORY_MESSAGES` | Maximum recent messages considered for prompting |
| `CHAT_HISTORY_MAX_CHARS` | Character budget for conversation history |
| `CHAT_CONTEXT_MAX_CHARS` | Character budget for retrieved evidence |

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

## Gemini document-grounded chat

STEP 06 adds persistent conversations and Gemini answer generation on top of the STEP 05 retrieval pipeline. Configure a Gemini model that is available to your Google AI project:

```env
GEMINI_API_KEY=your-key
GEMINI_CHAT_MODEL=gemini-2.5-flash-lite
GEMINI_TIMEOUT_SECONDS=45
GEMINI_MAX_RETRIES=3
GEMINI_MAX_OUTPUT_TOKENS=1024

CHAT_RAG_TOP_K=5
CHAT_HISTORY_MESSAGES=8
CHAT_HISTORY_MAX_CHARS=12000
CHAT_CONTEXT_MAX_CHARS=24000
```

Model availability, Free Tier eligibility, rate limits, and pricing depend on the API project and can change. Check Google AI Studio before deployment. A 429 or retryable server error receives bounded exponential retries; exhausted quota, timeouts, and provider errors become HTTP `503`. API keys are never returned or logged.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/chat/sessions` | Create an owned conversation |
| `GET` | `/api/v1/chat/sessions` | List the current user's conversations |
| `GET` | `/api/v1/chat/sessions/{session_id}/messages` | Read an owned conversation history |
| `PATCH` | `/api/v1/chat/sessions/{session_id}` | Rename an owned conversation |
| `DELETE` | `/api/v1/chat/sessions/{session_id}` | Delete a conversation and its messages |
| `POST` | `/api/v1/chat/sessions/{session_id}/messages` | Ask Gemini using selected indexed documents |

Create a session and ask a question:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/chat/sessions \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"title":"Ôn tập chương 2"}'

curl -X POST http://127.0.0.1:8000/api/v1/chat/sessions/SESSION_UUID/messages \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "message":"Tóm tắt chương 2",
    "document_ids":["DOCUMENT_UUID"]
  }'
```

The workflow validates ownership in PostgreSQL, searches only selected indexed documents, applies separate history/evidence budgets, and sends the resulting grounded prompt to Gemini. Retrieved PDF text is wrapped as untrusted `document_text`; the system instruction tells the model not to execute instructions found inside that text. The API builds citations only from retrieved Chroma metadata and never asks the model to invent citation objects.

If retrieval returns no evidence, the service does not call Gemini. It stores a deterministic insufficient-evidence response with an empty citation list. When Gemini fails, neither the user message nor an assistant message is persisted. A successful pair is committed atomically. This does not make an external Gemini call and a PostgreSQL transaction globally atomic; a response may be generated but discarded if the database commit subsequently fails.

## LangGraph AI Study Agent

STEP 07 adds a bounded, stateful Study Agent without introducing a multi-agent architecture. LangGraph orchestrates a typed per-request state, while PostgreSQL `chat_sessions` and `chat_messages` remain the durable conversation memory. The graph state contains user/session IDs, server-authorized document IDs, bounded history, retrieved context, tool-call history, execution status, and step count. It never contains an API key, JWT, or password.

```mermaid
flowchart LR
    A[JWT + request] --> B[Validate session and documents]
    B --> C[Route intent]
    C --> D[Execute bounded tools]
    D --> E[Generate grounded answer]
    E --> F[Validate answer and citations]
    F --> G[Atomically persist message pair]
    C -. step/tool limit .-> H[Safe termination]
    D -. tool failure .-> H
```

The graph has explicit `route_intent`, `execute_tools`, `generate_answer`, and `validate_response` nodes with conditional termination. `AGENT_MAX_STEPS`, LangGraph's runtime recursion limit, `AGENT_MAX_TOOL_CALLS`, and `AGENT_TIMEOUT_SECONDS` provide separate loop, tool, and wall-clock controls.

### Agent tool contracts

| Tool | Validated input | Structured output | Authorization |
| --- | --- | --- | --- |
| `search_documents` | Query, document UUIDs, bounded `top_k` | Matching chunks, distance, title, page, chunk ID | IDs must be in the server-created allowlist; RAG checks PostgreSQL and Chroma ownership again |
| `get_document_summary` | One document UUID | Extractive summary-source chunks | UUID must be authorized and owned |
| `get_document_metadata` | One document UUID | Safe title, filename, page and processing/index status | UUID must be authorized and owned |
| `get_learning_history` | User UUID | Quiz attempts, completion, aggregate accuracy, chat-session count | Supplied UUID must equal the JWT-derived user ID |

Tool selection is deterministic and bounded: questions, explanations, and outlines search documents; summaries retrieve summary-source chunks; learning plans combine retrieval with learning history. Gemini synthesizes the final response but cannot authorize documents, change the trusted user ID, execute arbitrary code, access files, or call unrestricted network tools.

### Agent API

```http
POST /api/v1/agent/chat
Authorization: Bearer ACCESS_TOKEN
Content-Type: application/json
```

```json
{
  "session_id": "SESSION_UUID",
  "message": "Hãy giải thích chương 1 và lập kế hoạch ôn tập",
  "document_ids": ["DOCUMENT_UUID"]
}
```

Example response:

```json
{
  "session_id": "SESSION_UUID",
  "answer": "...",
  "tools_used": ["search_documents", "get_learning_history"],
  "citations": [
    {
      "document_id": "DOCUMENT_UUID",
      "document_title": "Learning material",
      "page_number": 3,
      "chunk_id": "DOCUMENT_UUID:2"
    }
  ],
  "execution_steps": 4,
  "execution_status": "completed",
  "model": "gemini-2.5-flash-lite"
}
```

Agent configuration:

```env
AGENT_MAX_STEPS=8
AGENT_MAX_TOOL_CALLS=4
AGENT_TIMEOUT_SECONDS=60
AGENT_HISTORY_MESSAGES=8
AGENT_CONTEXT_MAX_CHARS=30000
```

PDF text and all tool outputs are wrapped as untrusted data. Citations are assembled only from successful retrieval outputs, never parsed from Gemini text. When all retrieval results are empty or tools fail, the graph returns a controlled insufficient-evidence response without calling Gemini. A timeout returns HTTP `504`; Gemini, embedding, vector-store, and graph execution failures return `503`.

## AI Quiz Generator

STEP 08 generates document-grounded multiple-choice quizzes with Gemini structured output and grades attempts deterministically in PostgreSQL.

```text
Owned indexed document
        │
        ▼
RAG retrieves authorized source chunks
        │
        ▼
Gemini + Pydantic GeneratedQuiz schema
        │
        ├── exactly four unique options
        ├── exactly one correct option
        ├── explanation
        └── validated source chunk IDs
        │
        ▼
PostgreSQL Quiz → Questions → AnswerOptions
        │
        ▼
QuizAttempt → deterministic grading → UserAnswers
```

The API never returns `is_correct`, the correct option ID, or explanations before submission. Correctness is read exclusively from PostgreSQL during grading; the client cannot submit or influence a correctness value.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/quizzes/generate` | Generate and persist a quiz from one owned indexed document |
| `GET` | `/api/v1/quizzes` | List the current user's quizzes |
| `GET` | `/api/v1/quizzes/{quiz_id}` | Read a quiz without answers |
| `POST` | `/api/v1/quizzes/{quiz_id}/attempts` | Start a new owned attempt |
| `POST` | `/api/v1/quizzes/attempts/{attempt_id}/submit` | Submit every answer once and grade atomically |
| `GET` | `/api/v1/quizzes/attempts/{attempt_id}/results` | Read results only after completion |

Generate a quiz:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/quizzes/generate \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"Ôn tập RAG",
    "number_of_questions":5,
    "difficulty":"medium",
    "document_id":"DOCUMENT_UUID"
  }'
```

Start and submit an attempt:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/quizzes/QUIZ_UUID/attempts \
  -H 'Authorization: Bearer ACCESS_TOKEN'

curl -X POST http://127.0.0.1:8000/api/v1/quizzes/attempts/ATTEMPT_UUID/submit \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "answers":[
      {"question_id":"QUESTION_UUID","selected_option_id":"OPTION_UUID"}
    ]
  }'
```

Configuration:

```env
QUIZ_MIN_QUESTIONS=1
QUIZ_MAX_QUESTIONS=10
QUIZ_CONTEXT_TOP_K=12
QUIZ_CONTEXT_MAX_CHARS=40000
QUIZ_MAX_OUTPUT_TOKENS=4096
```

Gemini receives untrusted evidence boundaries and a Pydantic response schema. The service rejects the response if it has the wrong question count, duplicate questions/options, anything other than one correct answer, missing explanations, or source chunk IDs that were not retrieved. Schema-valid output is still treated as untrusted until these semantic checks pass.

PostgreSQL stores quiz difficulty and question source references in migration `20261026_0004`. Submission locks the attempt row, verifies that every question is answered exactly once, verifies that each selected option belongs to its question, stores per-question correctness, computes the score, and sets `completed_at` in one transaction. A completed attempt cannot be submitted again.
