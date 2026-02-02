# SPARQL Store API Reference

API documentation for SPARQL storage abstraction layer.

## SPARQLStore (Base Class)

Abstract base class for SPARQL store implementations.

### Class Definition

```python
from storage.sparql.base import SPARQLStore

class SPARQLStore(ABC):
    """
    Abstract base class for SPARQL triple stores.
    
    Provides a unified interface for querying and updating
    RDF data regardless of the underlying store implementation.
    """
```

### Abstract Methods

#### query

```python
@abstractmethod
def query(
    self,
    sparql_query: str,
    graph_uri: str | None = None
) -> list[dict[str, Any]]
```

Execute SPARQL SELECT query.

**Parameters:**

- `sparql_query` (str): SPARQL query string
- `graph_uri` (str, optional): Target graph URI

**Returns:**

- `list[dict]`: Query results as list of bindings

#### update

```python
@abstractmethod
def update(
    self,
    sparql_update: str,
    graph_uri: str | None = None
) -> bool
```

Execute SPARQL UPDATE operation.

**Parameters:**

- `sparql_update` (str): SPARQL UPDATE string
- `graph_uri` (str, optional): Target graph URI

**Returns:**

- `bool`: Success status

#### insert_triples

```python
@abstractmethod
def insert_triples(
    self,
    triples: str | Graph,
    graph_uri: str
) -> int
```

Insert RDF triples into graph.

**Parameters:**

- `triples` (str | Graph): RDF data (Turtle string or Graph)
- `graph_uri` (str): Target graph URI

**Returns:**

- `int`: Number of triples inserted

## FusekiStore

Apache Fuseki implementation of SPARQLStore.

### Class Definition

```python
from storage.sparql.fuseki_store import FusekiStore

class FusekiStore(SPARQLStore):
    """
    Apache Fuseki SPARQL store implementation.
    
    Provides optimized access to Fuseki with connection pooling,
    query caching, and batch operations.
    """
```

### Constructor

```python
def __init__(
    self,
    endpoint: str = "http://localhost:3030/contracts",
    graph_uri: str | None = None,
    timeout: int = 30,
    enable_cache: bool = True,
    cache_ttl: int = 300,
    pool_size: int = 10
)
```

**Parameters:**

- `endpoint` (str): Fuseki endpoint URL
- `graph_uri` (str, optional): Default graph URI
- `timeout` (int): Query timeout in seconds
- `enable_cache` (bool): Enable query caching
- `cache_ttl` (int): Cache TTL in seconds
- `pool_size` (int): Connection pool size

**Example:**

```python
store = FusekiStore(
    endpoint="http://localhost:3030/contracts",
    graph_uri="http://example.org/contracts",
    enable_cache=True,
    cache_ttl=300
)
```

### Methods

#### query

```python
def query(
    self,
    sparql_query: str,
    graph_uri: str | None = None
) -> list[dict[str, Any]]
```

Execute SPARQL SELECT query with caching.

**Example:**

```python
results = store.query("""
    PREFIX proc: <http://procurement.kg/ontology#>
    SELECT ?contract ?id
    WHERE {
        ?contract a proc:Contract ;
                  proc:contractId ?id .
    }
    LIMIT 10
""")

for result in results:
    print(f"Contract: {result['contract']}")
    print(f"ID: {result['id']}")
```

#### update

```python
def update(
    self,
    sparql_update: str,
    graph_uri: str | None = None
) -> bool
```

Execute SPARQL UPDATE operation.

**Example:**

```python
success = store.update("""
    PREFIX proc: <http://procurement.kg/ontology#>
    INSERT DATA {
        GRAPH <http://example.org/contracts> {
            proc:Contract_ABC123 a proc:Contract ;
                proc:contractId "ABC123" .
        }
    }
""")

print(f"Update successful: {success}")
```

#### insert_triples

```python
def insert_triples(
    self,
    triples: str | Graph,
    graph_uri: str
) -> int
```

Insert RDF triples with batch optimization.

**Example:**

```python
from rdflib import Graph

g = Graph()
g.parse(data=turtle_data, format="turtle")

count = store.insert_triples(
    triples=g,
    graph_uri="http://example.org/contracts"
)

print(f"Inserted {count} triples")
```

#### batch_query

```python
def batch_query(
    self,
    queries: list[str],
    graph_uri: str | None = None
) -> list[list[dict[str, Any]]]
```

Execute multiple queries efficiently.

**Example:**

```python
queries = [
    "SELECT ?contract WHERE { ?contract a proc:Contract }",
    "SELECT ?clause WHERE { ?clause a proc:Clause }"
]

results = store.batch_query(queries)

for i, result in enumerate(results):
    print(f"Query {i+1}: {len(result)} results")
```

#### get_cache_stats

```python
def get_cache_stats(self) -> dict[str, Any]
```

Get query cache statistics.

**Returns:**

- `dict`: Cache statistics

**Example:**

```python
stats = store.get_cache_stats()

print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']}%")
print(f"Cache size: {stats['size']}")
```

#### clear_cache

```python
def clear_cache(self) -> None
```

Clear query cache.

**Example:**

```python
store.clear_cache()
print("Cache cleared")
```

## QueryCache

LRU cache for SPARQL queries with TTL.

### Class Definition

