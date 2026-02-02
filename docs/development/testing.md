# Testing Guide

Comprehensive guide for testing the Contract Knowledge Graph system.

## Test Structure

```
agents/tests/
├── agents/                    # Agent tests
│   ├── test_ingestion.py
│   ├── test_retrieval.py
│   └── test_schema_evolution.py
├── storage/                   # Storage tests
│   ├── test_fuseki_client.py
│   └── test_milvus_store.py
├── features/                  # Feature tests
│   └── test_new_features.py
├── ingestion/                 # Integration tests
│   └── test_full_ingestion.py
├── retrieval/                 # Retrieval tests
│   └── test_hybrid_rag.py
└── test_cases/               # Test case definitions
    ├── test_cases_simple.yaml
    ├── test_cases_medium.yaml
    └── test_cases_complex.yaml
```

## Running Tests

### All Tests

```bash
cd agents
uv run pytest
```

### Specific Test File

```bash
uv run pytest tests/agents/test_ingestion.py
```

### Specific Test Function

```bash
uv run pytest tests/agents/test_ingestion.py::test_document_ingestion
```

### By Marker

```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

### With Coverage

```bash
# Generate coverage report
uv run pytest --cov=agents/src --cov-report=html

# View report
open htmlcov/index.html
```

### Verbose Output

```bash
# Show print statements
uv run pytest -s

# Verbose output
uv run pytest -v

# Very verbose
uv run pytest -vv
```

## Writing Tests

### Unit Tests

Test individual components in isolation:

```python
import pytest
from agents.ingestion.clause_extraction import ClauseExtractionAgent

class TestClauseExtraction:
    """Test clause extraction agent."""
    
    def test_extract_clauses(self):
        """Test basic clause extraction."""
        agent = ClauseExtractionAgent()
        
        text = """
        1. Termination: Either party may terminate with 30 days notice.
        2. Payment: Payment due within 30 days of invoice.
        """
        
        clauses = agent.extract_clauses(text)
        
        assert len(clauses) == 2
        assert clauses[0].type == "TerminationClause"
        assert clauses[1].type == "PaymentClause"
    
    def test_empty_text(self):
        """Test with empty text."""
        agent = ClauseExtractionAgent()
        
        with pytest.raises(ValueError):
            agent.extract_clauses("")
    
    def test_invalid_format(self):
        """Test with invalid format."""
        agent = ClauseExtractionAgent()
        
        clauses = agent.extract_clauses("Random text without clauses")
        
        assert len(clauses) == 0
```

### Integration Tests

Test component interactions:

```python
import pytest
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

@pytest.mark.integration
class TestIngestionPipeline:
    """Test complete ingestion pipeline."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return IngestionOrchestrator(
            enable_schema_evolution=False,
            enable_reasoning=False
        )
    
    def test_full_ingestion(self, orchestrator, tmp_path):
        """Test complete document ingestion."""
        # Create test document
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("Test contract content")
        
        # Ingest
        result = orchestrator.ingest_document(
            file_path=str(doc_path),
            graph_uri="http://test.org/contracts"
        )
        
        # Verify
        assert result.success
        assert result.clauses_extracted > 0
        assert result.triples_loaded > 0
```

### Fixtures

Reusable test data and setup:

```python
import pytest
from pathlib import Path

@pytest.fixture
def sample_contract():
    """Sample contract data."""
    return {
        "id": "ABC123",
        "text": "Sample contract text...",
        "parties": ["IBM", "Acme Corp"]
    }

@pytest.fixture
def test_document(tmp_path):
    """Create temporary test document."""
    doc_path = tmp_path / "contract.txt"
    doc_path.write_text("Test contract content")
    return doc_path

@pytest.fixture(scope="session")
def fuseki_client():
    """Fuseki client for testing."""
    from storage.sparql.fuseki_store import FusekiStore
    
    client = FusekiStore(
        endpoint="http://localhost:3030/test",
        graph_uri="http://test.org/contracts"
    )
    
    yield client
    
    # Cleanup
    client.clear_graph()
```

### Parametrized Tests

Test multiple scenarios:

```python
import pytest

@pytest.mark.parametrize("text,expected_count", [
    ("Clause 1. Termination", 1),
    ("Clause 1. Termination\nClause 2. Payment", 2),
    ("", 0),
])
def test_clause_count(text, expected_count):
    """Test clause extraction with different inputs."""
    agent = ClauseExtractionAgent()
    clauses = agent.extract_clauses(text)
    assert len(clauses) == expected_count
```

### Mocking

Mock external dependencies:

```python
from unittest.mock import Mock, patch
import pytest

def test_with_mock_llm():
    """Test agent with mocked LLM."""
    mock_llm = Mock()
    mock_llm.invoke.return_value.content = "Mocked response"
    
    agent = ClauseExtractionAgent(llm=mock_llm)
    result = agent.extract_clauses("Test text")
    
    mock_llm.invoke.assert_called_once()

@patch('agents.ingestion.document_ingestion.extract_text')
def test_with_patched_function(mock_extract):
    """Test with patched function."""
    mock_extract.return_value = "Extracted text"
    
    agent = DocumentIngestionAgent()
    result = agent.process("test.pdf")
    
    assert result.text == "Extracted text"
```

## Test Markers

Mark tests for selective execution:

```python
import pytest

@pytest.mark.unit
def test_unit():
    """Unit test."""
    pass

@pytest.mark.integration
def test_integration():
    """Integration test."""
    pass

@pytest.mark.slow
def test_slow_operation():
    """Slow test."""
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    """Future test."""
    pass

@pytest.mark.skipif(
    not has_gpu(),
    reason="Requires GPU"
)
def test_gpu_operation():
    """GPU test."""
    pass
```

## Test Configuration

### pytest.ini

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: Unit tests
    integration: Integration tests
    slow: Slow tests
    gpu: Tests requiring GPU

addopts =
    -v
    --strict-markers
    --tb=short
    --cov=agents/src
    --cov-report=term-missing
```

### conftest.py

Shared fixtures and configuration:

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def test_data_dir():
    """Test data directory."""
    return Path(__file__).parent / "data"

@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment before each test."""
    # Setup
    yield
    # Teardown
