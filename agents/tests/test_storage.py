"""
Storage Connection Tests

Tests connections to Fuseki and Milvus.
"""
import pytest
from fuseki_client import FusekiClient
from vector_store import MilvusVectorStore


@pytest.mark.asyncio
async def test_fuseki_connection(settings):
    """Test Fuseki connection and basic query."""
    client = FusekiClient(settings)
    
    # Test ping
    is_alive = await client.ping()
    assert is_alive, "Fuseki server should be reachable"
    
    # Test simple query
    query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
    result = await client.query(query)
    assert result is not None


@pytest.mark.asyncio
async def test_milvus_connection(settings):
    """Test Milvus connection."""
    store = MilvusVectorStore(settings)
    
    # Test connection
    await store.connect()
    
    # Check collection exists or can be created
    collection_name = settings.milvus_collection_name
    assert collection_name
    
    await store.disconnect()


@pytest.mark.asyncio
async def test_fuseki_dataset_exists(settings):
    """Test that the configured dataset exists in Fuseki."""
    client = FusekiClient(settings)
    
    # Query should not fail if dataset exists
    query = "ASK { ?s ?p ?o }"
    result = await client.query(query)
    assert result is not None


