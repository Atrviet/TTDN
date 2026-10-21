# AI StudyMate

AI StudyMate is an intelligent learning assistant. STEP 01 provides the FastAPI foundation, versioned API routing, environment-based configuration, structured logging, async SQLAlchemy setup, Alembic, PostgreSQL via Docker Compose, and a database-independent health test.

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

## Run tests

From `AIStudyMate/backend` with the virtual environment activated:

```bash
pytest
```

## Database migrations

Alembic is configured for the async PostgreSQL URL in `.env`. No business tables or migrations are included in STEP 01. Future migrations can be generated from `AIStudyMate/backend` with:

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
