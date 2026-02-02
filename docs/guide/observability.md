# Observability Guide

This guide explains how to monitor and trace the Contract Knowledge Graph system using Phoenix and built-in logging.

## Overview

The system provides comprehensive observability through:

- **Phoenix Tracing** - LLM call tracking and performance analysis
- **Structured Logging** - Detailed operation logs with context
- **Performance Metrics** - Query timing and resource usage
- **Error Tracking** - Exception capture and debugging

## Phoenix Tracing

### Setup

Phoenix provides real-time observability for LLM operations:

```python
from observability.phoenix_tracer import setup_phoenix_tracing

# Setup Phoenix tracing
tracer = setup_phoenix_tracing(
    project_name="contract-kg",
    phoenix_port=6006,
    auto_start=True
)
```

### Docker Deployment

Phoenix runs as a Docker service:

```yaml
# docker-compose.yml
services:
  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    environment:
      - PHOENIX_PORT=6006
```

Start Phoenix:

```bash
docker-compose up -d phoenix
```

Access UI: **http://localhost:6006**

### Automatic Instrumentation

Phoenix automatically traces:

- **LangChain calls** - All LLM interactions
- **LangGraph workflows** - State transitions and nodes
- **Embeddings** - Vector generation operations
- **Tool calls** - SPARQL queries, vector searches

```python
from agents.retrieval.retrieval_orchestrator_langgraph_v2 import LangGraphRetrievalOrchestrator

# Phoenix tracing enabled automatically
orchestrator = LangGraphRetrievalOrchestrator()

# All LLM calls traced
result = orchestrator.query("List all contracts")

# View traces in Phoenix UI
```

### Trace Analysis

Phoenix UI provides:

1. **Trace Timeline** - Visual workflow execution
2. **LLM Metrics** - Token usage, latency, cost
3. **Error Tracking** - Failed operations and stack traces
4. **Performance Analysis** - Bottleneck identification

**Example Trace:**
```
Query: "List all contracts"
├─ Route Decision (50ms)
│  └─ LLM Call: gpt-4 (45ms, 150 tokens)
├─ SPARQL Generation (100ms)
│  └─ Template Match (5ms)
├─ Fuseki Query (2000ms)
└─ Answer Synthesis (500ms)
   └─ LLM Call: gpt-4 (480ms, 300 tokens)

Total: 2650ms
```

## Structured Logging

### Log Configuration

The system uses structured logging with context:

```python
from logger import get_module_logger

logger = get_module_logger(__name__)

# Logs include module, timestamp, level, message
logger.info("Processing query", extra={
    "query": "List contracts",
    "user_id": "user123",
    "session_id": "sess456"
})
```

### Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| `DEBUG` | Detailed debugging | "SPARQL query: SELECT * WHERE..." |
| `INFO` | Normal operations | "Query completed in 2.5s" |
| `WARNING` | Potential issues | "Cache miss for query" |
| `ERROR` | Operation failures | "Failed to connect to Fuseki" |
| `CRITICAL` | System failures | "Vector store unavailable" |

### Log Locations

Logs are organized by component:

```
logs/
├── ingestion/          # Document ingestion logs
│   ├── 2024-01-15.log
│   └── 2024-01-16.log
├── retrieval/          # Query execution logs
│   ├── 2024-01-15.log
│   └── 2024-01-16.log
├── schema_evolution/   # Ontology evolution logs
│   └── suggestions.log
└── system/            # System-level logs
    └── errors.log
```

### Viewing Logs

```bash
# View recent retrieval logs
tail -f logs/retrieval/$(date +%Y-%m-%d).log

# Search for errors
grep ERROR logs/**/*.log

# Analyze with script
python scripts/analysis/view_logs.py --component retrieval --date 2024-01-15
```

## Performance Metrics

### Query Timing

Track query performance:

```python
result = orchestrator.query("List all contracts")

# Access timing metrics
print(f"Total: {result['total_duration_ms']}ms")
print(f"Analysis: {result['analysis_time_ms']}ms")

# Breakdown in logs
# [INFO] Query routing: 50ms
# [INFO] SPARQL execution: 2000ms
# [INFO] Answer synthesis: 500ms
```

### Resource Usage

Monitor system resources:

```python
from observability.phoenix_datasets import create_evaluation_dataset

# Create performance dataset
dataset = create_evaluation_dataset(
    queries=test_queries,
    orchestrator=orchestrator
)

# Analyze metrics
print(f"Avg latency: {dataset.avg_latency}ms")
print(f"P95 latency: {dataset.p95_latency}ms")
print(f"Cache hit rate: {dataset.cache_hit_rate}%")
```

