# SPARQL Store API Reference

Comprehensive API documentation for Apache Jena Fuseki SPARQL client and triple store operations.

## Overview

The SPARQL Store module provides a Python interface to Apache Jena Fuseki for managing RDF knowledge graphs. It supports SPARQL queries, updates, RDF data loading, and full-text search with jena-text indexing.

**Key Features:**
- SPARQL SELECT, CONSTRUCT, ASK, and UPDATE operations
- RDF data loading (Turtle, JSON-LD, RDF/XML)
- Named graph management
- Full-text search with jena-text
- Contract and clause-specific operations
- Authentication support
- Comprehensive error handling

---

## FusekiClient

Main client for interacting with Apache Jena Fuseki SPARQL server.

### Class Definition

```python
from fuseki_client import FusekiClient

class FusekiClient:
    """
    Client for interacting with Apache Jena Fuseki SPARQL server.
    
    Provides methods for:
    - Executing SPARQL SELECT queries
    - Executing SPARQL CONSTRUCT queries
    - Executing SPARQL UPDATE operations
    - Loading RDF data (Turtle, JSON-LD, RDF/XML)
    - Managing named graphs
    - Full-text search with jena-text
    """
```

### Constructor

```python
def __init__(
    self,
    settings: Settings | None = None
)
```

Initialize the Fuseki client with configuration settings.

**Parameters:**

- **settings** : `Settings | None`, default=`None`
  - Configuration settings object. If None, uses default settings from environment.
  - Contains endpoints, authentication, and namespace configuration.

**Attributes:**

- **query_endpoint** : `str`
  - SPARQL query endpoint URL (e.g., "http://localhost:3030/contracts/query")
  
- **update_endpoint** : `str`
  - SPARQL update endpoint URL (e.g., "http://localhost:3030/contracts/update")
  
- **graph_store_endpoint** : `str`
  - Graph Store Protocol endpoint URL
  
- **auth** : `tuple[str, str] | None`
  - HTTP Basic authentication credentials (username, password)
  
- **PROC** : `Namespace`
  - Procurement ontology namespace
  
- **CONTRACT** : `Namespace`
  - Contract instance namespace

**Example:**

```python
from fuseki_client import FusekiClient
from config import get_settings

# Use default settings
client = FusekiClient()

# Use custom settings
settings = get_settings()
settings.fuseki_user = "admin"
settings.fuseki_password = "secret"
client = FusekiClient(settings=settings)

print(f"Query endpoint: {client.query_endpoint}")
print(f"Update endpoint: {client.update_endpoint}")
```

**Performance:**
- Initialization time: ~50ms
- Memory footprint: ~10MB

---

## Query Operations

### execute_select

```python
def execute_select(
    self,
    query: str,
    add_prefixes: bool = True
) -> list[dict[str, Any]]
```

Execute a SPARQL SELECT query and return results as list of dictionaries.

**Parameters:**

- **query** : `str`
  - SPARQL SELECT query string
  - Should not include PREFIX declarations if `add_prefixes=True`
  
- **add_prefixes** : `bool`, default=`True`
  - Whether to prepend common namespace prefixes automatically
  - Prefixes include: rdf, rdfs, owl, xsd, proc, contract, text

**Returns:**

- **results** : `list[dict[str, Any]]`
  - List of result bindings, where each dict maps variable names to values
  - Values are automatically converted from RDF types to Python types

**Raises:**

- **Exception**
  - If query execution fails (network error, syntax error, timeout)
  - Original exception is logged and re-raised

**Example:**

```python
# Simple SELECT query
query = """
SELECT ?contract ?value
WHERE {
    ?contract a proc:Contract ;
              proc:contractValue ?value .
    FILTER(?value > 100000)
}
LIMIT 10
"""

results = client.execute_select(query)

for row in results:
    print(f"Contract: {row['contract']}")
    print(f"Value: {row['value']}")

# Output:
# Contract: http://procurement.kg/contract#ABC123
# Value: 150000.00
# Contract: http://procurement.kg/contract#XYZ789
# Value: 250000.00
```

