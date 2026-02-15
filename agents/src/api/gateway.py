"""
API Gateway - Routes requests to appropriate microservices.

Routes:
- /api/v1/ingest/* -> Ingestion Service (port 8001)
- /api/v1/query -> Retrieval Service (port 8002)
- /api/v1/search -> Retrieval Service (port 8002)

Port: 8080
"""

from typing import Any, Dict
import httpx

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from logger import get_module_logger

logger = get_module_logger(__name__)


# Service URLs
INGESTION_SERVICE_URL = "http://ingestion-api:8001"
RETRIEVAL_SERVICE_URL = "http://retrieval-api:8002"


# Pydantic models
class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    gateway: str
    version: str
    services: Dict[str, str]


# Create FastAPI app
app = FastAPI(
    title="Contract KG - API Gateway",
    description="API Gateway for Contract Knowledge Graph microservices",
    version="1.0.0",
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
        "service": "Contract KG - API Gateway",
        "version": "1.0.0",
        "status": "running",
        "services": {
            "ingestion": f"{INGESTION_SERVICE_URL}",
            "retrieval": f"{RETRIEVAL_SERVICE_URL}"
        }
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint - checks all services."""
    services = {}
    
    # Check ingestion service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{INGESTION_SERVICE_URL}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                services["ingestion"] = "healthy"
            else:
                services["ingestion"] = f"unhealthy (status: {response.status_code})"
    except Exception as e:
        services["ingestion"] = f"unreachable: {str(e)}"
    
    # Check retrieval service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RETRIEVAL_SERVICE_URL}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                services["retrieval"] = "healthy"
            else:
                services["retrieval"] = f"unhealthy (status: {response.status_code})"
    except Exception as e:
        services["retrieval"] = f"unreachable: {str(e)}"
    
    # Overall status
    overall_status = "healthy" if all(
        "healthy" in status for status in services.values()
    ) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        gateway="running",
        version="1.0.0",
        services=services
    )


@app.api_route(
    "/api/v1/ingest/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def proxy_to_ingestion(path: str, request: Request):
    """Proxy requests to ingestion service."""
    try:
        async with httpx.AsyncClient() as client:
            # Forward request to ingestion service
            url = f"{INGESTION_SERVICE_URL}/api/v1/ingest/{path}"
            
            # Get request body if present
            body = await request.body()
            
            # Forward request
            response = await client.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                content=body,
                timeout=300.0  # 5 minutes for ingestion
            )
            
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code
            )
            
    except httpx.TimeoutException:
        logger.error(f"Timeout proxying to ingestion service: {path}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Ingestion service timeout"
        )
    except Exception as e:
        logger.error(f"Error proxying to ingestion service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ingestion service error: {str(e)}"
        )


@app.post("/api/v1/query")
async def proxy_query(request: Request):
    """Proxy query requests to retrieval service."""
    try:
        async with httpx.AsyncClient() as client:
            # Forward request to retrieval service
            url = f"{RETRIEVAL_SERVICE_URL}/api/v1/query"
            
            # Get request body
            body = await request.body()
            
            # Forward request
            response = await client.post(
                url=url,
                headers=dict(request.headers),
                content=body,
                timeout=60.0  # 1 minute for queries
            )
            
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout proxying query to retrieval service")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Query timeout"
        )
    except Exception as e:
        logger.error(f"Error proxying query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Retrieval service error: {str(e)}"
        )


@app.get("/api/v1/search")
async def proxy_search(request: Request):
    """Proxy search requests to retrieval service."""
    try:
        async with httpx.AsyncClient() as client:
            # Forward request to retrieval service
            url = f"{RETRIEVAL_SERVICE_URL}/api/v1/search"
            
            # Forward query parameters
            params = dict(request.query_params)
            
            # Forward request
            response = await client.get(
                url=url,
                params=params,
                headers=dict(request.headers),
                timeout=30.0  # 30 seconds for search
            )
            
            return JSONResponse(
                content=response.json() if response.content else {},
                status_code=response.status_code
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout proxying search to retrieval service")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Search timeout"
        )
    except Exception as e:
        logger.error(f"Error proxying search: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Retrieval service error: {str(e)}"
        )


@app.get("/api/v1/metrics")
async def get_aggregated_metrics():
    """Get aggregated metrics from all services."""
    metrics = {
        "gateway": "healthy",
        "services": {}
    }
    
    # Get ingestion metrics
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{INGESTION_SERVICE_URL}/api/v1/metrics",
                timeout=5.0
            )
            if response.status_code == 200:
                metrics["services"]["ingestion"] = response.json()
    except Exception as e:
        metrics["services"]["ingestion"] = {"error": str(e)}
    
    # Get retrieval metrics
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RETRIEVAL_SERVICE_URL}/api/v1/metrics",
                timeout=5.0
            )
            if response.status_code == 200:
                metrics["services"]["retrieval"] = response.json()
    except Exception as e:
        metrics["services"]["retrieval"] = {"error": str(e)}
    
    return metrics


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )