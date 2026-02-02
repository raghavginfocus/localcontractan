# Tests Directory

This directory contains all test scripts and test cases for the Contract Knowledge Graph RAG system.

## Directory Structure

### 🔍 `retrieval/`
Retrieval and query testing scripts:
- `test_hybrid_rag_queries.py` - Test hybrid RAG queries (KG + vector)
- `test_knowledge_graph_queries.py` - Test KG-only queries
- `test_new_document_queries.py` - Test queries on newly ingested documents
- `test_react_retrieval.py` - Test ReAct-based retrieval agent
- `test_multihop_retrieval.py` - Test multi-hop reasoning queries

### 📊 `observability/`
Observability and tracing tests:
- `test_phoenix_simple.py` - Simple Phoenix observability test
- `test_langgraph_phoenix.py` - LangGraph + Phoenix integration test
- `test_langgraph_v2.py` - LangGraph V2 orchestrator test

### 🤖 `agents/`
Individual agent component tests:
- `test_agents.py` - Test all agents
- `test_agent_individual.py` - Test individual agent components
- `test_llm_provider.py` - Test LLM provider implementations

### 📥 `ingestion/`
Ingestion pipeline tests:
- `test_full_ingestion.py` - Full end-to-end ingestion pipeline test

### 🏗️ `schema/`
Schema generation and evolution tests:
- `test_dynamic_schema_generation.py` - Test dynamic schema generation
- `test_shacl_generation.py` - Test SHACL shape generation
- `test_rule_generation.py` - Test rule generation

### 💾 `storage/`
Storage and infrastructure tests:
- `test_storage_abstraction.py` - Test storage abstraction layer
- `test_fuseki_client.py` - Test Fuseki SPARQL client

### ✨ `features/`
New feature tests:
- `test_new_features.py` - Test new experimental features

### 📋 `test_cases/`
YAML test case files for evaluation:
- `test_cases_simple.yaml` - Simple factual queries (6 test cases)
- `test_cases_medium.yaml` - Medium complexity analytical queries
- `test_cases_complex.yaml` - Complex multi-step reasoning queries
- `test_cases_retrieval.yaml` - Retrieval-specific test cases
- `test_cases_quick.yaml` - Quick smoke tests
- `test_cases_example.yaml` - Example test cases template

### 📊 `results/`
Test execution results and reports:
- Historical test run results and analysis reports

## Test Case Files Overview

### Simple Test Cases (`test_cases_simple.yaml`)
**Purpose:** Basic factual queries that should work with standard retrieval  
**Complexity Level:** Simple  
**Expected Strategy:** `simple` (RAG orchestrator)  
**Use Case:** Quick smoke tests, basic functionality verification

**Test Cases:**
- Contract counting
- Contract titles listing
- Termination clauses
- Payment terms
- Basic clause retrieval

**Run Command:**
```bash
make test-evaluate-simple
```

### Medium Test Cases (`test_cases_medium.yaml`)
**Purpose:** Analytical queries requiring reasoning across multiple contracts  
**Complexity Level:** Medium  
**Expected Strategy:** `simple` or `complex` depending on query  
**Use Case:** Testing analytical capabilities, clause extraction

**Test Cases:**
- Termination terms analysis
- Liability terms analysis
- Governing law and jurisdiction
- Intellectual property terms
- Confidentiality compliance
- Notice requirements

**Run Command:**
```bash
make test-evaluate-medium
```

### Complex Test Cases (`test_cases_complex.yaml`)
**Purpose:** Multi-dimensional queries requiring ReAct multi-step reasoning  
**Complexity Level:** Complex  
**Expected Strategy:** `complex` (ReAct agent)  
**Use Case:** Testing advanced reasoning, multi-hop queries

**Test Cases:**
- Risk analysis across contracts
- Compliance verification
- Contract comparison
- Multi-step reasoning queries

**Run Command:**
```bash
make test-evaluate-complex
```

## Running Tests

### Individual Test Scripts

```bash
cd agents
PYTHONPATH=src uv run python tests/<category>/<test_script>.py
```

### Evaluation with Test Cases

```bash
# Simple test cases
make test-evaluate YAML=tests/test_cases_simple.yaml

# Medium test cases
make test-evaluate YAML=tests/test_cases_medium.yaml

# Complex test cases
make test-evaluate YAML=tests/test_cases_complex.yaml
```

### Using pytest

```bash
cd agents
PYTHONPATH=src uv run pytest tests/ -v
```

## Test Categories

- **Unit Tests**: Test individual components (agents, storage, etc.)
- **Integration Tests**: Test component interactions (retrieval, ingestion)
- **End-to-End Tests**: Test complete workflows (full ingestion, retrieval pipeline)
- **Evaluation Tests**: Test against YAML test cases with metrics

## Documentation

- `README.md` - This file
- `MEDIUM_COMPLEX_TEST_CASES_SUMMARY.md` - Summary of medium/complex test cases