```python
from storage.sparql.query_cache import QueryCache

class QueryCache:
    """
    LRU cache for SPARQL query results with TTL.
    
    Provides significant performance improvements for
    repeated queries.
    """
```

### Constructor

```python
def __init__(
    self,
    max_size: int = 1000,
    ttl_seconds: int = 300
)
```

**Parameters:**

- `max_size` (int): Maximum cache entries
- `ttl_seconds` (int): Time-to-live in seconds

**Example:**

```python
cache = QueryCache(
    max_size=1000,
    ttl_seconds=300  # 5 minutes
)
```

### Methods

#### get

```python
def get(
    self,
    query: str
) -> list[dict[str, Any]] | None
```

Get cached query result.

**Parameters:**

- `query` (str): SPARQL query

**Returns:**

- `list[dict] | None`: Cached result or None

**Example:**

```python
result = cache.get(query)

if result is not None:
    print("Cache hit!")
else:
    print("Cache miss")
```

#### set

```python
def set(
    self,
    query: str,
    result: list[dict[str, Any]]
) -> None
```

Cache query result.

**Parameters:**

- `query` (str): SPARQL query
- `result` (list): Query result

**Example:**

```python
cache.set(query, results)
```

#### get_or_execute

```python
def get_or_execute(
    self,
    query: str,
    execute_fn: Callable[[str], list[dict]]
) -> list[dict[str, Any]]
```

Get from cache or execute and cache.

**Parameters:**

- `query` (str): SPARQL query
- `execute_fn` (Callable): Function to execute query

**Returns:**

- `list[dict]`: Query results

**Example:**

```python
def execute_query(q: str) -> list[dict]:
    return store.query(q)

result = cache.get_or_execute(query, execute_query)
```

#### stats

```python
def stats(self) -> dict[str, Any]
```

Get cache statistics.

**Returns:**

- `dict`: Statistics including hits, misses, hit rate

**Example:**

```python
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate']}%")
```

## SPARQLStoreFactory

Factory for creating SPARQL store instances.

### Class Definition

```python
from storage.sparql.factory import create_sparql_store

def create_sparql_store(
    store_type: str = "fuseki",
    **kwargs
) -> SPARQLStore
```

Create SPARQL store instance.

**Parameters:**

- `store_type` (str): Store type ("fuseki")
- `**kwargs`: Store-specific parameters

**Returns:**

- `SPARQLStore`: Store instance

**Example:**

```python
# Create Fuseki store
store = create_sparql_store(
    store_type="fuseki",
    endpoint="http://localhost:3030/contracts",
    enable_cache=True
)

# Use store
results = store.query("SELECT * WHERE { ?s ?p ?o } LIMIT 10")
```

## Connection Pooling

Efficient connection management for high-throughput scenarios.

### Configuration

```python
from storage.sparql.fuseki_store import FusekiStore

store = FusekiStore(
    endpoint="http://localhost:3030/contracts",
    pool_size=10,  # Number of connections
    pool_timeout=30  # Connection timeout
)
```

### Benefits

- **Reduced latency:** Reuse existing connections
- **Higher throughput:** Parallel query execution
- **Resource efficiency:** Controlled connection count

### Monitoring

```python
pool_stats = store.get_pool_stats()

print(f"Active connections: {pool_stats['active']}")
print(f"Idle connections: {pool_stats['idle']}")
print(f"Total connections: {pool_stats['total']}")
```

## Best Practices

### 1. Use Caching

```python
# ✅ Enable caching for repeated queries
store = FusekiStore(enable_cache=True, cache_ttl=300)

# First query - cache miss
results = store.query(query)  # ~2000ms

# Second query - cache hit
results = store.query(query)  # ~50ms
```

### 2. Batch Operations

```python
# ❌ Multiple individual queries
for query in queries:
    results = store.query(query)

# ✅ Single batch query
results = store.batch_query(queries)
```

### 3. Use Appropriate Timeouts

```python
# Short timeout for simple queries
store = FusekiStore(timeout=10)

# Longer timeout for complex queries
store = FusekiStore(timeout=60)
```

### 4. Monitor Cache Performance

```python
# Regularly check cache stats
stats = store.get_cache_stats()

if stats['hit_rate'] < 30:
    # Consider increasing cache size or TTL
    store.clear_cache()
    store = FusekiStore(
        cache_ttl=600,  # Increase TTL
        max_cache_size=2000  # Increase size
    )
```

### 5. Handle Errors Gracefully

```python
try:
    results = store.query(query)
except SPARQLStoreError as e:
    logger.error(f"Query failed: {e}")
    # Fallback logic
    results = []
```

## Performance Metrics

### Query Performance

| Operation | Without Cache | With Cache | Speedup |
|-----------|--------------|------------|---------|
| Simple SELECT | 2000ms | 50ms | 40x |
| Complex JOIN | 5000ms | 100ms | 50x |
| Aggregation | 3000ms | 75ms | 40x |

### Cache Statistics

| Metric | Typical Value |
|--------|--------------|
| Hit Rate | 50-90% |
| Average Latency (hit) | 50ms |
| Average Latency (miss) | 2000ms |
| Memory Usage | ~100MB (1000 entries) |

## See Also

- [Vector Store API](../api/storage/vector.md)
- [Apache Jena Architecture](../../architecture/jena.md)
- [Performance Optimizations](../../performance/optimizations.md)