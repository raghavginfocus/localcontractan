# Vector Store API Reference

Comprehensive API documentation for Milvus vector store and semantic search operations.

## Overview

The Vector Store module provides high-performance semantic search over contract clauses using Milvus vector database and sentence transformers. It enables similarity-based retrieval, metadata filtering, and RDF knowledge graph integration.

**Key Features:**
- Semantic similarity search with cosine distance
- Sentence transformer embeddings (384-768 dimensions)
- Metadata filtering (clause type, contract, document)
- RDF URI linking for hybrid RAG
- Batch insertion for efficiency
- Lazy loading for memory optimization
- Connection pooling for high throughput

---

## MilvusVectorStore

Main client for interacting with Milvus vector database.

### Class Definition

```python
from vector_store import MilvusVectorStore

class MilvusVectorStore:
    """
    Milvus-based vector store for contract clause embeddings.
    
    Features:
    - Semantic search over clause text
    - Metadata filtering (clause type, contract, etc.)
    - Batch insertion for efficiency
    - Automatic schema creation
    - RDF URI linking for knowledge graph integration
    """
```

### Constructor

```python
def __init__(
    self,
    settings: Settings | None = None
)
```

Initialize the Milvus vector store with configuration settings.

**Parameters:**

- **settings** : `Settings | None`, default=`None`
  - Configuration settings object. If None, uses default settings from environment.
  - Contains Milvus connection, embedding model, and collection configuration.

**Attributes:**

- **collection_name** : `str`
  - Name of the Milvus collection (default: "contract_clauses")
  
- **embedding_dim** : `int`
  - Dimension of embedding vectors (384 or 768)
  
- **embedding_model** : `SentenceTransformer`
  - Sentence transformer model for text encoding
  
- **collection** : `Collection`
  - Milvus collection object for operations

**Schema Fields:**
- `id` (VARCHAR, 128): Primary key
- `clause_id` (VARCHAR, 128): Clause identifier
- `contract_id` (VARCHAR, 128): Parent contract identifier
- `clause_type` (VARCHAR, 64): Type of clause
- `text` (VARCHAR, 65535): Clause text content
- `rdf_uri` (VARCHAR, 512): RDF URI in knowledge graph
- `graph_uri` (VARCHAR, 512): Named graph URI
- `embedding` (FLOAT_VECTOR, 384/768): Semantic embedding

**Example:**

```python
from vector_store import MilvusVectorStore
from config import get_settings

# Use default settings
store = MilvusVectorStore()

# Use custom settings
settings = get_settings()
settings.milvus_host = "localhost"
settings.milvus_port = 19530
settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
settings.embedding_dim = 384

store = MilvusVectorStore(settings=settings)

print(f"Collection: {store.collection_name}")
print(f"Embedding dimension: {store.embedding_dim}")
```

**Performance:**
- Initialization time: 2-5 seconds (model loading)
- Memory footprint: 500MB-1GB (embedding model)
- With lazy loading: ~50ms initialization, model loads on first use

---

## Insertion Operations

### add_clause

```python
def add_clause(
    self,
    clause_id: str,
    text: str,
    contract_id: str = "",
    clause_type: str = "",
    rdf_uri: str = "",
    graph_uri: str = ""
) -> None
```

Add a single clause to the vector store with RDF linking.

**Parameters:**

- **clause_id** : `str`
  - Unique identifier for the clause
  - Used for retrieval and updates
  
- **text** : `str`
  - Clause text content to embed
  - Automatically truncated to 65,000 characters if longer
  
- **contract_id** : `str`, default=`""`
  - Parent contract identifier
  - Used for filtering searches by contract
  
- **clause_type** : `str`, default=`""`
  - Type of clause (e.g., "TerminationClause", "PaymentClause")
  - Used for filtering searches by type
  
- **rdf_uri** : `str`, default=`""`
  - RDF URI of the clause in the knowledge graph
  - Enables hybrid RAG (vector + graph)
  
- **graph_uri** : `str`, default=`""`
  - Named graph URI for multi-tenant isolation

