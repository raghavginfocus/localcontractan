# Testing Guide

Comprehensive guide for testing the Contract Knowledge Graph system.

## Test Structure

```
agents/tests/
├── conftest.py                # Shared pytest fixtures
├── test_config.py            # Configuration tests
├── test_storage.py           # Storage connection tests
├── test_ingestion.py         # Document ingestion tests
├── test_retrieval.py         # Query and retrieval tests
├── test_api.py               # FastAPI endpoint tests
├── test_utilities.py         # Utility function tests
├── test_fuseki_client.py     # SPARQL client tests
├── test_clause_extraction.py # Clause extraction tests
├── test_vector_store.py      # Vector store tests
└── test_cases/               # Test case definitions (YAML)
    ├── test_cases_simple.yaml
    ├── test_cases_medium.yaml
    └── test_cases_complex.yaml
```

## Running Tests

### Prerequisites

Ensure dependencies are installed:

```bash
cd agents
uv sync
```

### All Tests

```bash
cd agents
PYTHONPATH=src uv run pytest
```

### With Coverage Report

```bash
cd agents
PYTHONPATH=src uv run pytest --cov=src --cov-report=html --cov-report=term
```

View HTML coverage report:

```bash
open htmlcov/index.html
```

### Specific Test File

```bash
PYTHONPATH=src uv run pytest tests/test_ingestion.py
```

### Specific Test Function

```bash
PYTHONPATH=src uv run pytest tests/test_ingestion.py::test_enhanced_document_ingestion
```

### Verbose Output

```bash
PYTHONPATH=src uv run pytest -v
```

### Stop on First Failure

```bash
PYTHONPATH=src uv run pytest -x
```

### Run Tests in Parallel

```bash
PYTHONPATH=src uv run pytest -n auto
```

## Test Categories

### Unit Tests (No External Dependencies)

These tests run without live services:

```bash
PYTHONPATH=src uv run pytest tests/test_config.py tests/test_utilities.py
```

**Tests:**
- Configuration validation
- Utility functions
- Data models
- Helper functions

### Integration Tests (Require Services)

These tests need Fuseki and Milvus running:

```bash
# Start services first
make services-up

# Run integration tests
PYTHONPATH=src uv run pytest tests/test_storage.py tests/test_fuseki_client.py
```

**Tests:**
- Fuseki connection
- Milvus connection
- SPARQL queries
- Vector operations

### End-to-End Tests

Full pipeline tests:

```bash
PYTHONPATH=src uv run pytest tests/test_ingestion.py tests/test_retrieval.py
```

## Current Test Coverage

### Overall Coverage: 27%

```
Component                        Coverage
─────────────────────────────────────────
config.py                        99%
directory_scanner.py             96%
query_classifier.py              79%
complexity_detector.py           77%
ontology_manager.py              74%
enhanced_document_ingestion.py   60%
api/main.py                      52%
batch_processor.py               46%
```

### Test Results Summary

- **Total Tests**: 62
- **Passing**: 49 (79%)
- **Failing**: 13 (21% - require live services)

## Writing Tests

### Test Structure

```python
import pytest
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

@pytest.mark.asyncio
async def test_document_extraction():
    """Test document text extraction"""
    # Arrange
    agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    
    # Act
    result = await agent.process("test_document.pdf")
    
    # Assert
    assert result is not None
    assert len(result.text) > 0
    assert result.confidence > 0.5
```

### Using Fixtures

```python
import pytest
from config import get_settings

@pytest.fixture
def settings():
    """Provide test settings"""
    return get_settings()

@pytest.fixture
def sample_text():
    """Provide sample contract text"""
    return """
    PAYMENT TERMS
    Payment shall be made within 30 days.
    """

def test_with_fixtures(settings, sample_text):
    """Test using fixtures"""
    assert settings is not None
    assert len(sample_text) > 0
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    """Test async function"""
    result = await some_async_function()
    assert result is not None
```

### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("contract.pdf", "pdf"),
    ("document.docx", "docx"),
    ("spreadsheet.xlsx", "xlsx"),
])
def test_file_extension(input, expected):
    """Test file extension detection"""
    ext = get_extension(input)
    assert ext == expected
