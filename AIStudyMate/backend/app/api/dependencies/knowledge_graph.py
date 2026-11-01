from typing import Annotated
from fastapi import Depends
from app.api.dependencies.auth import SessionDependency
from app.api.dependencies.chat import LLMDependency
from app.api.dependencies.rag import RAGServiceDependency
from app.core.config import get_settings
from app.services.knowledge_graph import KnowledgeGraphService

def get_knowledge_graph_service(session:SessionDependency,rag:RAGServiceDependency,llm:LLMDependency)->KnowledgeGraphService:
    s=get_settings(); return KnowledgeGraphService(session,rag,llm,batch_size=s.knowledge_graph_batch_size,max_chunks=s.knowledge_graph_max_chunks,max_output_tokens=s.knowledge_graph_max_output_tokens,timeout_seconds=s.knowledge_graph_timeout_seconds,validation_retries=s.knowledge_graph_validation_retries)
KnowledgeGraphServiceDependency=Annotated[KnowledgeGraphService,Depends(get_knowledge_graph_service)]
