# Contract Knowledge Graph Agents

> **Multi-Agent System for Intelligent Contract Analysis**

LLM-powered agents for automated contract ingestion, semantic extraction, and intelligent retrieval using Knowledge Graphs and Hybrid RAG.

##  Overview

This directory contains the core agent implementations for the Contract Knowledge Graph system. The agents are organized into three main pipelines:

1. **Ingestion Pipeline** (10 agents): Transform documents into knowledge graph
2. **Retrieval Pipeline** (4 agents): Answer queries using hybrid search
3. **Schema Evolution** (4 agents): Dynamically evolve ontology and rules

##  Key Features

- ** Document Ingestion**: Extract text from PDF/DOCX contracts with metadata
- ** Clause Extraction**: LLM-powered identification and classification of 10+ clause types
- ** Entity Recognition**: Extract parties, dates, amounts, jurisdictions
- ** Obligation & Risk Analysis**: Automatic risk scoring and compliance checking
- ** RDF Generation**: Convert extracted data to semantic RDF triples
- ** Knowledge Graph Loading**: Store in Apache Jena Fuseki with reasoning
- ** Vector Indexing**: Create semantic embeddings in Milvus
- ** SPARQL Generation**: Convert natural language to SPARQL queries
- ** Hybrid RAG**: Intelligently combine Knowledge Graph + vector search
- ** ReAct Reasoning**: Multi-step reasoning for complex queries

## Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Or install with dev dependencies
uv sync --dev
```

Alternatively, with pip:

```bash
pip install -e ".[dev]"
```

##  Directory Structure

```
agents/
├── src/
│   ├── agents/
│   │   ├── ingestion/          # 10 ingestion agents
│   │   ├── retrieval/          # 4 retrieval agents
│   │   ├── schema_evolution/   # 4 schema agents
│   │   └── shared/             # Base agent class
│   ├── storage/                # Storage abstraction
│   │   ├── sparql/             # Fuseki/SPARQL stores
│   │   └── vector/             # Milvus vector stores
│   ├── llm/                    # LLM provider abstraction
│   │   └── providers/          # Ollama, WatsonX
│   ├── observability/          # Phoenix tracing
│   └── logger/                 # Structured logging
├── tests/                      # All test files
└── checkpoints/                # LangGraph checkpoints
```

See [src/README.md](src/README.md) for detailed module documentation.

##  Quick Start

### Installation

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Or install with dev dependencies
uv sync --dev
```

Alternatively, with pip:

```bash
pip install -e ".[dev]"
```

### Configuration

Copy `env.example` to `.env` and configure:

```bash
cp env.example .env
```

