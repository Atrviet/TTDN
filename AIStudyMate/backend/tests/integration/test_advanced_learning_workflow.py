import os
from datetime import UTC,date,datetime,timedelta
from pathlib import Path
from uuid import UUID,uuid4
import pymupdf,pytest
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete,select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from app.ai.llm.base import LLMProvider
from app.ai.rag.service import IndexingResult
from app.ai.rag.vector_store import VectorSearchResult
from app.api.dependencies.chat import get_llm_provider
from app.api.dependencies.document import get_document_storage
from app.api.dependencies.rag import get_rag_service,get_vector_store
from app.db.session import get_db_session
from app.main import app
from app.models.advanced_learning import FlashcardDeck,KnowledgeGraph,StudyPlan,TutorSession
from app.models.common import RAGIndexingStatus
from app.models.document import Document,DocumentChunk
from app.models.quiz import Quiz,QuizAttempt
from app.models.user import User
from app.services.storage import LocalDocumentStorage

def pdf_bytes()->bytes:
    pdf=pymupdf.open();page=pdf.new_page();page.insert_text((72,72),"Python for loops iterate over an iterable. Functions use def and return values.");data=pdf.tobytes();pdf.close();return data

class FakeVector:
    async def delete_document(self,*args):return None

class WorkflowRAG:
    def __init__(self,factory):self.factory=factory
    async def index_document(self,document_id,user_id):
        async with self.factory() as s:
            doc=await s.scalar(select(Document).where(Document.id==document_id,Document.user_id==user_id));doc.indexing_status=RAGIndexingStatus.INDEXED;doc.embedding_provider="fake";doc.embedding_model="fake";doc.indexed_at=datetime.now(UTC);s.add(DocumentChunk(document_id=doc.id,chroma_id=f"{doc.id}:0",chunk_index=0,page_number=1,token_count=14));await s.commit()
        return IndexingResult(document_id,RAGIndexingStatus.INDEXED,1,False,"fake","fake")
    async def search(self,*,document_ids,**kwargs):
        doc_id=document_ids[0];return [VectorSearchResult(chroma_id=f"{doc_id}:0",text="Python for loops iterate over an iterable. Functions use def.",distance=.05,metadata={"document_id":str(doc_id),"document_title":"Python","page_number":1})]
    async def get_authorized_indexed_chunks(self,*,document_ids,**kwargs):return await self.search(document_ids=document_ids)

