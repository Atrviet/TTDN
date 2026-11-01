import os
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
from app.models.advanced_learning import KnowledgeGraph
from app.models.common import DocumentProcessingStatus, RAGIndexingStatus, UserRole
from app.models.document import Document, DocumentChunk
from app.models.user import User


class FakeRAG:
    def __init__(self): self.document_id=None
    async def get_authorized_indexed_chunks(self,**kwargs):
        return [VectorSearchResult(chroma_id=f"{self.document_id}:{i}",text=f"Python concept chunk {i}",distance=0,metadata={"document_id":str(self.document_id),"document_title":"Python","page_number":i+1}) for i in range(7)]


class FakeLLM(LLMProvider):
    def __init__(self): self.calls=0;self.fail=False;self.empty=False
    @property
    def model_name(self):return "fake"
    async def generate(self,**kwargs):return "unused"
    async def generate_structured(self,*,prompt,response_model,**kwargs):
        self.calls+=1
        if self.fail:raise LLMError("quota")
        if self.empty:return response_model.model_validate({"concepts":[],"relations":[]})
        chunk=prompt.split('"source_chunk_id": "',1)[1].split('"',1)[0]
        return response_model.model_validate({"concepts":[{"name":"Python","definition":"Ngôn ngữ lập trình","source_chunk_id":chunk,"confidence":.9},{"name":"PYTHON!","definition":"Một ngôn ngữ cấp cao","source_chunk_id":chunk,"confidence":.7},{"name":"Vòng lặp","definition":"Cấu trúc lặp","source_chunk_id":chunk,"confidence":.8}],"relations":[{"source":"Vòng lặp","target":"Python","relation_type":"part_of","source_chunk_id":chunk,"confidence":.75},{"source":"Không tồn tại","target":"Python","relation_type":"related_to","source_chunk_id":chunk,"confidence":.5}]})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_batch_deduplicate_provenance_ownership_empty_failure_and_delete():
    value=os.getenv("TEST_DATABASE_URL");parsed=make_url(value) if value else None
    if not parsed or "test" not in (parsed.database or ""):pytest.skip("Dedicated test database required")
    engine=create_async_engine(value);factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async def sessions():
        async with factory() as s:yield s
    suffix=uuid4().hex[:8];owner=User(username=f"kg_{suffix}",email=f"kg_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Owner",role=UserRole.STUDENT);other=User(username=f"kg_o_{suffix}",email=f"kg_o_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Other",role=UserRole.STUDENT)
    async with factory() as s:
        s.add_all([owner,other]);await s.flush();doc=Document(user_id=owner.id,title="Python",original_filename="p.pdf",file_path="p.pdf",file_size=10,mime_type="application/pdf",processing_status=DocumentProcessingStatus.READY,page_count=7,extracted_pages=[{"page_number":i+1,"text":f"chunk {i}"} for i in range(7)],pdf_metadata={},requires_ocr=False,indexing_status=RAGIndexingStatus.INDEXED,embedding_provider="test",embedding_model="test");s.add(doc);await s.flush();s.add_all([DocumentChunk(document_id=doc.id,chroma_id=f"{doc.id}:{i}",chunk_index=i,page_number=i+1,token_count=5) for i in range(7)]);await s.commit()
    rag=FakeRAG();rag.document_id=doc.id;llm=FakeLLM();app.dependency_overrides[get_db_session]=sessions;app.dependency_overrides[get_rag_service]=lambda:rag;app.dependency_overrides[get_llm_provider]=lambda:llm
    headers={"Authorization":f"Bearer {create_access_token(owner.id,owner.role)}"};other_headers={"Authorization":f"Bearer {create_access_token(other.id,other.role)}"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
            response=await client.post("/api/v1/knowledge-graphs/generate",headers=headers,json={"title":"Python Graph","document_ids":[str(doc.id)]});assert response.status_code==201,response.text;body=response.json();graph_id=body["id"]
            assert llm.calls==2;assert body["node_count"]==2;assert body["edge_count"]==1;assert body["nodes"][0]["sources"][0]["page_number"]==1;assert any(n["ambiguous"] for n in body["nodes"])
            assert (await client.get(f"/api/v1/knowledge-graphs/{graph_id}",headers=other_headers)).status_code==404
            concept_id=body["nodes"][0]["id"];assert (await client.get(f"/api/v1/knowledge-graphs/{graph_id}/concepts/{concept_id}",headers=headers)).status_code==200
            llm.empty=True;empty=await client.post("/api/v1/knowledge-graphs/generate",headers=headers,json={"title":"Empty","document_ids":[str(doc.id)]});assert empty.status_code==201 and empty.json()["node_count"]==0
            llm.empty=False;llm.fail=True;assert (await client.post("/api/v1/knowledge-graphs/generate",headers=headers,json={"title":"Failure","document_ids":[str(doc.id)]})).status_code==503
            assert (await client.delete(f"/api/v1/knowledge-graphs/{graph_id}",headers=headers)).status_code==204;assert (await client.get(f"/api/v1/knowledge-graphs/{graph_id}",headers=headers)).status_code==404
    finally:
        app.dependency_overrides.clear()
        async with factory() as s:
            await s.execute(delete(KnowledgeGraph).where(KnowledgeGraph.user_id.in_([owner.id,other.id])));await s.execute(delete(Document).where(Document.user_id.in_([owner.id,other.id])));await s.execute(delete(User).where(User.id.in_([owner.id,other.id])));await s.commit()
        await engine.dispose()
