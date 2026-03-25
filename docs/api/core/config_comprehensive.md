# Configuration API Reference

Comprehensive API documentation for application configuration management using Pydantic Settings.

## Overview

The Configuration module provides centralized settings management for the Contract Knowledge Graph system. It uses Pydantic Settings for type-safe configuration with environment variable support, validation, and default values.

**Key Features:**
- Type-safe configuration with Pydantic
- Environment variable loading from `.env` files
- Validation and default values
- 50+ configuration parameters
- Provider selection (LLM, storage, backends)
- Computed properties for derived values
- LRU caching for performance

---

## Settings

Main configuration class for all application settings.

### Class Definition

```python
from config import Settings

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Supports configuration for:
    - SPARQL stores (Fuseki)
    - Vector stores (Milvus)
    - LLM providers (WatsonX, Ollama)
    - Object storage (MinIO, IBM COS)
    - Document processing
    - Observability (Phoenix)
    - Schema evolution
    - Performance optimizations
    """
```

### Constructor

```python
def __init__(self, **kwargs)
```

Initialize settings from environment variables and `.env` file.

**Example:**

```python
from config import Settings

# Load from environment and .env
settings = Settings()

# Override specific values
settings = Settings(
    fuseki_url="http://custom-fuseki:3030",
    milvus_host="custom-milvus"
)

# Access settings
print(f"Fuseki URL: {settings.fuseki_url}")
print(f"LLM Provider: {settings.llm_provider}")
```

---

## Configuration Categories

### Fuseki SPARQL Configuration

```python
# Fuseki SPARQL Endpoint
fuseki_url: str = Field(
    default="http://localhost:3030",
    description="Base URL of the Fuseki SPARQL server"
)

fuseki_dataset: str = Field(
    default="contracts",
    description="Name of the Fuseki dataset"
)

fuseki_user: str = Field(
    default="",
    description="Fuseki admin username (leave empty if no auth required)"
)

fuseki_password: str = Field(
    default="",
    description="Fuseki admin password (leave empty if no auth required)"
)
```

**Example:**

```python
# .env file
FUSEKI_URL=http://fuseki:3030
FUSEKI_DATASET=contracts
FUSEKI_USER=admin
FUSEKI_PASSWORD=secret123

# Usage
settings = Settings()
print(f"Query endpoint: {settings.sparql_query_endpoint}")
# Output: http://fuseki:3030/contracts/query
```

---

### LLM Configuration

#### WatsonX Configuration

```python
# IBM watsonx.ai
watsonx_api_key: str = Field(
    default="",
    description="Watsonx API key (WATSONX_API_KEY)"
)

watsonx_project_id: str = Field(
    default="",
    description="Watsonx project ID (WATSONX_PROJECT_ID)"
)

watsonx_model_id: str = Field(
    default="",
    description="Watsonx model ID, e.g. meta-llama/llama-3-70b-instruct"
)

watsonx_url: str = Field(
    default="",
    description="Watsonx service URL, e.g. https://us-south.ml.cloud.ibm.com"
)
```

**Example:**

```python
# .env file
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id
WATSONX_MODEL_ID=meta-llama/llama-3-70b-instruct
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Usage
settings = Settings()
if settings.watsonx_api_key:
    print("✅ WatsonX configured")
```

#### Ollama Configuration

```python
# Local LLM (Ollama)
ollama_base_url: str = Field(
    default="http://localhost:11434",
    description="Ollama base URL for local LLM"
)

ollama_model: str = Field(
    default="llama3:8b",
    description="Ollama model to use"
)

ollama_fallback_model: str = Field(
    default="llama3:8b",
    description="Fallback Ollama model to use if the configured model is not available"
)
```

**Example:**

```python
# .env file
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_FALLBACK_MODEL=mistral:7b

# Usage
settings = Settings()
print(f"Ollama model: {settings.ollama_model}")
```

#### Provider Selection