**Advanced Example - Aggregation:**

```python
# Count contracts by jurisdiction
query = """
SELECT ?jurisdiction (COUNT(?contract) as ?count)
WHERE {
    ?contract a proc:Contract ;
              proc:governedBy ?jurisdiction .
}
GROUP BY ?jurisdiction
ORDER BY DESC(?count)
"""

results = client.execute_select(query)

for row in results:
    print(f"{row['jurisdiction']}: {row['count']} contracts")

# Output:
# http://procurement.kg/ontology#US: 45 contracts
# http://procurement.kg/ontology#EU: 32 contracts
```

**Performance:**
- Simple queries: 50-200ms
- Complex joins: 500-2000ms
- Aggregations: 200-1000ms

---

### execute_construct

```python
def execute_construct(
    self,
    query: str,
    add_prefixes: bool = True
) -> Graph
```

Execute a SPARQL CONSTRUCT query and return an RDFLib Graph.

**Parameters:**

- **query** : `str`
  - SPARQL CONSTRUCT query string
  
- **add_prefixes** : `bool`, default=`True`
  - Whether to prepend common namespace prefixes

**Returns:**

- **graph** : `Graph`
  - RDFLib Graph containing constructed triples
  - Can be serialized to various formats (Turtle, JSON-LD, etc.)

**Raises:**

- **Exception**
  - If query execution or graph parsing fails

**Example:**

```python
from rdflib import Graph

# Construct subgraph of high-value contracts
query = """
CONSTRUCT {
    ?contract a proc:Contract ;
              proc:contractValue ?value ;
              proc:hasClause ?clause .
    ?clause a ?clauseType .
}
WHERE {
    ?contract a proc:Contract ;
              proc:contractValue ?value ;
              proc:hasClause ?clause .
    ?clause a ?clauseType .
    FILTER(?value > 500000)
}
"""

graph = client.execute_construct(query)

print(f"Constructed {len(graph)} triples")

# Serialize to Turtle
turtle_data = graph.serialize(format="turtle")
print(turtle_data)

# Save to file
graph.serialize("high_value_contracts.ttl", format="turtle")
```

**Use Cases:**
- Extract subgraphs for analysis
- Transform data between ontologies
- Export data for external systems
- Create materialized views

**Performance:**
- Small graphs (<1000 triples): 100-300ms
- Medium graphs (1000-10000 triples): 500-2000ms
- Large graphs (>10000 triples): 2-10 seconds

---

### execute_ask

```python
def execute_ask(
    self,
    query: str,
    add_prefixes: bool = True
) -> bool
```

Execute a SPARQL ASK query and return boolean result.

**Parameters:**

- **query** : `str`
  - SPARQL ASK query string
  
- **add_prefixes** : `bool`, default=`True`
  - Whether to prepend common namespace prefixes

**Returns:**

- **result** : `bool`
  - True if the query pattern matches, False otherwise

**Raises:**

- **Exception**
  - If query execution fails

**Example:**

```python
# Check if contract exists
query = """
ASK {
    <http://procurement.kg/contract#ABC123> a proc:Contract .
}
"""

exists = client.execute_ask(query)
print(f"Contract exists: {exists}")

# Check for high-risk clauses
query = """
ASK {
    ?contract proc:hasClause ?clause .
    ?clause proc:introducesRisk proc:HighRisk .
}
"""

has_high_risk = client.execute_ask(query)
if has_high_risk:
    print("⚠️ High-risk clauses detected!")
```

**Use Cases:**
- Validation checks
- Existence queries
- Compliance verification
- Quick boolean tests

**Performance:**
- Typical execution: 20-100ms
- Faster than SELECT for boolean checks

---

## Update Operations

### execute_update

```python
def execute_update(
    self,
    update: str,
    add_prefixes: bool = True
) -> bool
```

Execute a SPARQL UPDATE operation (INSERT, DELETE, MODIFY).

**Parameters:**

- **update** : `str`
  - SPARQL UPDATE statement
  - Supports INSERT DATA, DELETE DATA, INSERT/DELETE WHERE
  
- **add_prefixes** : `bool`, default=`True`
  - Whether to prepend common namespace prefixes

**Returns:**

- **success** : `bool`
  - True if update executed successfully

**Raises:**

- **Exception**
  - If update fails (syntax error, permission denied, constraint violation)

**Example:**

```python
# Insert new contract
update = """
INSERT DATA {
    GRAPH <http://example.org/contracts> {
        proc:Contract_NEW123 a proc:Contract ;
            proc:contractId "NEW123" ;
            proc:contractValue "250000.00"^^xsd:decimal ;
            proc:effectiveDate "2024-01-01"^^xsd:date .
    }
}
"""

success = client.execute_update(update)
print(f"Insert successful: {success}")

# Update contract value
update = """
DELETE {
    ?contract proc:contractValue ?oldValue .
}
INSERT {
    ?contract proc:contractValue "300000.00"^^xsd:decimal .
}
WHERE {
    ?contract proc:contractId "NEW123" ;
              proc:contractValue ?oldValue .
}
"""

client.execute_update(update)
```

**Advanced Example - Conditional Update:**

```python
# Add risk flag to clauses with short notice periods
update = """
INSERT {
    ?clause proc:introducesRisk proc:ShortNoticeRisk .
}
WHERE {
    ?clause a proc:TerminationClause ;
            proc:noticePeriod ?days .
    FILTER(?days < 30)
    FILTER NOT EXISTS {
        ?clause proc:introducesRisk proc:ShortNoticeRisk .
    }
}
"""

client.execute_update(update)
```

**Performance:**
- Simple inserts: 50-200ms
- Complex updates: 200-1000ms
- Bulk operations: 1-5 seconds

---

## Data Loading

### load_turtle

```python
def load_turtle(
    self,
    turtle_data: str,
    graph_uri: str | None = None
) -> bool
```

Load Turtle RDF data into the triple store.

**Parameters:**

- **turtle_data** : `str`
  - RDF data in Turtle format
  - Must be valid Turtle syntax
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI
  - If None, loads into default graph

**Returns:**

- **success** : `bool`
  - True if data loaded successfully

**Raises:**

- **Exception**
  - If loading fails (invalid syntax, network error, permission denied)

**Example:**

```python
# Load Turtle data
turtle_data = """
@prefix proc: <http://procurement.kg/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

<http://procurement.kg/contract#ABC123> a proc:Contract ;
    proc:contractId "ABC123" ;
    proc:contractValue "150000.00"^^xsd:decimal ;
    proc:effectiveDate "2024-01-01"^^xsd:date ;
    proc:expirationDate "2025-01-01"^^xsd:date .
"""

success = client.load_turtle(
    turtle_data=turtle_data,
    graph_uri="http://example.org/contracts"
)

print(f"Loaded successfully: {success}")
```

**Batch Loading:**

```python
# Load multiple contracts
contracts = []
for i in range(100):
    contracts.append(f"""
<http://procurement.kg/contract#C{i:04d}> a proc:Contract ;
    proc:contractId "C{i:04d}" ;
    proc:contractValue "{10000 + i * 1000}"^^xsd:decimal .
""")

turtle_data = "\n".join(contracts)
client.load_turtle(turtle_data, "http://example.org/batch")
```

**Performance:**
- Small files (<1MB): 100-500ms
- Medium files (1-10MB): 1-5 seconds
- Large files (>10MB): 5-30 seconds

---

### load_graph

```python
def load_graph(
    self,
    graph: Graph,
    graph_uri: str | None = None
) -> bool
```

Load an RDFLib Graph into the triple store.

**Parameters:**

- **graph** : `Graph`
  - RDFLib Graph object containing triples
  
- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI

**Returns:**

- **success** : `bool`
  - True if graph loaded successfully

**Example:**

```python
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, XSD

# Create graph programmatically
g = Graph()
PROC = Namespace("http://procurement.kg/ontology#")
g.bind("proc", PROC)

contract_uri = URIRef("http://procurement.kg/contract#ABC123")
g.add((contract_uri, RDF.type, PROC.Contract))
g.add((contract_uri, PROC.contractId, Literal("ABC123")))
g.add((contract_uri, PROC.contractValue, Literal("150000.00", datatype=XSD.decimal)))

# Load into Fuseki
success = client.load_graph(
    graph=g,
    graph_uri="http://example.org/contracts"
)

print(f"Loaded {len(g)} triples")
```

**Performance:**
- Converts graph to Turtle internally
- Similar performance to `load_turtle`

---

## Contract Operations

### insert_contract

```python
def insert_contract(
    self,
    contract_id: str,
    value: float | None = None,
    effective_date: str | None = None,
    expiration_date: str | None = None,
    jurisdiction: str | None = None
) -> str
```

Insert a new contract into the knowledge graph with common properties.

**Parameters:**

- **contract_id** : `str`
  - Unique identifier for the contract
  - Used to construct the contract URI
  
- **value** : `float | None`, default=`None`
  - Contract value in decimal format
  
- **effective_date** : `str | None`, default=`None`
  - ISO 8601 date string (YYYY-MM-DD)
  
- **expiration_date** : `str | None`, default=`None`
  - ISO 8601 date string (YYYY-MM-DD)
  
- **jurisdiction** : `str | None`, default=`None`
  - Jurisdiction identifier (e.g., 'US', 'EU', 'UK')

**Returns:**

- **contract_uri** : `str`
  - Full URI of the created contract

**Example:**

```python
# Insert basic contract
contract_uri = client.insert_contract(
    contract_id="ABC123",
    value=150000.00,
    effective_date="2024-01-01",
    expiration_date="2025-01-01",
    jurisdiction="US"
)

print(f"Created contract: {contract_uri}")
# Output: http://procurement.kg/contract#ABC123

# Insert minimal contract
contract_uri = client.insert_contract(
    contract_id="MIN456",
    value=50000.00
)
```

**Batch Insert:**

```python
# Insert multiple contracts
contract_ids = []
for i in range(100):
    uri = client.insert_contract(
        contract_id=f"BATCH{i:04d}",
        value=10000 + i * 1000,
        effective_date="2024-01-01",
        jurisdiction="US"
    )
    contract_ids.append(uri)

print(f"Inserted {len(contract_ids)} contracts")
```

**Performance:**
- Single insert: 50-150ms
- Batch of 100: 5-15 seconds

---

### insert_clause

```python
def insert_clause(
    self,
    clause_id: str,
    contract_uri: str,
    clause_type: str,
    raw_text: str,
    notice_period: int | None = None
) -> str
```

Insert a clause into the knowledge graph and link it to a contract.

**Parameters:**

- **clause_id** : `str`
  - Unique identifier for the clause
  
- **contract_uri** : `str`
  - Full URI of the parent contract
  
- **clause_type** : `str`
  - Type of clause (e.g., 'TerminationClause', 'PaymentClause')
  - Must match ontology class names
  
- **raw_text** : `str`
  - Original text content of the clause
  - Automatically escaped for SPARQL
  
- **notice_period** : `int | None`, default=`None`
  - For termination clauses, the notice period in days

**Returns:**

- **clause_uri** : `str`
  - Full URI of the created clause

**Example:**

```python
# Insert termination clause
clause_uri = client.insert_clause(
    clause_id="TERM_001",
    contract_uri="http://procurement.kg/contract#ABC123",
    clause_type="TerminationClause",
    raw_text="Either party may terminate this agreement with 30 days written notice.",
    notice_period=30
)

print(f"Created clause: {clause_uri}")

# Insert payment clause
clause_uri = client.insert_clause(
    clause_id="PAY_001",
    contract_uri="http://procurement.kg/contract#ABC123",
    clause_type="PaymentClause",
    raw_text="Payment is due within 30 days of invoice date."
)
```

