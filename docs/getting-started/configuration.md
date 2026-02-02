# Configuration Guide

Comprehensive guide to configuring Contract-Jena for your environment.

## Configuration Files

### Environment Variables (`.env`)

The primary configuration file located at `agents/.env`:

```bash
# Copy template
cp agents/env.example agents/.env

# Edit configuration
nano agents/.env
```

### Python Settings (`config.py`)

Advanced configuration in [`agents/src/config.py`](../../agents/src/config.py) using Pydantic settings.

## Core Configuration

### Fuseki SPARQL Server

```bash
# Fuseki endpoint
FUSEKI_URL=http://localhost:3030
FUSEKI_DATASET=contracts

# Optional authentication
FUSEKI_USER=admin
FUSEKI_PASSWORD=admin123
```

**Production Settings:**
```bash
FUSEKI_URL=https://fuseki.your-domain.com
FUSEKI_USER=your_username
FUSEKI_PASSWORD=your_secure_password
```

### Milvus Vector Database

```bash
# Milvus connection
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=contract_clauses

# Connection pooling
MILVUS_POOL_SIZE=10
```

**Production Settings:**
```bash
MILVUS_HOST=milvus.your-domain.com
MILVUS_PORT=19530
MILVUS_USER=your_username
MILVUS_PASSWORD=your_secure_password
```

## LLM Configuration

### Provider Selection

```bash
# Choose provider: ollama, watsonx, openai, anthropic
LLM_PROVIDER=ollama
```

### Ollama (Local LLM)

```bash
# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_FALLBACK_MODEL=llama3:8b
```

**Available Models:**
- `llama3.1:8b` - Balanced performance (recommended)
- `qwen2.5-coder:7b` - Fast, code-focused
- `mistral:7b` - Good for reasoning
- `llama3:70b` - High quality (requires GPU)

**Pull Models:**
```bash
ollama pull llama3.1:8b
ollama pull qwen2.5-coder:7b
```

### IBM watsonx.ai

```bash
# watsonx configuration
LLM_PROVIDER=watsonx
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL=ibm/granite-13b-chat-v2
```

