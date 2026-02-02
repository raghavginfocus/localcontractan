# Ingestion Agents API Reference

API documentation for document ingestion agents.

## IngestionOrchestrator

Main orchestrator for the complete ingestion pipeline.

### Class Definition

```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

class IngestionOrchestrator:
    """
    Orchestrates the complete document ingestion pipeline.
    
    Coordinates multiple specialized agents to extract, structure,
    validate, and load contract data into the knowledge graph.
    """
```

### Constructor

```python
def __init__(
    self,
    settings: Settings | None = None,
    enable_schema_evolution: bool = True,
    enable_reasoning: bool = True,
    enable_vector_indexing: bool = True,
    enable_logging: bool = True
)
```

**Parameters:**

- `settings` (Settings, optional): Application settings
- `enable_schema_evolution` (bool): Enable automatic ontology extension
- `enable_reasoning` (bool): Enable inference after loading
- `enable_vector_indexing` (bool): Create vector embeddings
- `enable_logging` (bool): Enable detailed logging

### Methods

#### ingest_document

```python
def ingest_document(
    self,
    file_path: str | Path,
    graph_uri: str,
    document_id: str | None = None
) -> IngestionResult
```

Ingest a single document into the knowledge graph.

**Parameters:**

- `file_path` (str | Path): Path to document (PDF, DOCX)
- `graph_uri` (str): Target graph URI
- `document_id` (str, optional): Custom document ID

**Returns:**

- `IngestionResult`: Complete ingestion results

**Example:**

```python
orchestrator = IngestionOrchestrator(
    enable_schema_evolution=True,
    enable_reasoning=True
)

result = orchestrator.ingest_document(
    file_path="contract.pdf",
    graph_uri="http://example.org/contracts"
)

print(f"Success: {result.success}")
print(f"Clauses extracted: {result.clauses_extracted}")
print(f"Triples loaded: {result.triples_loaded}")
```

#### batch_ingest

```python
def batch_ingest(
    self,
    file_paths: list[str | Path],
    graph_uri: str,
    batch_size: int = 10
) -> list[IngestionResult]
```

Ingest multiple documents in batches.

**Parameters:**

- `file_paths` (list): List of document paths
- `graph_uri` (str): Target graph URI
- `batch_size` (int): Documents per batch

**Returns:**

- `list[IngestionResult]`: Results for each document

**Example:**

```python
results = orchestrator.batch_ingest(
    file_paths=["doc1.pdf", "doc2.pdf", "doc3.pdf"],
    graph_uri="http://example.org/contracts",
    batch_size=10
)

for result in results:
    print(f"Document {result.document_id}: {result.success}")
```

### Result Models

#### IngestionResult

```python
class IngestionResult(BaseModel):
    """Complete ingestion pipeline result."""
    
    document_id: str
    success: bool
    steps: list[IngestionStep]
    
    # Metrics
    clauses_extracted: int
    entities_extracted: int
    obligations_extracted: int
    risks_extracted: int
    triples_generated: int
    triples_loaded: int
    facts_inferred: int
    vectors_indexed: int
    
    # Schema evolution
    ontology_suggestions: list[dict]
    ontology_extensions_generated: list[str]
    rules_generated: list[str]
    shacl_shapes_generated: list[str]
    
    # Timing
    total_duration_ms: float
    started_at: datetime
    completed_at: datetime
```

## DocumentIngestionAgent

Extracts text and metadata from documents.

### Class Definition

```python
from agents.ingestion.document_ingestion import DocumentIngestionAgent

class DocumentIngestionAgent(BaseAgent):
    """Extract text and metadata from PDF/DOCX documents."""
```

### Methods

#### process

```python
def process(
    self,
    file_path: str | Path
) -> DocumentIngestionResult
```

Extract text and metadata from document.

**Parameters:**

- `file_path` (str | Path): Path to document

**Returns:**