**Batch Insert:**

```python
# Insert multiple clauses for a contract
contract_uri = "http://procurement.kg/contract#ABC123"
clauses = [
    ("TERM_001", "TerminationClause", "Termination text...", 30),
    ("PAY_001", "PaymentClause", "Payment text...", None),
    ("CONF_001", "ConfidentialityClause", "Confidentiality text...", None),
]

for clause_id, clause_type, text, notice in clauses:
    client.insert_clause(
        clause_id=clause_id,
        contract_uri=contract_uri,
        clause_type=clause_type,
        raw_text=text,
        notice_period=notice
    )
```

**Performance:**
- Single insert: 50-150ms
- Text escaping overhead: ~5ms

---

## Analysis Operations

### get_contract_risks

```python
def get_contract_risks(
    self,
    contract_uri: str
) -> list[dict[str, Any]]
```

Get all risks associated with a contract's clauses.

**Parameters:**

- **contract_uri** : `str`
  - Full URI of the contract

**Returns:**

- **risks** : `list[dict[str, Any]]`
  - List of risk information dictionaries with keys:
    - `clause`: Clause URI
    - `clauseType`: Type of clause
    - `risk`: Risk URI
    - `riskLabel`: Human-readable risk description

**Example:**

```python
contract_uri = "http://procurement.kg/contract#ABC123"
risks = client.get_contract_risks(contract_uri)

print(f"Found {len(risks)} risks:")
for risk in risks:
    print(f"  Clause: {risk['clause']}")
    print(f"  Type: {risk['clauseType']}")
    print(f"  Risk: {risk.get('riskLabel', 'Unknown')}")
    print()

# Output:
# Found 2 risks:
#   Clause: http://procurement.kg/contract#TERM_001
#   Type: http://procurement.kg/ontology#TerminationClause
#   Risk: Short notice period (30 days)
#
#   Clause: http://procurement.kg/contract#LIA_001
#   Type: http://procurement.kg/ontology#LiabilityClause
#   Risk: Unlimited liability exposure
```

**Use Cases:**
- Risk assessment dashboards
- Contract review workflows
- Compliance reporting
- Automated alerts

**Performance:**
- Typical execution: 50-200ms
- Depends on number of clauses

---

### get_compliance_issues

```python
def get_compliance_issues(
    self,
    contract_uri: str
) -> list[dict[str, Any]]
```

Get all compliance issues for a contract.

**Parameters:**

- **contract_uri** : `str`
  - Full URI of the contract

**Returns:**

- **issues** : `list[dict[str, Any]]`
  - List of compliance issue dictionaries with keys:
    - `issue`: Issue URI
    - `issueLabel`: Human-readable issue description

**Example:**

```python
contract_uri = "http://procurement.kg/contract#ABC123"
issues = client.get_compliance_issues(contract_uri)

if issues:
    print(f"⚠️ Found {len(issues)} compliance issues:")
    for issue in issues:
        print(f"  - {issue.get('issueLabel', issue['issue'])}")
else:
    print("✅ No compliance issues found")

# Output:
# ⚠️ Found 2 compliance issues:
#   - Missing data protection clause (GDPR requirement)
#   - Jurisdiction mismatch with company policy
```

**Performance:**
- Typical execution: 50-150ms

---

### search_contracts

```python
def search_contracts(
    self,
    jurisdiction: str | None = None,
    min_value: float | None = None,
    has_risk: str | None = None
) -> list[dict[str, Any]]
```

Search contracts with various filters.

**Parameters:**

- **jurisdiction** : `str | None`, default=`None`
  - Filter by jurisdiction (e.g., 'US', 'EU')
  
- **min_value** : `float | None`, default=`None`
  - Minimum contract value
  
- **has_risk** : `str | None`, default=`None`
  - Filter by risk type (e.g., 'HighRisk', 'ShortNoticeRisk')

**Returns:**

