"""
Ingestion Service - Microservice for document ingestion and processing.

Handles:
- Document upload and processing
- Clause extraction
- Entity extraction
- RDF generation
- Vector indexing
- Ontology evolution

Port: 8001
"""

from contextlib import asynccontextmanager
from typing import Any, Dict
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import BackgroundTasks
from api.job_manager import IngestionJobManager, JobStatus, JobInfo
from pydantic import BaseModel, Field

from config import get_settings
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator
from observability.phoenix_tracer import PhoenixTracer
from ontology_manager import initialize_ontology
from logger import get_module_logger

logger = get_module_logger(__name__)


# Pydantic models
class IngestionRequest(BaseModel):
    """Request model for ingestion endpoint."""
    file_path: str = Field(..., description="Path to document file")
    override: bool = Field(False, description="Override existing document")


class IngestionResponse(BaseModel):
    """Response model for ingestion endpoint."""
    status: str
    document_id: str
    message: str
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    service: str
    version: str
    dependencies: Dict[str, str]


# Application state
app_state = {
    "ingestion_orchestrator": None,
    "phoenix_tracer": None,
}


# Initialize job manager
job_manager = IngestionJobManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("Starting Ingestion Service...")
    
    config = get_settings()
    
    # Initialize Phoenix tracing
    if config.phoenix_enabled:
        app_state["phoenix_tracer"] = PhoenixTracer()
        logger.info("Phoenix tracing enabled")
    
    # Load ontology for ingestion (needed for ontology evolution)
    try:
        initialize_ontology()
        logger.info("Ontology loaded for ingestion")
    except Exception as e:
        logger.warning("Ontology not loaded at startup", error=str(e))

    # Initialize ingestion orchestrator
    app_state["ingestion_orchestrator"] = IngestionOrchestrator()

    logger.info("Ingestion Service started successfully on port 8001")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ingestion Service...")
    
    # Cleanup resources
    if app_state["phoenix_tracer"]:
        app_state["phoenix_tracer"].shutdown()
    
    logger.info("Ingestion Service shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Contract KG - Ingestion Service",
    description="Microservice for document ingestion and processing",
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
        "service": "Contract KG - Ingestion Service",
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
        service="ingestion",
        version="1.0.0",
        dependencies=dependencies
    )


@app.post("/api/v1/ingest", response_model=IngestionResponse)
async def ingest_document(request: IngestionRequest):
    """
    Ingest a document from file path.
    
    This endpoint processes a document file, extracts clauses and entities,
    generates RDF triples, and indexes them in the knowledge graph.
    """
    orchestrator = app_state["ingestion_orchestrator"]
    
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion orchestrator not initialized"
        )
    
    try:
        logger.info(f"Ingesting document: {request.file_path}")
        
        # Run ingestion
        result = await orchestrator.ingest(
            file_path=request.file_path,
            override=request.override
        )
        
        return IngestionResponse(
            status="success",
            document_id=result.get("document_id", "unknown"),
            message="Document ingested successfully",
            metadata=result
        )
        
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.file_path}"
        )
    except Exception as e:
        logger.error(f"Ingestion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@app.post("/api/v1/ingest/upload", response_model=IngestionResponse)
async def upload_and_ingest(
    file: UploadFile = File(...),
    override: bool = False
):
    """
    Upload and ingest a document.
    
    This endpoint accepts a file upload, saves it temporarily,
    and processes it through the ingestion pipeline.
    """
    orchestrator = app_state["ingestion_orchestrator"]
    
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingestion orchestrator not initialized"
        )
    
    try:
        logger.info(f"Uploading and ingesting file: {file.filename}")
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Run ingestion
            result = await orchestrator.ingest(
                file_path=tmp_path,
                override=override
            )
            
            return IngestionResponse(
                status="success",
                document_id=result.get("document_id", "unknown"),
                message=f"File '{file.filename}' ingested successfully",
                metadata=result
            )
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Upload and ingestion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload and ingestion failed: {str(e)}"
        )


# ============================================================================
# ASYNC JOB ENDPOINTS
# ============================================================================

@app.post("/api/v1/ingest/async")
async def ingest_async(
    request: IngestionRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit an ingestion job asynchronously.
    
    Returns immediately with a job_id. Use /api/v1/ingest/status/{job_id}
    to check progress.
    
    Best for: Large batches, long-running ingestion tasks
    """
    try:
        # Create job
        job_id = job_manager.create_job(request.dict())
        
        # Add background task
        background_tasks.add_task(
            run_ingestion_job,
            job_id=job_id,
            file_path=request.file_path,
            override=request.override
        )
        
        logger.info(f"Created async ingestion job: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Ingestion job submitted successfully",
            "check_status": f"/api/v1/ingest/status/{job_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create async job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@app.get("/api/v1/ingest/status/{job_id}")
async def get_job_status(job_id: str):
    """Get status of an ingestion job."""
    job = job_manager.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    
    return {
        "job_id": job.job_id,
        "status": job.status.value,
        "progress": job.progress,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "result": job.result,
        "error": job.error
    }


@app.get("/api/v1/ingest/jobs")
async def list_jobs(limit: int = 100, status_filter: str | None = None):
    """List ingestion jobs."""
    from api.job_manager import JobStatus
    
    status_enum = None
    if status_filter:
        try:
            status_enum = JobStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    jobs = job_manager.list_jobs(limit=limit, status=status_enum)
    
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "progress": job.progress,
                "created_at": job.created_at.isoformat(),
                "input_data": job.input_data
            }
            for job in jobs
        ]
    }


@app.delete("/api/v1/ingest/job/{job_id}")
async def delete_job(job_id: str):
    """Delete an ingestion job."""
    deleted = job_manager.delete_job(job_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    
    return {"message": f"Job {job_id} deleted successfully"}


async def run_ingestion_job(job_id: str, file_path: str, override: bool = False):
    """
    Background task to run ingestion job.
    
    Supports both single files and directories.
    Updates job status and progress in database.
    """
    import os
    from pathlib import Path
    
    orchestrator = app_state.get("ingestion_orchestrator")
    
    if not orchestrator:
        job_manager.mark_failed(job_id, "Ingestion orchestrator not initialized")
        return
    
    try:
        # Mark as running
        job_manager.update_status(job_id, JobStatus.RUNNING)
        logger.info(f"Starting ingestion job {job_id}: {file_path}")
        
        path = Path(file_path)
        
        # Check if path is a directory or file
        if path.is_dir():
            # Directory: scan and process all files
            logger.info(f"Processing directory: {file_path}")
            
            # Scan directory for documents
            from agents.ingestion.directory_scanner import DirectoryScanner
            scanner = DirectoryScanner()
            files = await scanner.scan_directory(str(path))
            
            if not files:
                job_manager.mark_completed(job_id, {
                    "status": "success",
                    "message": "No files found in directory",
                    "files_processed": 0
                })
                return
            
            # Process files in batch
            items = [{"file_path": f} for f in files]
            results = await orchestrator.ingest_batch(items, max_concurrent=5)
            
            # Aggregate results
            successful = sum(1 for r in results if r.get("status") == "success")
            failed = len(results) - successful
            
            result = {
                "status": "success",
                "message": f"Processed {len(results)} files",
                "files_processed": len(results),
                "successful": successful,
                "failed": failed,
                "results": results
            }
            
        else:
            # Single file
            logger.info(f"Processing single file: {file_path}")
            result = await orchestrator.ingest(
                file_path=file_path,
                override=override
            )
        
        # Mark as completed
        job_manager.mark_completed(job_id, result)
        logger.info(f"Completed ingestion job {job_id}")
        
    except Exception as e:
        # Mark as failed
        error_msg = str(e)
        job_manager.mark_failed(job_id, error_msg)
        logger.error(f"Failed ingestion job {job_id}: {error_msg}")


@app.get("/api/v1/metrics")
async def get_metrics():
    """Get ingestion service metrics."""
    try:
        from service_factory import get_service_factory
        factory = get_service_factory()
        sparql_store = factory.get_sparql_store()
        
        metrics = {
            "service": "ingestion",
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
        port=8001,
        log_level="info"
    )