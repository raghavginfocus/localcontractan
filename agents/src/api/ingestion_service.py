

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
from datetime import datetime
import json
from typing import Any, Dict, Optional
import requests
import os
import tempfile
import asyncio

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

import ibm_boto3
from ibm_botocore.client import Config

from dotenv import load_dotenv

from fastapi import Depends
from auth import verify_api_token

load_dotenv()

logger = get_module_logger(__name__)

# job_id -> asyncio.Event; .set() requests cancellation
_cancellation_tokens: dict[str, asyncio.Event] = {}

# job_id -> checkpoint dict (what's left to process)
_job_checkpoints: dict[str, dict] = {}


# Cloudant config
CLOUDANT_URL = os.getenv("CLOUDANT_URL")
DB_NAME = os.getenv("DB_NAME")
VIEW_PATH = os.getenv("VIEW_PATH")
CLOUDANT_USERNAME = os.getenv("CLOUDANT_USERNAME")
CLOUDANT_PASSWORD = os.getenv("CLOUDANT_PASSWORD")
# Store cache file in /app/data directory where appuser has write permissions
CACHE_FILE = os.getenv("CACHE_FILE", "/app/data/cached_view.json")

# COS config — follow your existing env names
SOURCE_COS_API_KEY = os.getenv("COS_API_KEY_ID")
SOURCE_COS_INSTANCE_CRN = os.getenv("COS_INSTANCE_CRN")
SOURCE_COS_AUTH_ENDPOINT = os.getenv("COS_AUTH_ENDPOINT")
SOURCE_COS_ENDPOINT = os.getenv("COS_ENDPOINT")
SOURCE_BUCKET = os.getenv("SOURCE_BUCKET")


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

def _register_job(job_id: str) -> asyncio.Event:
    """Create and register a fresh cancellation token for a job."""
    token = asyncio.Event()
    _cancellation_tokens[job_id] = token
    return token


def _is_stop_requested(job_id: str) -> bool:
    """Return True if cancellation has been requested for this job."""
    token = _cancellation_tokens.get(job_id)
    return token is not None and token.is_set()


def _cleanup_job(job_id: str) -> None:
    """Remove cancellation token after job finishes (any terminal state)."""
    _cancellation_tokens.pop(job_id, None)
    # Intentionally keep _job_checkpoints so /resume can still read it

# -----------------------------------------------------------------------------
# Initialize and return the COS client used for source document retrieval.
#
# Returns:
#     IBM COS client instance
# -----------------------------------------------------------------------------

def _get_source_cos_client():
    return ibm_boto3.client(
        "s3",
        ibm_api_key_id=SOURCE_COS_API_KEY,
        ibm_service_instance_id=SOURCE_COS_INSTANCE_CRN,
        ibm_auth_endpoint=SOURCE_COS_AUTH_ENDPOINT,
        config=Config(signature_version="oauth"),
        endpoint_url=SOURCE_COS_ENDPOINT,
    )

def _fetch_from_cloudant() -> dict:
    url = f"{CLOUDANT_URL}/{DB_NAME}/{VIEW_PATH}"
    resp = requests.get(url, auth=(CLOUDANT_USERNAME, CLOUDANT_PASSWORD), timeout=30)
    resp.raise_for_status()
    data = resp.json()

    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)

    return data

# -----------------------------------------------------------------------------
# Fetch latest Cloudant view data and cache it locally.
#
# Args:
#     force (bool):
#         If True, refresh cache even if cached data already exists
#
# Returns:
#     Cached Cloudant view response
# -----------------------------------------------------------------------------


def fetch_and_cache_view(force: bool = False) -> dict:
    if not force and os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            content = fh.read().strip()
        if content:
            return json.loads(content)

    return _fetch_from_cloudant()

# -----------------------------------------------------------------------------
# Extract document metadata and paths from cached Cloudant view data.
#
# Expected output format:
# [
#     {
#         "_id": "...",
#         "Doc_Name": "...",
#         "Doc_Path": "..."
#     }
# ]
#
# Returns:
#     List[dict] containing document metadata
# -----------------------------------------------------------------------------


