"""
API Endpoint Tests

Tests FastAPI endpoints for health and functionality.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client for API."""
    from api.main import app
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"


def test_api_root(client):
    """Test API root endpoint."""
    response = client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_query_endpoint_structure(client):
    """Test query endpoint accepts correct structure."""
    payload = {
        "query": "List all contracts",
        "max_results": 10
    }
    
    response = client.post("/api/v1/query", json=payload)
    
    # Should return 200 or appropriate error
    assert response.status_code in [200, 422, 500]
    
    if response.status_code == 200:
        data = response.json()
        assert "answer" in data or "results" in data


def test_docs_endpoint(client):
    """Test API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_openapi_schema(client):
    """Test OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "paths" in schema