class WorkflowLLM(LLMProvider):
    @property
    def model_name(self):return "workflow-fake"
    async def generate(self,**kwargs):return "Vòng lặp for duyệt từng phần tử trong iterable. Bạn dự đoán phần tử đầu tiên là gì?"
    async def generate_structured(self,*,response_model,prompt,**kwargs):
        name=response_model.__name__;chunk=next((part.split('"')[0] for part in prompt.split(":0")[:1] if False),None)
        import re
        found=re.search(r'[0-9a-f-]{36}:0',prompt);chunk_id=found.group(0) if found else "missing:0";doc_id=chunk_id.split(":")[0]
        if name=="GeneratedFlashcards":return response_model.model_validate({"cards":[{"front_text":"for lặp qua gì?","back_text":"iterable","explanation":"Theo tài liệu","source":{"chunk_id":chunk_id}}]})
        if name=="GeneratedQuiz":return response_model.model_validate({"questions":[{"question_text":"for dùng với gì?","options":[{"text":"iterable","is_correct":True},{"text":"integer","is_correct":False},{"text":"file only","is_correct":False},{"text":"nothing","is_correct":False}],"explanation":"for iterates over iterable","source_references":[{"chunk_id":chunk_id}]}]})
        if name=="IdentifiedTopics":return response_model.model_validate({"topics":[{"name":"Python","normalized_name":"python","description":"Python basics","evidence_chunk_ids":[chunk_id]}]})
        if name=="ExtractedKnowledge":return response_model.model_validate({"concepts":[{"name":"Python","definition":"Programming language","source_chunk_id":chunk_id,"confidence":.8},{"name":"for loop","definition":"Iteration construct","source_chunk_id":chunk_id,"confidence":.8}],"relations":[{"source":"for loop","target":"Python","relation_type":"part_of","source_chunk_id":chunk_id,"confidence":.7}]})
        raise AssertionError(name)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_advanced_learning_api_workflow(tmp_path:Path):
    value=os.getenv("TEST_DATABASE_URL");parsed=make_url(value) if value else None
    if not parsed or "test" not in (parsed.database or ""):pytest.skip("Dedicated test database required")
    engine=create_async_engine(value);factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async def sessions():
        async with factory() as s:yield s
    rag=WorkflowRAG(factory);app.dependency_overrides[get_db_session]=sessions;app.dependency_overrides[get_rag_service]=lambda:rag;app.dependency_overrides[get_llm_provider]=lambda:WorkflowLLM();app.dependency_overrides[get_document_storage]=lambda:LocalDocumentStorage(tmp_path/"documents");app.dependency_overrides[get_vector_store]=lambda:FakeVector()
    suffix=uuid4().hex[:8];email=f"flow_{suffix}@example.com";username=f"flow_{suffix}";user_id=None;doc_id=None;quiz_id=None;attempt_id=None;deck_id=None;plan_id=None;tutor_id=None;graph_id=None
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as c:
            assert (await c.post("/api/v1/auth/register",json={"username":username,"email":email,"password":"Password123!","full_name":"Workflow"})).status_code==201
            login=await c.post("/api/v1/auth/login",data={"username":username,"password":"Password123!"});headers={"Authorization":f"Bearer {login.json()['access_token']}"}
            user_id=(await c.get("/api/v1/users/me",headers=headers)).json()["id"]
            upload=await c.post("/api/v1/documents/upload",headers=headers,data={"title":"Python"},files={"file":("python.pdf",pdf_bytes(),"application/pdf")});assert upload.status_code==201,upload.text;doc_id=upload.json()["id"]
            assert (await c.post(f"/api/v1/documents/{doc_id}/index",headers=headers)).status_code==200
            flash=await c.post("/api/v1/flashcards/generate",headers={**headers,"Idempotency-Key":f"flash-{suffix}"},json={"document_ids":[doc_id],"topic":"Python","card_count":1,"difficulty":"medium","title":"Python"});assert flash.status_code==201,flash.text;deck_id=flash.json()["id"];card_id=flash.json()["cards"][0]["id"]
            tomorrow=date.today()+timedelta(days=10);plan=await c.post("/api/v1/study-plans/generate",headers=headers,json={"goal":"Learn Python","subject":"Python","exam_date":str(tomorrow),"available_days":[0,1,2,3,4,5,6],"daily_available_minutes":60,"preferred_session_minutes":30,"difficulty":"medium","document_ids":[doc_id],"timezone":"Asia/Ho_Chi_Minh"});assert plan.status_code==201,plan.text;plan_id=plan.json()["id"]
            tutor=await c.post("/api/v1/tutor/sessions",headers=headers,json={"title":"Python Tutor","document_ids":[doc_id]});tutor_id=tutor.json()["id"];assert (await c.post(f"/api/v1/tutor/sessions/{tutor_id}/messages",headers=headers,json={"message":"Giải thích for","mode":"socratic","difficulty":"beginner","document_ids":[doc_id]})).status_code==200
            graph=await c.post("/api/v1/knowledge-graphs/generate",headers=headers,json={"title":"Python Graph","document_ids":[doc_id]});assert graph.status_code==201,graph.text;graph_id=graph.json()["id"]
            quiz=await c.post("/api/v1/quizzes/generate",headers=headers,json={"title":"Python","number_of_questions":1,"difficulty":"medium","document_id":doc_id});assert quiz.status_code==201,quiz.text;quiz_id=quiz.json()["id"];question=quiz.json()["questions"][0]
            attempt=await c.post(f"/api/v1/quizzes/{quiz_id}/attempts",headers=headers);attempt_id=attempt.json()["id"];wrong=question["options"][1]["id"];assert (await c.post(f"/api/v1/quizzes/attempts/{attempt_id}/submit",headers=headers,json={"answers":[{"question_id":question["id"],"selected_option_id":wrong}]})).status_code==200
            assert (await c.post(f"/api/v1/flashcards/{card_id}/review",headers=headers,json={"rating":"again"})).status_code==200
            mastery=await c.post("/api/v1/learning/mastery/recalculate",headers=headers);assert mastery.status_code==200,mastery.text;assert mastery.json()["mastery"]["items"][0]["level"]=="needs_review"
            replanned=await c.post(f"/api/v1/study-plans/{plan_id}/replan",headers=headers,json={"reason":"Weak topic detected"});assert replanned.status_code==200,replanned.text;assert any(t["priority"]==1 and "Weakness Detection" in (t["description"] or "") for t in replanned.json()["tasks"])
            blocked=await c.delete(f"/api/v1/documents/{doc_id}",headers=headers);assert blocked.status_code==409 and "quizzes" in blocked.json()["detail"]["resource_types"]
    finally:
        app.dependency_overrides.clear()
        if user_id:
            uid=UUID(user_id)
            async with factory() as s:
                if attempt_id:await s.execute(delete(QuizAttempt).where(QuizAttempt.id==UUID(attempt_id)))
                if quiz_id:await s.execute(delete(Quiz).where(Quiz.id==UUID(quiz_id)))
                if graph_id:await s.execute(delete(KnowledgeGraph).where(KnowledgeGraph.id==UUID(graph_id)))
                if tutor_id:await s.execute(delete(TutorSession).where(TutorSession.id==UUID(tutor_id)))
                if plan_id:await s.execute(delete(StudyPlan).where(StudyPlan.id==UUID(plan_id)))
                if deck_id:await s.execute(delete(FlashcardDeck).where(FlashcardDeck.id==UUID(deck_id)))
                if doc_id:await s.execute(delete(Document).where(Document.id==UUID(doc_id)))
                await s.execute(delete(User).where(User.id==uid));await s.commit()
        await engine.dispose()