def _extract_doc_paths_from_cache() -> list[dict]:
    """
    Extract document paths from cached CloudAnt view with filtering.
    
    Filters applied:
    1. File type: Only .doc, .docx, .pdf files
    2. Doc_Type: Exclude "Assembled PDF" and "Contract Addendum"
    
    Returns:
        List of document metadata dicts with _id, Doc_Name, Doc_Path, Doc_Type
    """
    if not os.path.exists(CACHE_FILE):
        raise FileNotFoundError(f"Cache file not found: {CACHE_FILE}")

    with open(CACHE_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # Allowed file extensions (case-insensitive)
    ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf"}
    
    # Doc_Type values to exclude
    EXCLUDED_DOC_TYPES = {"Assembled PDF", "Contract Addendum"}

    docs = []
    total_docs = 0
    filtered_by_extension = 0
    filtered_by_doc_type = 0
    
    for row in data.get("rows", []):
        for item in row.get("value", []):
            total_docs += 1
            doc_path = item.get("Doc_Path")
            
            if not doc_path:
                continue
            
            # Filter 1: Check file extension
            file_ext = os.path.splitext(doc_path)[1].lower()
            if file_ext not in ALLOWED_EXTENSIONS:
                filtered_by_extension += 1
                logger.debug(
                    f"Skipping {doc_path}: unsupported file type {file_ext}. "
                    f"Only {ALLOWED_EXTENSIONS} are supported."
                )
                continue
            
            # Filter 2: Check Doc_Type
            doc_type = item.get("Doc_Type", "")
            if doc_type in EXCLUDED_DOC_TYPES:
                filtered_by_doc_type += 1
                logger.debug(
                    f"Skipping {doc_path}: excluded Doc_Type '{doc_type}'"
                )
                continue
            
            # Document passed all filters
            docs.append({
                "_id": item.get("_id"),
                "Doc_Name": item.get("Doc_Name"),
                "Doc_Path": doc_path,
                "Doc_Type": doc_type,
            })
    
    logger.info(
        f"Document filtering complete: "
        f"Total={total_docs}, "
        f"Accepted={len(docs)}, "
        f"Filtered by extension={filtered_by_extension}, "
        f"Filtered by Doc_Type={filtered_by_doc_type}"
    )
    
    return docs

# -----------------------------------------------------------------------------
# Load CloudAnt metadata for a specific document from cached view.
#
# This function searches the cached_view.json for a document matching the
# given Doc_Path and returns ALL metadata fields for that document.
#
# This is a GENERIC solution that works with ANY metadata structure - it
# returns the complete item dict without hardcoding specific field names.
#
# Args:
#     doc_path (str):
#         The Doc_Path to search for (e.g., "suppliers/contract.pdf")
#
# Returns:
#     dict: Complete metadata for the document, or empty dict if not found
#
# Example return value:
# {
#     "_id": "abc123",
#     "Doc_Name": "contract.pdf",
#     "Doc_Path": "suppliers/contract.pdf",
#     "Supplier_Name": "Acme Corp",
#     "Contract_Type": "MSA",
#     "Parent_Contract_ID": "parent_123",
#     ... (any other fields present in cached_view.json)
# }
# -----------------------------------------------------------------------------


def load_cloudant_metadata(doc_path: str) -> dict[str, Any]:
    """
    Load CloudAnt metadata for a specific document from cached view.
    
    Returns complete metadata dict for the document, or empty dict if not found.
    This is a generic solution that works with ANY metadata structure.
    """
    if not os.path.exists(CACHE_FILE):
        logger.warning(f"Cache file not found: {CACHE_FILE}")
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Search for the document in cached view
        for row in data.get("rows", []):
            for item in row.get("value", []):
                if item.get("Doc_Path") == doc_path:
                    # Return the complete item dict (all metadata fields)
                    logger.info(
                        f"Loaded CloudAnt metadata for document",
                        doc_path=doc_path,
                        metadata_fields=list(item.keys())
                    )
                    return item

        logger.warning(f"No CloudAnt metadata found for doc_path: {doc_path}")
        return {}

    except Exception as e:
        logger.error(f"Error loading CloudAnt metadata: {e}", exc_info=True)
        return {}

# -----------------------------------------------------------------------------
# Background job that refreshes Cloudant cache data and ingests documents
# into the ingestion pipeline asynchronously.
#
# Flow:
# 1. Validate ingestion orchestrator availability
# 2. Refresh cache view from Cloudant
# 3. Extract document paths from cached data
# 4. Download each file from COS
# 5. Store temporarily on local filesystem
# 6. Trigger orchestrator ingestion
# 7. Track per-document results and job progress
# 8. Update final job status (completed/failed)
#
# Args:
#     job_id (str):
#         Unique job identifier used for status/progress tracking
#
#     override (bool):
#         Whether to force re-ingestion of already indexed documents
#
#     limit (Optional[int]):
#         Optional limit on number of documents to ingest
#
# Returns:
#     None
#
# Side Effects:
#     - Updates job_manager state/progress
#     - Downloads files from COS
#     - Creates temporary files
#     - Triggers ingestion pipeline
# -----------------------------------------------------------------------------

async def run_cloudant_cache_pipeline_job(
    job_id: str,
    override: bool = False,
    limit: Optional[int] = None,
    resume_items: Optional[list] = None,
):
    orchestrator = app_state.get("ingestion_orchestrator")
    if not orchestrator:
        job_manager.mark_failed(job_id, "Ingestion orchestrator not initialized")
        return
    
    token = _register_job(job_id)

    try:
        job_manager.update_status(job_id, JobStatus.RUNNING)
        job_manager.update_progress(job_id, 1)
        # Track timing
        start_time = datetime.now()

        if resume_items is not None:
            docs = resume_items

        else: 
            logger.info("=" * 80)
            logger.info(f"📊 CLOUDANT CACHE PIPELINE STARTED")
            logger.info(f"   Job ID: {job_id}")
            logger.info(f"   Override: {override}")
            logger.info(f"   Limit: {limit if limit else 'No limit'}")
            logger.info("=" * 80)

            # Refresh cache
            logger.info("🔄 Refreshing CloudAnt cache...")
            data = fetch_and_cache_view(force=True)
            job_manager.update_progress(job_id, 15)
            logger.info("✅ CloudAnt cache refreshed successfully")

            # Extract and filter documents
            logger.info("🔍 Extracting and filtering documents...")
            docs = _extract_doc_paths_from_cache()
            original_count = len(docs)

            if limit:
                docs = docs[:limit]
                logger.info(f"📋 Limited to {limit} documents (from {original_count} total)")
            else:
                logger.info(f"📋 Processing all {original_count} documents")

        if not docs:
            logger.warning("⚠️  No documents found after filtering")
            job_manager.mark_completed(job_id, {
                "status": "success",
                "message": "Cache refreshed but no Doc_Path entries were found",
                "total_docs": 0,
                "successful": 0,
                "failed": 0,
                "results": [],
            })
            return

        # Initialize COS client
        logger.info(f"☁️  Connecting to IBM COS bucket: {SOURCE_BUCKET}")
        cos = _get_source_cos_client()
        
        total = len(docs)
        results = []
        failed = 0
        success_count = 0

        logger.info("=" * 80)
        logger.info(f"🚀 Starting document processing: {total} documents")
        logger.info("=" * 80)

        for idx, doc in enumerate(docs, start=1):
            if _is_stop_requested(job_id):
                 remaining = docs[idx - 1:]
                 checkpoint = {
                     "pipeline":         "cloudant_cache",
                     "override":         override,
                     "limit":            limit,
                     "remaining_items":  remaining,
                     "completed_so_far": results,
                     "failed_so_far":    failed,
                     "total_docs":       total,
                 }
                 _job_checkpoints[job_id] = checkpoint
                 job_manager.mark_stopped(job_id, checkpoint)
                 _cleanup_job(job_id)
                 return
            doc_path = doc["Doc_Path"]
            doc_name = doc.get("Doc_Name", os.path.basename(doc_path))
            doc_id = doc.get("_id", "unknown")
            doc_type = doc.get("Doc_Type", "Unknown")
            
            file_start_time = datetime.now()

            logger.info(f"📄 [{idx}/{total}] Processing: {doc_name}")
            logger.info(f"   Doc ID: {doc_id}")
            logger.info(f"   Doc Type: {doc_type}")
            logger.info(f"   Path: {doc_path}")
            logger.info(f"   Progress: {idx/total*100:.1f}% complete")

            try:
                # Download from COS
                logger.info(f"   ⬇️  Downloading from COS...")
                cos_obj = cos.get_object(Bucket=SOURCE_BUCKET, Key=doc_path)
                file_data = cos_obj["Body"].read()
                file_size_mb = len(file_data) / (1024 * 1024)
                logger.info(f"   📦 Downloaded: {file_size_mb:.2f} MB")

                suffix = os.path.splitext(doc_path)[1] or ".bin"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(file_data)
                    tmp_path = tmp.name

                try:
                    # Load CloudAnt metadata for this document
                    logger.info(f"   📋 Loading CloudAnt metadata...")
                    cloudant_metadata = load_cloudant_metadata(doc_path)
                    metadata_field_count = len(cloudant_metadata)
                    logger.info(f"   ✅ Loaded {metadata_field_count} metadata fields")
                    
                    # Ingest document
                    logger.info(f"   🔄 Starting ingestion...")
                    result = await orchestrator.ingest(
                        file_path=tmp_path,
                        override=override,
                        job_id=job_id,
                        cloudant_metadata=cloudant_metadata,
                    )
                    
                    # Calculate processing time
                    file_duration = (datetime.now() - file_start_time).total_seconds()
                    success_count += 1
                    
                    results.append({
                        "doc_id": doc_id,
                        "Doc_Name": doc_name,
                        "Doc_Path": doc_path,
                        "Doc_Type": doc_type,
                        "status": "success",
                        "processing_time_seconds": round(file_duration, 2),
                        "file_size_mb": round(file_size_mb, 2),
                        "metadata_fields": metadata_field_count,
                        "ingestion_result": (
                            result.model_dump(mode="json")
                            if hasattr(result, "model_dump") else result
                        ),
                    })
                    
                    # Log success
                    logger.info(f"   ✅ SUCCESS: {doc_name}")
                    logger.info(f"   Document ID: {result.document_id if hasattr(result, 'document_id') else 'N/A'}")
                    logger.info(f"   Processing time: {file_duration:.2f}s")
                    logger.info(f"   File size: {file_size_mb:.2f} MB")
                    logger.info(f"   Metadata fields: {metadata_field_count}")
                    logger.info(f"   Status: {success_count} succeeded, {failed} failed out of {idx} processed")
                    
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                        logger.info(f"   🗑️  Cleaned up temporary file")

            except Exception as exc:
                file_duration = (datetime.now() - file_start_time).total_seconds()
                failed += 1
                
                results.append({
                    "doc_id": doc_id,
                    "Doc_Name": doc_name,
                    "Doc_Path": doc_path,
                    "Doc_Type": doc_type,
                    "status": "failed",
                    "error": str(exc),
                    "processing_time_seconds": round(file_duration, 2),
                })
                
                # Log failure
                logger.error(f"   ❌ FAILED: {doc_name}")
                logger.error(f"   Error: {str(exc)}")
                logger.error(f"   Processing time: {file_duration:.2f}s")
                logger.error(f"   Status: {success_count} succeeded, {failed} failed out of {idx} processed")

# Calculate ingestion progress dynamically.
#
# First 15% of progress is reserved for:
# - Job initialization
# - Cache refresh operations
#
# Remaining 85% is distributed across document ingestion.
#
# Example:
# total = 10 docs
# idx = 5
#
# progress = 15 + (5/10 * 85)
#          = 57%
#
# max(total, 1) prevents division-by-zero errors.
# min(progress, 100) ensures progress never exceeds 100%.

            progress = 15 + int((idx / max(total, 1)) * 85)
            job_manager.update_progress(job_id, min(progress, 100))
            
            # Log progress every 10 documents
            if idx % 10 == 0 or idx == total:
                logger.info("=" * 80)
                logger.info(f"📊 PROGRESS UPDATE")
                logger.info(f"   Processed: {idx}/{total} ({idx/total*100:.1f}%)")
                logger.info(f"   Succeeded: {success_count}")
                logger.info(f"   Failed: {failed}")
                logger.info(f"   Success rate: {success_count/idx*100:.1f}%")
                logger.info("=" * 80)

        # Calculate total time
        total_duration = (datetime.now() - start_time).total_seconds()
        avg_time_per_doc = total_duration / total if total > 0 else 0
        
        logger.info("=" * 80)
        logger.info(f"🎉 CLOUDANT CACHE PIPELINE COMPLETED")
        logger.info(f"   Total documents: {total}")
        logger.info(f"   Successful: {success_count}")
        logger.info(f"   Failed: {failed}")
        logger.info(f"   Success rate: {success_count/total*100:.1f}%")
        logger.info(f"   Total time: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")
        logger.info(f"   Average time per document: {avg_time_per_doc:.2f}s")
        logger.info(f"   Throughput: {total/total_duration*60:.2f} documents/minute")
        logger.info("=" * 80)

        job_manager.mark_completed(job_id, {
            "status": "success",
            "total_docs": total,
            "successful": success_count,
            "failed": failed,
            "total_time_seconds": round(total_duration, 2),
            "avg_time_per_doc_seconds": round(avg_time_per_doc, 2),
            "throughput_docs_per_minute": round(total/total_duration*60, 2) if total_duration > 0 else 0,
            "results": results,
        })

    except Exception as exc:
        logger.error("=" * 80)
        logger.error(f"❌ CLOUDANT CACHE PIPELINE FAILED")
        logger.error(f"   Job ID: {job_id}")
        logger.error(f"   Error: {str(exc)}")
        logger.error("=" * 80)
        logger.error(f"Exception details:", exc_info=True)
        job_manager.mark_failed(job_id, str(exc))
    finally:
        _cleanup_job(job_id)


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

    try:
        fetch_and_cache_view(force=False)
    except Exception as exc:
        logger.error("Startup Cloudant fetch failed", error=str(exc))

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
async def ingest_document(request: IngestionRequest,_: bool = Depends(verify_api_token)):
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
    override: bool = False,_: bool = Depends(verify_api_token)
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
    background_tasks: BackgroundTasks,_: bool = Depends(verify_api_token)
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

# -----------------------------------------------------------------------------
# Retrieve current status and progress of an ingestion job.
#
# Used for polling-based progress tracking from UI/frontend.
#
# Path Params:
#     job_id (str):
#         Unique ingestion job identifier
#
# Returns:
#     {
#         "job_id": str,
#         "status": "queued|running|completed|failed",
#         "progress": int,
#         "result": Optional[dict]
#     }
# -----------------------------------------------------------------------------

@app.get("/api/v1/ingest/status/{job_id}")
async def get_job_status(job_id: str,_: bool = Depends(verify_api_token)):
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
async def list_jobs(limit: int = 100, status_filter: str | None = None,_: bool = Depends(verify_api_token)):
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
async def delete_job(job_id: str,_: bool = Depends(verify_api_token)):
    """Delete an ingestion job."""
    deleted = job_manager.delete_job(job_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}"
        )
    
    return {"message": f"Job {job_id} deleted successfully"}