```python
# LLM Provider Selection
llm_provider: str = Field(
    default="ollama",
    description="LLM provider to use: ollama, watsonx"
)
```

**Example:**

```python
# .env file
LLM_PROVIDER=watsonx  # or ollama

# Usage
settings = Settings()
if settings.llm_provider == "watsonx":
    # Use WatsonX
    pass
elif settings.llm_provider == "ollama":
    # Use Ollama
    pass
```

---

### Storage Configuration

#### SPARQL Store

```python
# Storage Provider Selection
sparql_store: str = Field(
    default="fuseki",
    description="SPARQL store to use: fuseki"
)
```

#### Vector Store

```python
vector_store: str = Field(
    default="milvus",
    description="Vector store to use: milvus"
)

# Milvus Vector Database
milvus_host: str = Field(
    default="localhost",
    description="Milvus server host"
)

milvus_port: int = Field(
    default=19530,
    description="Milvus server port"
)

milvus_collection: str = Field(
    default="contract_clauses",
    description="Milvus collection name for clause embeddings"
)

milvus_collection_v2: str = Field(
    default="contract_clauses_v2",
    description="Milvus collection name for v2 schema (dual embeddings + summaries)"
)
```

**Example:**

```python
# .env file
MILVUS_HOST=milvus
MILVUS_PORT=19530
MILVUS_COLLECTION=contract_clauses_v2

# Usage
settings = Settings()
print(f"Milvus URI: {settings.milvus_uri}")
# Output: http://milvus:19530
```

---

### Embedding Configuration

```python
# Embedding Model
embedding_model: str = Field(
    default="intfloat/e5-large-v2",
    description="Sentence transformer model for embeddings"
)

embedding_dim: int = Field(
    default=1024,
    description="Embedding dimension (must match the model)"
)

enable_text_embedding_fallback: bool = Field(
    default=True,
    description="When searching, fallback to full-text embeddings if needed"
)
```

**Supported Models:**

| Model | Dimensions | Speed | Quality |
|-------|-----------|-------|---------|
| intfloat/e5-large-v2 | 1024 | Medium | Best |
| sentence-transformers/all-MiniLM-L6-v2 | 384 | Fast | Good |
| sentence-transformers/all-mpnet-base-v2 | 768 | Medium | Better |

**Example:**

```python
# .env file
EMBEDDING_MODEL=intfloat/e5-large-v2
EMBEDDING_DIM=1024

# Usage
settings = Settings()
print(f"Embedding model: {settings.embedding_model}")
print(f"Dimensions: {settings.embedding_dim}")
```

---

### Object Storage Configuration

```python
# Object Storage (MinIO, IBM COS - S3-compatible)
object_storage_endpoint: str = Field(
    default="http://minio:9000",
    description="Object storage endpoint (MinIO: http://minio:9000, IBM COS: https://s3.region.cloud-object-storage.appdomain.cloud)"
)

object_storage_access_key: str = Field(
    default="minioadmin",
    description="Object storage access key"
)

object_storage_secret_key: str = Field(
    default="minioadmin",
    description="Object storage secret key"
)

object_storage_bucket: str = Field(
    default="procurement-contracts",
    description="Object storage bucket name"
)

object_storage_region: str = Field(
    default="us-east-1",
    description="Object storage region (MinIO: us-east-1; IBM COS: e.g. us-south)"
)
```

**Example:**

```python
# MinIO (local)
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1

# IBM Cloud Object Storage
OBJECT_STORAGE_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
OBJECT_STORAGE_ACCESS_KEY=your_access_key
OBJECT_STORAGE_SECRET_KEY=your_secret_key
OBJECT_STORAGE_BUCKET=my-contracts-bucket
OBJECT_STORAGE_REGION=us-south
```

---

### Artifact Store Configuration

```python
# Artifact storage (generated RDF/OWL/SHACL/rules, etc.)
artifact_store_backend: str = Field(
    default="local",
    description="Artifact store backend: local or object_storage"
)

artifact_store_prefix: str = Field(
    default="ingestion_artifacts",
    description="Object storage prefix for uploaded artifacts (when backend=object_storage)"
)

artifact_store_cleanup_local: bool = Field(
    default=False,
    description="Delete local artifact files after uploading to object storage"
)
```

