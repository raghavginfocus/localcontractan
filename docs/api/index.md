# API Reference Overview

Welcome to the Contract Knowledge Graph API Reference. This comprehensive documentation provides detailed information about all components of the system.

## Quick Navigation

### 🤖 Agents

Multi-agent system for document processing and retrieval:

- **[Ingestion Agents](agents/ingestion_comprehensive.md)** - Document parsing, clause extraction, entity extraction, RDF generation
- **[Retrieval Agents](agents/retrieval_comprehensive.md)** - Query processing, SPARQL generation, ReAct reasoning, answer synthesis
- **[Orchestrators](agents/orchestrators_comprehensive.md)** - Pipeline coordination, workflow management, multi-step processing
- **[Schema Evolution](agents/schema-evolution.md)** - Ontology design, pattern detection, SHACL generation

### 💾 Storage

Data persistence and retrieval systems:

- **[SPARQL Store](storage/sparql_comprehensive.md)** - Apache Jena Fuseki client, knowledge graph operations, text search
- **[Vector Store](storage/vector_comprehensive.md)** - Milvus client, semantic search, embedding management
- **[Object Storage](storage/object_storage_comprehensive.md)** - S3-compatible storage for MinIO and IBM Cloud Object Storage

### ⚙️ Core

Core system components:

- **[Configuration](core/config_comprehensive.md)** - Settings management, environment variables, validation
- **[Artifact Store](core/artifact_store_comprehensive.md)** - RDF, OWL, and rules artifact management

### 🤖 LLM

Language model integration:

- **[Providers](llm/providers_comprehensive.md)** - WatsonX AI, Ollama, provider factory, streaming support

### 📊 Models

Pydantic data models:

- **[Data Models](models/data_models_comprehensive.md)** - ExtractedClause, Party, ContractDate, MonetaryAmount, Jurisdiction

---

## Getting Started

### Installation

```bash
# Clone repository
git clone https://github.com/your-org/contract-jena.git
cd contract-jena

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp agents/env.example agents/.env
# Edit .env with your settings
```

### Basic Usage

#### Document Ingestion

```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator
import asyncio

async def ingest_document():
    orchestrator = IngestionOrchestrator()
    
    result = await orchestrator.ingest_document(
        document_path="contract.pdf",
        document_id="ABC123"
    )
    
    print(f"Clauses extracted: {result.clauses_extracted}")
    print(f"Entities extracted: {result.entities_extracted}")

asyncio.run(ingest_document())
```

#### Query & Retrieval

```python
from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator
import asyncio

async def query_contracts():
    orchestrator = RetrievalOrchestrator()
    
    result = await orchestrator.retrieve(
        question="What are the termination notice periods?"
    )
    
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence:.2f}")

asyncio.run(query_contracts())
```

---

## Architecture Overview

### Multi-Agent System

```
┌─────────────────────────────────────────────────────────┐
│                   Orchestrators                          │
│  ┌──────────────────┐      ┌──────────────────┐        │
│  │   Ingestion      │      │    Retrieval     │        │
│  │  Orchestrator    │      │   Orchestrator   │        │
│  └────────┬─────────┘      └────────┬─────────┘        │
└───────────┼──────────────────────────┼──────────────────┘
            │                          │
    ┌───────▼────────┐        ┌───────▼────────┐
    │  Ingestion     │        │   Retrieval    │
    │    Agents      │        │     Agents     │
    ├────────────────┤        ├────────────────┤
    │ • Clause       │        │ • Query        │
    │   Extraction   │        │   Analyzer     │
    │ • Entity       │        │ • SPARQL       │
    │   Extraction   │        │   Generator    │
    │ • RDF          │        │ • ReAct        │
    │   Generation   │        │   Agent        │
    │ • Validation   │        │ • Answer       │
    │                │        │   Synthesis    │
    └────────┬───────┘        └────────┬───────┘
             │                         │
    ┌────────▼─────────────────────────▼────────┐
    │            Storage Layer                   │
    ├────────────────┬──────────────┬───────────┤
    │  SPARQL Store  │ Vector Store │  Object   │
    │  (Fuseki)      │  (Milvus)    │  Storage  │
    └────────────────┴──────────────┴───────────┘
```

### Data Flow

**Ingestion Pipeline:**
1. Document parsing (PDF/DOCX → text)
2. Clause extraction (text → structured clauses)
3. Entity extraction (text → parties, dates, amounts)
4. RDF generation (structured data → RDF triples)
5. Knowledge graph loading (RDF → Fuseki)
6. Vector indexing (clauses → embeddings → Milvus)

**Retrieval Pipeline:**
1. Query analysis (question → complexity + sub-queries)
2. Strategy selection (simple → KG, complex → ReAct)
3. Knowledge retrieval (SPARQL + vector search + text search)
4. Answer synthesis (retrieved data → natural language answer)

---

## Key Features

### 🎯 Comprehensive Extraction

- **13+ clause types** recognized automatically
- **Entity extraction** for parties, dates, amounts, jurisdictions
- **Obligation & risk detection** with severity scoring
- **Structured attributes** for filtering and analysis

### 🔍 Hybrid RAG

- **Knowledge Graph** (SPARQL) for structured queries
- **Vector Search** (Milvus) for semantic similarity
- **Text Search** (Fuseki) for exact keyword matching
- **Smart routing** based on query characteristics

### 🤖 Multi-Step Reasoning

- **ReAct agent** for complex multi-step queries
- **Query decomposition** into sub-queries
- **Parallel execution** for performance
- **Self-reflection** for answer quality

### 📊 Rich Metadata