**Returns:**

- None (operation is synchronous and flushed immediately)

**Example:**

```python
# Add single clause
store.add_clause(
    clause_id="TERM_001",
    text="Either party may terminate this agreement with 30 days written notice.",
    contract_id="ABC123",
    clause_type="TerminationClause",
    rdf_uri="http://procurement.kg/contract#TERM_001",
    graph_uri="http://example.org/contracts"
)

# Add minimal clause (no metadata)
store.add_clause(
    clause_id="CLAUSE_002",
    text="Payment is due within 30 days of invoice date."
)

# Add clause with long text (auto-truncated)
long_text = "..." * 30000  # 90,000 characters
store.add_clause(
    clause_id="LONG_001",
    text=long_text  # Truncated to 65,000 chars
)
```

**Performance:**
- Embedding generation: 10-50ms per clause
- Insertion: 20-100ms per clause
- Total: 30-150ms per clause

**Use Cases:**
- Real-time clause ingestion
- Interactive document upload
- Single clause updates

---

### add_clauses_batch

```python
def add_clauses_batch(
    self,
    clauses: list[dict[str, Any]]
) -> int
```

Add multiple clauses to the vector store in batch with RDF linking.

**Parameters:**

- **clauses** : `list[dict[str, Any]]`
  - List of clause dictionaries, each containing:
    - `clause_id` (str, required): Unique identifier
    - `text` (str, required): Clause text content
    - `contract_id` (str, optional): Parent contract ID
    - `clause_type` (str, optional): Type of clause
    - `rdf_uri` (str, optional): RDF URI in knowledge graph
    - `graph_uri` (str, optional): Named graph URI

**Returns:**

- **count** : `int`
  - Number of clauses successfully inserted

**Example:**

```python
# Prepare batch of clauses
clauses = [
    {
        "clause_id": "TERM_001",
        "text": "Either party may terminate with 30 days notice.",
        "contract_id": "ABC123",
        "clause_type": "TerminationClause",
        "rdf_uri": "http://procurement.kg/contract#TERM_001",
        "graph_uri": "http://example.org/contracts"
    },
    {
        "clause_id": "PAY_001",
        "text": "Payment due within 30 days of invoice.",
        "contract_id": "ABC123",
        "clause_type": "PaymentClause",
        "rdf_uri": "http://procurement.kg/contract#PAY_001",
        "graph_uri": "http://example.org/contracts"
    },
    {
        "clause_id": "CONF_001",
        "text": "All information shall remain confidential.",
        "contract_id": "ABC123",
        "clause_type": "ConfidentialityClause",
        "rdf_uri": "http://procurement.kg/contract#CONF_001",
        "graph_uri": "http://example.org/contracts"
    }
]

# Batch insert
count = store.add_clauses_batch(clauses)
print(f"Inserted {count} clauses")

# Output: Inserted 3 clauses
```

**Large Batch Example:**

```python
# Insert 1000 clauses efficiently
clauses = []
for i in range(1000):
    clauses.append({
        "clause_id": f"CLAUSE_{i:04d}",
        "text": f"This is clause number {i} with some sample text.",
        "contract_id": f"CONTRACT_{i // 10}",
        "clause_type": "GenericClause",
        "rdf_uri": f"http://procurement.kg/contract#CLAUSE_{i:04d}",
        "graph_uri": "http://example.org/batch"
    })

count = store.add_clauses_batch(clauses)
print(f"Inserted {count:,} clauses")

# Output: Inserted 1,000 clauses
```

**Performance:**
- Batch embedding: 5-20ms per clause (parallelized)
- Batch insertion: 1-5ms per clause
- Total: 6-25ms per clause (much faster than individual inserts)

**Throughput:**
- Small batches (10-100): ~50-100 clauses/second
- Medium batches (100-1000): ~100-200 clauses/second
- Large batches (1000+): ~150-300 clauses/second

**Best Practices:**
- Use batch sizes of 100-1000 for optimal performance
- Larger batches reduce overhead but increase memory usage
- Monitor memory usage with very large batches

