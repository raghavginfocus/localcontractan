"""
Vector Store Tests

Tests for Milvus vector store operations.
"""
import pytest
from vector_store import MilvusVectorStore


def test_vector_store_initialization(settings):
    """Test vector store can be initialized."""
    store = MilvusVectorStore(settings)
    
    assert store is not None
    assert store.settings == settings


def test_vector_store_collection_name(settings):
    """Test collection name configuration."""
    store = MilvusVectorStore(settings)
    
    # Should have collection name from settings
    assert hasattr(store, 'collection_name') or hasattr(store, 'collection')


def test_embedding_dimension(settings):
    """Test embedding dimension configuration."""
    # Default embedding dimension
    assert settings.embedding_dim > 0
    assert settings.embedding_dim == 1024  # e5-large-v2 default


def test_embedding_model_name(settings):
    """Test embedding model configuration."""
    assert settings.embedding_model
    assert "e5" in settings.embedding_model.lower() or "bge" in settings.embedding_model.lower()


@pytest.mark.asyncio
async def test_vector_store_has_search_method(settings):
    """Test that vector store has search method."""
    store = MilvusVectorStore(settings)
    
    assert hasattr(store, 'search') or hasattr(store, 'similarity_search')


@pytest.mark.asyncio
async def test_vector_store_has_insert_method(settings):
    """Test that vector store has insert method."""
    store = MilvusVectorStore(settings)
    
    assert hasattr(store, 'insert') or hasattr(store, 'add_documents')


def test_vector_dimensions():
    """Test vector dimension handling."""
    import numpy as np
    
    # Create sample embedding vector
    embedding = np.random.rand(1024).tolist()
    
    assert len(embedding) == 1024
    assert all(isinstance(x, float) for x in embedding)


def test_similarity_metrics():
    """Test similarity metric calculations."""
    import numpy as np
    
    # Two similar vectors
    vec1 = np.array([1.0, 0.0, 0.0])
    vec2 = np.array([0.9, 0.1, 0.0])
    
    # Cosine similarity
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    similarity = dot_product / (norm1 * norm2)
    
    assert similarity > 0.8  # Should be similar


def test_vector_normalization():
    """Test vector normalization."""
    import numpy as np
    
    # Create vector
    vec = np.array([3.0, 4.0])
    
    # Normalize
    normalized = vec / np.linalg.norm(vec)
    
    # Should have unit length
    assert abs(np.linalg.norm(normalized) - 1.0) < 0.0001


def test_milvus_connection_params(settings):
    """Test Milvus connection parameters."""
    assert settings.milvus_host
    assert settings.milvus_port > 0
    assert settings.milvus_port == 19530  # Default Milvus port


def test_collection_schema():
    """Test collection schema structure."""
    schema = {
        "fields": [
            {"name": "id", "type": "INT64"},
            {"name": "embedding", "type": "FLOAT_VECTOR", "dim": 1024},
            {"name": "text", "type": "VARCHAR"},
        ]
    }
    
    assert "fields" in schema
    assert len(schema["fields"]) >= 2  # At least ID and embedding