Required environment variables:
- `FUSEKI_ENDPOINT`: Fuseki SPARQL endpoint (default: http://localhost:3030/contracts)
- `MILVUS_HOST`: Milvus host (default: localhost)
- `MILVUS_PORT`: Milvus port (default: 19530)
- `LLM_PROVIDER`: LLM provider (ollama or watsonx)
- `OLLAMA_BASE_URL`: Ollama endpoint (if using Ollama)
- `WATSONX_API_KEY`: WatsonX API key (if using WatsonX)

### Usage Examples

**Ingestion:**
```python
from agents.ingestion import IngestionOrchestrator
from config import get_settings

# Initialize orchestrator
orchestrator = IngestionOrchestrator(settings=get_settings())

# Ingest a document
result = await orchestrator.process({
    "file_path": "examples/contract.pdf",
    "document_id": "contract_001"
})

print(f"Ingested {result.triple_count} triples")
print(f"Indexed {result.vector_count} clauses")
```

**Retrieval:**
```python
from agents.retrieval import RetrievalOrchestratorV2
from config import get_settings

# Initialize retrieval orchestrator
orchestrator = RetrievalOrchestratorV2(settings=get_settings())

# Query the knowledge graph
response = await orchestrator.process({
    "query": "What are the high-risk termination clauses?"
})

print(response.answer)
print(f"Sources: {response.sources}")
```

**Direct Agent Usage:**
```python
from agents.ingestion import ClauseExtractionAgent
from agents.retrieval import RAGOrchestratorAgent

# Extract clauses from text
clause_agent = ClauseExtractionAgent()
clauses = await clause_agent.process({
    "document_text": "This agreement may be terminated...",
    "document_id": "doc_001"
})

# Simple RAG query
rag_agent = RAGOrchestratorAgent()
response = await rag_agent.process({
    "query": "What are the payment terms?"
})
```

##  Agent Pipelines

### Ingestion Pipeline (10 Agents)

1. **DocumentIngestionAgent**: Extract text from PDF/DOCX
2. **ClauseExtractionAgent**: Identify and classify clauses
3. **EntityExtractionAgent**: Extract parties, dates, amounts
4. **ObligationRiskAgent**: Analyze obligations and risks
5. **OntologyAlignmentAgent**: Align with ontology
6. **RDFGeneratorAgent**: Generate RDF triples
7. **ValidationAgent**: Validate extracted data
8. **FusekiLoaderAgent**: Load into Fuseki
9. **VectorIndexAgent**: Create vector embeddings
10. **ReasoningAgent**: Apply inference rules

### Retrieval Pipeline (4 Agents)

1. **UnifiedQueryAnalyzer**: Analyze query complexity
2. **SPARQLGeneratorAgent**: Generate SPARQL queries
3. **RAGOrchestratorAgent**: Simple RAG (vector + KG)
4. **ReactAgentOptimized**: Complex multi-step reasoning

### Schema Evolution (4 Agents)

1. **PatternDetectionAgent**: Detect data patterns
2. **OntologyDesignerAgent**: Design ontology extensions
3. **RuleGeneratorAgent**: Generate inference rules
4. **SHACLGeneratorAgent**: Generate validation shapes

# Analyze all runs and save to file
cd agents
PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py --output logs/ingestion/analysis_report.md

# Analyze only last 5 runs
PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py --last 5

# Print to console
PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py

# Custom log file
PYTHONPATH=src uv run python ../scripts/analyze_ingestion_logs.py --log-file logs/ingestion/ingestion.log

# Normal processing (skips duplicates automatically)
cd agents
PYTHONPATH=src uv run python ../scripts/run_ingestion_pipeline.py

# Force reprocessing
PYTHONPATH=src uv run python ../scripts/run_ingestion_pipeline.py --override

# Run evaluation on test files
cd /Users/manu/Documents/repos/contract-jena/agents && PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml tests/test_cases_retrieval.yaml --verbose 2>&1 | head -100

cd agents

# Run all tests from the new YAML file
PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml tests/test_cases_retrieval.yaml

# Run with verbose output
PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml tests/test_cases_retrieval.yaml --verbose

# Run specific test case
PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml tests/test_cases_retrieval.yaml --case-id termination_analysis

# Filter by category
PYTHONPATH=src uv run python ../scripts/evaluate_enhanced.py --yaml tests/test_cases_retrieval.yaml --category risk

cd agents

# Analyze all retrieval sessions
PYTHONPATH=src uv run python ../scripts/analyze_retrieval_logs.py

# Analyze last 10 sessions and save to file
PYTHONPATH=src uv run python ../scripts/analyze_retrieval_logs.py --last 10 --output logs/retrieval/analysis_report.md

## Monitoring

### Process & Thread Monitoring

**Using the monitoring script (recommended - cross-platform):**
```bash
# One-time snapshot
python scripts/monitor_ingestion.py

# Continuous monitoring (updates every 2 seconds)
python scripts/monitor_ingestion.py --watch

# Custom interval
python scripts/monitor_ingestion.py --watch --interval 1.0
```

**macOS terminal commands:**
```bash
# Find ingestion process PID
PID=$(pgrep -f "run_ingestion_pipeline")

# See thread count
ps -M $PID | wc -l

# See all threads with details
ps -M $PID

# See process info with thread count
ps -p $PID -M -o pid,ppid,command,thcount

# Monitor CPU/Memory usage
top -pid $PID

# See all Python processes
ps aux | grep -E "(python|uv)" | grep -v grep | head -20
```

**Linux terminal commands:**
```bash
# Process tree (requires pstree package)
pstree -p $(pgrep -f "run_ingestion_pipeline")

# Thread count
ps -M $(pgrep -f "run_ingestion_pipeline") | wc -l

# See all threads
ps -M $(pgrep -f "run_ingestion_pipeline")
```
