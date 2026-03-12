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
            document_id=getattr(result, "document_id", "unknown"),
            message="Document ingested successfully",
            metadata=result.model_dump(mode="json") if hasattr(result, "model_dump") else result,
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
                document_id=getattr(result, "document_id", "unknown"),
                message=f"File '{file.filename}' ingested successfully",
                metadata=result.model_dump(mode="json") if hasattr(result, "model_dump") else result,
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
        is_minio_prefix = file_path.startswith("minio://")
        
        # Check if path is a directory or file
        if is_minio_prefix:
            # MinIO prefix ingestion (Docling pipeline only)
            from config import get_settings
            from storage.object_storage import get_object_storage_from_config
            from document_registry import DocumentRegistry, ProcessingStatus
            import json

            settings = get_settings()
            if settings.ingestion_source != "docling":
                raise ValueError(
                    "minio:// ingestion requires INGESTION_SOURCE=docling"
                )

            storage = get_object_storage_from_config()
            if storage is None:
                raise ValueError(
                    "Object storage is not configured; cannot read minio:// inputs"
                )

            # Example: minio://input/examples
            # We treat everything after scheme as object key prefix.
            prefix = file_path[len("minio://") :].lstrip("/")
            is_single_key = prefix and not prefix.endswith("/")
            if is_single_key:
                # Treat as a single object key (file) rather than a "directory prefix"
                doc_keys = [prefix]
                # For caching and reverse-mapping, we need a directory-like prefix
                # that ends with "/".
                prefix_dir = str(Path(prefix).parent).rstrip("/") + "/"
            else:
                if prefix and not prefix.endswith("/"):
                    prefix = prefix + "/"
                prefix_dir = prefix

            logger.info(
                "Processing MinIO prefix recursively",
                prefix=prefix,
            )

            if not is_single_key:
                keys = storage.list_objects(prefix)
                doc_keys = [
                    k
                    for k in keys
                    if k.lower().endswith((".pdf", ".docx", ".doc", ".pptx"))
                ]

            if not doc_keys:
                job_manager.mark_completed(job_id, {
                    "status": "success",
                    "message": "No documents found under MinIO prefix",
                    "files_processed": 0,
                    "prefix": prefix,
                })
                return

            registry = DocumentRegistry(
                backend=settings.document_registry_backend,
                redis_url=settings.document_registry_redis_url,
                settings=settings,
            )

            # Write initial manifest for this job to object storage so we have a
            # durable record of which keys were discovered.
            manifest_prefix = "ingestion_manifests"
            manifest_key = f"{manifest_prefix}/{job_id}.json"
            job = job_manager.get_job(job_id)
            created_at = job.created_at.isoformat() if job and getattr(job, "created_at", None) else None
            manifest = {
                "job_id": job_id,
                "prefix": prefix,
                "created_at": created_at,
                "items": [
                    {"key": k, "status": "discovered"}
                    for k in doc_keys
                ],
            }
            try:
                storage.upload(
                    key=manifest_key,
                    data=json.dumps(manifest, indent=2).encode("utf-8"),
                    content_type="application/json",
                )
            except Exception as e:
                logger.warning(
                    "minio_manifest_write_failed",
                    error=str(e),
                    key=manifest_key,
                )

            # Download to a local cache so downstream agents can read as files.
            cache_root = Path("/app/data/minio_input_cache") / prefix_dir.rstrip("/")
            cache_root.mkdir(parents=True, exist_ok=True)

            local_files: list[str] = []
            skipped_unchanged = 0
            for key in doc_keys:
                meta = storage.get_object_metadata(key)
                etag = meta.get("etag", "")
                identity = f"{storage.bucket}:{key}:{etag}"
                identity_hash = registry.compute_identity_hash(identity)
                already, rec = registry.is_processed(content_hash=identity_hash)
                if already and rec and rec.status == ProcessingStatus.COMPLETED and not override:
                    skipped_unchanged += 1
                    continue

                rel = key[len(prefix_dir):] if key.startswith(prefix_dir) else Path(key).name
                local_path = cache_root / rel
                local_path.parent.mkdir(parents=True, exist_ok=True)
                if (not local_path.exists()) or override:
                    local_path.write_bytes(storage.download(key))
                local_files.append(str(local_path))

            if not local_files:
                job_manager.mark_completed(job_id, {
                    "status": "success",
                    "message": "All documents under prefix already processed (etag unchanged)",
                    "files_processed": 0,
                    "prefix": prefix,
                    "skipped_unchanged": skipped_unchanged,
                })
                # Update manifest to mark all items as skipped_unchanged
                try:
                    manifest["items"] = [
                        {
                            "key": k,
                            "status": "skipped_unchanged",
                        }
                        for k in doc_keys
                    ]
                    storage.upload(
                        key=manifest_key,
                        data=json.dumps(manifest, indent=2).encode("utf-8"),
                        content_type="application/json",
                    )
                except Exception as e:
                    logger.warning(
                        "minio_manifest_update_failed",
                        error=str(e),
                        key=manifest_key,
                    )
                return

            items = [{"file_path": f} for f in local_files]

            # Progress callback: incorporate skipped_unchanged so progress reflects
            # both already-processed docs and new ones.
            total_docs = len(doc_keys)
            base_done = skipped_unchanged

            async def _progress_callback(done_in_batch: int, batch_total: int) -> None:
                try:
                    total_done = base_done + done_in_batch
                    percent = int((total_done / max(total_docs, 1)) * 100)
                    job_manager.update_progress(job_id, percent)
                except Exception as e:
                    logger.warning("progress_callback_failed", error=str(e))

            ingestion_results = await orchestrator.ingest_batch(
                items,
                max_concurrent=5,
                progress_callback=_progress_callback,
                override=override,
                job_id=job_id,
            )

            # Register completion by (key, etag) identity so future runs can skip
            # without downloading.
            # Note: this is best-effort; failures here shouldn't fail the whole job.
            try:
                # Map local cache path back to MinIO key
                cache_prefix = str(cache_root) + "/"
                item_status_by_key: dict[str, str] = {}
                for r, local_path in zip(ingestion_results, local_files):
                    rel = local_path.replace(cache_prefix, "")
                    key = prefix_dir + rel
                    meta = storage.get_object_metadata(key)
                    etag = meta.get("etag", "")
                    identity = f"{storage.bucket}:{key}:{etag}"
                    identity_hash = registry.compute_identity_hash(identity)
                    doc_id = getattr(r, "document_id", None) or getattr(r, "get", lambda _k, _d=None: None)("document_id") or "unknown"
                    ok = getattr(r, "success", None)
                    status = ProcessingStatus.COMPLETED if ok else ProcessingStatus.FAILED
                    item_status_by_key[key] = status.value
                    registry.register_by_hash(
                        content_hash=identity_hash,
                        filename=Path(local_path).name,
                        document_id=str(doc_id),
                        status=status,
                        metadata={
                            "minio_key": key,
                            "etag": etag,
                            "size": meta.get("size", ""),
                            "last_modified": meta.get("last_modified", ""),
                            "prefix": prefix,
                        },
                    )
                # Update manifest with per-key status
                try:
                    manifest["items"] = [
                        {
                            "key": k,
                            "status": item_status_by_key.get(k, "skipped_unchanged")
                            if k in item_status_by_key
                            else "skipped_unchanged",
                        }
                        for k in doc_keys
                    ]
                    storage.upload(
                        key=manifest_key,
                        data=json.dumps(manifest, indent=2).encode("utf-8"),
                        content_type="application/json",
                    )
                except Exception as e:
                    logger.warning(
                        "minio_manifest_update_failed",
                        error=str(e),
                        key=manifest_key,
                    )
            except Exception as _e:
                logger.warning("minio_registry_update_failed", error=str(_e))

            result = {
                "status": "success",
                "message": f"Processed {len(ingestion_results)} files from MinIO",
                "files_processed": len(ingestion_results),
                "prefix": prefix,
                "skipped_unchanged": skipped_unchanged,
                "results": [
                    r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                    for r in ingestion_results
                ],
            }

        elif path.is_dir():
            # Directory: scan and process all files
            logger.info(f"Processing directory: {file_path}")
            
            # Scan directory for documents
            from agents.ingestion.directory_scanner import DirectoryScannerAgent
            scanner = DirectoryScannerAgent()
            scan_result = await scanner.process(str(path))
            files = [f.path for f in scan_result.discovered_files if f.category != "unsupported"]
            
            if not files:
                job_manager.mark_completed(job_id, {
                    "status": "success",
                    "message": "No files found in directory",
                    "files_processed": 0
                })
                return
            
            # Process files in batch
            items = [{"file_path": f} for f in files]

            total_docs = len(items)

            async def _dir_progress_callback(done_in_batch: int, batch_total: int) -> None:
                try:
                    percent = int((done_in_batch / max(total_docs, 1)) * 100)
                    job_manager.update_progress(job_id, percent)
                except Exception as e:
                    logger.warning("dir_progress_callback_failed", error=str(e))

            results = await orchestrator.ingest_batch(
                items,
                max_concurrent=5,
                progress_callback=_dir_progress_callback,
                job_id=job_id,
            )
            
            # Aggregate results (results are IngestionResult objects)
            successful = sum(
                1 for r in results
                if getattr(r, "success", r.get("success", False))
            )
            failed = len(results) - successful
            results_serializable = [
                r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                for r in results
            ]
            result = {
                "status": "success",
                "message": f"Processed {len(results)} files",
                "files_processed": len(results),
                "successful": successful,
                "failed": failed,
                "results": results_serializable,
            }
            
        else:
            # Single file
            logger.info(f"Processing single file: {file_path}")
            ingestion_result = await orchestrator.ingest(
                file_path=file_path,
                override=override,
                job_id=job_id,
            )
            # Convert IngestionResult to JSON-serializable dict (datetime -> str)
            result = (
                ingestion_result.model_dump(mode="json")
                if hasattr(ingestion_result, "model_dump")
                else ingestion_result
            )
        # Mark as completed (result must be JSON-serializable)
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