@app.post("/api/v1/ingest/job/{job_id}/stop")
async def stop_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status not in (JobStatus.RUNNING, JobStatus.PENDING):
        raise HTTPException(
            status_code=409,
            detail=f"Job is not stoppable (current status: {job.status.value})"
        )

    token = _cancellation_tokens.get(job_id)
    if not token:
        raise HTTPException(
            status_code=409,
            detail="Job has no active cancellation token — it may have already finished."
        )

    token.set()
    job_manager.update_status(job_id, JobStatus.STOPPING)
    logger.info(f"Stop requested for job {job_id}")

    return {
        "job_id":      job_id,
        "message":     "Stop signal sent. Job will finish its current document then checkpoint.",
        "poll_status": f"/api/v1/ingest/status/{job_id}",
    }

@app.post("/api/v1/ingest/job/{job_id}/resume")
async def resume_job(job_id: str, background_tasks: BackgroundTasks):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status != JobStatus.STOPPED:
        raise HTTPException(
            status_code=409,
            detail=f"Only STOPPED jobs can be resumed (current status: {job.status.value})"
        )

    checkpoint = _job_checkpoints.get(job_id)
    if not checkpoint and isinstance(job.result, dict):
        checkpoint = job.result.get("__checkpoint__")

    if not checkpoint:
        raise HTTPException(
            status_code=422,
            detail="No checkpoint found. Only jobs stopped via /stop can be resumed."
        )

    pipeline = checkpoint.get("pipeline")
    override = checkpoint.get("override", False)

    if pipeline == "cloudant_cache":
        remaining = checkpoint.get("remaining_items", [])
        if not remaining:
            raise HTTPException(status_code=422, detail="Checkpoint has no remaining items.")

        new_job_id = job_manager.create_job({
            "source":       "cloudant_cache_pipeline_resume",
            "resumed_from": job_id,
            "override":     override,
            "remaining":    len(remaining),
        })
        background_tasks.add_task(
            run_cloudant_cache_pipeline_job,
            job_id=new_job_id,
            override=override,
            resume_items=remaining,
        )

    elif pipeline in ("minio", "directory"):
        remaining   = checkpoint.get("resume_files", [])
        source_path = checkpoint.get("file_path", "")
        if not remaining:
            raise HTTPException(status_code=422, detail="Checkpoint has no remaining files.")

        new_job_id = job_manager.create_job({
            "source":       f"{pipeline}_resume",
            "resumed_from": job_id,
            "file_path":    source_path,
            "override":     override,
            "remaining":    len(remaining),
        })
        background_tasks.add_task(
            run_ingestion_job,
            job_id=new_job_id,
            file_path=source_path,
            override=override,
            resume_files=remaining,
        )

    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown pipeline in checkpoint: '{pipeline}'"
        )

    return {
        "original_job_id": job_id,
        "new_job_id":      new_job_id,
        "status":          "pending",
        "remaining_items": len(remaining),
        "message":         "Resume job created. Original checkpoint preserved.",
        "poll_status":     f"/api/v1/ingest/status/{new_job_id}",
    }