---

## Search Operations

### search

```python
def search(
    self,
    query: str,
    top_k: int = 5,
    clause_type: str | None = None,
    contract_id: str | None = None,
    graph_uri: str | None = None
) -> list[dict[str, Any]]
```

Search for similar clauses with RDF linking and metadata filtering.

**Parameters:**

- **query** : `str`
  - Search query text (natural language)
  - Automatically embedded using the same model as clauses
  
- **top_k** : `int`, default=`5`
  - Number of results to return
  - Range: 1-1000 (practical limit ~100 for performance)
  
- **clause_type** : `str | None`, default=`None`
  - Optional filter by clause type
  - Must match exactly (case-sensitive)
  
- **contract_id** : `str | None`, default=`None`
  - Optional filter by contract
  - Useful for contract-specific searches
  
- **graph_uri** : `str | None`, default=`None`
  - Optional filter by named graph
  - Enables multi-tenant isolation

**Returns:**

- **results** : `list[dict[str, Any]]`
  - List of matching clauses, each containing:
    - `clause_id` (str): Clause identifier
    - `contract_id` (str): Parent contract ID
    - `clause_type` (str): Type of clause
    - `text` (str): Clause text content
    - `rdf_uri` (str): RDF URI in knowledge graph
    - `graph_uri` (str): Named graph URI
    - `score` (float): Similarity score (0.0-1.0, higher is better)

**Example:**

```python
# Simple semantic search
results = store.search(
    query="What are the termination notice requirements?",
    top_k=5
)

print(f"Found {len(results)} similar clauses:")
for result in results:
    print(f"  Score: {result['score']:.3f}")
    print(f"  Type: {result['clause_type']}")
    print(f"  Text: {result['text'][:100]}...")
    print(f"  RDF URI: {result['rdf_uri']}")
    print()

# Output:
# Found 5 similar clauses:
#   Score: 0.892
#   Type: TerminationClause
#   Text: Either party may terminate this agreement with 30 days written notice...
#   RDF URI: http://procurement.kg/contract#TERM_001
```

**Filtered Search:**

```python
# Search only termination clauses
results = store.search(
    query="notice period requirements",
    top_k=10,
    clause_type="TerminationClause"
)

# Search within specific contract
results = store.search(
    query="payment terms",
    top_k=5,
    contract_id="ABC123"
)

# Search in specific graph (multi-tenant)
results = store.search(
    query="data protection",
    top_k=10,
    graph_uri="http://example.org/eu_contracts"
)

# Combined filters
results = store.search(
    query="liability limitations",
    top_k=5,
    clause_type="LiabilityClause",
    contract_id="ABC123",
    graph_uri="http://example.org/contracts"
)
```

**Similarity Score Interpretation:**

| Score Range | Interpretation | Action |
|-------------|---------------|--------|
| 0.9 - 1.0 | Highly similar | Direct match |
| 0.7 - 0.9 | Very similar | Strong candidate |
| 0.5 - 0.7 | Moderately similar | Review needed |
| 0.3 - 0.5 | Somewhat similar | Weak match |
| 0.0 - 0.3 | Not similar | Likely irrelevant |

**Performance:**
- Query embedding: 10-50ms
- Vector search: 20-200ms (depends on collection size)
- Total: 30-250ms

**Search Performance by Collection Size:**

| Collection Size | Search Time | Memory |
|----------------|-------------|--------|
| 1K vectors | 20-50ms | 50MB |
| 10K vectors | 50-100ms | 200MB |
| 100K vectors | 100-200ms | 1GB |
| 1M vectors | 200-500ms | 5GB |

---

### search_by_embedding

```python
def search_by_embedding(
    self,
    embedding: list[float],
    top_k: int = 5,
    graph_uri: str | None = None
) -> list[dict[str, Any]]
```

Search using a pre-computed embedding vector with RDF linking.

**Parameters:**

- **embedding** : `list[float]`
  - Pre-computed embedding vector
  - Must match the collection's embedding dimension (384 or 768)
  
- **top_k** : `int`, default=`5`
  - Number of results to return
  