**Get Credentials:**
1. Sign up at [IBM Cloud](https://cloud.ibm.com/)
2. Create watsonx.ai instance
3. Generate API key
4. Copy project ID

### OpenAI

```bash
# OpenAI configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview
```

**Models:**
- `gpt-4-turbo-preview` - Best quality
- `gpt-4` - Stable
- `gpt-3.5-turbo` - Fast and cheap

### Anthropic Claude

```bash
# Anthropic configuration
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-opus-20240229
```

**Models:**
- `claude-3-opus-20240229` - Highest quality
- `claude-3-sonnet-20240229` - Balanced
- `claude-3-haiku-20240307` - Fast

## Embedding Configuration

### Embedding Model

```bash
# Embedding model for vector search
EMBEDDING_MODEL=intfloat/e5-large-v2
EMBEDDING_DIM=1024
```

**Available Models:**

| Model | Dimensions | Quality | Speed |
|-------|------------|---------|-------|
| `intfloat/e5-large-v2` | 1024 | High | Medium |
| `intfloat/e5-base-v2` | 768 | Medium | Fast |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | Low | Very Fast |
| `BAAI/bge-large-en-v1.5` | 1024 | High | Medium |

**Change Embedding Model:**
```bash
# 1. Update .env
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DIM=1024

# 2. Migrate Milvus schema
make data-migrate-milvus

# 3. Re-index documents
make ingest-override
```

## Performance Configuration

### Query Caching

```bash
# Enable SPARQL query caching
ENABLE_QUERY_CACHE=true
QUERY_CACHE_SIZE=1000
QUERY_CACHE_TTL=3600  # 1 hour
```

**Tuning:**
- **Small workload**: `QUERY_CACHE_SIZE=100`
- **Medium workload**: `QUERY_CACHE_SIZE=1000` (default)
- **Large workload**: `QUERY_CACHE_SIZE=5000`

### Template-Based SPARQL

```bash
# Enable template matching for simple queries
ENABLE_SPARQL_TEMPLATES=true
```

**Impact:** 95% speed improvement for simple queries (200s → 5-10s)

### Connection Pooling

```bash
# Milvus connection pool
MILVUS_POOL_SIZE=10

# Adjust based on concurrent queries
# Low concurrency: 5
# Medium concurrency: 10 (default)
# High concurrency: 20
```

## Logging Configuration

### Log Levels

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Enable detailed agent explanations
ENABLE_AGENT_EXPLANATIONS=false  # Disabled for performance
```

**Development:**
```bash
LOG_LEVEL=DEBUG
ENABLE_AGENT_EXPLANATIONS=true
```

**Production:**
```bash
LOG_LEVEL=INFO
ENABLE_AGENT_EXPLANATIONS=false
```

### Log Directories

Logs are stored in `agents/logs/`:
```
agents/logs/
├── ingestion/
│   └── ingestion.log
├── retrieval/
│   └── retrieval.log
└── schema/
    └── schema.log
```

## Document Processing

### Upload Configuration

```bash
# Document upload settings
UPLOAD_DIRECTORY=./data/uploads
MAX_FILE_SIZE_MB=50

# Supported formats: PDF, DOCX
```

### Duplicate Detection

```bash
# Enable duplicate document detection
ENABLE_DUPLICATE_CHECK=true

# Backend: sqlite, redis, fuseki
DOCUMENT_REGISTRY_BACKEND=sqlite

# Redis URL (if using redis backend)
DOCUMENT_REGISTRY_REDIS_URL=redis://localhost:6379/0
```

## Ontology Configuration

### Namespaces

```bash
# Ontology namespaces
PROCUREMENT_NAMESPACE=http://procurement.kg/ontology#
CONTRACT_NAMESPACE=http://procurement.kg/contract#
```

### Schema Files

Located in `agents/src/schemas/`:
```
schemas/
├── ontology/
│   └── procurement.owl
├── rules/
│   └── risk_rules.rules
└── shacl/
    └── contract_shapes.ttl
```

## Advanced Configuration

### Python Settings

Edit `agents/src/config.py` for advanced options:

```python
class Settings(BaseSettings):
    # Override defaults
    fuseki_url: str = "http://localhost:3030"
    milvus_host: str = "localhost"
    
    # Add custom settings
    custom_timeout: int = 300
    custom_retries: int = 3
```

### Environment-Specific Configs

Create multiple environment files:

```bash
# Development
agents/.env.dev

# Staging
agents/.env.staging

# Production
agents/.env.prod
```

Load specific environment:
```bash
# Set environment
export ENV=prod

# Load config
cp agents/.env.${ENV} agents/.env
```

## Configuration Validation

### Check Configuration

```bash
# Verify services are accessible
make health

# Test Fuseki connection
curl http://localhost:3030/$/ping

# Test Milvus connection
make check-milvus-data

# Test Ollama
curl http://localhost:11434/api/tags
```

### Common Issues

**Fuseki Connection Failed:**
```bash
# Check if Fuseki is running
docker ps | grep fuseki

# Check Fuseki logs
make services-logs-fuseki

# Restart Fuseki
docker restart fuseki
```

**Milvus Connection Failed:**
```bash
# Check Milvus status
docker ps | grep milvus

# Check Milvus logs
make services-logs-milvus

# Restart Milvus
docker restart milvus-standalone
```

**Ollama Model Not Found:**
```bash
# List installed models
ollama list

# Pull missing model
ollama pull llama3.1:8b
```

## Security Best Practices

### API Keys

```bash
# Never commit .env to git
echo ".env" >> .gitignore

# Use environment variables in production
export WATSONX_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

### Secrets Management

**Development:**
- Use `.env` file (not committed)

**Production:**
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
- Use Kubernetes secrets
- Use environment variables

### Network Security

```bash
# Restrict Fuseki access
FUSEKI_URL=http://internal-fuseki:3030

# Use TLS for external services
FUSEKI_URL=https://fuseki.your-domain.com
MILVUS_HOST=milvus.your-domain.com
```

## Configuration Templates

### Development

```bash
# .env.dev
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5-coder:7b
LOG_LEVEL=DEBUG
ENABLE_AGENT_EXPLANATIONS=true
ENABLE_QUERY_CACHE=true
```

### Production

```bash
# .env.prod
LLM_PROVIDER=watsonx
WATSONX_API_KEY=${WATSONX_API_KEY}
LOG_LEVEL=INFO
ENABLE_AGENT_EXPLANATIONS=false
ENABLE_QUERY_CACHE=true
QUERY_CACHE_SIZE=5000
```

## Next Steps

- **[Quick Start](quickstart.md)**: Run your first query
- **[Architecture Overview](../architecture/overview.md)**: Understand the system
- **[Performance Optimizations](../performance/optimizations.md)**: Tune for your workload