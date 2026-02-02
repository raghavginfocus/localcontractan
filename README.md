# Procurement Knowledge Graph RAG System

> **AI-Powered Contract Analysis using Knowledge Graphs and Hybrid RAG**

An intelligent system for automated contract ingestion, semantic extraction, and retrieval using Apache Jena, LangGraph agents, and vector databases.

## Overview

This system transforms unstructured contract documents into a queryable knowledge graph, enabling intelligent contract analysis through:

- **Multi-Agent Ingestion Pipeline**: 10 specialized LLM agents extract clauses, entities, obligations, and risks
- **Hybrid RAG Retrieval**: Combines knowledge graph (SPARQL) and vector search for accurate answers
- **Semantic Reasoning**: Apache Jena inference engine applies domain rules
- **Observability**: Phoenix integration for tracing and monitoring
- **Production-Ready**: Docker-based deployment with FastAPI

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Documents     │────▶│  Ingestion       │────▶│  Knowledge      │
│  (PDF/DOCX)     │     │  Pipeline        │     │  Graph          │
└─────────────────┘     │  (10 Agents)     │     │  (Fuseki)       │
                        └──────────────────┘     └─────────────────┘
                                │                          │
                                ▼                          ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │  Vector Store    │     │  Reasoning      │
                        │  (Milvus)        │     │  Engine (Jena)  │
                        └──────────────────┘     └─────────────────┘
                                │                          │
                                └──────────┬───────────────┘
                                           ▼
                                ┌──────────────────┐
                                │  Retrieval       │
                                │  Pipeline        │
                                │  (Hybrid RAG)    │
                                └──────────────────┘
```

### Key Components

- **Agents** (`agents/`): Python-based LLM agents using LangGraph
- **Jena Core** (`jena-core/`): Java-based ontology management and reasoning
- **Fuseki Server** (`fuseki-server/`): SPARQL endpoint for knowledge graph
- **Docker** (`docker/`): Service orchestration (Fuseki, Milvus, Ollama, Phoenix)
- **Ontology** (`ontology/`): Procurement domain ontology (OWL)
- **Scripts** (`scripts/`): Utilities for ingestion, analysis, and evaluation

## Quick Start

### Prerequisites

- **Docker** & **Docker Compose**
- **Python 3.11+**
- **uv** (Python package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Make** (optional, for convenience commands)

### 1. Initial Setup

```bash
# Clone the repository
git clone git@github.ibm.com:bpod-wxtechlab/procurement_grag.git
cd procurement_grag

# Install Python dependencies
cd agents
uv sync

# Setup environment variables
cp env.example .env
# Edit .env with your configuration (LLM provider, API keys, etc.)
```

### 2. Start Services

```bash
# Start all services (Fuseki, Milvus, Ollama, Phoenix)
make services-up

# Or manually with docker-compose
cd docker
docker-compose up -d

# Check service health
make health
```

**Service URLs:**
- Fuseki: http://localhost:3030 (admin/admin123)
- Ollama: http://localhost:11434
- Phoenix: http://localhost:6006
- API: http://localhost:8001
- Docs: http://localhost:8000

**Optional: Start Milvus Web UI (Attu)**

Attu provides a web interface to browse and manage Milvus vector collections:

```bash
# Start services with Attu UI
make services-up-ui

# Or manually with docker-compose
cd docker && docker-compose --profile with-ui up -d

# Access Attu at: http://localhost:8080
```

### 3. Load Initial Data

```bash
# Setup Fuseki dataset and load ontology
make data-setup-fuseki
make data-load-ontology

# Or run complete data setup
make data-load-all
```

### 4. Run Ingestion

```bash
# Ingest all documents in examples/ directory
make ingest

# Or ingest a single document
make ingest-single FILE=examples/contract.pdf

# Monitor ingestion progress
python scripts/ingestion/monitor_ingestion.py --watch
```

### 5. Query the System

**Using the API:**
```bash
# Start the API service
make api-up

# Query via API
make api-query Q="What are the termination clauses in the contracts?"

# Or use curl directly
curl -X POST http://localhost:8001/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What are high-risk obligations?", "max_results": 10}'
```

**Using Python:**
```python
from agents.retrieval import RetrievalOrchestratorV2
from config import get_settings

orchestrator = RetrievalOrchestratorV2(settings=get_settings())
response = await orchestrator.process({
    "query": "What are the payment terms?"
})
print(response.answer)
```

## Common Tasks

### Ingestion Pipeline

```bash
# Run complete ingestion
make ingest

# Force reprocess all documents
make ingest-override

# Ingest single document
make ingest-single FILE=path/to/contract.pdf

# Analyze ingestion logs
make logs-analyze-ingestion
```

### Retrieval & Testing

```bash
# Run retrieval tests
make retrieval-test

# Evaluate with test cases
make evaluate-yaml YAML=agents/tests/test_cases/test_cases_retrieval.yaml

# Test specific category
make evaluate-category CAT=risk

# Run API tests
make api-test-all
```

### Service Management

```bash
# Start all services (without UI)
make services-up

# Start all services with Milvus UI (Attu)
make services-up-ui

# Stop all services
make services-down

# Restart services
make services-restart

# View logs
make services-logs
make services-logs-fuseki
make services-logs-milvus

# Check service status
make services-status
make health
```

### Data Management

```bash
# Load ontology
make data-load-ontology

# Setup text indexing
make data-setup-text-index

# Migrate Milvus schema
make data-migrate-milvus

# Check data
make check-fuseki-data
make check-milvus-data
```

### Monitoring & Analysis

```bash
# View logs
make logs-view
make logs-view-all

# Analyze ingestion logs
make logs-analyze-ingestion
make logs-analyze-ingestion-last N=5

# Analyze retrieval logs
make logs-analyze-retrieval
make logs-analyze-retrieval-last N=10

# Clean caches
make clean-cache
make clean-all
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Test specific components
make test-fuseki
make ingest-test
make retrieval-test

# Run evaluation
make evaluate
make evaluate-verbose
```

## Documentation

```bash
# Serve documentation locally
make docs-serve
# Visit http://localhost:8000

# Or use Docker
make docs-docker-up

# Build documentation
make docs-build
```

## Development

### Project Structure

```
procurement_grag/
├── agents/                 # Python agents (ingestion, retrieval, schema evolution)
│   ├── src/
│   │   ├── agents/        # Agent implementations
│   │   ├── storage/       # Storage abstraction (SPARQL, Vector)
│   │   ├── llm/           # LLM provider abstraction
│   │   └── api/           # FastAPI service
│   └── tests/             # Test suites
├── jena-core/             # Java-based Jena integration
├── fuseki-server/         # Fuseki server configuration
├── docker/                # Docker Compose setup
├── ontology/              # OWL ontology files
├── rules/                 # Jena reasoning rules
├── scripts/               # Utility scripts
├── docs/                  # MkDocs documentation
└── examples/              # Sample contract documents
```

### Environment Configuration

Key environment variables in `agents/.env`:

```bash
# LLM Provider (ollama or watsonx)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Or for WatsonX
# LLM_PROVIDER=watsonx
# WATSONX_API_KEY=your_api_key
# WATSONX_PROJECT_ID=your_project_id

# Storage
FUSEKI_ENDPOINT=http://localhost:3030/contracts
MILVUS_HOST=localhost
MILVUS_PORT=19530

# Observability
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:4317
```

### Adding New Documents

1. Place documents in `examples/` directory
2. Run ingestion: `make ingest`
3. Verify: `make verify`

### Extending the System

- **Add new agent**: Create in `agents/src/agents/`
- **Add new ontology class**: Edit `ontology/procurement.owl`
- **Add reasoning rule**: Edit `rules/procurement.rules`
- **Add test case**: Edit `agents/tests/test_cases/*.yaml`

## Troubleshooting

### Services not starting
```bash
# Check Docker status
docker ps

# View service logs
make services-logs

# Restart services
make services-restart
```

### Ingestion failures
```bash
# Check pre-ingestion
cd agents
PYTHONPATH=src uv run python ../scripts/ingestion/pre_ingestion_check.py

# View ingestion logs
make logs-analyze-ingestion
```

### Query not returning results
```bash
# Verify data in Fuseki
make check-fuseki-data

# Verify Milvus data
make check-milvus-data

# Check API health
make api-health
```

## Performance

- **Ingestion**: ~2-5 minutes per document (depends on LLM provider)
- **Query Response**: <2 seconds for simple queries, <5 seconds for complex
- **Concurrent Requests**: Supports 10+ concurrent API requests

## Contributing

See [docs/development/contributing.md](docs/development/contributing.md) for guidelines.

## License

MIT License - See LICENSE file for details.

## Resources

- **Documentation**: http://localhost:8000 (after `make docs-serve`)
- **API Docs**: http://localhost:8001/docs (after `make api-up`)
- **Phoenix Observability**: http://localhost:6006
- **Fuseki UI**: http://localhost:3030

## Support

For issues and questions, please open an issue in the repository.

---

**Quick Commands Reference:**

```bash
make help              # Show all available commands
make quickstart        # Complete setup and first run
make services-up       # Start all services
make ingest            # Run ingestion pipeline
make api-up            # Start API service
make test              # Run tests
make docs-serve        # Serve documentation