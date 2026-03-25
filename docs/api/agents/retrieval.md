# Retrieval Agents API Reference

Complete API reference for query processing and retrieval agents with comprehensive examples, parameter descriptions, and usage patterns.

---

## Table of Contents

- [LangGraphRetrievalOrchestrator](#langgraphretrievalorchestrator) - Main query orchestrator
- [ReActRetrievalAgent](#reactretrievalagent) - Multi-step reasoning agent
- [SPARQLGeneratorAgent](#sparqlgeneratoragent) - Natural language to SPARQL
- [QueryClassifier](#queryclassifier) - Query type classification
- [Complete Examples](#complete-examples) - End-to-end workflows

---

## LangGraphRetrievalOrchestrator

Main orchestrator for query processing using LangGraph workflow management.

### Class Definition

```python
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator

orchestrator = LangGraphRetrievalOrchestrator()
result = await orchestrator.process_query("What are the payment terms?")
```

**Purpose**: Coordinates the entire query processing pipeline with state management, observability, and error recovery.

**Parameters:**
- `sparql_store` (SPARQLStore, optional): SPARQL triple store
- `vector_store` (VectorStore, optional): Vector store for semantic search
- `settings` (Settings, optional): Application configuration
- `enable_logging` (bool, default=True): Enable structured logging
- `checkpoint_path` (str): Path for workflow checkpointing

**Key Features:**
- LangGraph workflow management
- Phoenix observability integration
- Iterative answer refinement (optional)
- Comprehensive timing metrics
- Error recovery and retry logic

**Performance:**
- Simple queries: 2-5 seconds
- Complex queries: 5-15 seconds
- With refinement: 10-30 seconds

### Methods

#### `process_query`

```python
async def process_query(
    query: str,
    max_results: int = 10,
    graph_uri: str | None = None
) -> dict[str, Any]
```

Process a natural language query and return answer with sources.

**Returns:** Dictionary with `answer`, `sources`, `reasoning_steps`, `metadata`

**Example:**
```python
result = await orchestrator.process_query(
    query="Find contracts with termination notice > 60 days",
    max_results=20
)

print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])}")
print(f"Time: {result['metadata']['processing_time']:.2f}s")
```

---

## ReActRetrievalAgent

Multi-step reasoning agent using the ReAct (Reasoning + Acting) pattern.

### Class Definition

```python
from agents.retrieval.react_agent_optimized import ReActRetrievalAgent

agent = ReActRetrievalAgent()
result = await agent.process({"question": "Which supplier has most contracts?"})
```

**Purpose**: Execute complex multi-step retrieval with reasoning, action, and observation cycles.

**Parameters:**
- `sparql_store` (SPARQLStore, optional): Knowledge graph store
- `vector_store` (VectorStore, optional): Semantic search store
- `settings` (Settings, optional): Configuration
- `llm` (BaseChatModel, optional): Language model

**Key Features:**
- Parallel sub-query execution
- Optimized answer synthesis
- Comprehensive timing breakdown
- Confidence scoring

**Action Types:**
- `SPARQL_QUERY`: Execute structured SPARQL
- `VECTOR_SEARCH`: Semantic similarity search
- `HYBRID_RETRIEVAL`: Combined approach
- `SYNTHESIZE`: Generate final answer

**Performance:**
- Simple: 1-2 iterations, 2-5 seconds
- Medium: 2-4 iterations, 5-10 seconds
- Complex: 4-8 iterations, 10-20 seconds

### Methods

#### `process`

```python
async def process(input_data: dict[str, Any]) -> ReActResult
```

Execute multi-step reasoning to answer a query.

**Input:** Dictionary with `question` (required), `max_results`, `decomposition_plan`

**Returns:** `ReActResult` with steps, answer, confidence, timing

**Example:**
```python
result = await agent.process({
    "question": "Compare payment terms across suppliers",
    "max_results": 50
})

print(f"Answer: {result.final_answer}")
print(f"Iterations: {result.total_iterations}")
print(f"Confidence: {result.confidence}")

for step in result.steps:
    print(f"Step {step.iteration}: {step.action_type}")
    print(f"  Duration: {step.duration_ms:.0f}ms")
```

---

## SPARQLGeneratorAgent

Convert natural language questions to SPARQL queries.

### Class Definition

```python
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent

agent = SPARQLGeneratorAgent()
result = await agent.generate_sparql("Find all Adobe contracts")
```

**Purpose**: Generate valid SPARQL queries from natural language with ontology awareness.

**Parameters:**
- `settings` (Settings, optional): Configuration
- `llm` (BaseChatModel, optional): Language model
- `sparql_store` (SPARQLStore, optional): For query execution

**Key Features:**
- Deep ontology knowledge
- Text index optimization
- Query explanation generation
- Template-based optimization

**Supported Query Types:**
- Simple lookups
- Filters and aggregations
- Text search
- Temporal queries
- Complex joins

**Performance:**
- Generation: 200-500ms
- Execution: 100ms-3s (depends on complexity)

### Methods

#### `generate_sparql`

```python
async def generate_sparql(
    question: str,
    query_type: str = "auto",
    max_results: int = 10
) -> SPARQLQuery
```

Generate SPARQL query from natural language.

**Returns:** `SPARQLQuery` with query string, type, explanation

**Example:**
```python
result = await agent.generate_sparql(
    question="Find contracts with value > 1000000",
    query_type="auto",
    max_results=50
)

print("Generated SPARQL:")
print(result.query)
print(f"\nExplanation: {result.explanation}")

# Execute the query
results = await agent.execute_sparql(result.query)
print(f"Found {len(results)} results")
```

---

## QueryClassifier

Classify queries to determine optimal retrieval strategy.

### Class Definition

```python
from agents.retrieval.query_classifier import QueryClassifier

classifier = QueryClassifier()
classification = classifier.classify("Find contracts with 30 days notice")
```

**Purpose**: Fast rule-based classification to route queries to optimal retrieval method.

**Routes:**
- `TEXT_INDEX`: Exact keywords/numbers (fast)
- `VECTOR`: Semantic/fuzzy queries
- `SPARQL`: Structured queries
- `HYBRID`: Complex multi-source queries

**Key Features:**
- Rule-based (no LLM calls)
- Fast (< 10ms)
- High accuracy (95%+)
- Pattern matching

**Performance:**
- Classification: < 10ms
- No API costs
- Deterministic results

### Methods

#### `classify`

```python
def classify(query: str) -> QueryClassification
```

Classify a query to determine retrieval strategy.

**Returns:** `QueryClassification` with route, confidence, reasoning

**Example:**
```python
result = classifier.classify(
    "Find contracts similar to Adobe master agreement"
)

print(f"Primary route: {result.primary_route}")
print(f"Confidence: {result.confidence}")
print(f"Reasoning: {result.reasoning}")
print(f"Semantic intent: {result.has_semantic_intent}")
print(f"Keywords: {result.detected_keywords}")
```

---

## Complete Examples

### Basic Query Processing

```python
import asyncio
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator

async def main():
    orchestrator = LangGraphRetrievalOrchestrator()
    
    result = await orchestrator.process_query(
        query="What are the termination notice periods?",
        max_results=10
    )
    
    print(f"Answer: {result['answer']}")
    print(f"\nSources ({len(result['sources'])}):")
    for source in result['sources'][:3]:
        print(f"  - {source.get('title', 'N/A')}")
    
    print(f"\nMetadata:")
    print(f"  Processing time: {result['metadata']['processing_time']:.2f}s")
    print(f"  KG facts: {result['metadata'].get('kg_facts_count', 0)}")
    print(f"  Vector results: {result['metadata'].get('vector_results_count', 0)}")

asyncio.run(main())
```

### Custom Retrieval Pipeline

```python
from agents.retrieval.query_classifier import QueryClassifier
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.react_agent_optimized import ReActRetrievalAgent

async def custom_pipeline(query: str):
    # Step 1: Classify
    classifier = QueryClassifier()
    classification = classifier.classify(query)
    
    print(f"Query type: {classification.primary_route}")
    
    # Step 2: Route
    if classification.primary_route == "SPARQL":
        sparql_agent = SPARQLGeneratorAgent()
        sparql_result = await sparql_agent.generate_sparql(query)
        results = await sparql_agent.execute_sparql(sparql_result.query)
        return {"results": results, "method": "SPARQL"}
    else:
        react_agent = ReActRetrievalAgent()
        result = await react_agent.process({"question": query})
        return {"answer": result.final_answer, "method": "REACT"}

result = asyncio.run(custom_pipeline("Find high-value contracts"))
```

### Performance Monitoring

```python
import time

async def monitor_performance():
    orchestrator = LangGraphRetrievalOrchestrator()
    
    queries = [
        "Simple: Show contract ABC123",
        "Medium: Find all Adobe contracts",
        "Complex: Compare terms across suppliers"
    ]
    
    for query in queries:
        start = time.time()
        result = await orchestrator.process_query(query)
        elapsed = time.time() - start
        
        print(f"\nQuery: {query}")
        print(f"  Time: {elapsed:.2f}s")
        print(f"  Answer length: {len(result['answer'])} chars")

asyncio.run(monitor_performance())
```

### Error Handling

```python
async def safe_query(query: str):
    orchestrator = LangGraphRetrievalOrchestrator()
    
    try:
        result = await orchestrator.process_query(query)
        return {"success": True, "result": result}
    except ValueError as e:
        return {"success": False, "error": "invalid_query"}
    except TimeoutError as e:
        return {"success": False, "error": "timeout"}
    except Exception as e:
        return {"success": False, "error": "unknown", "message": str(e)}

result = asyncio.run(safe_query("Find contracts"))
```

---

## Performance Tips

### 1. Cache Orchestrator Instance

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_orchestrator():
    return LangGraphRetrievalOrchestrator()

orchestrator = get_orchestrator()
```

### 2. Parallel Query Processing

```python
async def process_parallel(queries: list[str]):
    orchestrator = LangGraphRetrievalOrchestrator()
    results = await asyncio.gather(*[
        orchestrator.process_query(q) for q in queries
    ])
    return results
```

### 3. Enable Query Caching

```python
from config import Settings

settings = Settings(
    enable_query_cache=True,
    query_cache_ttl=3600
)
orchestrator = LangGraphRetrievalOrchestrator(settings=settings)
```

---

## See Also

- [Ingestion Agents API](ingestion.md) - Document ingestion
- [Storage API](../storage/sparql.md) - SPARQL operations
- [LLM Providers](../llm/providers.md) - LLM configuration
- [Configuration Guide](../../getting-started/configuration.md) - Setup