### Database Metrics

Track database performance:

```python
from storage.sparql.fuseki_store import FusekiStore

store = FusekiStore()

# Get cache statistics
stats = store.get_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']}%")
```

## Error Tracking

### Exception Logging

Errors are automatically logged with context:

```python
try:
    result = orchestrator.query(question)
except Exception as e:
    logger.error(
        "Query failed",
        exc_info=True,  # Include stack trace
        extra={
            "question": question,
            "error_type": type(e).__name__
        }
    )
```

### Error Analysis

Analyze error patterns:

```bash
# View error logs
tail -f logs/system/errors.log

# Count error types
grep ERROR logs/**/*.log | cut -d: -f3 | sort | uniq -c

# Analyze with script
python scripts/analysis/analyze_errors.py --days 7
```

## Monitoring Dashboards

### Phoenix Dashboard

Access at **http://localhost:6006**

**Key Metrics:**
- Total traces
- Average latency
- Token usage
- Error rate
- Cost tracking

### Custom Dashboards

Create custom monitoring:

```python
from observability.phoenix_datasets import PhoenixDatasetManager

manager = PhoenixDatasetManager()

# Export metrics
metrics = manager.export_metrics(
    start_date="2024-01-01",
    end_date="2024-01-15"
)

# Visualize
import matplotlib.pyplot as plt

plt.plot(metrics['dates'], metrics['latencies'])
plt.xlabel('Date')
plt.ylabel('Avg Latency (ms)')
plt.title('Query Performance Over Time')
plt.show()
```

## Alerting

### Log-Based Alerts

Monitor logs for critical issues:

```bash
# Alert on errors
tail -f logs/system/errors.log | grep CRITICAL | \
  while read line; do
    echo "ALERT: $line" | mail -s "System Alert" admin@example.com
  done
```

### Performance Alerts

Alert on slow queries:

```python
result = orchestrator.query(question)

if result['total_duration_ms'] > 10000:  # 10 seconds
    logger.warning(
        "Slow query detected",
        extra={
            "question": question,
            "duration_ms": result['total_duration_ms'],
            "strategy": result['strategy']
        }
    )
    # Send alert
    send_alert(f"Slow query: {question}")
```

## Best Practices

### 1. Enable Tracing in Production

Always enable Phoenix tracing:

```python
# In production config
ENABLE_PHOENIX_TRACING=true
PHOENIX_ENDPOINT=http://phoenix:6006
```

### 2. Use Structured Logging

Include context in logs:

```python
# ❌ Bad
logger.info("Query completed")

# ✅ Good
logger.info("Query completed", extra={
    "question": question,
    "duration_ms": duration,
    "result_count": len(results),
    "cache_hit": cache_hit
})
```

### 3. Monitor Key Metrics

Track critical metrics:

- **Latency:** P50, P95, P99
- **Error rate:** % of failed queries
- **Cache hit rate:** % of cached queries
- **Token usage:** LLM cost tracking

### 4. Set Up Alerts

Alert on critical issues:

- Queries >10 seconds
- Error rate >5%
- Cache hit rate <30%
- System resource exhaustion

### 5. Regular Log Analysis

Analyze logs weekly:

```bash
# Run analysis scripts
python scripts/analysis/analyze_retrieval_logs.py --week
python scripts/analysis/analyze_ingestion_logs.py --week
```

## Troubleshooting

### Phoenix Not Receiving Traces

**Problem:** No traces in Phoenix UI

**Solutions:**
1. Check Phoenix is running: `docker ps | grep phoenix`
2. Verify endpoint: `echo $PHOENIX_ENDPOINT`
3. Check network connectivity: `curl http://localhost:6006`
4. Review Phoenix logs: `docker logs phoenix`

### High Log Volume

**Problem:** Logs consuming too much disk space

**Solutions:**
1. Adjust log levels (INFO → WARNING)
2. Enable log rotation
3. Archive old logs
4. Filter verbose components

### Missing Metrics

**Problem:** Metrics not appearing in Phoenix

**Solutions:**
1. Verify auto-instrumentation is enabled
2. Check LangChain/LangGraph versions
3. Review tracer setup code
4. Check for instrumentation errors in logs

## Next Steps

- [Performance Optimizations](../performance/optimizations.md) - Tune system performance
- [Retrieval Guide](../guide/retrieval.md) - Query the knowledge graph
- [Architecture Overview](../architecture/overview.md) - System design