```

## Coverage

### Measuring Coverage

```bash
# Run with coverage
uv run pytest --cov=agents/src

# Generate HTML report
uv run pytest --cov=agents/src --cov-report=html

# Show missing lines
uv run pytest --cov=agents/src --cov-report=term-missing
```

### Coverage Goals

- **Overall:** >80%
- **Critical paths:** >90%
- **New code:** 100%

### Excluding Code

```python
def debug_function():  # pragma: no cover
    """Debug function not tested."""
    print("Debug info")
```

## Performance Testing

### Timing Tests

```python
import time
import pytest

def test_performance():
    """Test performance requirements."""
    agent = ClauseExtractionAgent()
    
    start = time.time()
    result = agent.extract_clauses(large_text)
    duration = time.time() - start
    
    assert duration < 5.0  # Must complete in 5 seconds
```

### Benchmarking

```python
import pytest

@pytest.mark.benchmark
def test_benchmark(benchmark):
    """Benchmark clause extraction."""
    agent = ClauseExtractionAgent()
    
    result = benchmark(agent.extract_clauses, test_text)
    
    assert result is not None
```

## Test Data

### YAML Test Cases

```yaml
# tests/test_cases/test_cases_simple.yaml
test_cases:
  - name: "Simple contract query"
    query: "List all contracts"
    expected_intent: "list_contracts"
    expected_complexity: "simple"
    
  - name: "Find specific contract"
    query: "Find contract ABC123"
    expected_intent: "find_contract"
    expected_complexity: "simple"
```

### Loading Test Cases

```python
import yaml
import pytest

def load_test_cases(file_path):
    """Load test cases from YAML."""
    with open(file_path) as f:
        data = yaml.safe_load(f)
    return data['test_cases']

@pytest.mark.parametrize(
    "test_case",
    load_test_cases("tests/test_cases/test_cases_simple.yaml")
)
def test_from_yaml(test_case):
    """Test from YAML test case."""
    classifier = QueryClassifier()
    
    intent = classifier.classify(test_case['query'])
    
    assert intent == test_case['expected_intent']
```

## Continuous Integration

### GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install uv
          cd agents
          uv sync
      
      - name: Run tests
        run: |
          cd agents
          uv run pytest --cov=agents/src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## Best Practices

### 1. Test Naming

```python
# ✅ Good - descriptive names
def test_extract_clauses_from_valid_contract():
    pass

def test_extract_clauses_raises_error_on_empty_text():
    pass

# ❌ Bad - vague names
def test_1():
    pass

def test_extraction():
    pass
```

### 2. Arrange-Act-Assert

```python
def test_clause_extraction():
    # Arrange
    agent = ClauseExtractionAgent()
    text = "Sample contract text"
    
    # Act
    result = agent.extract_clauses(text)
    
    # Assert
    assert len(result) > 0
    assert result[0].type == "TerminationClause"
```

### 3. One Assertion Per Test

```python
# ✅ Good - focused tests
def test_clause_count():
    clauses = extract_clauses(text)
    assert len(clauses) == 2

def test_clause_types():
    clauses = extract_clauses(text)
    assert clauses[0].type == "TerminationClause"

# ❌ Bad - multiple concerns
def test_everything():
    clauses = extract_clauses(text)
    assert len(clauses) == 2
    assert clauses[0].type == "TerminationClause"
    assert clauses[1].confidence > 0.8
```

### 4. Use Fixtures

```python
# ✅ Good - reusable setup
@pytest.fixture
def agent():
    return ClauseExtractionAgent()

def test_with_fixture(agent):
    result = agent.extract_clauses(text)
    assert result is not None

# ❌ Bad - repeated setup
def test_without_fixture():
    agent = ClauseExtractionAgent()
    result = agent.extract_clauses(text)
    assert result is not None
```

### 5. Clean Up Resources

```python
@pytest.fixture
def temp_file(tmp_path):
    """Create temporary file."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("content")
    
    yield file_path
    
    # Cleanup happens automatically with tmp_path
```

## Troubleshooting

### Tests Failing Locally

1. Check dependencies: `uv sync`
2. Clear cache: `pytest --cache-clear`
3. Run with verbose: `pytest -vv`
4. Check environment variables

### Flaky Tests

```python
# Retry flaky tests
@pytest.mark.flaky(reruns=3)
def test_flaky_operation():
    pass
```

### Debugging Tests

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use pytest debugger
pytest --pdb  # Drop into debugger on failure
```

## See Also

- [Contributing Guide](../development/contributing.md)
- [Deployment Guide](../development/deployment.md)
- [Performance Optimizations](../performance/optimizations.md)