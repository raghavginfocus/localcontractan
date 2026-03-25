# Orchestrators API Reference

Comprehensive API documentation for ingestion and retrieval orchestrators that coordinate multi-agent workflows.

## Overview

Orchestrators manage complex multi-step workflows by coordinating multiple agents, handling data flow, managing state, and providing comprehensive logging. They implement the orchestration layer of the multi-agent architecture.

**Key Features:**
- Multi-agent coordination
- Pipeline state management
- Comprehensive logging and tracing
- Error handling and recovery
- Performance monitoring
- Async/await support
- Dependency injection

---

## RetrievalOrchestrator

Orchestrates the complete retrieval pipeline for answering questions using hybrid RAG.

### Class Definition

```python
from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator

class RetrievalOrchestrator:
    """
    Complete orchestration for the retrieval pipeline.
    
    Pipeline Flow:
    1. Query understanding and strategy determination
    2. Knowledge Graph retrieval (if needed)
    3. Vector store retrieval (if needed)
    4. Result combination and answer generation
    5. Response formatting
    """
```

### Constructor

```python
def __init__(
    self,
    sparql_store: SPARQLStore | None = None,
    vector_store: VectorStore | None = None,
    settings: Settings | None = None,
    enable_logging: bool = True,
    enable_react: bool = True
)
```

Initialize the retrieval orchestrator with dependency injection.

**Parameters:**

- **sparql_store** : `SPARQLStore | None`, default=`None`
  - SPARQL store for KG queries
  - If None, obtained from service factory
  
- **vector_store** : `VectorStore | None`, default=`None`
  - Vector store for semantic search
  - If None, obtained from service factory
  
- **settings** : `Settings | None`, default=`None`
  - Application settings
  - If None, uses default settings
  
- **enable_logging** : `bool`, default=`True`
  - Whether to enable detailed logging
  - Creates session log files
  
- **enable_react** : `bool`, default=`True`
  - Whether to enable ReAct for complex queries
  - Enables multi-step reasoning

**Attributes:**

- **query_analyzer** : `UnifiedQueryAnalyzer`
  - Analyzes query complexity and decomposes complex queries
  
- **query_classifier** : `QueryClassifier`
  - Routes queries to optimal retrieval strategy
  
- **fuseki_client** : `FusekiClient`
  - Client for text search operations
  
- **rag_logger** : `RAGLogger`
  - Logger for session files and answer logging
  
- **rag_orchestrator** : `RAGOrchestratorAgent`
  - Standard RAG orchestrator for simple queries
  
- **react_agent** : `ReActRetrievalAgent`
  - ReAct agent for complex multi-step queries
  
- **sparql_agent** : `SPARQLGeneratorAgent`
  - SPARQL query generator

**Example:**

```python
from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from config import get_settings

# Initialize with defaults
orchestrator = RetrievalOrchestrator()

# Initialize with custom settings
settings = get_settings()
orchestrator = RetrievalOrchestrator(
    settings=settings,
    enable_logging=True,
    enable_react=True
)

# Initialize with dependency injection
from service_factory import get_service_factory

factory = get_service_factory()
orchestrator = RetrievalOrchestrator(
    sparql_store=factory.get_sparql_store(),
    vector_store=factory.get_vector_store(),
    settings=settings
)
```

**Performance:**
- Initialization: 100-500ms
- First query: +2-5s (model loading)
- Subsequent queries: Fast (models cached)

---

### retrieve

```python
async def retrieve(
    self,
    question: str,
    graph_uri: str | None = None,
    strategy: RetrievalStrategy | None = None,
    force_react: bool = False
) -> RetrievalResult
```

Process a question through the complete retrieval pipeline.

**Parameters:**

- **question** : `str`
  - Natural language question
  - Can be simple or complex
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI to query
  - Enables multi-tenant isolation
  
- **strategy** : `RetrievalStrategy | None`, default=`None`
  - Optional retrieval strategy
  - Auto-determined if not provided
  - Options: `KG_ONLY`, `VECTOR_ONLY`, `HYBRID`, `REACT_MULTI_STEP`, `DIRECT`
  
- **force_react** : `bool`, default=`False`
  - Force use of ReAct agent regardless of complexity
  - Useful for testing or specific use cases

**Returns:**

