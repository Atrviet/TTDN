# Internship defense package

## Demonstration scenario (10–12 minutes)

Prepare one short Vietnamese PDF with clear headings and five factual statements. Pre-index a backup copy and keep screenshots in case the external Gemini service is unavailable.

1. **Register and login (1 minute):** create a student account, sign in, point out short-lived access token and protected routes.
2. **Upload PDF (1 minute):** upload the prepared PDF, show validation, extracted pages and owner-only document library.
3. **Index and search (1 minute):** start indexing, explain chunk size/overlap, PostgreSQL metadata versus Chroma vectors, then issue a semantic search.
4. **Grounded AI Chat (2 minutes):** ask a factual question; show streamed text and citations with title/page/chunk. Ask an out-of-context question to demonstrate the insufficient-evidence response.
5. **Study Agent (2 minutes):** request “Giải thích chương 1 và lập kế hoạch ôn tập ba ngày”; show routed tools, bounded steps and citations.
6. **Quiz (2 minutes):** generate four questions, emphasize structured Pydantic validation and hidden correct answers, complete and submit once, then show deterministic grading/explanations.
7. **Analytics (1 minute):** open overview, progress and weak topics; explain that metrics come only from completed attempts.
8. **Operations (1 minute):** show Swagger, container health, test summary and backup strategy. Close with measured limitations rather than claiming unlimited scale.

Demo checklist: Docker services healthy, Gemini quota available, local embedding model cached, PDF under size limit, browser logged out, clock/timezone correct, backup demo account available.

## Technical report outline

1. Problem statement, stakeholders and measurable goals.
2. Requirements: functional, security, performance and constraints.
3. Technology selection and rejected alternatives.
4. Modular architecture and dependency boundaries.
5. Database design, constraints, ownership and migrations.
6. Authentication and authorization threat model.
7. PDF extraction, Unicode preprocessing and chunking.
8. RAG indexing/retrieval and PostgreSQL–Chroma consistency.
9. Gemini prompt strategy, citations, quota/error handling and SSE.
10. LangGraph typed state, tools, limits and persistence.
11. Quiz generation, structured validation and deterministic grading.
12. Analytics formulas and data limitations.
13. Frontend architecture, token storage and accessible states.
14. Testing strategy, matrix, measured performance and defects fixed.
15. Docker deployment, backup/restore and operational risks.
16. Limitations, ethical considerations and future roadmap.

## Presentation outline (12–15 slides)

1. Title, role and project objective.
2. User problem and core use cases.
3. Feature walkthrough.
4. System architecture diagram.
5. Database ER diagram and ownership model.
6. RAG pipeline and citation flow.
7. LangGraph agent graph and safe tools.
8. Authentication and security controls.
9. Quiz and analytics workflow.
10. Realtime SSE and cancellation.
11. Test pyramid and integration matrix.
12. Measured performance—not estimates.
13. Docker deployment and data durability.
14. Known limitations and production gap.
15. Conclusion and live demo/Q&A.

## Architecture explanation

React never talks directly to Gemini, PostgreSQL, Chroma or the filesystem. Nginx serves the SPA and proxies same-origin API/SSE traffic to FastAPI. FastAPI validates identity and ownership before invoking services. PostgreSQL is the authoritative transactional store; PDFs are private persistent files; Chroma is a rebuildable semantic index linked through stable chunk IDs. Gemini generates only after authorized retrieval. LangGraph coordinates bounded tools whose server-side context supplies the real user ID, so LLM-generated identity claims are ignored.

## Security explanation

- Argon2 password hashing; signed typed JWTs with issuer/audience/expiry.
- Registration cannot self-assign admin; every resource query is scoped by authenticated owner.
- Access token stays in memory; refresh token currently uses session storage and is a documented production gap.
- API keys exist only in backend runtime environment; frontend image contains no Gemini secret.
- PDF type/size/extraction validation and non-public storage.
- Retrieved text is delimited as untrusted data; system instructions explicitly reject embedded commands.
- Agent has an allowlist of tools, validated arguments, time/step/tool-call limits and no shell/filesystem/network tool.
- Streaming authentication uses headers, not query strings; incomplete streams are not persisted.
- Database and backend are not published by production Compose; Nginx adds browser security headers and TLS is terminated externally.

## RAG evaluation methodology

Build a versioned Vietnamese evaluation set from documents not used while tuning. Each record contains question, authorized document IDs, expected answer facts, relevant page/chunk labels, and whether the correct behavior is abstention.

Measure separately:

- **Retrieval Recall@k:** fraction of questions whose labeled relevant chunk appears in top-k.
- **MRR:** reciprocal rank of the first relevant chunk.
- **Citation precision:** cited chunks that actually support the answer divided by all citations.
- **Faithfulness/groundedness:** supported answer claims divided by factual claims, reviewed with a rubric and sampled by two humans.
- **Answer correctness:** required expected facts present without contradiction.
- **Abstention accuracy:** out-of-context questions correctly rejected.
- **Latency:** retrieval, time-to-first-token and total response p50/p95.
- **Cost/quota:** input/output tokens and failures by response category.

Freeze embedding model, chunk settings and collection version for each run. Compare configurations on the same set; report confidence intervals/sample size and qualitative failure categories. Do not claim retrieval quality from latency measurements or a few demo questions.

## Common defense questions and suggested answers

**Why both PostgreSQL and ChromaDB?** PostgreSQL owns transactions, constraints, users and metadata. Chroma optimizes similarity search and is derived/rebuildable; it is not the source of truth.

**How do citations avoid hallucination?** Citations are created only from retrieved authorized chunks, never parsed from arbitrary model text. This reduces but cannot eliminate hallucination; faithfulness still needs evaluation.

**Why LangGraph instead of a simple prompt?** The agent needs explicit typed state, conditional tool routing, bounded iteration and auditable tool history. Simple chat remains a direct RAG path.

**Can one user access another user's document by guessing UUIDs?** Repository/service queries scope resource IDs to the authenticated user and return non-disclosing 404 responses. Integration tests cover cross-user access.

**Why SSE rather than WebSocket?** The use case is one-way incremental output per request. POST-based SSE over fetch supports JSON body, Bearer header, proxies and cancellation with less protocol/state complexity.

**What happens if Gemini fails after output starts?** The client receives a terminal safe error event. The server rolls back and does not persist the partial exchange.

**Why is grading deterministic?** Gemini creates a validated quiz once; submission compares stored option IDs on the backend. The LLM is not called to decide a student's score.

**What does “weak topic” mean?** It is derived only from actual incorrect answers grouped by available quiz/document topic metadata. Missing labels mean the system returns limited or empty insight rather than inventing one.

**What is the biggest production gap?** Stateless refresh tokens/sessionStorage, single-node Chroma/files, limited observability and no sustained-load/HA evidence. Production would add rotating HttpOnly refresh cookies, revocation, managed storage/database/vector service and monitoring.

**How would you scale indexing?** Move CPU/network-heavy indexing to an idempotent job queue, store job status in PostgreSQL, use shared object/vector storage, bound concurrency and retry only safe stages.

**How do you evaluate Vietnamese retrieval?** Use a labeled Vietnamese question–chunk set and Recall@k/MRR, then evaluate answer faithfulness/citations separately. Preserve Unicode and compare chunk/embedding configurations under a fixed dataset.

**Is the project production-ready?** It is production-oriented and demonstrable: boundaries, tests, images, health checks and backups exist. It is not proven production-ready until load, restore, security scanning, observability, HA and operational SLOs are validated in the target environment.
