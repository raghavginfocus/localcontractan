# Vector Store API Reference

API documentation for vector storage abstraction layer.

## VectorStore (Base Class)

Abstract base class for vector store implementations.

### Class Definition

```python
from storage.vector.base import VectorStore

class VectorStore(ABC):
    """
    Abstract base class for vector stores.
    
    Provides a unified interface for storing and searching
    vector embeddings regardless of the underlying implementation.
    """
```

### Abstract Methods

#### search

```python
@abstractmethod
def search(
    self,
    query_text: str,
    collection_name: str,
    top_k: int = 10,
    filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]
```

Search for similar vectors.

**Parameters:**

- `query_text` (str): Query text to embed and search
- `collection_name` (str): Collection to search in
- `top_k` (int): Number of results to return
- `filters` (dict, optional): Metadata filters

**Returns:**

- `list[dict]`: Search results with scores

#### insert

```python
@abstractmethod
def insert(
    self,
    texts: list[str],
    collection_name: str,
    metadata: list[dict[str, Any]] | None = None
) -> list[str]
```

Insert text embeddings.

**Parameters:**

- `texts` (list): Texts to embed and insert
- `collection_name` (str): Target collection
- `metadata` (list, optional): Metadata for each text

**Returns:**

- `list[str]`: Inserted vector IDs

## MilvusStore

Milvus implementation of VectorStore.

### Class Definition

```python
from storage.vector.milvus_store import MilvusStore

class MilvusStore(VectorStore):
    """
    Milvus vector store implementation.
    
    Provides high-performance vector similarity search with
    lazy loading, connection pooling, and batch operations.
    """
```

### Constructor

```python
def __init__(
    self,
    host: str = "localhost",
    port: int = 19530,
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    dimension: int = 384,
    lazy_load: bool = True,
    pool_size: int = 10
)
```

**Parameters:**

- `host` (str): Milvus server host
- `port` (int): Milvus server port
- `embedding_model` (str): Sentence transformer model
- `dimension` (int): Embedding dimensions
- `lazy_load` (bool): Lazy load embedding model
- `pool_size` (int): Connection pool size

**Example:**

```python
store = MilvusStore(
    host="localhost",
    port=19530,
    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    lazy_load=True
)
```

### Methods

#### search

```python
def search(
    self,
    query_text: str,
    collection_name: str = "contract_clauses",
    top_k: int = 10,
    filters: dict[str, Any] | None = None
) -> list[dict[str, Any]]
```

Search for similar vectors.

**Example:**

```python
results = store.search(
    query_text="data protection requirements",
    collection_name="contract_clauses",
    top_k=10,
    filters={"document_id": {"$in": ["ABC123", "XYZ789"]}}
)

for result in results:
    print(f"Score: {result['score']}")
    print(f"Text: {result['text']}")
    print(f"Metadata: {result['metadata']}")
```

#### insert

```python
def insert(
    self,
    texts: list[str],
    collection_name: str = "contract_clauses",
    metadata: list[dict[str, Any]] | None = None
) -> list[str]
```

Insert text embeddings.

**Example:**

```python
texts = [
    "Either party may terminate with 30 days notice",
    "Payment due within 30 days of invoice"
]

metadata = [
    {"document_id": "ABC123", "clause_type": "termination"},
    {"document_id": "ABC123", "clause_type": "payment"}
]

ids = store.insert(
    texts=texts,
    collection_name="contract_clauses",
    metadata=metadata
)

print(f"Inserted {len(ids)} vectors")
```

#### batch_insert

```python
def batch_insert(
    self,
    texts: list[str],
    collection_name: str,
    metadata: list[dict[str, Any]] | None = None,
    batch_size: int = 100
) -> list[str]
```

Insert vectors in batches for efficiency.

**Parameters:**

- `texts` (list): Texts to insert
- `collection_name` (str): Target collection
- `metadata` (list, optional): Metadata for each text
- `batch_size` (int): Vectors per batch

**Returns:**

- `list[str]`: Inserted vector IDs

**Example:**

```python
# Insert 1000 clauses in batches of 100
ids = store.batch_insert(
    texts=clause_texts,
    collection_name="contract_clauses",
    metadata=clause_metadata,
    batch_size=100
)

print(f"Inserted {len(ids)} vectors in batches")
```

#### create_collection

```python
def create_collection(
    self,
    collection_name: str,
    dimension: int | None = None,
    metric_type: str = "L2"
) -> bool
```

Create a new collection.

**Parameters:**

- `collection_name` (str): Collection name
- `dimension` (int, optional): Vector dimensions
- `metric_type` (str): Distance metric (L2, IP, COSINE)

**Returns:**

- `bool`: Success status

**Example:**

```python
success = store.create_collection(
    collection_name="contract_clauses",
    dimension=384,
    metric_type="COSINE"
)

print(f"Collection created: {success}")
```

#### delete_collection

```python
def delete_collection(
    self,
    collection_name: str
) -> bool
```

Delete a collection.

**Example:**

```python
success = store.delete_collection("old_collection")
print(f"Collection deleted: {success}")
```

#### get_collection_stats

```python
def get_collection_stats(
    self,
    collection_name: str
) -> dict[str, Any]
```

Get collection statistics.

**Returns:**

- `dict`: Statistics including vector count, dimension

**Example:**

```python
stats = store.get_collection_stats("contract_clauses")

print(f"Vector count: {stats['count']}")
print(f"Dimension: {stats['dimension']}")
print(f"Index type: {stats['index_type']}")
```

