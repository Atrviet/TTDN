"""Reproducible local smoke benchmark against a running development API.

Creates an isolated temporary account and learning document, measures real HTTP
latencies, then removes all generated database/file/vector data.
"""

import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pymupdf
from sqlalchemy import delete

from app.db.session import AsyncSessionFactory
from app.models.user import User


API = "http://127.0.0.1:8000/api/v1"


async def main() -> None:
    suffix = uuid4().hex[:10]
    username = f"perf_{suffix}"
    email = f"{username}@example.com"
    password = "PerformanceOnly123!"
    document_id: str | None = None
    session_id: str | None = None
    timings: dict[str, float] = {}

    with tempfile.TemporaryDirectory() as directory:
        pdf_path = Path(directory) / "performance.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "Retrieval augmented generation retrieves relevant evidence before "
            "the language model answers. Citations connect answers to sources.",
        )
        pdf.save(pdf_path)
        pdf.close()

        async with httpx.AsyncClient(timeout=180) as client:
            health_samples: list[float] = []
            for _ in range(20):
                started = time.perf_counter()
                response = await client.get(f"{API}/health")
                response.raise_for_status()
                health_samples.append((time.perf_counter() - started) * 1000)
            timings["health_p50_ms"] = statistics.median(health_samples)
            timings["health_p95_ms"] = sorted(health_samples)[18]

            response = await client.post(
                f"{API}/auth/register",
                json={"username": username, "email": email, "password": password, "full_name": "Perf Test"},
            )
            response.raise_for_status()
            response = await client.post(
                f"{API}/auth/login", data={"username": username, "password": password}
            )
            response.raise_for_status()
            headers = {"Authorization": f"Bearer {response.json()['access_token']}"}

            with pdf_path.open("rb") as source:
                response = await client.post(
                    f"{API}/documents/upload",
                    headers=headers,
                    data={"title": "Performance RAG"},
                    files={"file": (pdf_path.name, source, "application/pdf")},
                )
            response.raise_for_status()
            document_id = response.json()["id"]

            started = time.perf_counter()
            response = await client.post(f"{API}/documents/{document_id}/index", headers=headers)
            response.raise_for_status()
            timings["document_index_ms"] = (time.perf_counter() - started) * 1000

            started = time.perf_counter()
            response = await client.post(
                f"{API}/rag/search",
                headers=headers,
                json={"query": "What is retrieval augmented generation?", "document_ids": [document_id], "top_k": 5},
            )
            response.raise_for_status()
            timings["retrieval_ms"] = (time.perf_counter() - started) * 1000

            response = await client.post(
                f"{API}/chat/sessions", headers=headers, json={"title": "Performance chat"}
            )
            response.raise_for_status()
            session_id = response.json()["id"]
            started = time.perf_counter()
            first_token: float | None = None
            async with client.stream(
                "POST",
                f"{API}/chat/sessions/{session_id}/messages/stream",
                headers=headers,
                json={"message": "Explain RAG briefly.", "document_ids": [document_id]},
            ) as stream:
                stream.raise_for_status()
                async for line in stream.aiter_lines():
                    if line == "event: token" and first_token is None:
                        first_token = (time.perf_counter() - started) * 1000
                    if line == "event: complete":
                        break
            timings["ai_time_to_first_token_ms"] = first_token or -1
            timings["ai_total_ms"] = (time.perf_counter() - started) * 1000

            if session_id:
                await client.delete(f"{API}/chat/sessions/{session_id}", headers=headers)
            if document_id:
                await client.delete(f"{API}/documents/{document_id}", headers=headers)

    async with AsyncSessionFactory() as session:
        await session.execute(delete(User).where(User.email == email))
        await session.commit()
    print(json.dumps({key: round(value, 2) for key, value in timings.items()}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