async def run_ingestion_job(job_id: str, file_path: str, override: bool = False, resume_files: Optional[list] = None):
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
    
    token = _register_job(job_id)
    
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

            if resume_files is not None:
                local_files = resume_files
                skipped_unchanged = 0
            else:
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

            # local_files: list[str] = []
            # skipped_unchanged = 0
            # for key in doc_keys:
            #     meta = storage.get_object_metadata(key)
            #     etag = meta.get("etag", "")
            #     identity = f"{storage.bucket}:{key}:{etag}"
            #     identity_hash = registry.compute_identity_hash(identity)
            #     already, rec = registry.is_processed(content_hash=identity_hash)
            #     if already and rec and rec.status == ProcessingStatus.COMPLETED and not override:
            #         skipped_unchanged += 1
            #         continue

            #     rel = key[len(prefix_dir):] if key.startswith(prefix_dir) else Path(key).name
            #     local_path = cache_root / rel
            #     local_path.parent.mkdir(parents=True, exist_ok=True)
            #     if (not local_path.exists()) or override:
            #         local_path.write_bytes(storage.download(key))
            #     local_files.append(str(local_path))

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

            ingestion_results = []
            for idx, local_path in enumerate(local_files, start=1):
            
                if _is_stop_requested(job_id):
                    remaining = local_files[idx - 1:]
                    checkpoint = {
                        "pipeline":     "minio",
                        "file_path":    file_path,
                        "override":     override,
                        "resume_files": remaining,
                    }
                    _job_checkpoints[job_id] = checkpoint
                    job_manager.mark_stopped(job_id, checkpoint)
                    _cleanup_job(job_id)
                    return
            
                try:
                    r = await orchestrator.ingest(
                        file_path=local_path,
                        override=override,
                        job_id=job_id,
                    )
                    ingestion_results.append(r)
                except Exception as exc:
                    logger.error(f"Failed to ingest {local_path}: {exc}")
                    ingestion_results.append({"success": False, "error": str(exc)})
            
                progress = int((idx / max(len(local_files), 1)) * 100)
                job_manager.update_progress(job_id, progress)

            # ingestion_results = await orchestrator.ingest_batch(
            #     items,
            #     max_concurrent=10,
            #     progress_callback=_progress_callback,
            #     override=override,
            #     job_id=job_id,
            # )

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

            if resume_files is not None:
                files = resume_files
            else:
                scan_result = await scanner.process(str(path))
                files = [f.path for f in scan_result.discovered_files if f.category != "unsupported"]
            
                if not files:
                    job_manager.mark_completed(job_id, {
                        "status": "success",
                        "message": "No files found in directory",
                        "files_processed": 0
                    })
                    return

            # scan_result = await scanner.process(str(path))
            # files = [f.path for f in scan_result.discovered_files if f.category != "unsupported"]
            
            # if not files:
            #     job_manager.mark_completed(job_id, {
            #         "status": "success",
            #         "message": "No files found in directory",
            #         "files_processed": 0
            #     })
            #     return
            
            # Process files in batch
            items = [{"file_path": f} for f in files]

            total_docs = len(items)

            async def _dir_progress_callback(done_in_batch: int, batch_total: int) -> None:
                try:
                    percent = int((done_in_batch / max(total_docs, 1)) * 100)
                    job_manager.update_progress(job_id, percent)
                except Exception as e:
                    logger.warning("dir_progress_callback_failed", error=str(e))

            results = []
            for idx, f in enumerate(files, start=1):
            
                if _is_stop_requested(job_id):
                    remaining = files[idx - 1:]
                    checkpoint = {
                        "pipeline":     "directory",
                        "file_path":    file_path,
                        "override":     override,
                        "resume_files": remaining,
                    }
                    _job_checkpoints[job_id] = checkpoint
                    job_manager.mark_stopped(job_id, checkpoint)
                    _cleanup_job(job_id)
                    return

                try:
                    r = await orchestrator.ingest(
                        file_path=f,
                        override=override,
                        job_id=job_id,
                    )
                    results.append(r)
                except Exception as exc:
                    logger.error(f"Failed to ingest {f}: {exc}")
                    results.append({"success": False, "error": str(exc)})

                progress = int((idx / max(len(files), 1)) * 100)
                job_manager.update_progress(job_id, progress)

            # results = await orchestrator.ingest_batch(
            #     items,
            #     max_concurrent=10,
            #     progress_callback=_dir_progress_callback,
            #     job_id=job_id,
            # )
            
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
    finally:
        _cleanup_job(job_id)

