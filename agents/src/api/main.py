"""
FastAPI application for Contract Knowledge Graph agents.

Provides REST API endpoints for:
- Document ingestion
- Query/retrieval
- Health checks
- Metrics
"""

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import get_settings
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator
from observability.phoenix_tracer import PhoenixTracer
from ontology_manager import initialize_ontology
from logger import get_module_logger

logger = get_module_logger(__name__)


# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str = Field(..., description="Natural language query")
    max_results: int = Field(10, ge=1, le=100, description="Maximum number of results")
    include_reasoning: bool = Field(True, description="Include reasoning steps")


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    query: str
    answer: str
    sources: List[Dict[str, Any]]
    reasoning_steps: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any]


class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint."""
    file_path: str = Field(..., description="Path to document file")
    override: bool = Field(False, description="Override existing document")


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint."""
    success: bool
    document_id: str
    message: str
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    version: str
    services: Dict[str, str]


# Global state
app_state = {
    "ingestion_orchestrator": None,
    "retrieval_orchestrator": None,
    "phoenix_tracer": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Contract KG API...")
    
    config = get_settings()
    
    # Initialize Phoenix tracing
    if config.phoenix_enabled:
        app_state["phoenix_tracer"] = PhoenixTracer()
        logger.info("Phoenix tracing enabled")
    
    # Load ontology so retrieval (SPARQL generator) knows full schema
    try:
        initialize_ontology()
        logger.info("Ontology loaded for retrieval (full schema available)")
    except Exception as e:
        logger.warning("Ontology not loaded at startup; SPARQL will use fallback context", error=str(e))

    # Initialize orchestrators
    app_state["ingestion_orchestrator"] = IngestionOrchestrator()
    app_state["retrieval_orchestrator"] = LangGraphRetrievalOrchestrator()

    logger.info("Contract KG API started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Contract KG API...")
    
    # Cleanup resources
    if app_state["phoenix_tracer"]:
        app_state["phoenix_tracer"].shutdown()
    
    logger.info("Contract KG API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Contract Knowledge Graph API",
    description="REST API for contract analysis using semantic knowledge graphs and RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint."""
    return {
        "message": "Contract Knowledge Graph API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    config = get_settings()
    
    # Check service connectivity
    services = {
        "fuseki": "unknown",
        "milvus": "unknown",
        "phoenix": "enabled" if config.phoenix_enabled else "disabled",
    }
    
    # TODO: Add actual health checks for services
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services=services,
    )


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process a natural language query against the knowledge graph.
    
    Args:
        request: Query request with query text and options
        
    Returns:
        Query response with answer, sources, and reasoning
    """
    try:
        logger.info(f"Processing query: {request.query}")
        
        retrieval_orchestrator = app_state["retrieval_orchestrator"]
        if not retrieval_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Retrieval service not initialized",
            )
        
        # Process query
        result = await retrieval_orchestrator.process_query(
            query=request.query,
            max_results=request.max_results,
        )
        
        # Format response
        response = QueryResponse(
            query=request.query,
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
            reasoning_steps=result.get("reasoning_steps") if request.include_reasoning else None,
            metadata={
                "processing_time": result.get("processing_time", 0),
                "num_sources": len(result.get("sources", [])),
            },
        )
        
        logger.info(f"Query processed successfully: {request.query}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}",
        )


@app.post("/api/v1/ingest", response_model=IngestionResponse)
async def ingest_document(request: IngestionRequest):
    """
    Ingest a document into the knowledge graph.
    
    Args:
        request: Ingestion request with file path and options
        
    Returns:
        Ingestion response with success status and metadata
    """
    try:
        logger.info(f"Ingesting document: {request.file_path}")
        
        ingestion_orchestrator = app_state["ingestion_orchestrator"]
        if not ingestion_orchestrator:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ingestion service not initialized",
            )
        
        # Process document
        result = await ingestion_orchestrator.process_document(
            file_path=request.file_path,
            override=request.override,
        )
        
        # Format response
        response = IngestionResponse(
            success=result.get("success", False),
            document_id=result.get("document_id", ""),
            message=result.get("message", ""),
            metadata={
                "processing_time": result.get("processing_time", 0),
                "num_clauses": result.get("num_clauses", 0),
                "num_entities": result.get("num_entities", 0),
            },
        )
        
        logger.info(f"Document ingested successfully: {request.file_path}")
        return response
        
    except Exception as e:
        logger.error(f"Error ingesting document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error ingesting document: {str(e)}",
        )


@app.post("/api/v1/ingest/upload", response_model=IngestionResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    override: bool = False,
):
    """
    Upload and ingest a document.
    
    Args:
        file: Uploaded file
        override: Override existing document
        
    Returns:
        Ingestion response with success status and metadata
    """
    try:
        logger.info(f"Uploading and ingesting file: {file.filename}")
        
        # Save uploaded file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Ingest the file
            request = IngestionRequest(file_path=tmp_file_path, override=override)
            response = await ingest_document(request)
            return response
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
        
    except Exception as e:
        logger.error(f"Error uploading and ingesting file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading and ingesting file: {str(e)}",
        )


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get system metrics."""
    try:
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


