import os
from datetime import UTC,datetime
from decimal import Decimal
from uuid import uuid4
import pytest
from httpx import ASGITransport,AsyncClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession,async_sessionmaker,create_async_engine
from app.core.security import create_access_token,hash_password
from app.db.session import get_db_session
from app.main import app
from app.models.advanced_learning import Flashcard,FlashcardDeck,FlashcardReview
from app.models.common import DocumentProcessingStatus,FlashcardReviewRating,UserRole
from app.models.document import Document
from app.models.quiz import AnswerOption,Question,Quiz,QuizAttempt,UserAnswer
from app.models.user import User

@pytest.mark.integration
@pytest.mark.asyncio
async def test_learning_mastery_mapping_recommendations_and_isolation():
    value=os.getenv("TEST_DATABASE_URL");parsed=make_url(value) if value else None
    if not parsed or "test" not in (parsed.database or ""):pytest.skip("Dedicated test database required")
    engine=create_async_engine(value);factory=async_sessionmaker(engine,class_=AsyncSession,expire_on_commit=False)
    async def sessions():
        async with factory() as s:yield s
    suffix=uuid4().hex[:8];owner=User(username=f"learn_{suffix}",email=f"learn_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Owner",role=UserRole.STUDENT);other=User(username=f"learn_o_{suffix}",email=f"learn_o_{suffix}@x.test",hashed_password=hash_password("Password123!"),full_name="Other",role=UserRole.STUDENT)
    async with factory() as s:
        s.add_all([owner,other]);await s.flush();doc=Document(user_id=owner.id,title="Python",original_filename="p.pdf",file_path="p.pdf",file_size=10,mime_type="application/pdf",processing_status=DocumentProcessingStatus.READY,page_count=1,extracted_pages=[{"page_number":1,"text":"Python"}],pdf_metadata={},requires_ocr=False);s.add(doc);await s.flush()
        quiz=Quiz(user_id=owner.id,document_id=doc.id,title="Python",difficulty="medium");s.add(quiz);await s.flush();questions=[]
        for i in range(2):
            q=Question(quiz_id=quiz.id,question_text=f"Q{i}",question_order=i);s.add(q);await s.flush();correct=AnswerOption(question_id=q.id,option_text="Correct",is_correct=True,option_order=0);wrong=AnswerOption(question_id=q.id,option_text="Wrong",is_correct=False,option_order=1);s.add_all([correct,wrong]);await s.flush();questions.append((q,correct,wrong))
        attempt=QuizAttempt(quiz_id=quiz.id,user_id=owner.id,score=1,total_questions=2,completed_at=datetime.now(UTC));s.add(attempt);await s.flush();s.add_all([UserAnswer(attempt_id=attempt.id,question_id=questions[0][0].id,selected_option_id=questions[0][1].id,is_correct=True),UserAnswer(attempt_id=attempt.id,question_id=questions[1][0].id,selected_option_id=questions[1][2].id,is_correct=False)])
        deck=FlashcardDeck(user_id=owner.id,title="Python");card=Flashcard(deck=deck,front_text="for",back_text="loop",card_order=0);s.add(deck);s.add(card);await s.flush();s.add(FlashcardReview(flashcard_id=card.id,rating=FlashcardReviewRating.AGAIN,reviewed_at=datetime.now(UTC),interval_days=0,ease_factor=Decimal("2.50"),repetition_count=0,next_review_at=datetime.now(UTC)));await s.commit()
    app.dependency_overrides[get_db_session]=sessions;headers={"Authorization":f"Bearer {create_access_token(owner.id,owner.role)}"};other_headers={"Authorization":f"Bearer {create_access_token(other.id,other.role)}"}
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
            empty=await client.post("/api/v1/learning/mastery/recalculate",headers=other_headers);assert empty.status_code==200 and empty.json()["topics_calculated"]==0
            response=await client.post("/api/v1/learning/mastery/recalculate",headers=headers);assert response.status_code==200,response.text;body=response.json();assert body["mappings_created"]==3;assert body["topics_calculated"]==1
            topic=body["mastery"]["items"][0];assert topic["level"]=="needs_review";assert topic["evidence_count"]==3;assert topic["components"]["quiz"]["score"]==pytest.approx(.5);assert topic["components"]["flashcard"]["score"]==0
            weak=(await client.get("/api/v1/learning/weak-topics",headers=headers)).json();assert len(weak["items"])==1
            assert (await client.get("/api/v1/learning/mastery",headers=other_headers)).json()["items"]==[]
            recs=(await client.get("/api/v1/learning/recommendations",headers=headers)).json()["items"];assert {r["recommendation_type"] for r in recs}>={"flashcard_review","practice_quiz","tutor"}
            mappings=(await client.get("/api/v1/learning/topic-mappings",headers=headers)).json();mapping=mappings[0];corrected=await client.patch(f"/api/v1/learning/topic-mappings/{mapping['id']}",headers=headers,json={"topic_name":"Algorithms"});assert corrected.status_code==200 and corrected.json()["is_verified"] is True and corrected.json()["provenance"]=="user_corrected"
            assert (await client.patch(f"/api/v1/learning/topic-mappings/{mapping['id']}",headers=other_headers,json={"topic_name":"Stolen"})).status_code==404
    finally:
        app.dependency_overrides.clear()
        async with factory() as s:
            await s.execute(delete(UserAnswer).where(UserAnswer.attempt_id==attempt.id));await s.execute(delete(QuizAttempt).where(QuizAttempt.id==attempt.id));await s.execute(delete(Quiz).where(Quiz.id==quiz.id));await s.execute(delete(FlashcardDeck).where(FlashcardDeck.id==deck.id));await s.execute(delete(Document).where(Document.id==doc.id));await s.execute(delete(User).where(User.id.in_([owner.id,other.id])));await s.commit()
        await engine.dispose()