- **contracts** : `list[dict[str, Any]]`
  - List of matching contracts with keys:
    - `contract`: Contract URI
    - `value`: Contract value (if available)
    - `jurisdiction`: Jurisdiction URI (if available)

**Example:**

```python
# Find high-value US contracts
contracts = client.search_contracts(
    jurisdiction="US",
    min_value=100000.00
)

print(f"Found {len(contracts)} contracts:")
for contract in contracts:
    print(f"  {contract['contract']}: ${contract.get('value', 'N/A')}")

# Find contracts with high risk
risky_contracts = client.search_contracts(
    has_risk="HighRisk"
)

print(f"Found {len(risky_contracts)} high-risk contracts")

# Combined filters
contracts = client.search_contracts(
    jurisdiction="EU",
    min_value=50000.00,
    has_risk="ShortNoticeRisk"
)
```

**Performance:**
- Simple filters: 100-300ms
- Multiple filters: 200-500ms
- Depends on dataset size

---

## Graph Management

### get_triple_count

```python
def get_triple_count(
    self,
    graph_uri: str | None = None
) -> int
```

Get the total number of triples in a graph.

**Parameters:**

- **graph_uri** : `str | None`, default=`None`
  - Optional named graph URI
  - If None, counts triples in default graph

**Returns:**

- **count** : `int`
  - Number of triples

**Example:**

```python
# Count triples in default graph
total = client.get_triple_count()
print(f"Total triples: {total:,}")

# Count triples in named graph
count = client.get_triple_count("http://example.org/contracts")
print(f"Contracts graph: {count:,} triples")

# Monitor graph growth
import time

initial = client.get_triple_count()
# ... perform operations ...
time.sleep(1)
final = client.get_triple_count()

print(f"Added {final - initial:,} triples")
```

**Performance:**
- Execution time: 20-100ms
- Scales with dataset size

---

### delete_graph

```python
def delete_graph(
    self,
    graph_uri: str
) -> bool
```

Delete all triples from a named graph.

**Parameters:**

- **graph_uri** : `str`
  - URI of the graph to delete

**Returns:**

- **success** : `bool`
  - True if deletion successful

**Raises:**

- **Exception**
  - If deletion fails

**Example:**

```python
# Delete a named graph
success = client.delete_graph("http://example.org/old_contracts")

if success:
    print("Graph deleted successfully")
else:
    print("Failed to delete graph")

# Safe deletion with confirmation
graph_uri = "http://example.org/test_data"
count = client.get_triple_count(graph_uri)

if count > 0:
    confirm = input(f"Delete {count:,} triples? (yes/no): ")
    if confirm.lower() == "yes":
        client.delete_graph(graph_uri)
        print("Deleted")
```

**Warning:**
- This operation is irreversible
- Use with caution in production
- Consider backup before deletion

**Performance:**
- Small graphs (<10K triples): 100-500ms
- Large graphs (>100K triples): 1-10 seconds

---

### list_graphs

```python
def list_graphs(self) -> list[str]
```

List all named graphs in the dataset.

**Returns:**

- **graphs** : `list[str]`
  - List of graph URIs

**Example:**

```python
graphs = client.list_graphs()

print(f"Found {len(graphs)} named graphs:")
for graph_uri in graphs:
    count = client.get_triple_count(graph_uri)
    print(f"  {graph_uri}: {count:,} triples")

# Output:
# Found 3 named graphs:
#   http://example.org/contracts: 15,234 triples
#   http://example.org/suppliers: 8,456 triples
#   http://example.org/metadata: 1,023 triples
```

**Performance:**
- Execution time: 50-200ms

---

## Full-Text Search

### text_search

```python
def text_search(
    self,
    search_term: str,
    field: str = "text",
    clause_type: str | None = None,
    limit: int = 10
) -> list[dict[str, Any]]
```

Fast text search using jena-text index.

**Parameters:**

- **search_term** : `str`
  - Text to search for
  - Supports Lucene query syntax
  
- **field** : `str`, default=`"text"`
  - Which field to search: "text", "summary", "keyPoint"
  
