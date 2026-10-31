# Deployment and operations

AI StudyMate is packaged as three services: an unprivileged Nginx frontend, a non-root FastAPI backend, and PostgreSQL 16. The backend runs Alembic migrations before Uvicorn starts. PostgreSQL and FastAPI have no published host ports; only the frontend binds to `127.0.0.1:8080` for a local browser or host TLS proxy.

## Local Docker Compose

Requirements: Docker Desktop/Engine with Compose v2 and at least 6 GB free RAM. The local embedding model and PyTorch make the first backend build comparatively large and slow.

```bash
cp .env.docker.example .env
openssl rand -base64 48
```

Put the generated value in `JWT_SECRET_KEY`, choose a strong independent `POSTGRES_PASSWORD`, and set `GEMINI_API_KEY`. Do not reuse the example placeholders.

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:8080/healthz
curl --fail http://127.0.0.1:8080/api/v1/health

cd backend
AI_STUDYMATE_API=http://127.0.0.1:8080/api/v1 .venv/bin/python -m scripts.system_smoke
```

Open <http://127.0.0.1:8080> and Swagger at <http://127.0.0.1:8080/docs>. Follow logs without printing environment values:

```bash
docker compose logs -f --tail=100 backend frontend
```

Stop while preserving data:

```bash
docker compose down
```

`docker compose down -v` irreversibly deletes PostgreSQL, PDFs, Chroma vectors and model cache; never use it against data that has not been backed up.

## Persistent data

| Volume | Responsibility | Backup priority |
| --- | --- | --- |
| `postgres_data` | Transactional system of record | Required |
| `document_data` | Uploaded source PDFs | Required |
| `chroma_data` | Derived vector index | Recommended; can be rebuilt from PDFs |
| `model_cache` | Downloaded local embedding model | Optional |

PostgreSQL and PDF storage must be backed up as one logical recovery point. If Chroma is not restored, reset affected indexing metadata and re-index documents rather than assuming old vector IDs remain valid.

## Backup and restore

Create a timestamped logical database backup:

```bash
mkdir -p backups
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' \
  > backups/ai_studymate.dump
```

Archive the PDF and Chroma volumes:

```bash
docker run --rm \
  -v ai-studymate_document_data:/source:ro \
  -v "$PWD/backups:/backup" alpine \
  tar czf /backup/documents.tar.gz -C /source .

docker run --rm \
  -v ai-studymate_chroma_data:/source:ro \
  -v "$PWD/backups:/backup" alpine \
  tar czf /backup/chroma.tar.gz -C /source .
```

Test backups regularly on a separate machine/database. To restore during a planned outage:

```bash
docker compose stop backend frontend
docker compose exec -T postgres sh -c \
  'dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < backups/ai_studymate.dump

docker run --rm \
  -v ai-studymate_document_data:/target \
  -v "$PWD/backups:/backup:ro" alpine \
  sh -c 'rm -rf /target/* && tar xzf /backup/documents.tar.gz -C /target'

docker run --rm \
  -v ai-studymate_chroma_data:/target \
  -v "$PWD/backups:/backup:ro" alpine \
  sh -c 'rm -rf /target/* && tar xzf /backup/chroma.tar.gz -C /target'

docker compose up -d
```

Restore commands are destructive and must only target a confirmed recovery environment. Keep encrypted off-host copies and document retention policy.

## Practical hosting strategy: one Ubuntu VM

For an internship demonstration, use an Ubuntu 24.04 VM with 4 vCPU, 8 GB RAM and sufficient encrypted disk. Install Docker Engine from Docker's official repository. Clone a pinned release tag, create the root `.env` directly on the VM with mode `0600`, and run `docker compose up -d --build`.

1. Point `studymate.example.com` to the VM.
2. Keep Compose bound to `127.0.0.1:8080`.
3. Install Caddy on the host and use `deploy/Caddyfile.example`; Caddy obtains and renews TLS certificates.
4. Allow only SSH, HTTP and HTTPS in the firewall. Do not open ports 5432/5433 or 8000.
5. Set `CORS_ORIGINS=["https://studymate.example.com"]`.
6. Schedule encrypted PostgreSQL/PDF backups and monitor disk, container health, HTTP 5xx and Gemini quota errors.
7. Deploy a pinned Git tag, run migrations through the backend entrypoint, verify health, then execute the demo smoke path.

For larger or regulated workloads, move PostgreSQL and object storage to managed services, use a secrets manager, add centralized logs/metrics, multiple backend replicas with a shared vector service, token revocation and automated rollback. The current single-VM design is practical for demonstration but is not evidence of high availability.

## Production security checklist

- Generate distinct high-entropy database and JWT secrets; never commit `.env`.
- Rotate the Gemini key that was ever pasted into a chat, terminal history or ticket.
- Terminate HTTPS at Caddy/load balancer and set the exact HTTPS CORS origin.
- Keep database/backend ports private and restrict SSH by key/IP.
- Run containers/images with vulnerability scanning and pin reviewed versions/digests.
- Back up and restore-test PostgreSQL and PDFs; monitor volume capacity.
- Keep access tokens short-lived. The current refresh-token design needs rotation, server-side revocation and `HttpOnly` cookies before higher-risk production use.
- Treat PDFs and retrieved text as untrusted. Preserve upload validation, ownership checks, context boundaries and graph limits.

## Rollout and rollback

Before rollout: back up, run tests, run `docker compose config`, build images, and record the Git tag. After rollout: check all health endpoints, registration/login, upload/index/search and one AI request. For application rollback, deploy the previous image/tag. Database downgrade is not automatic; write a reviewed forward-fix or restore a verified backup when a migration is not backward compatible.