- **graph_uri** : `str | None`, default=`None`
  - Optional filter by named graph

**Returns:**

- **results** : `list[dict[str, Any]]`
  - List of matching clauses (same format as `search`)

**Example:**

```python
# Generate embedding separately
text = "What are the payment terms?"
embedding = store.embedding_model.encode(text).tolist()

# Search with pre-computed embedding
results = store.search_by_embedding(
    embedding=embedding,
    top_k=10
)

# Useful for caching embeddings
query_cache = {}
query = "termination notice"

if query not in query_cache:
    query_cache[query] = store.embedding_model.encode(query).tolist()

results = store.search_by_embedding(
    embedding=query_cache[query],
    top_k=5
)
```

**Use Cases:**
- Embedding caching for repeated queries
- Custom embedding generation
- Integration with external embedding services
- Batch query processing

**Performance:**
- No embedding generation overhead
- Search time: 20-200ms (same as regular search)

---

## Deletion Operations

### delete_by_contract

```python
def delete_by_contract(
    self,
    contract_id: str
) -> int
```

Delete all clauses for a specific contract.

**Parameters:**

- **contract_id** : `str`
  - Contract identifier to delete clauses for

**Returns:**

- **count** : `int`
  - Number of clauses deleted

**Example:**

```python
# Delete all clauses for a contract
count = store.delete_by_contract("ABC123")
print(f"Deleted {count} clauses")

# Output: Deleted 15 clauses

# Safe deletion with confirmation
contract_id = "ABC123"
results = store.search(query="", top_k=1000, contract_id=contract_id)
clause_count = len(results)

if clause_count > 0:
    confirm = input(f"Delete {clause_count} clauses? (yes/no): ")
    if confirm.lower() == "yes":
        deleted = store.delete_by_contract(contract_id)
        print(f"Deleted {deleted} clauses")
```

**Performance:**
- Deletion time: 50-500ms (depends on clause count)
- Scales linearly with number of clauses

---

### delete_by_clause

```python
def delete_by_clause(
    self,
    clause_id: str
) -> int
```

Delete a specific clause by its identifier.

**Parameters:**

- **clause_id** : `str`
  - Clause identifier to delete

**Returns:**

- **count** : `int`
  - Number of clauses deleted (0 or 1)

**Example:**

```python
# Delete single clause
count = store.delete_by_clause("TERM_001")

if count > 0:
    print("Clause deleted successfully")
else:
    print("Clause not found")

# Batch deletion
clause_ids = ["TERM_001", "PAY_001", "CONF_001"]
deleted_count = 0

for clause_id in clause_ids:
    deleted_count += store.delete_by_clause(clause_id)

print(f"Deleted {deleted_count} clauses")
```

**Performance:**
- Single deletion: 20-100ms

---

## Collection Management

### get_collection_stats

```python
def get_collection_stats(self) -> dict[str, Any]
```

Get statistics about the collection.

**Returns:**

- **stats** : `dict[str, Any]`
  - Dictionary containing:
    - `name` (str): Collection name
    - `num_entities` (int): Number of vectors in collection
    - `schema` (str): Collection schema description

**Example:**

```python
stats = store.get_collection_stats()

print(f"Collection: {stats['name']}")
print(f"Vector count: {stats['num_entities']:,}")
print(f"Schema: {stats['schema']}")

# Output:
# Collection: contract_clauses
# Vector count: 15,234
# Schema: <CollectionSchema>...

# Monitor collection growth
import time

initial_stats = store.get_collection_stats()
initial_count = initial_stats['num_entities']

# ... perform insertions ...

time.sleep(1)
final_stats = store.get_collection_stats()
final_count = final_stats['num_entities']

print(f"Added {final_count - initial_count:,} vectors")
```

**Performance:**
- Execution time: 10-50ms

---

### drop_collection

```python
def drop_collection(self) -> None
```

Drop the entire collection (use with caution!).

**Returns:**

- None

**Warning:**
- This operation is irreversible
- All vectors and metadata are permanently deleted
- Use only for testing or cleanup