- **result** : `RetrievalResult`
  - Complete retrieval result with answer and metadata

**Example:**

```python
import asyncio

# Simple query
result = await orchestrator.retrieve(
    question="What are the termination notice periods in our contracts?"
)

print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Strategy: {result.strategy.value}")
print(f"Duration: {result.total_duration_ms:.0f}ms")

# Output:
# Answer: The termination notice periods vary by contract...
# Confidence: 0.85
# Strategy: hybrid
# Duration: 2500ms
```

**Complex Query Example:**

```python
# Complex multi-step query
result = await orchestrator.retrieve(
    question="Compare the payment terms and termination clauses across all contracts with Company A"
)

print(f"Strategy: {result.strategy.value}")
# Output: Strategy: react_multi_step

print(f"Steps: {len(result.steps)}")
# Output: Steps: 5

for step in result.steps:
    print(f"  {step.step_name}: {step.duration_ms:.0f}ms")

# Output:
#   react_iteration_1: 1200ms
#   react_iteration_2: 800ms
#   react_iteration_3: 1500ms
#   react_iteration_4: 900ms
#   react_iteration_5: 600ms
```

**With Named Graph:**

```python
# Query specific graph
result = await orchestrator.retrieve(
    question="List all contracts",
    graph_uri="http://example.org/contracts/2024"
)
```

**Force Strategy:**

```python
# Force specific strategy
result = await orchestrator.retrieve(
    question="Count contracts",
    strategy=RetrievalStrategy.KG_ONLY
)

# Force ReAct for testing
result = await orchestrator.retrieve(
    question="Simple question",
    force_react=True
)
```

**Performance:**
- Simple queries (KG_ONLY): 500-2000ms
- Hybrid queries: 2000-5000ms
- Complex queries (ReAct): 5000-15000ms

---

### retrieve_batch

```python
async def retrieve_batch(
    self,
    questions: list[str],
    graph_uri: str | None = None
) -> list[RetrievalResult]
```

Process multiple questions in sequence.

**Parameters:**

- **questions** : `list[str]`
  - List of questions to process
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI for all questions

**Returns:**

- **results** : `list[RetrievalResult]`
  - List of retrieval results

**Example:**

```python
# Batch processing
questions = [
    "What are the termination notice periods?",
    "List all payment terms",
    "Which contracts have liability clauses?"
]

results = await orchestrator.retrieve_batch(questions)

for i, result in enumerate(results, 1):
    print(f"\nQuestion {i}: {result.question}")
    print(f"Answer: {result.answer[:100]}...")
    print(f"Duration: {result.total_duration_ms:.0f}ms")
```

**Performance:**
- Sequential processing (not parallel)
- Total time = sum of individual query times

---

### get_pipeline_summary

```python
def get_pipeline_summary(
    self,
    result: RetrievalResult
) -> dict[str, Any]
```

Get a summary of the pipeline execution.

**Parameters:**

- **result** : `RetrievalResult`
  - Retrieval result to summarize

**Returns:**

- **summary** : `dict[str, Any]`
  - Pipeline execution summary

**Example:**

```python
result = await orchestrator.retrieve("What are the payment terms?")

summary = orchestrator.get_pipeline_summary(result)

print(f"Question: {summary['question']}")
print(f"Success: {summary['success']}")
print(f"Strategy: {summary['strategy']}")
print(f"Duration: {summary['total_duration_ms']:.0f}ms")
print(f"\nMetrics:")
print(f"  KG facts: {summary['metrics']['kg_facts']}")
print(f"  Vector contexts: {summary['metrics']['vector_contexts']}")
print(f"  Confidence: {summary['metrics']['confidence']:.2f}")
print(f"  Answer length: {summary['metrics']['answer_length']}")
print(f"\nSteps:")
for step_name, step_info in summary['steps'].items():
    print(f"  {step_name}: {step_info['duration_ms']:.0f}ms ({'✓' if step_info['success'] else '✗'})")
```

---

## RetrievalStrategy

Enum defining retrieval strategies.