**Example:**

```python
# Local storage
ARTIFACT_STORE_BACKEND=local

# Object storage with cleanup
ARTIFACT_STORE_BACKEND=object_storage
ARTIFACT_STORE_PREFIX=ingestion_artifacts
ARTIFACT_STORE_CLEANUP_LOCAL=true
```

---

### Document Processing Configuration

```python
# Document Processing
upload_directory: str = Field(
    default="./data/uploads",
    description="Directory for uploaded documents"
)

max_file_size_mb: int = Field(
    default=50,
    description="Maximum file size in MB"
)

# Ingestion/Retrieval Switchover (legacy vs docling pipeline)
ingestion_source: str = Field(
    default="legacy",
    description="Ingestion pipeline: legacy (PyPDF2) or docling"
)

retrieval_fuseki_dataset: str = Field(
    default="contracts",
    description="Fuseki dataset for retrieval reads (ingestion uses fuseki_dataset)"
)

retrieval_milvus_collection: str = Field(
    default="contract_clauses_v2",
    description="Milvus collection for retrieval reads (ingestion uses milvus_collection_v2)"
)
```

**Example:**

```python
# .env file
UPLOAD_DIRECTORY=./data/uploads
MAX_FILE_SIZE_MB=100
INGESTION_SOURCE=docling
RETRIEVAL_FUSEKI_DATASET=contracts
RETRIEVAL_MILVUS_COLLECTION=contract_clauses_v2
```

---

### Ontology Configuration

```python
# Ontology
ontology_path: str = Field(
    default="src/schemas/ontology/procurement.owl",
    description="Path to the OWL ontology file"
)

procurement_namespace: str = Field(
    default="http://procurement.kg/ontology#",
    description="Namespace for procurement ontology"
)

contract_namespace: str = Field(
    default="http://procurement.kg/contract#",
    description="Namespace for contract instances"
)
```

**Example:**

```python
# .env file
ONTOLOGY_PATH=src/schemas/ontology/procurement.owl
PROCUREMENT_NAMESPACE=http://procurement.kg/ontology#
CONTRACT_NAMESPACE=http://procurement.kg/contract#

# Usage
settings = Settings()
print(f"Ontology: {settings.ontology_path}")
print(f"Namespace: {settings.procurement_namespace}")
```

---

### Document Registry Configuration

```python
# Document Registry (Duplicate Detection)
document_registry_backend: str = Field(
    default="sqlite",
    description="Document registry backend: redis, sqlite, fuseki"
)

document_registry_redis_url: str = Field(
    default="redis://localhost:6379/0",
    description="Redis URL for document registry (if backend=redis)"
)

enable_duplicate_check: bool = Field(
    default=True,
    description="Enable duplicate document detection"
)
```

**Example:**

```python
# SQLite (default)
DOCUMENT_REGISTRY_BACKEND=sqlite
ENABLE_DUPLICATE_CHECK=true

# Redis
DOCUMENT_REGISTRY_BACKEND=redis
DOCUMENT_REGISTRY_REDIS_URL=redis://redis:6379/0
ENABLE_DUPLICATE_CHECK=true
```

---

### Observability Configuration

```python
# Logging
log_level: str = Field(
    default="INFO",
    description="Logging level"
)

enable_agent_explanations: bool = Field(
    default=True,
    description="Whether to automatically generate process explanations for all agents"
)

# Observability / Phoenix Tracing
phoenix_enabled: bool = Field(
    default=True,
    description="Enable Phoenix tracing and observability integration"
)

phoenix_collector_endpoint: str = Field(
    default="http://phoenix:4317",
    description="OTLP gRPC endpoint for Phoenix collector"
)
```

**Example:**

