from fastapi import APIRouter

from app.api.v1.endpoints.agent import router as agent_router
from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.flashcards import router as flashcards_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.rag import router as rag_router
from app.api.v1.endpoints.quizzes import router as quizzes_router
from app.api.v1.endpoints.users import router as users_router
from app.api.v1.endpoints.study_plans import router as study_plans_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(documents_router)
api_router.include_router(flashcards_router)
api_router.include_router(rag_router)
api_router.include_router(chat_router)
api_router.include_router(agent_router)
api_router.include_router(quizzes_router)
api_router.include_router(analytics_router)
api_router.include_router(study_plans_router)