```python
from agents.retrieval.retrieval_orchestrator import RetrievalStrategy

class RetrievalStrategy(str, Enum):
    """Retrieval strategy types."""
    KG_ONLY = "kg_only"  # Only use Knowledge Graph
    VECTOR_ONLY = "vector_only"  # Only use Vector Store
    HYBRID = "hybrid"  # Use both KG and Vector
    REACT_MULTI_STEP = "react_multi_step"  # ReAct reasoning for complex queries
    DIRECT = "direct"  # Direct answer without retrieval
```

**Usage:**

```python
# Specify strategy
result = await orchestrator.retrieve(
    question="Count contracts",
    strategy=RetrievalStrategy.KG_ONLY
)
```

---

## RetrievalResult

Result of the complete retrieval pipeline.

### Class Definition

```python
from agents.retrieval.retrieval_orchestrator import RetrievalResult

class RetrievalResult(BaseModel):
    """Result of the complete retrieval pipeline."""
    
    question: str
    success: bool
    steps: list[RetrievalStep]
    strategy: RetrievalStrategy
    kg_facts_count: int
    vector_context_count: int
    text_search_count: int
    answer: str
    confidence: float
    sparql_query: str | None
    total_duration_ms: float
    analysis_time_ms: float
    retrieval_time_ms: float
    synthesis_time_ms: float
    started_at: datetime | None
    completed_at: datetime | None
    log_file: str | None
    error: str | None
```

**Example:**

```python
result = await orchestrator.retrieve("What are the payment terms?")

# Access result fields
print(f"Question: {result.question}")
print(f"Success: {result.success}")
print(f"Answer: {result.answer}")
print(f"Confidence: {result.confidence:.2f}")
print(f"Strategy: {result.strategy.value}")

# Metrics
print(f"\nMetrics:")
print(f"  KG facts: {result.kg_facts_count}")
print(f"  Vector contexts: {result.vector_context_count}")
print(f"  Text search results: {result.text_search_count}")

# Timing
print(f"\nTiming:")
print(f"  Total: {result.total_duration_ms:.0f}ms")
print(f"  Analysis: {result.analysis_time_ms:.0f}ms")
print(f"  Retrieval: {result.retrieval_time_ms:.0f}ms")
print(f"  Synthesis: {result.synthesis_time_ms:.0f}ms")

# Steps
print(f"\nSteps: {len(result.steps)}")
for step in result.steps:
    print(f"  {step.step_name}: {step.duration_ms:.0f}ms")

# Log file
if result.log_file:
    print(f"\nLog file: {result.log_file}")
```

---

## RetrievalStep

Represents a step in the retrieval pipeline with timing.

```python
from agents.retrieval.retrieval_orchestrator import RetrievalStep

class RetrievalStep(BaseModel):
    """Represents a step in the retrieval pipeline with timing."""
    
    step_name: str
    started_at: datetime
    completed_at: datetime | None
    success: bool
    duration_ms: float
    result: dict[str, Any]
    error: str | None
    llm_time_ms: float
    retrieval_time_ms: float
    processing_time_ms: float
```

---

## IngestionOrchestrator

Orchestrates the complete document ingestion pipeline.

### Class Definition

```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

class IngestionOrchestrator:
    """
    Orchestrates the complete document ingestion pipeline.
    
    Pipeline Flow:
    1. Document parsing and preprocessing
    2. Clause extraction
    3. Entity extraction
    4. Obligation and risk detection
    5. RDF generation
    6. Knowledge graph loading
    7. Vector indexing
    8. Artifact storage
    """
```

### Constructor

```python
def __init__(
    self,
    settings: Settings | None = None,
    enable_logging: bool = True
)
```

Initialize the ingestion orchestrator.

**Parameters:**

- **settings** : `Settings | None`, default=`None`
  - Application settings
  
- **enable_logging** : `bool`, default=`True`
  - Whether to enable detailed logging

**Example:**

```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

# Initialize
orchestrator = IngestionOrchestrator()

# With custom settings
settings = get_settings()
orchestrator = IngestionOrchestrator(
    settings=settings,
    enable_logging=True
)
```

---

### ingest_document

```python
async def ingest_document(
    self,
    document_path: str,
    document_id: str | None = None,
    graph_uri: str | None = None
) -> IngestionResult
```

Ingest a single document through the complete pipeline.

**Parameters:**

- **document_path** : `str`
  - Path to document file
  - Supported formats: PDF, DOCX, TXT
  
