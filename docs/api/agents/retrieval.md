# Retrieval Agents API Reference

Complete API reference for query processing and retrieval agents with examples.

---

## QueryClassifierAgent

Classify user queries to determine the best retrieval strategy.

### Class Definition

```python
from agents.retrieval.query_classifier import QueryClassifierAgent
from config import get_settings

agent = QueryClassifierAgent(settings=get_settings())
```

### Methods

#### `process(query: str) -> QueryClassification`

Classify a user query.

**Parameters:**

- `query` (str): User's natural language query

**Returns:**

- `QueryClassification`: Object containing query type and complexity

**Example:**

```python
from agents.retrieval.query_classifier import QueryClassifierAgent
from config import get_settings

async def classify_queries():
    agent = QueryClassifierAgent(settings=get_settings())
    
    queries = [
        "What are the payment terms in contract ABC123?",
        "Compare liability clauses across all Adobe contracts",
        "Find contracts with termination clauses and payment terms > 60 days"
    ]
    
    for query in queries:
        result = await agent.process(query)
        print(f"\nQuery: {query}")
        print(f"  Type: {result.query_type}")
        print(f"  Complexity: {result.complexity}")
        print(f"  Requires: {result.required_capabilities}")

# Run classification
asyncio.run(classify_queries())
```

**Output:**

```
Query: What are the payment terms in contract ABC123?
  Type: simple_lookup
  Complexity: low
  Requires: ['sparql']

Query: Compare liability clauses across all Adobe contracts
  Type: aggregation
  Complexity: medium
  Requires: ['sparql', 'vector_search']

Query: Find contracts with termination clauses and payment terms > 60 days
  Type: multi_hop
  Complexity: high
  Requires: ['sparql', 'vector_search', 'reasoning']
```

### Query Types

| Type | Description | Example |
|------|-------------|---------|
| `simple_lookup` | Direct entity lookup | "Show contract ABC123" |
| `semantic_search` | Similarity-based search | "Find contracts about data privacy" |
| `aggregation` | Aggregate across entities | "Count all active contracts" |
| `comparison` | Compare multiple entities | "Compare terms in contracts A and B" |
| `multi_hop` | Multi-step reasoning | "Find suppliers with late payments" |
| `temporal` | Time-based queries | "Show contracts expiring next month" |

### QueryClassification Model

```python
class QueryClassification(BaseModel):
    query_type: str                    # Type of query
    complexity: str                    # low, medium, high
    required_capabilities: List[str]   # Required retrieval methods
    entities: List[str]                # Detected entities
    intent: str                        # User's intent
    confidence: float                  # Classification confidence
```

---

## SPARQLGeneratorAgent

Generate SPARQL queries from natural language.

### Class Definition

```python
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from config import get_settings

agent = SPARQLGeneratorAgent(settings=get_settings())
```

### Methods

#### `process(input_data: dict) -> SPARQLQuery`

Generate SPARQL query from natural language.

**Parameters:**

- `input_data` (dict): Dictionary with:
    - `query`: Natural language query
    - `query_type`: Query type (from classifier)
    - `entities`: Detected entities (optional)

**Returns:**

- `SPARQLQuery`: Object containing generated SPARQL query

**Example:**

```python
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from config import get_settings

async def generate_sparql():
    agent = SPARQLGeneratorAgent(settings=get_settings())
    
    result = await agent.process({
        "query": "Find all contracts with Adobe as supplier",
        "query_type": "simple_lookup"
    })
    
    print("Generated SPARQL:")
    print(result.sparql)
    print(f"\nConfidence: {result.confidence}")

# Run generation
asyncio.run(generate_sparql())
```

**Output:**

```
Generated SPARQL:
PREFIX contract: <http://example.org/contract#>
PREFIX org: <http://example.org/organization#>

SELECT ?contract ?title ?date
WHERE {
  ?contract a contract:Contract ;
            contract:hasSupplier ?supplier ;
            contract:title ?title ;
            contract:effectiveDate ?date .
  ?supplier org:name "Adobe" .
}
ORDER BY DESC(?date)

Confidence: 0.92
```

### Complete Example with Execution

```python
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from fuseki_client import FusekiClient
from config import get_settings

async def query_contracts():
    settings = get_settings()
    
    # Generate SPARQL
    generator = SPARQLGeneratorAgent(settings=settings)
    sparql_result = await generator.process({
        "query": "Show payment terms for contract ABC123",
        "query_type": "simple_lookup"
    })
    
    # Execute query
    fuseki = FusekiClient(settings)
    results = fuseki.query(sparql_result.sparql)
    
    print(f"Found {len(results)} results:")
    for row in results:
        print(f"  - {row}")

asyncio.run(query_contracts())
```

---

## HybridRAGAgent

Combine SPARQL and vector search for comprehensive retrieval.

### Class Definition

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