```

### Mocking External Services

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.asyncio
async def test_with_mock():
    """Test with mocked service"""
    with patch('fuseki_client.FusekiClient') as mock_client:
        mock_client.return_value.query.return_value = [
            {"contract": "ABC123"}
        ]
        
        result = await query_contracts()
        assert len(result) == 1
```

## Test Configuration

### pytest.ini

Located in `agents/pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
```

### Coverage Configuration

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/test_*.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      fuseki:
        image: stain/jena-fuseki:latest
        ports:
          - 3030:3030
      
      milvus:
        image: milvusdb/milvus:v2.3.4
        ports:
          - 19530:19530
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      
      - name: Install dependencies
        run: cd agents && uv sync
      
      - name: Run tests
        run: cd agents && PYTHONPATH=src uv run pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./agents/coverage.xml
```

## Best Practices

### 1. Test Naming

Use descriptive names:

```python
# Good
def test_enhanced_document_ingestion_extracts_text_from_pdf():
    pass

# Avoid
def test_ingestion():
    pass
```

### 2. Arrange-Act-Assert Pattern

```python
def test_clause_extraction():
    # Arrange: Set up test data
    agent = ClauseExtractionAgent(settings=get_settings())
    text = "Payment terms: Net 30 days"
    
    # Act: Execute the function
    result = await agent.process({"text": text})
    
    # Assert: Verify the result
    assert len(result.clauses) > 0
    assert result.clauses[0].clause_type == "payment"
```

### 3. Test Independence

Each test should be independent:

```python
# Good: Independent tests
def test_feature_a():
    result = function_a()
    assert result == expected_a

def test_feature_b():
    result = function_b()
    assert result == expected_b

# Avoid: Tests depending on each other
def test_setup():
    global data
    data = setup_data()

def test_using_setup():
    # Depends on test_setup running first
    assert data is not None
```

### 4. Use Fixtures for Common Setup

```python
@pytest.fixture
def ingestion_agent():
    """Reusable agent fixture"""
    return EnhancedDocumentIngestionAgent(settings=get_settings())

def test_pdf_extraction(ingestion_agent):
    result = await ingestion_agent.process("test.pdf")
    assert result is not None

def test_docx_extraction(ingestion_agent):
    result = await ingestion_agent.process("test.docx")
    assert result is not None
```

### 5. Test Error Conditions

```python
def test_invalid_file_format():
    """Test handling of invalid file format"""
    agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    
    with pytest.raises(ValueError):
        await agent.process("invalid.xyz")

def test_missing_file():
    """Test handling of missing file"""
    agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    
    with pytest.raises(FileNotFoundError):
        await agent.process("nonexistent.pdf")
```

## Debugging Tests

### Run with Debug Output

```bash
PYTHONPATH=src uv run pytest -vv --tb=long
```

### Use pdb for Debugging

```python
def test_with_debugger():
    result = some_function()
    import pdb; pdb.set_trace()  # Breakpoint
    assert result is not None
```

### Print Statements

```bash
PYTHONPATH=src uv run pytest -s  # Show print statements
```

## Performance Testing

### Measure Test Duration

```bash
PYTHONPATH=src uv run pytest --durations=10
```

### Profile Tests

```bash
PYTHONPATH=src uv run pytest --profile
```

## Test Data

### Sample Files

Located in `examples/` directory:

- PDF contracts
- DOCX documents
- Excel spreadsheets
- Email files (.eml)

### Test Fixtures

Located in `tests/fixtures/`:

- Sample contract text
- Mock responses
- Test configurations

## Troubleshooting

### Common Issues

**Issue**: Tests fail with "ModuleNotFoundError"

**Solution**: Set PYTHONPATH

```bash
PYTHONPATH=src uv run pytest
```

**Issue**: Integration tests fail

**Solution**: Ensure services are running

```bash
make services-up
make health
```

**Issue**: Async tests not running

**Solution**: Install pytest-asyncio

```bash
uv add --dev pytest-asyncio
```

## Next Steps

1. **Increase Coverage**: Target 35-40% coverage
2. **Add Integration Tests**: Test full pipelines
3. **Performance Tests**: Benchmark critical paths
4. **CI/CD Integration**: Automate testing

## See Also

- [API Reference](../api/agents/ingestion.md)
- [Development Guide](contributing.md)
- [Deployment Guide](deployment.md)