- `DocumentIngestionResult`: Extracted text and metadata

**Example:**

```python
agent = DocumentIngestionAgent()
result = agent.process("contract.pdf")

print(f"Text length: {len(result.text)}")
print(f"Metadata: {result.metadata}")
```

#### Result Model

```python
class DocumentIngestionResult(BaseModel):
    text: str
    metadata: dict[str, Any]
    page_count: int
    file_type: str
    extraction_time_ms: float
```

## ClauseExtractionAgent

Identifies and extracts contract clauses.

### Class Definition

```python
from agents.ingestion.clause_extraction import ClauseExtractionAgent

class ClauseExtractionAgent(BaseAgent):
    """Extract and classify contract clauses."""
```

### Methods

#### extract_clauses

```python
def extract_clauses(
    self,
    text: str,
    document_id: str | None = None
) -> list[ExtractedClause]
```

Extract clauses from contract text.

**Parameters:**

- `text` (str): Contract text
- `document_id` (str, optional): Document identifier

**Returns:**

- `list[ExtractedClause]`: Extracted clauses

**Example:**

```python
agent = ClauseExtractionAgent()
clauses = agent.extract_clauses(contract_text)

for clause in clauses:
    print(f"{clause.type}: {clause.text[:100]}...")
```

#### Result Model

```python
class ExtractedClause(BaseModel):
    clause_id: str
    type: str  # TerminationClause, PaymentClause, etc.
    text: str
    confidence: float
    start_position: int
    end_position: int
    metadata: dict[str, Any]
```

## EntityExtractionAgent

Extracts named entities from clauses.

### Class Definition

```python
from agents.ingestion.entity_extraction import EntityExtractionAgent

class EntityExtractionAgent(BaseAgent):
    """Extract named entities from contract text."""
```

### Methods

#### extract_entities

```python
def extract_entities(
    self,
    clauses: list[ExtractedClause]
) -> EntityExtractionResult
```

Extract entities from clauses.

**Parameters:**

- `clauses` (list): List of extracted clauses

**Returns:**

- `EntityExtractionResult`: Extracted entities

**Example:**

```python
agent = EntityExtractionAgent()
result = agent.extract_entities(clauses)

for entity in result.entities:
    print(f"{entity.type}: {entity.value}")
```

#### Result Model

```python
class Entity(BaseModel):
    entity_id: str
    type: str  # Party, Date, Money, Location, etc.
    value: str
    confidence: float
    source_clause_id: str
    metadata: dict[str, Any]

class EntityExtractionResult(BaseModel):
    entities: list[Entity]
    entity_count: int
    extraction_time_ms: float
```

## ObligationRiskAgent

Identifies obligations and risks in contracts.

### Class Definition

```python
from agents.ingestion.obligation_risk import ObligationRiskAgent

class ObligationRiskAgent(BaseAgent):
    """Identify contractual obligations and risks."""
```

### Methods

#### analyze

```python
def analyze(
    self,
    clauses: list[ExtractedClause]
) -> ObligationRiskResult
```

Analyze clauses for obligations and risks.

**Parameters:**

- `clauses` (list): List of extracted clauses

**Returns:**

- `ObligationRiskResult`: Identified obligations and risks

**Example:**

```python
agent = ObligationRiskAgent()
result = agent.analyze(clauses)

print(f"Obligations: {len(result.obligations)}")
print(f"Risks: {len(result.risks)}")
```

#### Result Models

```python
class Obligation(BaseModel):
    obligation_id: str
    type: str
    text: str
    party: str | None
    deadline: str | None
    severity: str
    source_clause_id: str

class Risk(BaseModel):
    risk_id: str
    type: str
    description: str
    severity: str  # low, medium, high, critical
    likelihood: str
    impact: str
    source_clause_id: str

class ObligationRiskResult(BaseModel):
    obligations: list[Obligation]
    risks: list[Risk]
    analysis_time_ms: float
```