```python
# .env file
LOG_LEVEL=DEBUG
ENABLE_AGENT_EXPLANATIONS=true
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:4317
```

---

### Schema Evolution Configuration

```python
# Schema Evolution
ontology_evolution_mode: str = Field(
    default="conservative",
    description="Schema evolution mode: conservative, suggestive, or adaptive"
)

generate_owl_extensions: bool = Field(
    default=False,
    description="Whether to generate OWL extensions for new concepts"
)

generate_rules: bool = Field(
    default=False,
    description="Whether to generate inference rules for patterns"
)

generate_shacl: bool = Field(
    default=True,
    description="Whether to generate SHACL validation shapes for new classes"
)

enable_pattern_detection: bool = Field(
    default=True,
    description="Whether to enable comprehensive pattern detection (risk, compliance, obligations)"
)

enable_schema_governance: bool = Field(
    default=True,
    description="Whether to enable schema versioning, conflict resolution, and rollback"
)
```

**Example:**

```python
# .env file
ONTOLOGY_EVOLUTION_MODE=adaptive
GENERATE_OWL_EXTENSIONS=true
GENERATE_RULES=true
GENERATE_SHACL=true
ENABLE_PATTERN_DETECTION=true
ENABLE_SCHEMA_GOVERNANCE=true
```

---

### Performance Configuration

```python
# Performance Optimizations (currently disabled by default)
enable_query_cache: bool = Field(
    default=False,
    description="Enable query result caching for faster repeated queries"
)

query_cache_size: int = Field(
    default=100,
    description="Maximum number of queries to cache"
)

query_cache_ttl: int = Field(
    default=3600,
    description="Cache time-to-live in seconds (default: 1 hour)"
)

enable_sparql_templates: bool = Field(
    default=False,
    description="Enable SPARQL template matching for common queries"
)

enable_fast_complexity_detection: bool = Field(
    default=False,
    description="Enable fast rule-based complexity detection"
)

skip_vector_when_kg_sufficient: bool = Field(
    default=False,
    description="Skip vector search when KG results are sufficient"
)

kg_sufficient_threshold: int = Field(
    default=3,
    description="Minimum KG facts to consider sufficient"
)
```

**Example:**

```python
# .env file
ENABLE_QUERY_CACHE=true
QUERY_CACHE_SIZE=200
QUERY_CACHE_TTL=7200
ENABLE_SPARQL_TEMPLATES=true
SKIP_VECTOR_WHEN_KG_SUFFICIENT=true
KG_SUFFICIENT_THRESHOLD=5
```

---

### ReAct Configuration

```python
# ReAct Configuration
always_use_react: bool = Field(
    default=True,
    description="Always use ReAct agent for all queries (simplified architecture)"
)

# Improved Agentic Architecture
enable_iterative_refinement: bool = Field(
    default=False,
    description="Enable new iterative refinement with answer critique"
)

max_refinement_iterations: int = Field(
    default=3,
    description="Maximum refinement iterations for answer improvement"
)
```

**Example:**

```python
# .env file
ALWAYS_USE_REACT=true
ENABLE_ITERATIVE_REFINEMENT=true
MAX_REFINEMENT_ITERATIONS=3
```

---

## Computed Properties

### sparql_query_endpoint

```python
@property
def sparql_query_endpoint(self) -> str:
    """Get the SPARQL query endpoint URL."""
    return f"{self.fuseki_url}/{self.fuseki_dataset}/query"
```

**Example:**

```python
settings = Settings()
print(settings.sparql_query_endpoint)
# Output: http://localhost:3030/contracts/query
```

### sparql_update_endpoint

```python
@property
def sparql_update_endpoint(self) -> str:
    """Get the SPARQL update endpoint URL."""
    return f"{self.fuseki_url}/{self.fuseki_dataset}/update"
```

### graph_store_endpoint

```python
@property
def graph_store_endpoint(self) -> str:
    """Get the Graph Store Protocol endpoint URL."""
    return f"{self.fuseki_url}/{self.fuseki_dataset}/data"
```