@app.get("/api/v1/metrics")
async def get_metrics(_: bool = Depends(verify_api_token)):
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

# -----------------------------------------------------------------------------
# Trigger asynchronous Cloudant cache ingestion pipeline.
#
# This endpoint:
# - Refreshes Cloudant cached view data
# - Extracts document paths from cache
# - Downloads documents from COS
# - Starts asynchronous ingestion pipeline
#
# Returns immediately with a job_id for polling.
#
# Query Params:
#     override (bool):
#         Force re-ingestion of already processed documents
#
#     limit (Optional[int]):
#         Restrict number of documents processed
#
# Returns:
#     {
#         "job_id": str,
#         "status": "pending",
#         "check_status": str
#     }
#
# Use:
#     /api/v1/ingest/status/{job_id}
# to track progress and results.
# -----------------------------------------------------------------------------


@app.get("/api/v1/cloudant/cache/refresh")
async def refresh_cloudant_cache(
    background_tasks: BackgroundTasks,
    override: bool = False,
    limit: Optional[int] = None, _: bool = Depends(verify_api_token)
):
    job_id = job_manager.create_job({
        "source": "cloudant_cache_pipeline",
        "override": override,
        "limit": limit,
    })

    background_tasks.add_task(
        run_cloudant_cache_pipeline_job,
        job_id=job_id,
        override=override,
        limit=limit,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "check_status": f"/api/v1/ingest/status/{job_id}",
    }