**Example:**

```python
# Drop collection (dangerous!)
store.drop_collection()
print("Collection dropped")

# Safe drop with confirmation
stats = store.get_collection_stats()
count = stats['num_entities']

confirm = input(f"Drop collection with {count:,} vectors? (yes/no): ")
if confirm.lower() == "yes":
    store.drop_collection()
    print("Collection dropped")
else:
    print("Operation cancelled")
```

**Performance:**
- Execution time: 100-1000ms

---

### close

```python
def close(self) -> None
```

Close the connection to Milvus.

**Returns:**

- None

**Example:**

```python
# Close connection when done
store.close()
print("Connection closed")

# Use with context manager (recommended)
class MilvusVectorStoreContext:
    def __enter__(self):
        self.store = MilvusVectorStore()
        return self.store
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.store.close()

# Automatic cleanup
with MilvusVectorStoreContext() as store:
    results = store.search("query", top_k=5)
    # Connection automatically closed
```

**Performance:**
- Execution time: 10-50ms

---

## Embedding Models

### Supported Models

The vector store supports any sentence-transformers model. Common choices:

| Model | Dimensions | Speed | Quality | Use Case |
|-------|-----------|-------|---------|----------|
| all-MiniLM-L6-v2 | 384 | Fast | Good | General purpose |
| all-mpnet-base-v2 | 768 | Medium | Better | High quality |
| all-MiniLM-L12-v2 | 384 | Fast | Good | Balanced |
| paraphrase-multilingual | 768 | Slow | Best | Multilingual |

**Configuration:**

```python
from config import Settings

# Use different model
settings = Settings()
settings.embedding_model = "sentence-transformers/all-mpnet-base-v2"
settings.embedding_dim = 768

store = MilvusVectorStore(settings=settings)
```

**Model Loading:**

```python
# Eager loading (default)
store = MilvusVectorStore()  # Model loaded immediately (~2-5s)

# Lazy loading (recommended for faster startup)
settings = Settings()
settings.lazy_load_embedding = True
store = MilvusVectorStore(settings=settings)  # Model loaded on first use
```

**Performance Comparison:**

| Model | Load Time | Encode Time | Memory |
|-------|-----------|-------------|--------|
| all-MiniLM-L6-v2 | 2s | 10ms | 500MB |
| all-mpnet-base-v2 | 3s | 20ms | 1GB |
| all-MiniLM-L12-v2 | 2.5s | 15ms | 700MB |

---

## Index Configuration

### Index Types

Milvus supports various index types for different use cases:

```python
# IVF_FLAT - Balanced performance (default)
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128}
}

# HNSW - Best quality, slower build
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 200}
}

# IVF_SQ8 - Memory efficient
index_params = {
    "metric_type": "COSINE",
    "index_type": "IVF_SQ8",
    "params": {"nlist": 128}
}
```

### Metric Types

```python
# Cosine similarity (default, recommended)
metric_type = "COSINE"  # Range: 0.0-1.0, higher is better

# L2 (Euclidean distance)
metric_type = "L2"  # Range: 0.0-∞, lower is better

# Inner product
metric_type = "IP"  # Range: -∞-∞, higher is better
```

**Recommendation:** Use COSINE for semantic similarity (normalized vectors).

---

## Hybrid RAG Integration

The vector store integrates with the SPARQL knowledge graph through RDF URIs:

### Example Workflow