- **document_id** : `str | None`, default=`None`
  - Optional document identifier
  - Auto-generated if not provided
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI
  - Enables multi-tenant isolation

**Returns:**

- **result** : `IngestionResult`
  - Complete ingestion result with metrics

**Example:**

```python
# Ingest single document
result = await orchestrator.ingest_document(
    document_path="contracts/ABC123.pdf",
    document_id="ABC123",
    graph_uri="http://example.org/contracts"
)

print(f"Success: {result.success}")
print(f"Document ID: {result.document_id}")
print(f"Clauses extracted: {result.clauses_extracted}")
print(f"Entities extracted: {result.entities_extracted}")
print(f"RDF triples: {result.rdf_triples}")
print(f"Duration: {result.total_duration_ms:.0f}ms")

# Access artifacts
print(f"\nArtifacts:")
print(f"  RDF: {result.artifact_paths['rdf']}")
print(f"  Log: {result.artifact_paths['log']}")
```

**Performance:**
- Small documents (<10 pages): 5-15 seconds
- Medium documents (10-50 pages): 15-60 seconds
- Large documents (>50 pages): 60-300 seconds

---

### ingest_batch

```python
async def ingest_batch(
    self,
    document_paths: list[str],
    job_id: str | None = None,
    graph_uri: str | None = None
) -> list[IngestionResult]
```

Ingest multiple documents in batch.

**Parameters:**

- **document_paths** : `list[str]`
  - List of document file paths
  
- **job_id** : `str | None`, default=`None`
  - Optional job identifier for grouping
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI

**Returns:**

- **results** : `list[IngestionResult]`
  - List of ingestion results

**Example:**

```python
# Batch ingestion
document_paths = [
    "contracts/ABC123.pdf",
    "contracts/XYZ789.pdf",
    "contracts/DEF456.pdf"
]

results = await orchestrator.ingest_batch(
    document_paths=document_paths,
    job_id="batch_20240110",
    graph_uri="http://example.org/contracts"
)

# Summary
successful = sum(1 for r in results if r.success)
print(f"Processed {len(results)} documents")
print(f"Successful: {successful}")
print(f"Failed: {len(results) - successful}")

# Details
for result in results:
    print(f"\n{result.document_id}:")
    print(f"  Status: {'✓' if result.success else '✗'}")
    print(f"  Clauses: {result.clauses_extracted}")
    print(f"  Duration: {result.total_duration_ms:.0f}ms")
```

---

## Usage Patterns

### Basic Retrieval

```python
from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator
import asyncio

async def main():
    # Initialize
    orchestrator = RetrievalOrchestrator()
    
    # Query
    result = await orchestrator.retrieve(
        "What are the termination notice periods?"
    )
    
    # Display result
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Sources: {result.kg_facts_count} KG + {result.vector_context_count} vector")

asyncio.run(main())
```

### Batch Retrieval

```python
async def batch_query():
    orchestrator = RetrievalOrchestrator()
    
    questions = [
        "What are the payment terms?",
        "List all termination clauses",
        "Which contracts have liability limits?"
    ]
    
    results = await orchestrator.retrieve_batch(questions)
    
    for i, result in enumerate(results, 1):
        print(f"\n=== Question {i} ===")
        print(f"Q: {result.question}")
        print(f"A: {result.answer[:200]}...")
        print(f"Confidence: {result.confidence:.2f}")

asyncio.run(batch_query())
```

### Basic Ingestion

```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

async def ingest():
    orchestrator = IngestionOrchestrator()
    
    result = await orchestrator.ingest_document(
        document_path="contract.pdf",
        document_id="ABC123"
    )
    
    if result.success:
        print(f"✓ Ingested successfully")
        print(f"  Clauses: {result.clauses_extracted}")
        print(f"  Entities: {result.entities_extracted}")
        print(f"  RDF triples: {result.rdf_triples}")
    else:
        print(f"✗ Ingestion failed: {result.error}")

asyncio.run(ingest())
```

### Batch Ingestion

