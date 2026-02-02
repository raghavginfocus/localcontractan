# Retrieval Agents API Reference

API documentation for query and retrieval agents.

## LangGraphRetrievalOrchestrator

Main orchestrator for query processing using LangGraph.

### Class Definition

```python
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator

class LangGraphRetrievalOrchestrator:
    """
    LangGraph-based orchestrator for hybrid RAG retrieval.
    
    Combines knowledge graph queries with vector similarity search
    to answer natural language questions about contracts.
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
    checkpoint_path: str = "checkpoints/retrieval.db"
)
```

**Parameters:**

- `sparql_store` (SPARQLStore, optional): SPARQL store instance
- `vector_store` (VectorStore, optional): Vector store instance
- `settings` (Settings, optional): Application settings
- `enable_logging` (bool): Enable detailed logging
- `checkpoint_path` (str): Path for state checkpointing

### Methods

#### query

```python
def query(
    self,
    question: str,
    graph_uri: str | None = None
) -> dict[str, Any]
```

Process a natural language query.

**Parameters:**

- `question` (str): Natural language question
- `graph_uri` (str, optional): Target graph URI

**Returns:**

- `dict`: Query results with answer and metadata

**Example:**

```python
orchestrator = LangGraphRetrievalOrchestrator(
    enable_logging=True
)

result = orchestrator.query(
    question="What are the termination clauses in IBM contracts?",
    graph_uri="http://example.org/contracts"
)

print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']}")
print(f"Duration: {result['total_duration_ms']}ms")
```

### Result Structure

```python
{
    # Answer
    "answer": str,
    "confidence": float,
    "success": bool,
    "error": str | None,
    
    # Query analysis
    "complexity": str,  # "simple" or "complex"
    "strategy": str,    # "template" or "react"
    "analysis_time_ms": float,
    
    # Results metadata
    "kg_facts_count": int,
    "vector_results_count": int,
    "sparql_query": str | None,
    
    # Timing
    "started_at": str,
    "completed_at": str,
    "total_duration_ms": float,
    
    # Logging
    "log_file": str | None
}
```

## ReActLangGraphAgent

ReAct agent for complex multi-step reasoning.

### Class Definition

```python
from agents.retrieval.react_agent_langgraph import ReActLangGraphAgent

class ReActLangGraphAgent(BaseAgent):
    """
    LangGraph-based ReAct agent for complex retrieval.
    
    Uses thought-action-observation loops to break down
    complex queries into manageable steps.
    """
```

### Constructor

```python
def __init__(
    self,
    sparql_store: SPARQLStore | None = None,
    vector_store: VectorStore | None = None,
    sparql_agent: SPARQLGeneratorAgent | None = None,
    enable_checkpointing: bool = False,
    checkpoint_db_path: str = "./checkpoints/react_agent.db",
    **kwargs
)
```

**Parameters:**

- `sparql_store` (SPARQLStore, optional): SPARQL store
- `vector_store` (VectorStore, optional): Vector store
- `sparql_agent` (SPARQLGeneratorAgent, optional): SPARQL generator
- `enable_checkpointing` (bool): Enable state persistence
- `checkpoint_db_path` (str): Checkpoint database path

### Methods

#### query

```python
def query(
    self,
    question: str,
    sub_queries: list[dict] | None = None,
    max_iterations: int = 10
) -> dict[str, Any]
```

Execute ReAct reasoning loop.

**Parameters:**

- `question` (str): Natural language question
- `sub_queries` (list, optional): Pre-decomposed sub-queries
- `max_iterations` (int): Maximum reasoning iterations

**Returns:**

- `dict`: Query results with reasoning steps

**Example:**

```python
agent = ReActLangGraphAgent()

result = agent.query(
    question="Compare payment terms across IBM and Oracle contracts"
)

print(f"Answer: {result['final_answer']}")
print(f"Steps: {len(result['steps'])}")
```

## SPARQLGeneratorAgent

Generates SPARQL queries from natural language.

### Class Definition

```python
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent

class SPARQLGeneratorAgent(BaseAgent):
    """Generate SPARQL queries from natural language questions."""
```

### Methods

#### generate

```python
def generate(
    self,
    question: str,
    intent: str | None = None,
    context: dict[str, Any] | None = None
) -> str
```

Generate SPARQL query.

**Parameters:**

- `question` (str): Natural language question
- `intent` (str, optional): Query intent (e.g., "list_contracts")
- `context` (dict, optional): Additional context

**Returns:**

- `str`: SPARQL query

**Example:**

```python
agent = SPARQLGeneratorAgent()

query = agent.generate(
    question="Find contracts with IBM",
    intent="find_contract",
    context={"party_name": "IBM Corporation"}
)

print(query)
```

#### generate_from_template

```python
def generate_from_template(
    self,
    intent: str,
    params: dict[str, Any]
) -> str
```

Generate query from template.

**Parameters:**

- `intent` (str): Template intent
- `params` (dict): Template parameters

**Returns:**

- `str`: SPARQL query

**Example:**

```python
query = agent.generate_from_template(
    intent="list_contracts",
    params={"min_value": 1000000}
)
```

## QueryClassifier

Classifies query intent and complexity.

### Class Definition

```python
from agents.retrieval.query_classifier import QueryClassifier

class QueryClassifier:
    """Classify query intent and complexity."""
```

### Methods

#### classify

```python
def classify(
    self,
    question: str
) -> str
```

Classify query intent.

**Parameters:**

- `question` (str): Natural language question

**Returns:**

- `str`: Intent classification

**Example:**

