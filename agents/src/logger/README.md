# Production-Grade Logging System

A unified, modular logging system following SOLID principles and the factory pattern.

## Features

- ✅ **Per-module log files** - Each module has its own log file in `logs/modules/{module_name}/`
- ✅ **Log rotation** - Automatic rotation when files reach size limit (default: 10MB, 5 backups)
- ✅ **Structured logging** - JSON and text formats supported
- ✅ **Analytics-ready** - Structured data for easy analysis
- ✅ **Context binding** - Correlation IDs and context propagation
- ✅ **Performance metrics** - Built-in performance logging
- ✅ **SOLID principles** - Interface-based, extensible design
- ✅ **Factory pattern** - Consistent with other services (SPARQLStore, VectorStore)

## Quick Start

### Basic Usage

```python
from contract_kg.logging import get_module_logger

# Get logger for your module
logger = get_module_logger(__name__)

# Log messages
logger.info("Operation started", operation="load_graph")
logger.warning("Low memory", available_mb=512)
logger.error("Failed to connect", host="localhost", port=3030)
```

### With Context Binding

```python
# Bind context for correlation
logger = logger.bind(
    component="GraphManager",
    graph_id="doc123",
    user_id="user456"
)

# All subsequent logs include the context
logger.info("Graph loaded")  # Includes component, graph_id, user_id
logger.info("Triples added", count=150)  # Includes context + count
```

### Using ServiceFactory (Dependency Injection)

```python
from contract_kg.service_factory import get_service_factory

factory = get_service_factory()
logger = factory.get_logger("graph_manager")

logger.info("Using dependency injection")
```

### Performance Metrics

```python
import time

start = time.time()
# ... do work ...
duration_ms = (time.time() - start) * 1000

logger.log_performance("load_graph", duration_ms, graph_id="doc123")
logger.log_metric("triples_loaded", 150, graph_id="doc123")
```

### JSON Format (Analytics)

```python
# Enable JSON format for analytics
logger = get_module_logger(__name__, enable_json=True)

logger.info("Operation", operation="load", count=100)
# Output: {"timestamp": "...", "level": "INFO", "message": "...", ...}
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Module Code                      │
│  logger = get_module_logger(__name__)   │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         LoggerFactory                    │
│  (Singleton per module)                  │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         ModuleLogger                     │
│  - File handler (rotating)               │
│  - Console handler (optional)            │
│  - JSON/Text formatter                   │
│  - Context binding                       │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│    logs/modules/{module_name}/          │
│    {module_name}.log                     │
│    {module_name}.log.1                  │
│    {module_name}.log.2                  │
└─────────────────────────────────────────┘
```

## Log File Structure

```
logs/
├── modules/                    # Module-specific logs (NEW)
│   ├── graph_manager/
│   │   └── graph_manager.log
│   ├── ingestion_orchestrator/
│   │   └── ingestion_orchestrator.log
│   └── retrieval_orchestrator/
│       └── retrieval_orchestrator.log
├── ingestion/                  # Legacy category logs
├── retrieval/                 # Legacy category logs
└── ...
```

## Configuration

### Environment Variables

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Enable JSON format for analytics
LOG_JSON_FORMAT=false
```

### Programmatic Configuration

```python
logger = get_module_logger(
    __name__,
    log_level="DEBUG",
    enable_console=True,
    enable_json=False,
    max_bytes=20 * 1024 * 1024,  # 20MB
    backup_count=10
)
```

## Migration Guide

### Before (Old Way)

```python
import logging
import structlog

logger = structlog.get_logger()
file_logger = logging.getLogger("agents")
```

### After (New Way)

```python
from contract_kg.logging import get_module_logger

logger = get_module_logger(__name__)
```

### With Dependency Injection

```python
# In __init__ method
def __init__(self, logger=None, **kwargs):
    if logger is None:
        factory = get_service_factory()
        logger = factory.get_logger(self.__class__.__name__)
    self.logger = logger
```

## Analytics Integration

The structured logging format makes it easy to build analytics:

```python
# Enable JSON logging
logger = get_module_logger(__name__, enable_json=True)

# Log with structured data
logger.info(
    "Query executed",
    query_type="SPARQL",
    duration_ms=150.5,
    result_count=42,
    graph_id="doc123"
)
```

Logs can be easily parsed and analyzed:
- Query performance metrics
- Error rates by module
- Usage patterns
- Performance trends

## Best Practices

1. **Use module name**: Always use `__name__` or explicit module name
2. **Bind context early**: Bind context at the start of operations
3. **Use appropriate levels**: DEBUG for development, INFO for production
4. **Log metrics**: Use `log_metric()` and `log_performance()` for analytics
5. **Structured data**: Pass data as kwargs, not in message strings

## Examples

### Example 1: Graph Manager

```python
from contract_kg.logging import get_module_logger

class GraphManager:
    def __init__(self):
        self.logger = get_module_logger(__name__)
    
    def load_graph(self, graph_id: str):
        logger = self.logger.bind(graph_id=graph_id)
        logger.info("Loading graph")
        
        try:
            # ... load graph ...
            logger.info("Graph loaded", triple_count=150)
        except Exception as e:
            logger.exception("Failed to load graph", error=str(e))
            raise
```

### Example 2: Agent with Dependency Injection

```python
from contract_kg.service_factory import get_service_factory

class MyAgent:
    def __init__(self, logger=None):
        if logger is None:
            factory = get_service_factory()
            logger = factory.get_logger(self.__class__.__name__)
        self.logger = logger
    
    def process(self, data):
        self.logger.info("Processing", data_size=len(data))
        # ... process ...
```

## Extensibility

The system is designed for extensibility:

```python
from contract_kg.logging.base import BaseLogger
from contract_kg.logging.factory import LoggerFactory

class CustomLogger(BaseLogger):
    # Implement BaseLogger interface
    ...

# Register custom logger
LoggerFactory.register_logger_type("custom", CustomLogger)

# Use it
logger = LoggerFactory.create_logger("my_module", logger_type="custom")
```