```python
async def batch_ingest():
    orchestrator = IngestionOrchestrator()
    
    documents = [
        "contracts/contract1.pdf",
        "contracts/contract2.pdf",
        "contracts/contract3.pdf"
    ]
    
    results = await orchestrator.ingest_batch(
        document_paths=documents,
        job_id="batch_001"
    )
    
    # Summary
    successful = sum(1 for r in results if r.success)
    total_clauses = sum(r.clauses_extracted for r in results)
    total_time = sum(r.total_duration_ms for r in results)
    
    print(f"Batch complete:")
    print(f"  Documents: {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Total clauses: {total_clauses}")
    print(f"  Total time: {total_time/1000:.1f}s")

asyncio.run(batch_ingest())
```

---

## Best Practices

### 1. Use Async/Await

```python
# ✅ Async (recommended)
result = await orchestrator.retrieve(question)

# ❌ Sync (blocks event loop)
result = asyncio.run(orchestrator.retrieve(question))
```

### 2. Enable Logging for Debugging

```python
# ✅ Enable logging
orchestrator = RetrievalOrchestrator(enable_logging=True)

# Check log files
result = await orchestrator.retrieve(question)
print(f"Log file: {result.log_file}")
```

### 3. Handle Errors Gracefully

```python
try:
    result = await orchestrator.retrieve(question)
    if not result.success:
        print(f"Query failed: {result.error}")
        # Fallback logic
except Exception as e:
    print(f"Orchestrator error: {e}")
```

### 4. Monitor Performance

```python
result = await orchestrator.retrieve(question)

if result.total_duration_ms > 10000:
    print(f"⚠️ Slow query: {result.total_duration_ms:.0f}ms")
    
    # Analyze steps
    for step in result.steps:
        if step.duration_ms > 2000:
            print(f"  Slow step: {step.step_name} ({step.duration_ms:.0f}ms)")
```

### 5. Use Appropriate Strategies

```python
# Simple queries - use KG_ONLY for speed
if is_simple_count_query(question):
    result = await orchestrator.retrieve(
        question,
        strategy=RetrievalStrategy.KG_ONLY
    )

# Complex queries - let orchestrator decide
else:
    result = await orchestrator.retrieve(question)
```

---

## Performance Optimization

### Parallel Batch Processing

```python
import asyncio

async def parallel_batch():
    orchestrator = RetrievalOrchestrator()
    
    questions = [
        "Question 1",
        "Question 2",
        "Question 3"
    ]
    
    # Process in parallel
    tasks = [orchestrator.retrieve(q) for q in questions]
    results = await asyncio.gather(*tasks)
    
    return results

# Much faster than sequential
results = asyncio.run(parallel_batch())
```

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_retrieve(question: str):
    return asyncio.run(orchestrator.retrieve(question))

# First call - hits orchestrator
result1 = cached_retrieve("What are the payment terms?")

# Second call - returns cached result
result2 = cached_retrieve("What are the payment terms?")  # Instant
```

---

## Troubleshooting

### Slow Queries

**Problem:** Queries taking >10 seconds

**Solutions:**
```python
# 1. Check strategy
result = await orchestrator.retrieve(question)
print(f"Strategy: {result.strategy.value}")

# 2. Analyze steps
for step in result.steps:
    print(f"{step.step_name}: {step.duration_ms:.0f}ms")

# 3. Force faster strategy
result = await orchestrator.retrieve(
    question,
    strategy=RetrievalStrategy.KG_ONLY
)
```

### Low Confidence

**Problem:** Low confidence scores

**Solutions:**
```python
# Check data sources
print(f"KG facts: {result.kg_facts_count}")
print(f"Vector contexts: {result.vector_context_count}")

# If low, may need more data or better embeddings
```

### Ingestion Failures

**Problem:** Documents failing to ingest

**Solutions:**
```python
result = await orchestrator.ingest_document(document_path)

if not result.success:
    print(f"Error: {result.error}")
    
    # Check steps
    for step in result.steps:
        if not step.success:
            print(f"Failed step: {step.step_name}")
            print(f"Error: {step.error}")
```

---

## See Also

- **[Ingestion Agents](ingestion_comprehensive.md)** - Individual ingestion agents
- **[Retrieval Agents](retrieval_comprehensive.md)** - Individual retrieval agents
- **[Configuration](../core/config_comprehensive.md)** - Orchestrator configuration
- **[SPARQL Store](../storage/sparql_comprehensive.md)** - Knowledge graph operations
- **[Vector Store](../storage/vector_comprehensive.md)** - Semantic search operations