```python
from fuseki_client import FusekiClient
from vector_store import MilvusVectorStore

# Initialize both stores
fuseki = FusekiClient()
milvus = MilvusVectorStore()

# 1. Insert clause into knowledge graph
clause_uri = fuseki.insert_clause(
    clause_id="TERM_001",
    contract_uri="http://procurement.kg/contract#ABC123",
    clause_type="TerminationClause",
    raw_text="Either party may terminate with 30 days notice.",
    notice_period=30
)

# 2. Insert same clause into vector store with RDF link
milvus.add_clause(
    clause_id="TERM_001",
    text="Either party may terminate with 30 days notice.",
    contract_id="ABC123",
    clause_type="TerminationClause",
    rdf_uri=clause_uri,  # Link to knowledge graph
    graph_uri="http://example.org/contracts"
)

# 3. Semantic search returns RDF URIs
results = milvus.search(
    query="What are the termination requirements?",
    top_k=5
)

# 4. Enrich with knowledge graph data
for result in results:
    rdf_uri = result['rdf_uri']
    
    # Query knowledge graph for additional context
    query = f"""
    SELECT ?risk ?riskLabel WHERE {{
        <{rdf_uri}> proc:introducesRisk ?risk .
        OPTIONAL {{ ?risk rdfs:label ?riskLabel }}
    }}
    """
    
    risks = fuseki.execute_select(query)
    result['risks'] = risks
    
    print(f"Clause: {result['text'][:50]}...")
    print(f"Score: {result['score']:.3f}")
    print(f"Risks: {len(risks)}")
```

**Benefits:**
- **Vector search** for semantic similarity
- **Graph queries** for structured relationships
- **Combined results** for comprehensive answers

---

## Best Practices

### 1. Use Batch Operations

```python
# ❌ Individual inserts (slow)
for clause in clauses:
    store.add_clause(**clause)

# ✅ Batch insert (fast)
store.add_clauses_batch(clauses)
```

**Performance Impact:**
- Individual: ~100ms per clause
- Batch: ~10ms per clause (10x faster)

### 2. Appropriate top_k Values

```python
# ❌ Too many results (slow, irrelevant)
results = store.search(query, top_k=1000)

# ✅ Reasonable limit (fast, relevant)
results = store.search(query, top_k=10)
```

**Guidelines:**
- Interactive search: top_k=5-10
- Analysis: top_k=20-50
- Bulk processing: top_k=100 (max)

### 3. Use Filters to Narrow Search

```python
# ❌ Search entire collection
results = store.search(query, top_k=10)

# ✅ Filter by relevant metadata
results = store.search(
    query=query,
    top_k=10,
    clause_type="TerminationClause",
    contract_id="ABC123"
)
```

**Performance Impact:**
- Unfiltered: 100-200ms
- Filtered: 50-100ms (2x faster)

### 4. Monitor Collection Size

```python
# Regular monitoring
stats = store.get_collection_stats()
count = stats['num_entities']

if count > 1_000_000:
    logger.warning(f"Large collection: {count:,} vectors")
    # Consider partitioning or archiving
```

### 5. Handle Errors Gracefully

```python
try:
    results = store.search(query, top_k=10)
except Exception as e:
    logger.error(f"Search failed: {e}")
    results = []  # Fallback to empty results
```

---

## Performance Optimization

### Memory Optimization

```python
# 1. Use lazy loading
settings = Settings()
settings.lazy_load_embedding = True
store = MilvusVectorStore(settings=settings)

# 2. Use smaller embedding model
settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
settings.embedding_dim = 384  # vs 768 for larger models

# 3. Limit batch sizes
store.add_clauses_batch(clauses[:1000])  # Process in chunks
```

### Search Optimization

```python
# 1. Use appropriate index
# IVF_FLAT for balanced performance
# HNSW for best quality (slower build)

# 2. Tune search parameters
search_params = {
    "metric_type": "COSINE",
    "params": {"nprobe": 10}  # Lower = faster, higher = better quality
}

# 3. Use filters to reduce search space
results = store.search(
    query=query,
    top_k=10,
    clause_type="TerminationClause"  # Reduces candidates
)
```

### Throughput Optimization

```python
# 1. Batch operations
clauses_batch = []
for clause in clauses:
    clauses_batch.append(clause)
    
    if len(clauses_batch) >= 100:
        store.add_clauses_batch(clauses_batch)
        clauses_batch = []

# 2. Parallel processing
from concurrent.futures import ThreadPoolExecutor

def search_query(query):
    return store.search(query, top_k=10)

queries = ["query1", "query2", "query3"]

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(search_query, queries))
```

---

## Troubleshooting

### Slow Searches

