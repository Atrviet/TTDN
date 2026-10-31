"""Destructive-data smoke journey intended for a disposable deployment stack."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
import pymupdf


API = os.getenv("AI_STUDYMATE_API", "http://127.0.0.1:8080/api/v1").rstrip("/")


async def checked(response: httpx.Response, step: str) -> dict:
    if response.is_error:
        raise RuntimeError(f"{step} failed ({response.status_code}): {response.text[:500]}")
    print(f"PASS {step}: HTTP {response.status_code}")
    return response.json() if response.content else {}


async def main() -> None:
    suffix = uuid4().hex[:10]
    username = f"smoke_{suffix}"
    password = "SmokeJourney123!"

    with tempfile.TemporaryDirectory() as directory:
        pdf_path = Path(directory) / "rag-lesson.pdf"
        pdf = pymupdf.open()
        page = pdf.new_page()
        page.insert_text(
            (72, 72),
            "RAG lesson. Retrieval augmented generation retrieves relevant document chunks "
            "before answering. Citations connect an answer to its evidence. "
            "A safe assistant should refuse unsupported claims.",
        )
        pdf.save(pdf_path)
        pdf.close()

        async with httpx.AsyncClient(timeout=240) as client:
            await checked(await client.get(f"{API}/health"), "health")
            await checked(
                await client.post(
                    f"{API}/auth/register",
                    json={
                        "username": username,
                        "email": f"{username}@example.com",
                        "password": password,
                        "full_name": "System Smoke",
                    },
                ),
                "register",
            )
            tokens = await checked(
                await client.post(f"{API}/auth/login", data={"username": username, "password": password}),
                "login",
            )
            headers = {"Authorization": f"Bearer {tokens['access_token']}"}

            with pdf_path.open("rb") as source:
                document = await checked(
                    await client.post(
                        f"{API}/documents/upload",
                        headers=headers,
                        data={"title": "RAG Defense Lesson"},
                        files={"file": (pdf_path.name, source, "application/pdf")},
                    ),
                    "upload PDF",
                )
            document_id = document["id"]
            await checked(
                await client.post(f"{API}/documents/{document_id}/index", headers=headers),
                "index document",
            )
            search = await checked(
                await client.post(
                    f"{API}/rag/search",
                    headers=headers,
                    json={"query": "What does RAG retrieve?", "document_ids": [document_id], "top_k": 3},
                ),
                "semantic search",
            )
            if not search.get("results"):
                raise RuntimeError("semantic search returned no evidence")

            session = await checked(
                await client.post(f"{API}/chat/sessions", headers=headers, json={"title": "Smoke journey"}),
                "create chat session",
            )
            session_id = session["id"]
            events: list[str] = []
            async with client.stream(
                "POST",
                f"{API}/chat/sessions/{session_id}/messages/stream",
                headers=headers,
                json={"message": "Explain RAG briefly.", "document_ids": [document_id]},
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        events.append(line.removeprefix("event: "))
            required_events = {"citations", "token", "complete"}
            if not required_events.issubset(events):
                raise RuntimeError(f"chat stream missing events: {required_events - set(events)}")
            print("PASS grounded chat stream: citations + token + complete")

            agent = await checked(
                await client.post(
                    f"{API}/agent/chat",
                    headers=headers,
                    json={
                        "session_id": session_id,
                        "message": "Explain the lesson and recommend a study activity.",
                        "document_ids": [document_id],
                    },
                ),
                "LangGraph agent",
            )
            if agent.get("execution_status") != "completed":
                raise RuntimeError(f"agent did not complete: {agent.get('execution_status')}")

            quiz = await checked(
                await client.post(
                    f"{API}/quizzes/generate",
                    headers=headers,
                    json={
                        "title": "RAG Smoke Quiz",
                        "number_of_questions": 2,
                        "difficulty": "easy",
                        "document_id": document_id,
                    },
                ),
                "generate quiz",
            )
            attempt = await checked(
                await client.post(f"{API}/quizzes/{quiz['id']}/attempts", headers=headers),
                "start quiz attempt",
            )
            answers = [
                {"question_id": question["id"], "selected_option_id": question["options"][0]["id"]}
                for question in attempt["quiz"]["questions"]
            ]
            await checked(
                await client.post(
                    f"{API}/quizzes/attempts/{attempt['id']}/submit",
                    headers=headers,
                    json={"answers": answers},
                ),
                "submit and grade quiz",
            )
            await checked(
                await client.get(f"{API}/quizzes/attempts/{attempt['id']}/results", headers=headers),
                "quiz results",
            )
            overview = await checked(
                await client.get(f"{API}/analytics/overview", headers=headers),
                "analytics update",
            )
            if overview.get("total_quizzes_attempted") != 1:
                raise RuntimeError(f"analytics did not include completed attempt: {json.dumps(overview)}")

    print("SYSTEM SMOKE PASSED")


if __name__ == "__main__":
    asyncio.run(main())
