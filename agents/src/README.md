# Source Code Directory (`src/`)

This directory contains the core source code for the Contract Knowledge Graph RAG system. The codebase is organized into logical modules following a clean architecture pattern.

## Directory Structure

### `agents/`
LLM-powered agents organized by pipeline:

#### `agents/ingestion/` - Ingestion Pipeline
Complete document-to-knowledge-graph pipeline:
- **Document Processing**: `document_ingestion.py` - Document intake and parsing
- **Semantic Extraction**: 
  - `clause_extraction.py` - Extract contract clauses
  - `entity_extraction.py` - Extract entities (parties, dates, amounts, jurisdictions)
  - `obligation_risk.py` - Extract obligations and risks
- **Ontology & RDF**:
  - `ontology_alignment.py` - Align extracted data with ontology
  - `rdf_generator.py` - Generate RDF triples
- **Validation & Loading**:
  - `validation_agent.py` - Validate extracted data
  - `fuseki_loader.py` - Load RDF into Fuseki
  - `reasoning_agent.py` - Apply reasoning rules
  - `vector_index.py` - Index in vector store
- **Orchestration**: `ingestion_orchestrator.py` - Orchestrates the complete pipeline
- **Utilities**: `resource_manager.py` - Resource management

#### `agents/retrieval/` - Retrieval Pipeline
Query processing and answer generation:
- **Query Analysis**:
  - `unified_query_analyzer.py` - Comprehensive query analysis
  - `query_classifier.py` - Classify query complexity
  - `complexity_detector.py` - Detect query complexity
  - `query_decomposer.py` - Decompose complex queries
- **SPARQL Generation**: `sparql_generator.py` - Generate SPARQL queries
- **Retrieval Orchestration**:
  - `retrieval_orchestrator.py` - Original retrieval orchestrator
  - `retrieval_orchestrator_langgraph_v2.py` - LangGraph-based orchestrator (recommended)
  - `rag_orchestrator.py` - RAG orchestrator for simple queries
- **ReAct Agents**:
  - `react_agent_optimized.py` - Optimized ReAct agent for complex queries
  - `react_agent_langgraph.py` - LangGraph-based ReAct agent
- **Answer Generation**: `synthesis_optimizer.py` - Optimize answer synthesis

#### `agents/schema_evolution/` - Schema Evolution
Dynamic schema and rule generation:
- `ontology_designer.py` - Design and extend ontologies
- `pattern_detection.py` - Detect patterns in data
- `rule_generator.py` - Generate inference rules
- `shacl_generator.py` - Generate SHACL validation shapes

#### `agents/shared/` - Shared Components
- `base.py` - Base agent class with LLM initialization and common utilities

### `storage/`
Storage abstraction layer with factory pattern:

#### `storage/sparql/`
SPARQL/RDF storage implementations:
- `base.py` - Abstract base class for SPARQL stores
- `fuseki_store.py` - Fuseki SPARQL store implementation
- `factory.py` - Factory for creating store instances

#### `storage/vector/`
Vector database storage implementations:
- `base.py` - Abstract base class for vector stores
- `milvus_store.py` - Milvus vector store implementation
- `factory.py` - Factory for creating store instances

### `llm/`
LLM provider abstraction and implementations:

#### `llm/providers/`
LLM provider implementations:
- `base.py` - Abstract base class for LLM providers
- `ollama_provider.py` - Ollama local LLM provider
- `watsonx_provider.py` - IBM WatsonX provider

#### LLM Utilities
- `provider_factory.py` - Factory for creating LLM providers
- `batch_helper.py` - Batch processing utilities for LLM calls

### `observability/`
Observability and monitoring:
- `phoenix_tracer.py` - Phoenix observability setup
- `phoenix_datasets.py` - Phoenix datasets and experiments integration

### `logger/`
Structured logging system:
- `base.py` - Base logger interface
- `module_logger.py` - Module-specific logger implementation
- `factory.py` - Logger factory
- `example_usage.py` - Usage examples

### `schemas/`
Ontology schemas, rules, and SHACL shapes:
- `ontology/` - OWL ontology files (e.g., `procurement.owl`)
- `rules/` - Jena inference rules (e.g., `risk_rules.rules`)
- `shacl/` - SHACL validation shapes (e.g., `contract_shapes.ttl`)

### Core Utilities (Root Level)

**Configuration & Settings**:
- `config.py` - Application settings and configuration (Pydantic Settings)

**Service Management**:
- `service_factory.py` - Factory for creating services (stores, clients, etc.)

**Storage Clients**:
- `fuseki_client.py` - Direct Fuseki client (legacy, prefer `storage/sparql/`)
- `vector_store.py` - Direct vector store client (legacy, prefer `storage/vector/`)

**Data Management**:
- `document_registry.py` - Document registry and tracking
- `artifact_store.py` - Artifact storage (RDF, rules, logs)
- `graph_manager.py` - Knowledge graph management utilities
- `ontology_manager.py` - Ontology management and loading

**Pipeline & Processing**:
- `pipeline.py` - End-to-end processing pipeline
- `batch_processor.py` - Batch processing utilities

**Schema & Governance**:
- `schema_governance.py` - Schema versioning and governance

**Utilities**:
- `health.py` - System health checking
- `agent_explanation.py` - Agent explanation generation
- `logging_config.py` - Logging configuration
- `logging_utils.py` - Logging utilities (RAG logger, etc.)

## Architecture Principles

### 1. **Separation of Concerns**
- **Agents** handle business logic and LLM interactions
- **Storage** provides abstraction over data stores
- **LLM** abstracts over different LLM providers
- **Observability** handles tracing and monitoring

### 2. **Factory Pattern**
- `service_factory.py` - Creates storage instances
- `llm/provider_factory.py` - Creates LLM providers
- `storage/*/factory.py` - Creates store instances

### 3. **Abstraction Layers**
- Storage abstraction (`storage/base.py`) allows switching between implementations
- LLM provider abstraction (`llm/providers/base.py`) supports multiple LLM backends
- Agent base class (`agents/shared/base.py`) provides common functionality

### 4. **Modularity**
- Each agent is self-contained with clear responsibilities
- Storage implementations are pluggable
- LLM providers are interchangeable

## Key Design Patterns

- **Orchestrator Pattern**: `ingestion_orchestrator.py`, `retrieval_orchestrator*.py`
- **Factory Pattern**: Service and provider factories
- **Strategy Pattern**: Different retrieval strategies (simple/complex)
- **Template Method**: Base agent class defines structure
- **Observer Pattern**: Logging and observability hooks

## Import Guidelines

### Preferred Imports

```python
# Agents
from agents.ingestion import IngestionOrchestrator, DocumentIngestionAgent
from agents.retrieval import RetrievalOrchestrator, RAGOrchestratorAgent
from agents.shared import BaseAgent

# Storage (use abstraction)
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory

# LLM (use abstraction)
from llm.provider_factory import LLMProviderFactory

# Configuration
from config import Settings, get_settings

# Logging
from logger import get_module_logger
from logging_utils import get_rag_logger

# Observability
from observability import setup_phoenix_tracing
```

### Avoid Direct Imports

```python
# ❌ Don't import implementations directly
from storage.sparql.fuseki_store import FusekiStore
from storage.vector.milvus_store import MilvusStore

# ✅ Use factories or base classes
from service_factory import get_service_factory
sparql_store = get_service_factory().get_sparql_store()
```

## Module Dependencies

```
agents/
  ├── shared/ (base classes)
  ├── ingestion/ (depends on: storage, llm, logger)
  ├── retrieval/ (depends on: storage, llm, logger, observability)
  └── schema_evolution/ (depends on: llm, logger)

storage/
  ├── sparql/ (independent)
  └── vector/ (independent)

llm/
  └── providers/ (independent)

observability/ (depends on: external Phoenix SDK)
logger/ (independent)
```

## Code Organization Best Practices

1. **Keep modules focused**: Each file should have a single, clear responsibility
2. **Use type hints**: All functions should have type annotations
3. **Document classes and functions**: Use docstrings following Google/NumPy style
4. **Follow naming conventions**: 
   - Classes: `PascalCase`
   - Functions: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`
5. **Error handling**: Use structured logging for errors
6. **Async/await**: Use async for I/O operations (storage, LLM calls)

## Testing

Test files are located in `agents/tests/` and organized by category:
- `tests/retrieval/` - Retrieval tests
- `tests/ingestion/` - Ingestion tests
- `tests/observability/` - Observability tests
- etc.

See `agents/tests/README.md` for details.
