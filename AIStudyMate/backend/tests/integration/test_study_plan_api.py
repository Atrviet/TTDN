import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.ai.llm.base import LLMError, LLMProvider
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.rag import get_rag_service
from app.core.security import create_access_token, hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.advanced_learning import StudyPlan
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document
from app.models.user import User
from app.ai.topics import IdentifiedTopics


def db_url():
    value=os.getenv("TEST_DATABASE_URL"); parsed=make_url(value) if value else None
    if not parsed or "test" not in (parsed.database or ""): pytest.skip("Dedicated test database required")
    return value


class FakeRAG:
    async def search(self,**kwargs):
        return [VectorSearchResult(chroma_id="planner-chunk",text="Variables and functions",distance=.1,metadata={"document_id":str(kwargs["document_ids"][0]),"document_title":"Python","page_number":1})]
class FakeLLM(LLMProvider):
    fail=False
    @property
    def model_name(self): return "fake"
    async def generate(self,**kwargs): return "unused"
    async def generate_structured(self,**kwargs):
        if self.fail: raise LLMError("outage")
        return IdentifiedTopics.model_validate({"topics":[{"name":"Variables","normalized_name":"variables","description":"Basics","evidence_chunk_ids":["planner-chunk"]}]})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_complete_replan_and_ownership():
    engine=create_async_engine(db_url()); factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async def sessions():
        async with factory() as session: yield session
    suffix=uuid4().hex[:8]; owner=User(username=f"plan_{suffix}",email=f"plan_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Owner",role=UserRole.STUDENT); other=User(username=f"other_{suffix}",email=f"other_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Other",role=UserRole.STUDENT)
    async with factory() as session:
        session.add_all([owner,other]); await session.flush(); doc=Document(user_id=owner.id,title="Python",original_filename="p.pdf",file_path="p.pdf",file_size=10,mime_type="application/pdf",processing_status=DocumentProcessingStatus.READY,page_count=1,extracted_pages=[{"page_number":1,"text":"Variables"}],pdf_metadata={},requires_ocr=False,indexing_status=RAGIndexingStatus.INDEXED,embedding_provider="test",embedding_model="test"); session.add(doc); await session.commit()
    app.dependency_overrides[get_db_session]=sessions; app.dependency_overrides[get_rag_service]=lambda:FakeRAG(); llm=FakeLLM(); app.dependency_overrides[get_llm_provider]=lambda:llm
    headers={"Authorization":f"Bearer {create_access_token(owner.id,owner.role)}"}; other_headers={"Authorization":f"Bearer {create_access_token(other.id,other.role)}"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
            payload={"goal":"Pass exam","subject":"Python","exam_date":str(datetime.now(UTC).date()+timedelta(days=14)),"available_days":[0,1,2,3,4,5,6],"daily_available_minutes":60,"preferred_session_minutes":30,"difficulty":"medium","document_ids":[str(doc.id)],"timezone":"UTC"}
            generated=await client.post("/api/v1/study-plans/generate",headers=headers,json=payload); assert generated.status_code==201,generated.text; body=generated.json(); plan_id=body["id"]; assert body["tasks"] and any(t["task_type"]=="review" for t in body["tasks"])
            assert (await client.get(f"/api/v1/study-plans/{plan_id}",headers=other_headers)).status_code==404
            task=body["tasks"][0]; completed=await client.patch(f"/api/v1/study-tasks/{task['id']}",headers=headers,json={"status":"completed","actual_duration_minutes":25}); assert completed.status_code==200
            replanned=await client.post(f"/api/v1/study-plans/{plan_id}/replan",headers=headers,json={}); assert replanned.status_code==200,replanned.text; assert any(t["id"]==task["id"] and t["status"]=="completed" for t in replanned.json()["tasks"])
            impossible={**payload,"exam_date":str(datetime.now(UTC).date()+timedelta(days=1)),"available_days":[(datetime.now(UTC).date()+timedelta(days=1)).weekday()],"daily_available_minutes":15,"preferred_session_minutes":15,"difficulty":"hard"}; assert (await client.post("/api/v1/study-plans/generate",headers=headers,json=impossible)).status_code==409
            llm.fail=True; assert (await client.post("/api/v1/study-plans/generate",headers=headers,json=payload)).status_code==503
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(StudyPlan).where(StudyPlan.user_id.in_([owner.id,other.id]))); await session.execute(delete(Document).where(Document.user_id.in_([owner.id,other.id]))); await session.execute(delete(User).where(User.id.in_([owner.id,other.id]))); await session.commit()
        await engine.dispose()