agent = HybridRAGAgent(settings=get_settings())
```

### Methods

#### `process(query: str) -> HybridRAGResult`

Perform hybrid retrieval using both SPARQL and vector search.

**Parameters:**

- `query` (str): User's natural language query

**Returns:**

- `HybridRAGResult`: Combined results from both retrieval methods

**Example:**

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

async def hybrid_search():
    agent = HybridRAGAgent(settings=get_settings())
    
    result = await agent.process(
        "Find contracts with confidentiality clauses and payment terms"
    )
    
    print(f"SPARQL Results: {len(result.sparql_results)}")
    print(f"Vector Results: {len(result.vector_results)}")
    print(f"Combined Score: {result.combined_score}")
    
    print("\nTop 3 Results:")
    for i, item in enumerate(result.ranked_results[:3], 1):
        print(f"{i}. {item['title']} (score: {item['score']:.2f})")

asyncio.run(hybrid_search())
```

**Output:**

```
SPARQL Results: 15
Vector Results: 23
Combined Score: 0.87

Top 3 Results:
1. Master Services Agreement - Adobe (score: 0.94)
2. Participation Agreement - Salesforce (score: 0.89)
3. Amendment 001 - George P Johnson (score: 0.85)
```

### Retrieval Strategies

The agent automatically selects the best strategy:

```python
# Strategy 1: SPARQL-first (structured queries)
"Show all contracts signed in 2023"

# Strategy 2: Vector-first (semantic queries)
"Find contracts about data protection"

# Strategy 3: Hybrid (complex queries)
"Compare liability terms in Adobe and Salesforce contracts"
```

---

## ReActRetrievalAgent

Multi-step reasoning agent using ReAct pattern.

### Class Definition

```python
from agents.retrieval.react_retrieval import ReActRetrievalAgent
from config import get_settings

agent = ReActRetrievalAgent(settings=get_settings())
```

### Methods

#### `process(query: str) -> ReActResult`

Process complex queries using reasoning and action steps.

**Parameters:**

- `query` (str): Complex user query requiring multi-step reasoning

**Returns:**

- `ReActResult`: Result with reasoning steps and final answer

**Example:**

```python
from agents.retrieval.react_retrieval import ReActRetrievalAgent
from config import get_settings

async def complex_query():
    agent = ReActRetrievalAgent(settings=get_settings())
    
    result = await agent.process(
        "Which supplier has the most contracts with payment terms over 60 days?"
    )
    
    print("Reasoning Steps:")
    for i, step in enumerate(result.reasoning_steps, 1):
        print(f"\n{i}. {step.thought}")
        print(f"   Action: {step.action}")
        print(f"   Observation: {step.observation[:100]}...")
    
    print(f"\nFinal Answer: {result.final_answer}")

asyncio.run(complex_query())
```

**Output:**

```
Reasoning Steps:

1. I need to find all contracts with payment terms > 60 days
   Action: sparql_query
   Observation: Found 45 contracts with payment terms > 60 days...

2. Now I need to group these by supplier and count
   Action: aggregate_by_supplier
   Observation: Adobe: 18, Salesforce: 15, George P Johnson: 12...

3. Adobe has the most contracts meeting the criteria
   Action: verify_result
   Observation: Confirmed: Adobe has 18 contracts with payment terms > 60 days...

Final Answer: Adobe has the most contracts (18) with payment terms over 60 days.
```

### ReAct Pattern

The agent follows the Reasoning + Acting pattern:

1. **Thought**: Analyze what needs to be done
2. **Action**: Execute a tool or query
3. **Observation**: Process the result
4. **Repeat**: Until answer is found

---

## Complete Retrieval Pipeline

End-to-end retrieval example:

```python
import asyncio
from agents.retrieval.query_classifier import QueryClassifierAgent
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.hybrid_rag import HybridRAGAgent
from agents.retrieval.react_retrieval import ReActRetrievalAgent
from config import get_settings

async def intelligent_retrieval(user_query: str):
    """Intelligent query processing pipeline"""
    settings = get_settings()
    
    # Step 1: Classify query
    print("Step 1: Classifying query...")
    classifier = QueryClassifierAgent(settings=settings)
    classification = await classifier.process(user_query)
    print(f"  Type: {classification.query_type}")
    print(f"  Complexity: {classification.complexity}")
    
    # Step 2: Choose retrieval strategy
    print("\nStep 2: Retrieving information...")
    
    if classification.complexity == "low":
        # Simple SPARQL query
        generator = SPARQLGeneratorAgent(settings=settings)
        result = await generator.process({
            "query": user_query,
            "query_type": classification.query_type
        })
        print(f"  Used: SPARQL")
        return result
    
    elif classification.complexity == "medium":
        # Hybrid retrieval
        hybrid = HybridRAGAgent(settings=settings)
        result = await hybrid.process(user_query)
        print(f"  Used: Hybrid RAG")
        return result
    
    else:  # high complexity
        # Multi-step reasoning
        react = ReActRetrievalAgent(settings=settings)
        result = await react.process(user_query)
        print(f"  Used: ReAct")
        return result

# Test with different queries
queries = [
    "Show contract ABC123",  # Low complexity
    "Find contracts about data privacy",  # Medium complexity
    "Which supplier has the best payment terms?"  # High complexity
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)
    result = asyncio.run(intelligent_retrieval(query))
```

