# Test Suite

Minimal focused test suite for Contract Knowledge Graph system.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_config.py           # Configuration tests (5 tests)
├── test_storage.py          # Storage connection tests (3 tests)
├── test_ingestion.py        # Ingestion pipeline tests (4 tests)
├── test_retrieval.py        # Retrieval pipeline tests (3 tests)
├── test_api.py              # API endpoint tests (5 tests)
└── test_cases/              # YAML test cases for evaluation
```

## Running Tests

### All Tests
```bash
cd agents
PYTHONPATH=src uv run pytest tests/ -v
```

### Specific Test File
```bash
PYTHONPATH=src uv run pytest tests/test_config.py -v
```

### With Coverage Report
```bash
PYTHONPATH=src uv run pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
```

### View Coverage Report
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Categories

### 1. Configuration Tests (`test_config.py`)
- Settings load correctly
- LLM provider configured
- Fuseki configuration valid
- Milvus configuration valid

### 2. Storage Tests (`test_storage.py`)
- Fuseki connection works
- Milvus connection works
- Dataset exists

### 3. Ingestion Tests (`test_ingestion.py`)
- Directory scanner discovers files
- PDF extraction works
- DOCX extraction works
- Batch processor initializes

### 4. Retrieval Tests (`test_retrieval.py`)
- SPARQL generation works
- Complexity detection works
- Context-aware generation

### 5. API Tests (`test_api.py`)
- Health endpoint responds
- Query endpoint structure correct
- Documentation available
- OpenAPI schema valid

## Prerequisites

Tests require:
- Services running (Fuseki, Milvus) for integration tests
- Sample documents in `examples/` directory
- Environment variables configured in `.env`

## Skipping Tests

Tests automatically skip if:
- Required services not available
- Sample files not found
- Configuration missing

## Coverage Goals

- **Target**: 40-50% overall coverage
- **Critical Paths**: 80%+ (API, ingestion, retrieval)
- **Focus**: Core functionality over edge cases