- **clause_type** : `str | None`, default=`None`
  - Optional clause type filter (e.g., "TerminationClause")
  
- **limit** : `int`, default=`10`
  - Maximum results to return

**Returns:**

- **results** : `list[dict[str, Any]]`
  - List of matching clauses with keys:
    - `clause`: Clause URI
    - `text`: Clause text (if available)
    - `summary`: Clause summary (if available)

**Example:**

```python
# Simple text search
results = client.text_search(
    search_term="termination notice",
    limit=10
)

print(f"Found {len(results)} matches:")
for result in results:
    print(f"  Clause: {result['clause']}")
    print(f"  Text: {result.get('text', 'N/A')[:100]}...")
    print()

# Search with clause type filter
results = client.text_search(
    search_term="30 days",
    clause_type="TerminationClause",
    limit=5
)

# Search in summaries
results = client.text_search(
    search_term="data protection",
    field="summary",
    limit=20
)

# Lucene query syntax
results = client.text_search(
    search_term="termination AND (30 OR 60) days",
    limit=10
)
```

**Lucene Query Syntax:**
- `AND`, `OR`, `NOT` operators
- Wildcards: `term*`, `*term`, `te?m`
- Phrase search: `"exact phrase"`
- Proximity: `"term1 term2"~5`
- Fuzzy: `term~0.8`

**Performance:**
- Indexed search: 10-50ms
- Much faster than SPARQL FILTER with regex
- Scales well with large datasets

**Use Cases:**
- Quick clause lookup
- Contract search interfaces
- Compliance keyword scanning
- Similar clause finding

---

## Utility Methods

### health_check

```python
def health_check(self) -> bool
```

Check if Fuseki server is accessible and responding.

**Returns:**

- **healthy** : `bool`
  - True if server is accessible, False otherwise

**Example:**

```python
if client.health_check():
    print("✅ Fuseki server is healthy")
else:
    print("❌ Fuseki server is not responding")
    # Implement fallback or retry logic
```

**Use Cases:**
- Application startup checks
- Health monitoring endpoints
- Automated testing
- Load balancer health checks

**Performance:**
- Execution time: 20-100ms

---

## Common Namespace Prefixes

The client automatically includes these prefixes when `add_prefixes=True`:

```sparql
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX proc: <http://procurement.kg/ontology#>
PREFIX contract: <http://procurement.kg/contract#>
PREFIX text: <http://jena.apache.org/text#>
```

**Example:**

```python
# With automatic prefixes (recommended)
query = """
SELECT ?contract WHERE {
    ?contract a proc:Contract .
}
"""
results = client.execute_select(query, add_prefixes=True)

# Without automatic prefixes (manual control)
query = """
PREFIX proc: <http://procurement.kg/ontology#>
SELECT ?contract WHERE {
    ?contract a proc:Contract .
}
"""
results = client.execute_select(query, add_prefixes=False)
```

---

## Best Practices

### 1. Use Parameterized Queries

```python
# ❌ String concatenation (SQL injection risk)
contract_id = user_input
query = f'SELECT * WHERE {{ ?c proc:contractId "{contract_id}" }}'

# ✅ Use helper methods with parameters
contract_uri = client.insert_contract(contract_id=contract_id, value=value)
```

### 2. Batch Operations

```python
# ❌ Individual inserts
for contract in contracts:
    client.insert_contract(**contract)

# ✅ Batch insert with single UPDATE
triples = []
for contract in contracts:
    triples.append(f"<{contract['uri']}> a proc:Contract .")
turtle_data = "\n".join(triples)
client.load_turtle(turtle_data)
```

### 3. Use Named Graphs

```python
# ✅ Organize data in named graphs
client.load_turtle(
    turtle_data=contracts_data,
    graph_uri="http://example.org/contracts/2024"
)

client.load_turtle(
    turtle_data=suppliers_data,
    graph_uri="http://example.org/suppliers"
)

# Easy to manage and delete
client.delete_graph("http://example.org/contracts/2024")
```