## RDFGeneratorAgent

Converts structured data to RDF triples.

### Class Definition

```python
from agents.ingestion.rdf_generator import RDFGeneratorAgent

class RDFGeneratorAgent(BaseAgent):
    """Generate RDF triples from structured contract data."""
```

### Methods

#### generate_rdf

```python
def generate_rdf(
    self,
    document_id: str,
    clauses: list[ExtractedClause],
    entities: list[Entity],
    obligations: list[Obligation],
    risks: list[Risk],
    alignment: AlignmentResult
) -> RDFGenerationResult
```

Generate RDF graph from contract data.

**Parameters:**

- `document_id` (str): Document identifier
- `clauses` (list): Extracted clauses
- `entities` (list): Extracted entities
- `obligations` (list): Identified obligations
- `risks` (list): Identified risks
- `alignment` (AlignmentResult): Ontology alignment

**Returns:**

- `RDFGenerationResult`: Generated RDF graph

**Example:**

```python
agent = RDFGeneratorAgent()
result = agent.generate_rdf(
    document_id="ABC123",
    clauses=clauses,
    entities=entities,
    obligations=obligations,
    risks=risks,
    alignment=alignment
)

print(result.rdf_graph.serialize(format="turtle"))
```

#### Result Model

```python
class RDFGenerationResult(BaseModel):
    rdf_graph: Graph  # rdflib.Graph
    triple_count: int
    generation_time_ms: float
    namespaces: dict[str, str]
```

## ValidationAgent

Validates RDF data against SHACL shapes.

### Class Definition

```python
from agents.ingestion.validation_agent import ValidationAgent

class ValidationAgent(BaseAgent):
    """Validate RDF data using SHACL shapes."""
```

### Methods

#### validate

```python
def validate(
    self,
    rdf_graph: Graph,
    shacl_shapes: Graph | None = None
) -> ValidationResult
```

Validate RDF graph against SHACL shapes.

**Parameters:**

- `rdf_graph` (Graph): RDF graph to validate
- `shacl_shapes` (Graph, optional): SHACL shapes (uses default if None)

**Returns:**

- `ValidationResult`: Validation results

**Example:**

```python
agent = ValidationAgent()
result = agent.validate(rdf_graph)

if not result.conforms:
    for violation in result.violations:
        print(f"Error: {violation.message}")
```

#### Result Model

```python
class Violation(BaseModel):
    focus_node: str
    result_path: str
    value: str
    message: str
    severity: str

class ValidationResult(BaseModel):
    conforms: bool
    violations: list[Violation]
    validation_time_ms: float
```

## FusekiLoaderAgent

Loads RDF data into Apache Fuseki.

### Class Definition

```python
from agents.ingestion.fuseki_loader import FusekiLoaderAgent

class FusekiLoaderAgent(BaseAgent):
    """Load RDF data into Fuseki triple store."""
```

### Methods

#### load

```python
def load(
    self,
    rdf_graph: Graph,
    graph_uri: str,
    batch_size: int = 1000
) -> LoadResult
```

Load RDF graph into Fuseki.

**Parameters:**

- `rdf_graph` (Graph): RDF graph to load
- `graph_uri` (str): Target graph URI
- `batch_size` (int): Triples per batch

**Returns:**

- `LoadResult`: Load statistics

**Example:**

```python
agent = FusekiLoaderAgent()
result = agent.load(
    rdf_graph=rdf,
    graph_uri="http://example.org/contracts"
)

print(f"Loaded {result.triples_loaded} triples")
```

#### Result Model

```python
class LoadResult(BaseModel):
    triples_loaded: int
    load_time_ms: float
    graph_uri: str
    success: bool
    error: str | None
```

## See Also

- [Retrieval Agents API](../api/agents/retrieval.md)
- [Schema Evolution Agents API](../api/agents/schema-evolution.md)
- [Ingestion Guide](../../guide/ingestion.md)