**Problem:** Searches taking >1 second

**Solutions:**
1. Check collection size: `stats = store.get_collection_stats()`
2. Optimize index parameters
3. Reduce top_k value
4. Use filters to narrow search space
5. Consider partitioning large collections

### High Memory Usage

**Problem:** Excessive memory consumption

**Solutions:**
1. Enable lazy loading: `settings.lazy_load_embedding = True`
2. Use smaller embedding model (384 vs 768 dimensions)
3. Reduce batch sizes
4. Close connections when not in use: `store.close()`

### Connection Errors

**Problem:** Cannot connect to Milvus

**Solutions:**
1. Check Milvus server status: `docker ps | grep milvus`
2. Verify host and port: `settings.milvus_host`, `settings.milvus_port`
3. Check network connectivity: `ping milvus_host`
4. Review Milvus logs: `docker logs milvus-standalone`

### Low Search Quality

**Problem:** Irrelevant search results

**Solutions:**
1. Use better embedding model (all-mpnet-base-v2)
2. Increase top_k to see more candidates
3. Check query phrasing (be specific)
4. Verify clause text quality
5. Consider fine-tuning embedding model

---

## Complete Example

```python
from vector_store import MilvusVectorStore
from fuseki_client import FusekiClient
from config import get_settings

# Initialize stores
settings = get_settings()
milvus = MilvusVectorStore(settings=settings)
fuseki = FusekiClient(settings=settings)

# Get collection stats
stats = milvus.get_collection_stats()
print(f"Collection: {stats['name']}")
print(f"Vectors: {stats['num_entities']:,}")

# Prepare clauses for insertion
clauses = [
    {
        "clause_id": "TERM_001",
        "text": "Either party may terminate with 30 days notice.",
        "contract_id": "ABC123",
        "clause_type": "TerminationClause",
        "rdf_uri": "http://procurement.kg/contract#TERM_001",
        "graph_uri": "http://example.org/contracts"
    },
    {
        "clause_id": "PAY_001",
        "text": "Payment due within 30 days of invoice.",
        "contract_id": "ABC123",
        "clause_type": "PaymentClause",
        "rdf_uri": "http://procurement.kg/contract#PAY_001",
        "graph_uri": "http://example.org/contracts"
    }
]

# Batch insert
count = milvus.add_clauses_batch(clauses)
print(f"Inserted {count} clauses")

# Semantic search
results = milvus.search(
    query="What are the payment terms?",
    top_k=5,
    clause_type="PaymentClause"
)

print(f"\nFound {len(results)} similar clauses:")
for result in results:
    print(f"  Score: {result['score']:.3f}")
    print(f"  Text: {result['text']}")
    print(f"  RDF URI: {result['rdf_uri']}")
    
    # Enrich with knowledge graph
    rdf_uri = result['rdf_uri']
    query = f"""
    SELECT ?contract ?value WHERE {{
        <{rdf_uri}> ^proc:hasClause ?contract .
        ?contract proc:contractValue ?value .
    }}
    """
    
    kg_results = fuseki.execute_select(query)
    if kg_results:
        print(f"  Contract Value: ${kg_results[0]['value']}")
    print()

# Cleanup
milvus.close()
```

**Output:**
```
Collection: contract_clauses
Vectors: 15,234

Inserted 2 clauses

Found 2 similar clauses:
  Score: 0.912
  Text: Payment due within 30 days of invoice.
  RDF URI: http://procurement.kg/contract#PAY_001
  Contract Value: $150000.00

  Score: 0.784
  Text: Invoice payment terms are net 30 days.
  RDF URI: http://procurement.kg/contract#PAY_002
  Contract Value: $250000.00
```

---

## See Also

- **[SPARQL Store API](sparql_comprehensive.md)** - Knowledge graph operations
- **[Ingestion Agents](../agents/ingestion_comprehensive.md)** - Data ingestion pipeline
- **[Retrieval Agents](../agents/retrieval_comprehensive.md)** - Query orchestration
- **[Configuration](../core/config.md)** - Settings and environment variables