- **Provenance tracking** (page numbers, sections)
- **Confidence scores** for all extractions
- **Comprehensive logging** with session files
- **Performance metrics** for optimization

---

## API Categories

### Agents

Intelligent agents that perform specific tasks:

| Agent | Purpose | Key Methods |
|-------|---------|-------------|
| **ClauseExtractionAgent** | Extract and classify contract clauses | `process()` |
| **EntityExtractionAgent** | Extract parties, dates, amounts | `process()` |
| **SPARQLGeneratorAgent** | Generate SPARQL queries from questions | `process()` |
| **ReActRetrievalAgent** | Multi-step reasoning for complex queries | `process()` |
| **IngestionOrchestrator** | Coordinate ingestion pipeline | `ingest_document()`, `ingest_batch()` |
| **RetrievalOrchestrator** | Coordinate retrieval pipeline | `retrieve()`, `retrieve_batch()` |

### Storage

Data persistence and retrieval:

| Component | Purpose | Key Methods |
|-----------|---------|-------------|
| **FusekiClient** | SPARQL queries and text search | `query()`, `text_search()`, `load_rdf()` |
| **MilvusVectorStore** | Semantic search with embeddings | `search()`, `insert()`, `create_collection()` |
| **S3CompatibleStorage** | Object storage for artifacts | `upload()`, `download()`, `list_objects()` |

### Core

System configuration and utilities:

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **Settings** | Configuration management | 50+ parameters, validation, env vars |
| **ArtifactStore** | Artifact management | RDF, OWL, rules storage with versioning |

### Models

Pydantic data models for type safety:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **ExtractedClause** | Contract clause representation | `clause_type`, `raw_text`, `attributes` |
| **Party** | Contract party | `name`, `role`, `contact_info` |
| **ContractDate** | Significant dates | `date_type`, `date_value` |
| **MonetaryAmount** | Financial values | `amount_type`, `value`, `currency` |
| **Jurisdiction** | Legal jurisdiction | `name`, `jurisdiction_type` |

---

## Performance Characteristics

### Ingestion

- **Small documents** (<10 pages): 5-15 seconds
- **Medium documents** (10-50 pages): 15-60 seconds
- **Large documents** (>50 pages): 60-300 seconds
- **Batch processing**: Parallel execution supported

### Retrieval

- **Simple queries** (KG only): 500-2000ms
- **Hybrid queries**: 2000-5000ms
- **Complex queries** (ReAct): 5000-15000ms
- **Caching**: Significant speedup for repeated queries

### Storage

- **SPARQL queries**: 100-1000ms (depends on complexity)
- **Vector search**: 50-500ms (depends on collection size)
- **Text search**: 50-200ms (indexed)

---

## Common Patterns

### Error Handling

```python
from pydantic import ValidationError

try:
    result = await orchestrator.retrieve(question)
    if not result.success:
        print(f"Query failed: {result.error}")
except ValidationError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Async Operations

```python
import asyncio

# Sequential
result1 = await orchestrator.retrieve(question1)
result2 = await orchestrator.retrieve(question2)

# Parallel
results = await asyncio.gather(
    orchestrator.retrieve(question1),
    orchestrator.retrieve(question2)
)
```

### Configuration

```python
from config import get_settings

# Get settings
settings = get_settings()

# Access configuration
print(f"Fuseki URL: {settings.fuseki_url}")
print(f"Milvus host: {settings.milvus_host}")
print(f"LLM model: {settings.llm_model_id}")

# Override for testing
settings.enable_logging = False
```

---

## Best Practices

### 1. Use Type Hints

```python
from agents.ingestion.clause_extraction import ExtractedClause

def process_clause(clause: ExtractedClause) -> str:
    return clause.summary
```

### 2. Enable Logging

```python
orchestrator = RetrievalOrchestrator(enable_logging=True)
result = await orchestrator.retrieve(question)
print(f"Log file: {result.log_file}")
```

### 3. Handle Errors Gracefully

```python
if not result.success:
    print(f"Error: {result.error}")
    # Implement fallback logic
```

### 4. Monitor Performance

```python
if result.total_duration_ms > 10000:
    print(f"⚠️ Slow query: {result.total_duration_ms:.0f}ms")
```

### 5. Use Dependency Injection

```python
from service_factory import get_service_factory

factory = get_service_factory()
orchestrator = RetrievalOrchestrator(
    sparql_store=factory.get_sparql_store(),
    vector_store=factory.get_vector_store()
)
```

---

## Troubleshooting

### Common Issues

**Issue: Slow queries**
- Check query complexity
- Review step timing in logs
- Consider caching
- Use appropriate strategy (KG_ONLY for simple queries)

**Issue: Low confidence scores**
- Verify data quality in knowledge graph
- Check vector embeddings
- Review retrieval sources (KG facts, vector contexts)

**Issue: Ingestion failures**
- Check document format (PDF/DOCX supported)
- Verify file accessibility
- Review error logs
- Check LLM availability

**Issue: Connection errors**
- Verify Fuseki is running
- Check Milvus connectivity
- Validate configuration settings
- Review network/firewall settings

---

## Additional Resources

- **[User Guide](../guide/ingestion.md)** - Step-by-step tutorials
- **[Architecture](../architecture/overview.md)** - System design details
- **[Performance](../performance/optimizations.md)** - Optimization techniques
- **[Development](../development/contributing.md)** - Contributing guidelines

---

## Support

For questions, issues, or contributions:

- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/contract-jena/issues)
- **Documentation**: [Full documentation](https://contract-jena.github.io/)
- **Email**: support@example.com

---

## License

This project is licensed under the MIT License. See LICENSE file for details.