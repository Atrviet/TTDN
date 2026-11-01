import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response, status
from app.ai.llm.base import LLMError
from app.ai.rag.service import DocumentNotIndexableError, IndexConfigurationMismatchError, RAGDocumentNotFoundError
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.knowledge_graph import KnowledgeGraphServiceDependency
from app.schemas.knowledge_graph import ConceptDetail, GenerateKnowledgeGraphRequest, GraphEdge, GraphEdgesResponse, GraphNode, GraphNodesResponse, KnowledgeGraphDetail, KnowledgeGraphList, KnowledgeGraphSummary, RelationType, SourceReference
from app.services.knowledge_graph import KnowledgeGraphDocumentError, KnowledgeGraphGenerationError, KnowledgeGraphLimitError, KnowledgeGraphNotFoundError, KnowledgeGraphPersistenceError

router=APIRouter(prefix="/knowledge-graphs",tags=["Knowledge Graphs"])

def summary(graph)->KnowledgeGraphSummary:
    return KnowledgeGraphSummary(id=graph.id,title=graph.title,description=graph.description,document_ids=[d.id for d in graph.documents],node_count=len({s.concept_id for s in graph.concept_sources}),edge_count=len(graph.relations),created_at=graph.created_at,updated_at=graph.updated_at)

def data(graph)->tuple[list[GraphNode],list[GraphEdge]]:
    sources:dict[UUID,list[SourceReference]]={}
    definitions:dict[UUID,set[str]]={}
    concepts={}
    for item in graph.concept_sources:
        concepts[item.concept_id]=item.concept; definitions.setdefault(item.concept_id,set()).add((item.definition or "").strip())
        sources.setdefault(item.concept_id,[]).append(SourceReference(document_id=item.document_id,document_title=item.document.title,chunk_id=item.document_chunk.chroma_id,page_number=item.page_number,definition=item.definition,confidence=float(item.confidence)))
    nodes=[GraphNode(id=c.id,name=c.name,normalized_name=c.normalized_name,definition=c.description,sources=sources.get(c.id,[]),ambiguous=len({d for d in definitions.get(c.id,set()) if d})>1 or any("Alternative extracted definition:" in d for d in definitions.get(c.id,set()))) for c in concepts.values()]
    edges=[]
    for rel in graph.relations:
        ref=None
        if rel.document is not None and rel.document_chunk is not None and rel.page_number is not None:
            ref=SourceReference(document_id=rel.document_id,document_title=rel.document.title,chunk_id=rel.document_chunk.chroma_id,page_number=rel.page_number,confidence=float(rel.confidence))
        edges.append(GraphEdge(id=rel.id,source=rel.source_concept_id,target=rel.target_concept_id,relation_type=RelationType(rel.relation_type),confidence=float(rel.confidence),source_reference=ref))
    return nodes,edges

def detail(graph)->KnowledgeGraphDetail:
    nodes,edges=data(graph); return KnowledgeGraphDetail(**summary(graph).model_dump(),nodes=nodes,edges=edges)

@router.post("/generate",response_model=KnowledgeGraphDetail,status_code=status.HTTP_201_CREATED)
async def generate(payload:GenerateKnowledgeGraphRequest,user:CurrentUser,service:KnowledgeGraphServiceDependency):
    try: return detail(await service.generate(payload,user.id))
    except (KnowledgeGraphDocumentError,RAGDocumentNotFoundError) as exc: raise HTTPException(404,"Document not found") from exc
    except (DocumentNotIndexableError,IndexConfigurationMismatchError) as exc: raise HTTPException(409,str(exc) or "Document index is incompatible") from exc
    except KnowledgeGraphLimitError as exc: raise HTTPException(413,str(exc)) from exc
    except (LLMError,KnowledgeGraphGenerationError,asyncio.TimeoutError) as exc: raise HTTPException(503,"Knowledge extraction is temporarily unavailable") from exc
    except KnowledgeGraphPersistenceError as exc: raise HTTPException(500,"Unable to save knowledge graph") from exc

@router.get("",response_model=KnowledgeGraphList)
async def list_graphs(user:CurrentUser,service:KnowledgeGraphServiceDependency): return KnowledgeGraphList(items=[summary(g) for g in await service.list(user.id)])

async def owned(graph_id,user,service):
    try:return await service.get(graph_id,user.id)
    except KnowledgeGraphNotFoundError as exc:raise HTTPException(404,"Knowledge graph not found") from exc

@router.get("/{graph_id}",response_model=KnowledgeGraphDetail)
async def get_graph(graph_id:UUID,user:CurrentUser,service:KnowledgeGraphServiceDependency): return detail(await owned(graph_id,user,service))
@router.get("/{graph_id}/nodes",response_model=GraphNodesResponse)
async def get_nodes(graph_id:UUID,user:CurrentUser,service:KnowledgeGraphServiceDependency): return GraphNodesResponse(nodes=data(await owned(graph_id,user,service))[0])
@router.get("/{graph_id}/edges",response_model=GraphEdgesResponse)
async def get_edges(graph_id:UUID,user:CurrentUser,service:KnowledgeGraphServiceDependency): return GraphEdgesResponse(edges=data(await owned(graph_id,user,service))[1])
@router.get("/{graph_id}/concepts/{concept_id}",response_model=ConceptDetail)
async def get_concept(graph_id:UUID,concept_id:UUID,user:CurrentUser,service:KnowledgeGraphServiceDependency):
    graph=await owned(graph_id,user,service); nodes,edges=data(graph); node=next((n for n in nodes if n.id==concept_id),None)
    if node is None: raise HTTPException(404,"Concept not found")
    return ConceptDetail(**node.model_dump(),incoming_edges=[e for e in edges if e.target==concept_id],outgoing_edges=[e for e in edges if e.source==concept_id])
@router.delete("/{graph_id}",status_code=204)
async def delete_graph(graph_id:UUID,user:CurrentUser,service:KnowledgeGraphServiceDependency):
    try:await service.delete(graph_id,user.id);return Response(status_code=204)
    except KnowledgeGraphNotFoundError as exc:raise HTTPException(404,"Knowledge graph not found") from exc