---

## Answer Generation

Generate natural language answers from retrieval results:

```python
from agents.retrieval.answer_generator import AnswerGeneratorAgent
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

async def generate_answer():
    settings = get_settings()
    
    # Retrieve information
    rag = HybridRAGAgent(settings=settings)
    retrieval_result = await rag.process(
        "What are the payment terms in Adobe contracts?"
    )
    
    # Generate natural language answer
    generator = AnswerGeneratorAgent(settings=settings)
    answer = await generator.process({
        "query": "What are the payment terms in Adobe contracts?",
        "context": retrieval_result.ranked_results
    })
    
    print(f"Answer: {answer.text}")
    print(f"\nSources:")
    for source in answer.sources:
        print(f"  - {source}")

asyncio.run(generate_answer())
```

**Output:**

```
Answer: Based on the Adobe contracts in the system, payment terms 
typically range from 30 to 60 days from invoice date. The Master 
Services Agreement specifies Net 30 terms, while some Participation 
Agreements allow up to 60 days for international transactions.

Sources:
  - Master Services Agreement - Adobe (2023-01-15)
  - Participation Agreement US - Adobe (2023-03-20)
  - Amendment 001 - Adobe (2023-06-10)
```

---

## Caching and Performance

### Enable Query Caching

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

# Enable caching for repeated queries
agent = HybridRAGAgent(
    settings=get_settings(),
    enable_cache=True,
    cache_ttl=3600  # 1 hour
)

# First call: retrieves from database
result1 = await agent.process("Find Adobe contracts")

# Second call: returns cached result (much faster)
result2 = await agent.process("Find Adobe contracts")
```

### Batch Queries

Process multiple queries efficiently:

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

async def batch_queries():
    agent = HybridRAGAgent(settings=get_settings())
    
    queries = [
        "Show Adobe contracts",
        "Find Salesforce agreements",
        "List George P Johnson contracts"
    ]
    
    # Process in parallel
    results = await asyncio.gather(*[
        agent.process(q) for q in queries
    ])
    
    for query, result in zip(queries, results):
        print(f"{query}: {len(result.ranked_results)} results")

asyncio.run(batch_queries())
```

---

## Error Handling

Handle retrieval errors gracefully:

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

async def safe_retrieval(query: str):
    agent = HybridRAGAgent(settings=get_settings())
    
    try:
        result = await agent.process(query)
        return result
    except ConnectionError:
        print("Database connection failed")
        return None
    except ValueError as e:
        print(f"Invalid query: {e}")
        return None
    except Exception as e:
        print(f"Retrieval failed: {e}")
        return None

result = asyncio.run(safe_retrieval("Find contracts"))
```

---

## Advanced Features

### Custom Ranking

Customize result ranking:

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

agent = HybridRAGAgent(settings=get_settings())

# Custom ranking weights
result = await agent.process(
    query="Find important contracts",
    ranking_weights={
        "sparql_score": 0.4,
        "vector_score": 0.3,
        "recency": 0.2,
        "importance": 0.1
    }
)
```

### Filter Results

Apply filters to retrieval:

```python
from agents.retrieval.hybrid_rag import HybridRAGAgent
from config import get_settings

agent = HybridRAGAgent(settings=get_settings())

result = await agent.process(
    query="Find contracts",
    filters={
        "supplier": "Adobe",
        "date_from": "2023-01-01",
        "date_to": "2023-12-31",
        "status": "active"
    }
)
```

---

## Performance Tips

### 1. Use Query Classification

Always classify queries first to choose the right strategy:

```python
# Good: Classify then retrieve
classification = await classifier.process(query)
if classification.complexity == "low":
    result = await sparql_agent.process(query)
else:
    result = await hybrid_agent.process(query)

# Avoid: Always using complex retrieval
result = await react_agent.process(query)  # Slow for simple queries!
```

### 2. Limit Result Size

Retrieve only what you need:

```python
result = await agent.process(
    query="Find contracts",
    limit=10  # Top 10 results only
)
```

### 3. Use Async Processing

Process multiple queries in parallel:

```python
# Good: Parallel processing
results = await asyncio.gather(*[
    agent.process(q) for q in queries
])

# Avoid: Sequential processing
results = []
for q in queries:
    results.append(await agent.process(q))  # Slow!
```

---

## See Also

- [Ingestion Agents API](ingestion.md)
- [Storage API](../storage/sparql.md)
- [Query & Retrieval Guide](../../guide/retrieval.md)