```python
classifier = QueryClassifier()

intent = classifier.classify("List all contracts")
# Returns: "list_contracts"

intent = classifier.classify("Analyze risks in IBM contracts")
# Returns: "analyze_risks"
```

**Intent Types:**

- `list_contracts` - List all contracts
- `find_contract` - Find specific contract
- `list_clauses` - List clauses by type
- `find_party` - Find contracts by party
- `get_details` - Get contract details
- `analyze_*` - Analysis queries (complex)
- `compare_*` - Comparison queries (complex)
- `summarize_*` - Summarization queries (complex)

#### detect_complexity

```python
def detect_complexity(
    self,
    question: str
) -> str
```

Detect query complexity.

**Parameters:**

- `question` (str): Natural language question

**Returns:**

- `str`: "simple" or "complex"

**Example:**

```python
complexity = classifier.detect_complexity("List all contracts")
# Returns: "simple"

complexity = classifier.detect_complexity("Compare payment terms")
# Returns: "complex"
```

## SynthesisOptimizer

Generates natural language answers from retrieved data.

### Class Definition

```python
from agents.retrieval.synthesis_optimizer import SynthesisOptimizer

class SynthesisOptimizer(BaseAgent):
    """Synthesize natural language answers from retrieved facts."""
```

### Methods

#### synthesize

```python
def synthesize(
    self,
    question: str,
    kg_facts: list[dict],
    vector_results: list[dict],
    context: dict[str, Any] | None = None
) -> SynthesisResult
```

Generate answer from facts.

**Parameters:**

- `question` (str): Original question
- `kg_facts` (list): Knowledge graph facts
- `vector_results` (list): Vector search results
- `context` (dict, optional): Additional context

**Returns:**

- `SynthesisResult`: Generated answer with metadata

**Example:**

```python
synthesizer = SynthesisOptimizer()

answer = synthesizer.synthesize(
    question="What are the termination clauses?",
    kg_facts=kg_results,
    vector_results=vector_results,
    context={"contract_count": 5}
)

print(f"Answer: {answer.text}")
print(f"Confidence: {answer.confidence}")
```

#### Result Model

```python
class SynthesisResult(BaseModel):
    text: str
    confidence: float
    citations: list[str]
    synthesis_time_ms: float
    token_count: int
```

## QueryDecomposer

Decomposes complex queries into sub-queries.

### Class Definition

```python
from agents.retrieval.query_decomposer import QueryDecomposer

class QueryDecomposer(BaseAgent):
    """Decompose complex queries into manageable sub-queries."""
```

### Methods

#### decompose

```python
def decompose(
    self,
    question: str
) -> list[dict[str, Any]]
```

Decompose query into sub-queries.

**Parameters:**

- `question` (str): Complex question

**Returns:**

- `list[dict]`: List of sub-queries

**Example:**

```python
decomposer = QueryDecomposer()

sub_queries = decomposer.decompose(
    "Compare payment terms between IBM and Oracle contracts"
)

for sq in sub_queries:
    print(f"Step {sq['step']}: {sq['query']}")
```

**Sub-query Structure:**

```python
{
    "step": int,
    "query": str,
    "type": str,  # "kg_query", "vector_search", "synthesis"
    "dependencies": list[int],
    "params": dict[str, Any]
}
```

## ComplexityDetector

Detects query complexity for routing.

### Class Definition

```python
from agents.retrieval.complexity_detector import ComplexityDetector

class ComplexityDetector:
    """Detect query complexity for routing decisions."""
```

### Methods

#### detect

```python
def detect(
    self,
    question: str
) -> dict[str, Any]
```

Detect query complexity.

**Parameters:**

- `question` (str): Natural language question

**Returns:**

- `dict`: Complexity analysis

**Example:**

```python
detector = ComplexityDetector()

analysis = detector.detect(
    "What are the high-risk clauses in contracts over $1M?"
)

print(f"Complexity: {analysis['complexity']}")
print(f"Reasoning: {analysis['reasoning']}")
```

**Result Structure:**

```python
{
    "complexity": str,  # "simple" or "complex"
    "score": float,     # 0.0 to 1.0
    "reasoning": str,
    "indicators": {
        "multi_hop": bool,
        "aggregation": bool,
        "comparison": bool,
        "temporal": bool,
        "cross_document": bool
    }
}
```

## UnifiedQueryAnalyzer

Unified query analysis combining classification and decomposition.

### Class Definition

```python
from agents.retrieval.unified_query_analyzer import UnifiedQueryAnalyzer

class UnifiedQueryAnalyzer(BaseAgent):
    """Unified query analysis for routing and planning."""
```

### Methods

#### analyze

```python
def analyze(
    self,
    question: str
) -> QueryAnalysisResult
```

Perform complete query analysis.

**Parameters:**

- `question` (str): Natural language question

**Returns:**

- `QueryAnalysisResult`: Complete analysis

**Example:**

```python
analyzer = UnifiedQueryAnalyzer()

analysis = analyzer.analyze(
    "Find high-value contracts with termination clauses"
)

print(f"Intent: {analysis.intent}")
print(f"Complexity: {analysis.complexity}")
print(f"Strategy: {analysis.strategy}")
```

#### Result Model

```python
class QueryAnalysisResult(BaseModel):
    intent: str
    complexity: str
    strategy: str  # "template", "react", "hybrid"
    sub_queries: list[dict]
    confidence: float
    analysis_time_ms: float
```

## See Also

- [Ingestion Agents API](../api/agents/ingestion.md)
- [Schema Evolution Agents API](../api/agents/schema-evolution.md)
- [Retrieval Guide](../../guide/retrieval.md)
- [Hybrid RAG Architecture](../../architecture/hybrid-rag.md)