### 4. Handle Errors Gracefully

```python
try:
    results = client.execute_select(query)
except Exception as e:
    logger.error(f"Query failed: {e}")
    # Implement retry logic or fallback
    results = []
```

### 5. Use Text Search for Performance

```python
# ❌ Slow SPARQL regex filter
query = """
SELECT ?clause ?text WHERE {
    ?clause proc:rawText ?text .
    FILTER(REGEX(?text, "termination", "i"))
}
"""

# ✅ Fast text index search
results = client.text_search("termination", limit=100)
```

---

## Performance Characteristics

### Query Performance

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Simple SELECT | 50-200ms | <10 results |
| Complex JOIN | 500-2000ms | Multiple patterns |
| Aggregation | 200-1000ms | GROUP BY, COUNT |
| CONSTRUCT | 100-5000ms | Depends on result size |
| ASK | 20-100ms | Boolean check |
| UPDATE | 50-200ms | Single triple |
| Text Search | 10-50ms | Indexed search |

### Data Loading Performance

| Data Size | Load Time | Throughput |
|-----------|-----------|------------|
| 1K triples | 100-300ms | ~5K triples/s |
| 10K triples | 1-3s | ~5K triples/s |
| 100K triples | 10-30s | ~5K triples/s |
| 1M triples | 2-5 min | ~5K triples/s |

### Optimization Tips

1. **Use LIMIT** for large result sets
2. **Create indexes** on frequently queried properties
3. **Use text search** instead of REGEX filters
4. **Batch operations** when possible
5. **Monitor query performance** and optimize slow queries

---

## Error Handling

### Common Exceptions

```python
from SPARQLWrapper import SPARQLExceptions

try:
    results = client.execute_select(query)
except SPARQLExceptions.QueryBadFormed as e:
    print(f"Invalid SPARQL syntax: {e}")
except SPARQLExceptions.EndPointNotFound as e:
    print(f"Endpoint not accessible: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Retry Logic

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def robust_query(client, query):
    return client.execute_select(query)

# Use with automatic retries
results = robust_query(client, query)
```

---

## See Also

- **[Vector Store API](vector_comprehensive.md)** - Semantic search with Milvus
- **[Ingestion Agents](../agents/ingestion_comprehensive.md)** - Data ingestion pipeline
- **[Retrieval Agents](../agents/retrieval_comprehensive.md)** - Query orchestration
- **[Configuration](../core/config.md)** - Settings and environment variables

---

## Complete Example

```python
from fuseki_client import FusekiClient
from config import get_settings

# Initialize client
settings = get_settings()
client = FusekiClient(settings=settings)

# Check health
if not client.health_check():
    raise Exception("Fuseki server not available")

# Insert contract
contract_uri = client.insert_contract(
    contract_id="DEMO_001",
    value=150000.00,
    effective_date="2024-01-01",
    expiration_date="2025-01-01",
    jurisdiction="US"
)

# Insert clauses
clause_uri = client.insert_clause(
    clause_id="TERM_001",
    contract_uri=contract_uri,
    clause_type="TerminationClause",
    raw_text="Either party may terminate with 30 days notice.",
    notice_period=30
)

# Search contracts
contracts = client.search_contracts(
    jurisdiction="US",
    min_value=100000.00
)

print(f"Found {len(contracts)} high-value US contracts")

# Text search
results = client.text_search(
    search_term="termination notice",
    clause_type="TerminationClause",
    limit=10
)

print(f"Found {len(results)} termination clauses")

# Get risks
risks = client.get_contract_risks(contract_uri)
if risks:
    print(f"⚠️ Contract has {len(risks)} risks")

# Get statistics
total_triples = client.get_triple_count()
graphs = client.list_graphs()

print(f"Total triples: {total_triples:,}")
print(f"Named graphs: {len(graphs)}")
```

**Output:**
```
Found 12 high-value US contracts
Found 8 termination clauses
⚠️ Contract has 1 risks
Total triples: 45,678
Named graphs: 3