# Contributing Guide

Guidelines for contributing to the Contract Knowledge Graph project.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- uv (Python package manager)

### Development Setup

1. **Clone the repository:**

```bash
git clone https://github.com/your-org/contract-jena.git
cd contract-jena
```

2. **Install dependencies:**

```bash
cd agents
uv sync
```

3. **Configure environment:**

```bash
cp agents/env.example agents/.env
# Edit .env with your settings
```

4. **Start services:**

```bash
docker-compose up -d
```

5. **Verify setup:**

```bash
cd agents
uv run python -c "from config import get_settings; print('Setup OK')"
```

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feature/*` - New features
- `bugfix/*` - Bug fixes
- `hotfix/*` - Production hotfixes

### Creating a Feature

1. **Create feature branch:**

```bash
git checkout -b feature/my-feature develop
```

2. **Make changes and commit:**

```bash
git add .
git commit -m "feat: add new feature"
```

3. **Push and create PR:**

```bash
git push origin feature/my-feature
# Create pull request on GitHub
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Code style (formatting)
- `refactor` - Code refactoring
- `perf` - Performance improvement
- `test` - Tests
- `chore` - Maintenance

**Examples:**

```bash
feat(ingestion): add PDF text extraction
fix(retrieval): correct SPARQL query generation
docs(api): update ingestion agent documentation
perf(cache): implement query caching with TTL
```

## Code Standards

### Python Style

Follow [PEP 8](https://pep8.org/) and use type hints:

```python
def process_document(
    file_path: str | Path,
    graph_uri: str
) -> IngestionResult:
    """
    Process a document and load into knowledge graph.
    
    Args:
        file_path: Path to document
        graph_uri: Target graph URI
        
    Returns:
        Ingestion results with metrics
    """
    # Implementation
    pass
```

### Code Formatting

Use `ruff` for formatting:

```bash
# Format code
ruff format agents/src/

# Check formatting
ruff check agents/src/
```

### Type Checking

Use `mypy` for type checking:

```bash
mypy agents/src/
```

### Linting

```bash
# Run linter
ruff check agents/src/

# Fix auto-fixable issues
ruff check --fix agents/src/
```

## Testing

### Running Tests

```bash
# All tests
cd agents
uv run pytest

# Specific test file
uv run pytest tests/agents/test_ingestion.py

# With coverage
uv run pytest --cov=agents/src --cov-report=html
```

### Writing Tests

```python
import pytest
from agents.ingestion.document_ingestion import DocumentIngestionAgent

def test_document_ingestion():
    """Test document ingestion agent."""
    agent = DocumentIngestionAgent()
    
    result = agent.process("test.pdf")
    
    assert result.success
    assert len(result.text) > 0
    assert result.metadata is not None

@pytest.fixture
def sample_contract():
    """Fixture for sample contract."""
    return {
        "id": "ABC123",
        "text": "Sample contract text..."
    }

def test_with_fixture(sample_contract):
    """Test using fixture."""
    assert sample_contract["id"] == "ABC123"
```

### Test Coverage

Maintain >80% test coverage:

```bash
# Generate coverage report
uv run pytest --cov=agents/src --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def extract_clauses(
    self,
    text: str,
    document_id: str | None = None
) -> list[ExtractedClause]:
    """
    Extract clauses from contract text.
    
    Args:
        text: Contract text to analyze
        document_id: Optional document identifier
        
    Returns:
        List of extracted clauses with metadata
        
    Raises:
        ValueError: If text is empty
        
    Example:
        >>> agent = ClauseExtractionAgent()
        >>> clauses = agent.extract_clauses(contract_text)
        >>> print(f"Found {len(clauses)} clauses")
    """
    pass
```

### Building Documentation

```bash
# Install MkDocs
pip install mkdocs-material

# Serve locally
make docs-serve

# Build static site
make docs-build

# Deploy to GitHub Pages
make docs-deploy
```

## Pull Request Process

### Before Submitting

1. **Run tests:**

```bash
uv run pytest
```

2. **Check formatting:**

```bash
ruff format agents/src/
ruff check agents/src/
```

3. **Update documentation:**

```bash
# Update relevant docs
vim docs/guide/my-feature.md
```

4. **Update CHANGELOG:**

```markdown
## [Unreleased]

### Added
- New feature description
```

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass
- [ ] No new warnings
```

### Review Process

1. **Automated checks** must pass
2. **At least one approval** required
3. **All comments** must be resolved
4. **Squash and merge** to main

## Project Structure

```
contract-jena/
├── agents/                 # Python agents
│   ├── src/
│   │   ├── agents/        # Agent implementations
│   │   ├── storage/       # Storage abstractions
│   │   ├── llm/           # LLM providers
│   │   └── observability/ # Monitoring
│   ├── tests/             # Test suite
│   └── pyproject.toml     # Dependencies
├── docs/                  # Documentation
├── docker/                # Docker configs
├── scripts/               # Utility scripts
└── ontology/             # OWL ontologies
```

## Common Tasks

### Adding a New Agent

1. **Create agent file:**

```python
# agents/src/agents/my_category/my_agent.py
from agents.shared.base import BaseAgent

class MyAgent(BaseAgent):
    """My new agent."""
    
    def process(self, input_data):
        # Implementation
        pass
```

2. **Add tests:**

```python
# agents/tests/agents/test_my_agent.py
def test_my_agent():
    agent = MyAgent()
    result = agent.process(test_data)
    assert result.success
```

3. **Update documentation:**

```markdown
# docs/api/agents/my-category.md
## MyAgent
Description and API reference
```

### Adding a New Storage Backend

1. **Implement interface:**

```python
# agents/src/storage/my_store/my_implementation.py
from storage.base import BaseStore

class MyStore(BaseStore):
    def query(self, query: str):
        # Implementation
        pass
```

2. **Add factory method:**

```python
# agents/src/storage/factory.py
def create_store(store_type: str):
    if store_type == "my_store":
        return MyStore()
```

3. **Add tests and docs**

## Debugging

### Enable Debug Logging

```python
# In .env
LOG_LEVEL=DEBUG
```

### Use Debugger

```python
# Add breakpoint
import pdb; pdb.set_trace()

# Or use VS Code debugger
# Set breakpoint in IDE
```

### Phoenix Tracing

```python
# Enable Phoenix for LLM debugging
from observability.phoenix_tracer import setup_phoenix_tracing

setup_phoenix_tracing()

# View traces at http://localhost:6006
```

## Performance Profiling

### Profile Code

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
result = agent.process(data)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Memory Profiling

```python
from memory_profiler import profile

@profile
def my_function():
    # Code to profile
    pass
```

## Release Process

1. **Update version:**

```bash
# In pyproject.toml
version = "1.1.0"
```

2. **Update CHANGELOG:**

```markdown
## [1.1.0] - 2024-01-15

### Added
- New features

### Fixed
- Bug fixes
```

3. **Create release:**

```bash
git tag -a v1.1.0 -m "Release v1.1.0"
git push origin v1.1.0
```

4. **Build and publish:**

```bash
uv build
uv publish
```

## Getting Help

- **Documentation:** https://contract-jena.github.io
- **Issues:** https://github.com/your-org/contract-jena/issues
- **Discussions:** https://github.com/your-org/contract-jena/discussions
- **Slack:** #contract-kg channel

## Code of Conduct

Be respectful, inclusive, and professional. See [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) for details.