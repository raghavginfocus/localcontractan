# Contract Knowledge Graph - Procurement Semantic GraphRAG

> **Intelligent Contract Analysis with Knowledge Graphs and Hybrid RAG**

A production-ready, multi-agent system for automated contract analysis, risk assessment, and compliance checking using Apache Jena Knowledge Graphs, Vector Search, and LLM-powered reasoning.

## Overview

Transform unstructured contract documents into a queryable semantic knowledge graph with automatic risk detection, compliance checking, and intelligent question answering.

**Key Capabilities:**
- **Automated Ingestion**: Extract clauses, entities, obligations from PDF/DOCX contracts
- **Semantic Understanding**: LLM-powered clause classification and entity recognition
- **Hybrid Search**: Combines vector similarity + SPARQL graph queries
- **Risk Detection**: Automatic identification of high-risk clauses and compliance issues
- **Multi-Agent System**: 10+ specialized agents for ingestion, retrieval, and reasoning
- **Observability**: Full tracing with Phoenix, structured logging, performance metrics

**Technology Stack:**
- **Knowledge Graph**: Apache Jena Fuseki + TDB2 with OWL ontology
- **Vector Store**: Milvus for semantic search (1024-dim embeddings)
- **LLM Providers**: IBM WatsonX AI, Ollama (local)
- **Orchestration**: LangGraph for agent workflows
- **Observability**: Arize Phoenix for tracing and evaluation

## Quick Start

```bash
# 1. Install dependencies
make install

# 2. Setup environment
make setup-env
# Edit agents/.env with your API keys (WatsonX, OpenAI, etc.)

# 3. Start all services (automatic initialization!)
make services-up
# Automatically creates dataset, loads ontology, configures text indexing

# 4. Verify system health
make health

# 5. Run ingestion on sample contracts
make ingest DIR=examples

# 6. View documentation
make docs-docker-up
```

Visit http://localhost:8000 for complete documentation.

### What Happens Automatically

When you run `make services-up`, the system automatically:
- Creates Fuseki dataset (`contracts`)
- Loads base ontology (`ontology/procurement.owl`)
- Configures text indexing for fast search
- Prepares reasoning rules
- Initializes all services (Fuseki, Milvus, Phoenix)

**No manual dataset or ontology setup required!** See [Setup Guide](docs/getting-started/setup-guide.md) for details.

## Documentation

### Docker-based Documentation Server (Recommended)

The Docker-based documentation server has **auto-reload enabled** - it automatically detects changes to documentation files and rebuilds without requiring a restart.

```bash
# Start documentation server
make docs-docker-up

# Stop documentation server
make docs-docker-down

# Restart documentation server (if needed)
make docs-docker-restart

# View logs
make docs-docker-logs
```

**Benefits:**
- Auto-reload on file changes (no restart needed)
- Consistent environment
- No local Python dependencies required
- Runs alongside other services

### Local Documentation Server

For development without Docker:

```bash
# Start local server with live reload
make docs-serve
```

### Building Documentation

```bash
# Build static documentation
make docs-build

# Deploy to GitHub Pages
make docs-deploy
```

## System Architecture

### Microservices Design

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (8080)                       │
│              Unified Entry Point & Routing                   │
└────────────────┬────────────────────────────┬────────────────┘
                 │                            │
        ┌────────▼────────┐          ┌───────▼────────┐
        │ Ingestion API   │          │ Retrieval API  │
        │    (8001)       │          │    (8002)      │
        └────────┬────────┘          └───────┬────────┘
                 │                            │
        ┌────────▼────────────────────────────▼────────┐
        │         Apache Jena Fuseki (3030)            │
        │    Knowledge Graph + SPARQL + Reasoning      │
        └──────────────────┬───────────────────────────┘
                           │
        ┌──────────────────▼───────────────────────────┐
        │         Milvus Vector Store (19530)          │
        │      Semantic Search (1024-dim vectors)      │
        └──────────────────────────────────────────────┘
```

**Core Components:**
- **Microservices**: Ingestion API, Retrieval API, API Gateway
- **Multi-Agent System**: 10+ ingestion agents + 6+ retrieval agents
- **Knowledge Graph**: Apache Jena Fuseki + TDB2 with OWL ontology & inference rules
- **Vector Store**: Milvus for semantic search (IVF_FLAT index, COSINE metric)
- **Hybrid RAG**: Intelligent routing between vector search + SPARQL queries
- **LLM Providers**: IBM WatsonX AI, Ollama (local models)
- **Observability**: Arize Phoenix tracing, structured logging, performance metrics
- **Automatic Initialization**: Dataset creation, ontology loading on startup

## Key Features

- **Document Ingestion**: PDF/DOCX processing with clause extraction
- **Entity Recognition**: Contract parties, dates, obligations
- **Risk Analysis**: Automated risk scoring and classification
- **Semantic Search**: Vector + graph-based retrieval
- **Query Routing**: Automatic complexity detection
- **Schema Evolution**: Dynamic ontology updates

## Services

The system runs as microservices with automatic initialization:

```bash
# View all service URLs
make urls
```

**Core Services:**
- **API Gateway**: http://localhost:8080 (unified entry point)
- **Ingestion API**: http://localhost:8001 (document processing)
- **Retrieval API**: http://localhost:8002 (query processing)
- **Fuseki**: http://localhost:3030 (SPARQL endpoint, admin/admin123)
- **Milvus**: http://localhost:19530 (vector store)
- **Attu (Milvus UI)**: http://localhost:8081 (Milvus management)
- **Phoenix**: http://localhost:6006 (observability)
- **Documentation**: http://localhost:8000 (MkDocs)

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Test specific components
make test-fuseki
make test-complexity
```

## Common Workflows

```bash
# Complete quickstart
make quickstart

# Daily development
make daily-dev

# Full system reset
make full-reset
```

### Document Ingestion

```bash
# Ingest documents from directory
make ingest DIR=examples

# Force reprocess all documents (override existing)
make ingest-override DIR=examples

# Run ingestion test
make ingest-test
```

**Features:**
- Automatic directory scanning for PDF/DOCX files
- Batch processing with concurrency control
- Duplicate detection and skip logic
- Progress tracking and detailed logging
- Automatic retry on failures

## API Testing

```bash
# Query API directly
make api-query Q="What are the termination clauses?"

# Test API with different complexity levels
make api-test-simple
make api-test-medium
make api-test-complex
make api-test-all

# Test with custom YAML file
make api-test-custom YAML=path/to/test.yaml
```

## Service Management

```bash
# Start all services
make services-up

# Start services with UI (includes Attu for Milvus)
make services-up-ui

# Stop services
make services-down

# Restart services
make services-restart

# View service status
make services-status

# View service logs
make services-logs
make services-logs-fuseki
make services-logs-milvus

# Check service health
make health
```

## Logs

```bash
# View service logs
make logs-ingestion      # Ingestion service logs
make logs-retrieval      # Retrieval service logs
make logs-gateway        # API gateway logs
make logs-all            # All services

# View infrastructure logs
make services-logs-fuseki
make services-logs-milvus
make services-logs        # All infrastructure
```

## Verification

```bash
# Verify complete pipeline
make verify

# Verify data loaded in Fuseki and Milvus
make verify-data

# Verify Fuseki data
make verify-fuseki

# Verify Milvus-Fuseki connection
make verify-milvus

# Check Milvus collection data
make check-milvus-data

# Check Fuseki data
make check-fuseki-data
```

## Querying

```bash
# Run custom SPARQL query
make query-custom SPARQL="SELECT * WHERE { ?s ?p ?o } LIMIT 10"
```

## Development

```bash
# Check dependencies
make check-deps

# Clean temporary files
make clean

# Clean logs
make clean-logs

# Clean all caches (Redis LLM, embedding, SPARQL)
make clean-cache

# Clean everything (files, logs, and caches)
make clean-all

# View project info
make info

# View all commands
make help
```

## Agents API (Docker)

```bash
# Build agents API Docker image
make api-build

# Start/stop API service
make api-up
make api-down
make api-restart

# View API logs
make api-logs

# Open shell in API container
make api-shell

# Check API health
make api-health

# Run tests in API container
make api-test
```

## Java/Maven (Jena Core)

```bash
# Clean Maven build
make maven-clean

# Compile Java code
make maven-compile

# Run Java tests
make maven-test

# Package Java modules
make maven-package

# Install to local Maven repository
make maven-install
```

## Documentation Structure

Comprehensive documentation available at http://localhost:8000 (after running `make docs-docker-up`):

- **Getting Started**: Installation, configuration, quickstart guide
- **Architecture**: System overview, multi-agent design, hybrid RAG, knowledge graph
- **User Guides**:
- Document ingestion pipeline (complete deep dive)
- Query & retrieval strategies
- Schema evolution and ontology management
- Observability and monitoring
- **API Reference**: Complete API documentation for all agents, storage, and LLM providers
- **Development**: Contributing guidelines, testing strategies, deployment guides
- **Performance**: Optimization techniques, benchmarks, scaling strategies

**Key Documentation:**
- [Ingestion Pipeline Deep Dive](docs/guide/ingestion-pipeline-deep-dive.md) - Complete 100% coverage of ingestion process
- [Architecture Overview](docs/architecture/overview.md) - System architecture and design patterns
- [Quick Start Guide](docs/getting-started/quickstart.md) - Get up and running in 5 minutes


## Contributing

See [docs/development/contributing.md](docs/development/contributing.md) for contribution guidelines.

## License

[Add your license here]

## Links

- [Full Documentation](http://localhost:8000) (after running `make docs-docker-up`)
- [Apache Jena](https://jena.apache.org/)
- [Milvus](https://milvus.io/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Phoenix](https://phoenix.arize.com/)