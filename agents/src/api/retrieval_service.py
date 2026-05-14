"""
Retrieval Service - Microservice for query processing and retrieval.

Handles:
- Query processing
- SPARQL generation
- Vector search
- Answer synthesis
- Reasoning

Port: 8002
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_settings
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import (
    LangGraphRetrievalOrchestrator
)
from observability.phoenix_tracer import PhoenixTracer
from ontology_manager import initialize_ontology
from logger import get_module_logger

logger = get_module_logger(__name__)

from fastapi import Depends
from auth import verify_api_token

from typing import Optional
from pydantic_settings import BaseSettings




# Pydantic models
class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., description="Natural language query")
    max_results: int = Field(10, ge=1, le=100, description="Maximum number of results")


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    reasoning_steps: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    service: str
    version: str
    dependencies: Dict[str, str]


# Application state
app_state = {
    "retrieval_orchestrator": None,
    "phoenix_tracer": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Retrieval Service...")
    
    config = get_settings()
    
    # Initialize Phoenix tracing
    if config.phoenix_enabled:
        app_state["phoenix_tracer"] = PhoenixTracer()
        logger.info("Phoenix tracing enabled")
    
    # Load ontology so SPARQL generator knows full schema
    try:
        initialize_ontology()
        logger.info("Ontology loaded for retrieval (full schema available)")
    except Exception as e:
        logger.warning(
            "Ontology not loaded at startup; SPARQL will use fallback context",
            error=str(e)
        )

    # Initialize retrieval orchestrator with retrieval targets
    # (retrieval_fuseki_dataset, retrieval_milvus_collection)
    retrieval_settings = config.model_copy(update={
        "fuseki_dataset": config.retrieval_fuseki_dataset,
        "milvus_collection_v2": config.retrieval_milvus_collection,
    })
    app_state["retrieval_orchestrator"] = LangGraphRetrievalOrchestrator(
        settings=retrieval_settings
    )

    logger.info("Retrieval Service started successfully on port 8002")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Retrieval Service...")
    
    # Cleanup resources
    if app_state["phoenix_tracer"]:
        app_state["phoenix_tracer"].shutdown()
    
    logger.info("Retrieval Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Contract KG - Retrieval Service",
    description="Microservice for query processing and retrieval",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "service": "Contract KG - Retrieval Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    config = get_settings()
    
    # Check dependencies
    dependencies = {
        "fuseki": "unknown",
        "milvus": "unknown",
        "phoenix": "enabled" if config.phoenix_enabled else "disabled",
    }
    
    # Try to check Fuseki
    try:
        from service_factory import get_service_factory
        factory = get_service_factory()
        sparql_store = factory.get_sparql_store()
        triple_count = sparql_store.get_triple_count()
        dependencies["fuseki"] = f"healthy ({triple_count} triples)"
    except Exception as e:
        dependencies["fuseki"] = f"unhealthy: {str(e)}"
    
    # Try to check Milvus
    try:
        vector_store = factory.get_vector_store()
        dependencies["milvus"] = "healthy"
    except Exception as e:
        dependencies["milvus"] = f"unhealthy: {str(e)}"
    
    return HealthResponse(
        status="healthy",
        service="retrieval",
        version="1.0.0",
        dependencies=dependencies
    )


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest,_: bool = Depends(verify_api_token)):
    """
    Process a natural language query.
    
    This endpoint processes a natural language query, generates SPARQL,
    performs vector search, and synthesizes an answer with sources.
    """
    orchestrator = app_state["retrieval_orchestrator"]
    
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval orchestrator not initialized"
        )
    
    try:
        logger.info(f"Processing query: {request.query}")
        
        # Run retrieval
        result = await orchestrator.process_query(
            query=request.query,
            max_results=request.max_results
        )
        
        return QueryResponse(
            query=request.query,
            answer=result.get("answer", "No answer generated"),
            sources=result.get("sources", []),
            reasoning_steps=result.get("reasoning_steps"),
            metadata=result.get("metadata", {})
        )
        
    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )


@app.get("/api/v1/search")
async def search(
    q: str,
    limit: int = 10,
    search_type: str = "hybrid",_: bool = Depends(verify_api_token)
):
    """
    Simple search endpoint for quick lookups.
    
    Args:
        q: Search query
        limit: Maximum number of results
        search_type: Type of search (hybrid, vector, sparql)
    """
    orchestrator = app_state["retrieval_orchestrator"]
    
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrieval orchestrator not initialized"
        )
    
    try:
        logger.info(f"Search query: {q} (type: {search_type})")
        
        # Simplified search
        result = await orchestrator.process_query(
            query=q,
            max_results=limit,
        )
        
        return {
            "query": q,
            "results": result.get("sources", []),
            "count": len(result.get("sources", []))
        }
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/api/v1/metrics")
async def get_metrics(_: bool = Depends(verify_api_token)):
    """Get retrieval service metrics."""
    try:
        from service_factory import get_service_factory
        factory = get_service_factory()
        sparql_store = factory.get_sparql_store()
        
        metrics = {
            "service": "retrieval",
            "fuseki_triples": sparql_store.get_triple_count(),
            "status": "healthy"
        }
        
        return metrics
    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )