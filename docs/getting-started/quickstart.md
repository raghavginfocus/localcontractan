# Quick Start Guide

Get up and running with Contract-Jena in under 10 minutes.

## Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for services)
- **uv** package manager (recommended)
- **8GB+ RAM** (for running all services)

## Installation

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone Repository

```bash
git clone https://github.com/your-org/contract-jena.git
cd contract-jena
```

### 3. Setup Environment

```bash
# Complete setup (dependencies + environment)
make setup

# Or manually:
cd agents && uv sync
cp env.example .env
```

### 4. Configure Environment

Edit `agents/.env` with your settings:

```bash
# LLM Provider (choose one)
LLM_PROVIDER=ollama  # or watsonx

# Ollama settings (if using local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# watsonx.ai settings (if using IBM)
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Storage endpoints
FUSEKI_ENDPOINT=http://localhost:3030
MILVUS_HOST=localhost
MILVUS_PORT=19530
```

## Start Services

### Using Make (Recommended)

```bash
# Start all services (Fuseki, Milvus, Ollama, Phoenix)
make services-up

# Check service health
make health

# View service URLs
make urls
```

### Manual Docker Compose

```bash
cd docker
docker-compose up -d

# With UI (includes Attu for Milvus)
docker-compose --profile with-ui up -d
```

### Verify Services

```bash
# Check running services
make services-status

# View logs
make services-logs

# Individual service logs
make services-logs-fuseki
make services-logs-milvus
```

## Ingest Your First Document

### 1. Place Documents

```bash
# Copy your contracts to examples folder
cp /path/to/contract.pdf examples/
```

### 2. Run Ingestion

```bash
# Ingest all documents in examples/
make ingest

# Or ingest a single document
make ingest-single FILE=examples/contract.pdf
```

### 3. Monitor Progress

```bash
# View ingestion logs
make logs-view

# Analyze ingestion performance
make logs-analyze-ingestion
```

## Query the Knowledge Graph

### Using the API (Recommended)

```bash
# Start the API server (if not already running)
make api-up

# Query API directly with a question
make api-query Q="What are the termination clauses in the contracts?"

# Test with simple queries
make api-test-simple

# Test with medium complexity queries
make api-test-medium

# Test with complex queries
make api-test-complex

# Test all query levels
make api-test-all

# Test with custom YAML file
make api-test-custom YAML=path/to/test_cases.yaml
```

### Using the Evaluation Framework

```bash
# Run simple test cases
make test-evaluate YAML=tests/test_cases/test_cases_simple.yaml

# Run with verbose output
make evaluate-yaml-verbose YAML=tests/test_cases/test_cases_simple.yaml
```

### Using Python API

```python
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import (
    LangGraphRetrievalOrchestrator
)

# Initialize orchestrator
orchestrator = LangGraphRetrievalOrchestrator()

# Ask a question
result = await orchestrator.retrieve(
    question="What are the termination clauses in the contracts?"
)

print(f"Answer: {result['answer']}")
print(f"Confidence: {result['confidence']}")
print(f"KG Facts: {result['kg_facts_count']}")
```

### Using SPARQL Directly

```bash
# Custom SPARQL query
make query-custom SPARQL="SELECT ?contract ?title WHERE { 
  ?contract a proc:Contract ; 
            proc:hasTitle ?title 
} LIMIT 10"
```

## View Observability Dashboard

Phoenix provides real-time observability for all LLM calls and agent executions.

```bash
# Phoenix is automatically started with services
# Access at: http://localhost:6006

# View traces, spans, and performance metrics
open http://localhost:6006
```

## Next Steps

- **[Configuration Guide](configuration.md)**: Detailed configuration options
- **[Architecture Overview](../architecture/overview.md)**: Understand the system design
- **[Ingestion Guide](../guide/ingestion.md)**: Advanced ingestion features
- **[Retrieval Guide](../guide/retrieval.md)**: Query patterns and optimization

## Common Commands

```bash
# Service Management
make services-up          # Start all services
make services-down        # Stop all services
make services-restart     # Restart services
make health              # Check service health

# API Management
make api-up              # Start API server
make api-down            # Stop API server
make api-logs            # View API logs
make api-query Q="..."   # Query API directly with question
make api-test-simple     # Test API with simple queries
make api-test-medium     # Test API with medium queries
make api-test-complex    # Test API with complex queries
make api-test-all        # Test API with all query levels

# Data Operations
make ingest              # Run ingestion pipeline
make ingest-override     # Force reprocess all documents
make data-setup-text-index  # Setup text indexing

# Testing & Evaluation
make test                # Run all tests
make test-evaluate       # Run evaluation tests
make evaluate-verbose    # Verbose evaluation

# Monitoring
make logs-view           # View latest logs
make logs-analyze-ingestion  # Analyze ingestion logs
make logs-analyze-retrieval  # Analyze retrieval logs

# Utilities
make clean               # Clean temporary files
make clean-logs          # Clean log files
make clean-cache         # Clean all caches (Redis)
make clean-all           # Clean everything
make urls                # Display service URLs
```

## Troubleshooting

### Services Won't Start

```bash
# Check Docker is running
docker ps

# Check port conflicts
lsof -i :3030  # Fuseki
lsof -i :19530 # Milvus
lsof -i :6006  # Phoenix

# View service logs
make services-logs
```

### Ingestion Fails

```bash
# Check service health
make health

# Verify Fuseki is accessible
curl http://localhost:3030/$/ping

# Check Milvus connection
make check-milvus-data

# View detailed logs
make logs-view
```

### Slow Query Performance

```bash
# Check Phoenix traces
open http://localhost:6006

# Analyze retrieval logs
make logs-analyze-retrieval

# Run performance benchmarks
make benchmark
```

## Getting Help

- **Documentation**: Browse the full documentation
- **GitHub Issues**: [Report bugs or request features](https://github.com/your-org/contract-jena/issues)
- **Phoenix Dashboard**: Check LLM traces at http://localhost:6006