### milvus_uri

```python
@property
def milvus_uri(self) -> str:
    """Get the Milvus connection URI."""
    return f"http://{self.milvus_host}:{self.milvus_port}"
```

**Example:**

```python
settings = Settings()

print(f"Query: {settings.sparql_query_endpoint}")
print(f"Update: {settings.sparql_update_endpoint}")
print(f"Graph Store: {settings.graph_store_endpoint}")
print(f"Milvus: {settings.milvus_uri}")

# Output:
# Query: http://localhost:3030/contracts/query
# Update: http://localhost:3030/contracts/update
# Graph Store: http://localhost:3030/contracts/data
# Milvus: http://localhost:19530
```

---

## get_settings Function

```python
@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

Cached function to get settings instance. Uses LRU cache to avoid repeated environment variable parsing.

**Example:**

```python
from config import get_settings

# First call - loads from environment
settings1 = get_settings()

# Second call - returns cached instance
settings2 = get_settings()

# Same instance
assert settings1 is settings2
```

---

## Usage Examples

### Basic Usage

```python
from config import get_settings

# Get settings
settings = get_settings()

# Access configuration
print(f"Fuseki URL: {settings.fuseki_url}")
print(f"LLM Provider: {settings.llm_provider}")
print(f"Milvus Host: {settings.milvus_host}")
```

### Environment-Specific Configuration

```python
# Development (.env.development)
FUSEKI_URL=http://localhost:3030
MILVUS_HOST=localhost
LLM_PROVIDER=ollama
LOG_LEVEL=DEBUG

# Production (.env.production)
FUSEKI_URL=http://fuseki-prod:3030
MILVUS_HOST=milvus-prod
LLM_PROVIDER=watsonx
LOG_LEVEL=INFO
```

### Configuration Validation

```python
from config import get_settings

settings = get_settings()

# Validate required settings
required_settings = [
    ("fuseki_url", settings.fuseki_url),
    ("milvus_host", settings.milvus_host),
    ("llm_provider", settings.llm_provider),
]

missing = [name for name, value in required_settings if not value]

if missing:
    raise ValueError(f"Missing required settings: {', '.join(missing)}")

print("✅ All required settings configured")
```

### Dynamic Configuration

```python
from config import Settings

# Override for testing
test_settings = Settings(
    fuseki_url="http://test-fuseki:3030",
    milvus_host="test-milvus",
    llm_provider="ollama",
    enable_query_cache=True
)

# Use test settings
from fuseki_client import FusekiClient
client = FusekiClient(settings=test_settings)
```

---

## Configuration File Examples

### Complete .env File

```bash
# Fuseki SPARQL
FUSEKI_URL=http://fuseki:3030
FUSEKI_DATASET=contracts
FUSEKI_USER=admin
FUSEKI_PASSWORD=secret123

# LLM Provider
LLM_PROVIDER=watsonx

# WatsonX
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id
WATSONX_MODEL_ID=meta-llama/llama-3-70b-instruct
WATSONX_URL=https://us-south.ml.cloud.ibm.com

# Ollama (fallback)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530
MILVUS_COLLECTION=contract_clauses_v2

# Embedding
EMBEDDING_MODEL=intfloat/e5-large-v2
EMBEDDING_DIM=1024

# Object Storage (MinIO)
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1

# Artifact Store
ARTIFACT_STORE_BACKEND=object_storage
ARTIFACT_STORE_PREFIX=ingestion_artifacts
ARTIFACT_STORE_CLEANUP_LOCAL=true

# Document Processing
UPLOAD_DIRECTORY=./data/uploads
MAX_FILE_SIZE_MB=100
INGESTION_SOURCE=docling

# Ontology
ONTOLOGY_PATH=src/schemas/ontology/procurement.owl
PROCUREMENT_NAMESPACE=http://procurement.kg/ontology#
CONTRACT_NAMESPACE=http://procurement.kg/contract#

# Document Registry
DOCUMENT_REGISTRY_BACKEND=sqlite
ENABLE_DUPLICATE_CHECK=true

# Observability
LOG_LEVEL=INFO
ENABLE_AGENT_EXPLANATIONS=true
PHOENIX_ENABLED=true
PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:4317

# Schema Evolution
ONTOLOGY_EVOLUTION_MODE=adaptive
GENERATE_OWL_EXTENSIONS=true
GENERATE_RULES=true
GENERATE_SHACL=true
ENABLE_PATTERN_DETECTION=true
ENABLE_SCHEMA_GOVERNANCE=true

# Performance
ENABLE_QUERY_CACHE=true
QUERY_CACHE_SIZE=200
QUERY_CACHE_TTL=3600
ENABLE_SPARQL_TEMPLATES=true
SKIP_VECTOR_WHEN_KG_SUFFICIENT=true
KG_SUFFICIENT_THRESHOLD=5

# ReAct
ALWAYS_USE_REACT=true
ENABLE_ITERATIVE_REFINEMENT=true
MAX_REFINEMENT_ITERATIONS=3
```

---

## Best Practices

### 1. Use Environment Variables

```python
# ❌ Hardcode values
settings = Settings(
    fuseki_url="http://localhost:3030",
    watsonx_api_key="hardcoded_key"
)

# ✅ Use environment variables
# Set in .env file or environment
settings = get_settings()
```

### 2. Validate Configuration

```python
from config import get_settings

settings = get_settings()

# Validate critical settings
if settings.llm_provider == "watsonx":
    if not settings.watsonx_api_key:
        raise ValueError("WatsonX API key required")
    if not settings.watsonx_project_id:
        raise ValueError("WatsonX project ID required")

print("✅ Configuration validated")
```

### 3. Use Computed Properties

```python
# ❌ Manual URL construction
query_url = f"{settings.fuseki_url}/{settings.fuseki_dataset}/query"

# ✅ Use computed property
query_url = settings.sparql_query_endpoint
```

### 4. Environment-Specific Files

```bash
# Development
.env.development

# Staging
.env.staging

# Production
.env.production

# Load appropriate file
export ENV=production
python -m app --env-file .env.${ENV}
```

### 5. Secure Sensitive Data

```bash
# ❌ Commit .env to git
git add .env

# ✅ Use .env.example template
git add .env.example

# .gitignore
.env
.env.local
.env.*.local
```

---

## Troubleshooting

### Missing Environment Variables

**Problem:** Settings not loading from .env

**Solutions:**
```python
# 1. Check .env file exists
import os
print(os.path.exists(".env"))

# 2. Verify file encoding
# Must be UTF-8

# 3. Check for syntax errors
# KEY=value (no spaces around =)

# 4. Reload settings
from config import get_settings
get_settings.cache_clear()
settings = get_settings()
```

### Type Validation Errors

**Problem:** Pydantic validation fails

**Solutions:**
```python
# Check types match
MILVUS_PORT=19530  # ✅ int
MILVUS_PORT="19530"  # ❌ str (will be converted)

ENABLE_QUERY_CACHE=true  # ✅ bool
ENABLE_QUERY_CACHE=True  # ✅ bool
ENABLE_QUERY_CACHE=1  # ✅ bool (converted)
```

### Configuration Not Updating

**Problem:** Changes to .env not reflected

**Solutions:**
```python
# Clear cache
from config import get_settings
get_settings.cache_clear()

# Reload
settings = get_settings()

# Or restart application
```

---

## See Also

- **[LLM Providers](../llm/providers_comprehensive.md)** - LLM configuration
- **[SPARQL Store](../storage/sparql_comprehensive.md)** - Fuseki configuration
- **[Vector Store](../storage/vector_comprehensive.md)** - Milvus configuration
- **[Object Storage](../storage/object_storage_comprehensive.md)** - MinIO/COS configuration
- **[Artifact Store](artifact_store_comprehensive.md)** - Artifact management