## Embedding Models

### Lazy Loading

Embedding models are loaded on-demand to save memory:

```python
# Model not loaded yet
store = MilvusStore(lazy_load=True)

# Model loaded on first search/insert
results = store.search("query text")  # +2-3s first time
results = store.search("another query")  # Fast subsequent calls
```

**Benefits:**
- **Faster startup:** 2-5 seconds saved
- **Memory savings:** 500MB-1GB until first use
- **Resource efficiency:** Only load when needed

### Supported Models

| Model | Dimensions | Speed | Quality |
|-------|-----------|-------|---------|
| all-MiniLM-L6-v2 | 384 | Fast | Good |
| all-mpnet-base-v2 | 768 | Medium | Better |
| all-MiniLM-L12-v2 | 384 | Fast | Good |

**Example:**

```python
# Use different model
store = MilvusStore(
    embedding_model="sentence-transformers/all-mpnet-base-v2",
    dimension=768
)
```

## Search Parameters

### Metric Types

```python
# L2 (Euclidean distance)
store.create_collection(
    collection_name="clauses",
    metric_type="L2"
)

# Inner Product
store.create_collection(
    collection_name="clauses",
    metric_type="IP"
)

# Cosine Similarity
store.create_collection(
    collection_name="clauses",
    metric_type="COSINE"
)
```

### Search Parameters

```python
results = store.search(
    query_text="data protection",
    collection_name="contract_clauses",
    top_k=10,
    filters={
        "document_id": {"$in": ["ABC123", "XYZ789"]},
        "clause_type": {"$eq": "termination"}
    }
)
```

**Filter Operators:**
- `$eq` - Equal to
- `$ne` - Not equal to
- `$in` - In list
- `$nin` - Not in list
- `$gt` - Greater than
- `$gte` - Greater than or equal
- `$lt` - Less than
- `$lte` - Less than or equal

## Index Configuration

### Index Types

```python
# IVF_FLAT - Good balance
store.create_index(
    collection_name="clauses",
    index_type="IVF_FLAT",
    params={"nlist": 128}
)

# HNSW - Best quality
store.create_index(
    collection_name="clauses",
    index_type="HNSW",
    params={"M": 16, "efConstruction": 200}
)

# IVF_SQ8 - Memory efficient
store.create_index(
    collection_name="clauses",
    index_type="IVF_SQ8",
    params={"nlist": 128}
)
```

### Index Parameters

| Index Type | Parameters | Use Case |
|-----------|-----------|----------|
| IVF_FLAT | nlist | Balanced performance |
| HNSW | M, efConstruction | Best quality |
| IVF_SQ8 | nlist | Memory constrained |
| IVF_PQ | nlist, m | Large datasets |

## Connection Pooling

Efficient connection management:

```python
store = MilvusStore(
    host="localhost",
    port=19530,
    pool_size=10,  # Number of connections
    pool_timeout=30  # Connection timeout
)
```

**Benefits:**
- **Reduced latency:** Reuse connections
- **Higher throughput:** Parallel operations
- **Resource efficiency:** Controlled connections

## Best Practices

### 1. Use Appropriate Batch Sizes

```python
# ❌ Insert one at a time
for text in texts:
    store.insert([text], collection_name)

# ✅ Batch insert
store.batch_insert(
    texts=texts,
    collection_name=collection_name,
    batch_size=100
)
```

### 2. Filter Before Search

```python
# ✅ Filter to reduce search space
results = store.search(
    query_text="termination clause",
    filters={"document_id": {"$in": relevant_docs}},
    top_k=10
)
```

### 3. Choose Appropriate top_k

```python
# ❌ Too many results
results = store.search(query, top_k=1000)  # Slow

# ✅ Reasonable limit
results = store.search(query, top_k=10)  # Fast
```

### 4. Monitor Collection Size

```python
stats = store.get_collection_stats("contract_clauses")

if stats['count'] > 1000000:
    # Consider partitioning or archiving
    logger.warning("Large collection, consider optimization")
```

### 5. Use Lazy Loading

```python
# ✅ Enable lazy loading for faster startup
store = MilvusStore(lazy_load=True)

# Model loads on first use
results = store.search("query")
```

## Performance Metrics

### Search Performance

| Collection Size | Search Time | Memory |
|----------------|-------------|--------|
| 10K vectors | 50ms | 100MB |
| 100K vectors | 100ms | 500MB |
| 1M vectors | 200ms | 2GB |

### Batch Insert Performance

| Batch Size | Throughput | Latency |
|-----------|-----------|---------|
| 10 | 100/s | 100ms |
| 100 | 500/s | 200ms |
| 1000 | 1000/s | 1000ms |

## Troubleshooting

### Slow Searches

**Problem:** Searches taking >1 second

**Solutions:**
1. Check collection size
2. Optimize index parameters
3. Reduce top_k value
4. Use filters to narrow search

### High Memory Usage

**Problem:** Excessive memory consumption

**Solutions:**
1. Enable lazy loading
2. Use memory-efficient index (IVF_SQ8)
3. Reduce batch sizes
4. Archive old data

### Connection Errors

**Problem:** Connection timeouts or failures

**Solutions:**
1. Check Milvus server status
2. Increase pool timeout
3. Verify network connectivity
4. Check connection pool size

## See Also

- [SPARQL Store API](../api/storage/sparql.md)
- [Hybrid RAG Architecture](../../architecture/hybrid-rag.md)
- [Performance Optimizations](../../performance/optimizations.md)