# -----------------------------------------------------------------------------
# Retrieve current Cloudant cache metadata and status.
#
# This endpoint checks whether the local cached Cloudant
# view file exists and returns basic cache information.
#
# Returns:
#     {
#         "status": "present|missing",
#         "cache_file": str,
#         "size_bytes": int,
#         "rows": int
#     }
#
# Useful for:
# - Cache validation
# - Debugging
# - Monitoring cache freshness
# -----------------------------------------------------------------------------



@app.get("/api/v1/cloudant/cache/status")
async def cloudant_cache_status():
    if not os.path.exists(CACHE_FILE):
        return {"status": "missing", "cache_file": CACHE_FILE}

    stat = os.stat(CACHE_FILE)
    with open(CACHE_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    return {
        "status": "present",
        "cache_file": CACHE_FILE,
        "size_bytes": stat.st_size,
        "rows": len(data.get("rows", [])),
    }


@app.get("/api/v1/ingest/cloud/bulk", response_model=Dict[str, Any])
async def bulk_ingest_from_cloud_all(
    override: bool = False,_: bool = Depends(verify_api_token)
):
    """
    Download all documents from an IBM Cloud Object Storage bucket (including all nested folders) and ingest them.
    
    Args:
        override: Override existing document
        
    Returns:
        Dictionary containing bulk ingestion summary and individual file statuses
    """
    logger.info("Triggered bulk cloud ingestion for entire bucket")
    
    try:
        # Initialize the IBM COS Client using your existing environment variables
        source_cos = ibm_boto3.client(
            "s3",
            ibm_api_key_id=os.getenv("SOURCE_COS_API_KEY"),
            ibm_service_instance_id=os.getenv("SOURCE_COS_INSTANCE_CRN"),
            ibm_auth_endpoint=os.getenv("SOURCE_COS_AUTH_ENDPOINT"),
            config=Config(signature_version="oauth"),
            #config=Config(signature_version="s3v4")
            endpoint_url=os.getenv("SOURCE_COS_ENDPOINT_TEST"),
        )
        
        source_bucket = os.getenv("SOURCE_BUCKET")
        results = []
        
        # 1. First, count total files for progress tracking
        logger.info("Counting total files in bucket...")
        total_files = 0
        paginator = source_cos.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=source_bucket)
        
        for page in pages:
            if "Contents" in page:
                # Count only actual files, not folder markers
                total_files += sum(1 for obj in page["Contents"] if not obj["Key"].endswith("/"))
        
        logger.info(f"📊 BATCH INGESTION STARTED: {total_files} files to process from bucket '{source_bucket}'")
        logger.info("=" * 80)
        
        # 2. Reset paginator for actual processing
        pages = paginator.paginate(Bucket=source_bucket)
        processed_count = 0
        success_count = 0
        failed_count = 0
        start_time = datetime.now()
        
        # 3. Iterate through every page of results
        for page in pages:
            if "Contents" not in page:
                continue
                
            # 4. Iterate over every file in the current page
            for obj in page["Contents"]:
                file_key = obj["Key"]
                
                # Skip folder markers (empty objects that just represent a directory)
                if file_key.endswith("/"):
                    continue
                
                processed_count += 1
                file_start_time = datetime.now()
                
                logger.info(f"📄 [{processed_count}/{total_files}] Processing: {file_key}")
                logger.info(f"   Progress: {processed_count/total_files*100:.1f}% complete")
                
                try:
                    # Download the file object from COS
                    file_obj = source_cos.get_object(Bucket=source_bucket, Key=file_key)
                    file_data = file_obj["Body"].read()
                    
                    file_ext = os.path.splitext(file_key)[1]
                    
                    # Save securely to a temporary file in the pod
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                        tmp_file.write(file_data)
                        tmp_file_path = tmp_file.name
                        
                    try:
                        # Pass the local pod path to the existing ingestion orchestrator
                        request = IngestionRequest(file_path=tmp_file_path, override=override)
                        ingest_resp = await ingest_document(request)
                        
                        # Calculate processing time
                        file_duration = (datetime.now() - file_start_time).total_seconds()
                        
                        # Record success
                        success_count += 1
                        results.append({
                            "file": file_key,
                            "status": "success",
                            "document_id": ingest_resp.document_id,
                            "processing_time_seconds": round(file_duration, 2)
                        })
                        
                        logger.info(f"   ✅ SUCCESS: {file_key}")
                        logger.info(f"   Document ID: {ingest_resp.document_id}")
                        logger.info(f"   Processing time: {file_duration:.2f}s")
                        logger.info(f"   Status: {success_count} succeeded, {failed_count} failed out of {processed_count} processed")
                        
                    finally:
                        # Clean up the temporary file
                        if os.path.exists(tmp_file_path):
                            os.unlink(tmp_file_path)
                            logger.info(f"   🗑️  Cleaned up temporary file: {tmp_file_path}")
                            
                except Exception as file_e:
                    # Calculate processing time even for failures
                    file_duration = (datetime.now() - file_start_time).total_seconds()
                    failed_count += 1
                    
                    logger.error(f"   ❌ FAILED: {file_key}")
                    logger.error(f"   Error: {str(file_e)}")
                    logger.error(f"   Processing time: {file_duration:.2f}s")
                    logger.error(f"   Status: {success_count} succeeded, {failed_count} failed out of {processed_count} processed")
                    
                    # Record failure but allow the loop to continue to the next file
                    results.append({
                        "file": file_key,
                        "status": "failed",
                        "error": str(file_e),
                        "processing_time_seconds": round(file_duration, 2)
                    })
                
                logger.info("-" * 80)
        
        # Calculate total batch time
        total_duration = (datetime.now() - start_time).total_seconds()
        avg_time_per_file = total_duration / processed_count if processed_count > 0 else 0
        
        # Final summary
        logger.info("=" * 80)
        logger.info("🎉 BATCH INGESTION COMPLETED")
        logger.info(f"📊 SUMMARY:")
        logger.info(f"   Total files: {total_files}")
        logger.info(f"   Processed: {processed_count}")
        logger.info(f"   ✅ Succeeded: {success_count} ({success_count/processed_count*100:.1f}%)")
        logger.info(f"   ❌ Failed: {failed_count} ({failed_count/processed_count*100:.1f}%)")
        logger.info(f"   ⏱️  Total time: {total_duration:.2f}s ({total_duration/60:.1f} minutes)")
        logger.info(f"   ⚡ Average time per file: {avg_time_per_file:.2f}s")
        logger.info("=" * 80)
                    
        return {
            "message": "Bulk ingestion completed",
            "total_files": total_files,
            "total_processed": processed_count,
            "succeeded": success_count,
            "failed": failed_count,
            "success_rate": f"{success_count/processed_count*100:.1f}%" if processed_count > 0 else "0%",
            "total_time_seconds": round(total_duration, 2),
            "average_time_per_file_seconds": round(avg_time_per_file, 2),
            "results": results
        }
            
    except Exception as e:
        logger.error(f"Error pulling and ingesting from cloud: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing bulk cloud documents: {str(e)}",
        )




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info"
    )
