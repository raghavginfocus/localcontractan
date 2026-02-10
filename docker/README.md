# Docker Setup - Automatic Initialization

This directory contains Docker configurations for the Contract Knowledge Graph system with **automatic initialization**.

## Quick Start

```bash
# Start all services with automatic setup
cd docker
docker-compose up -d

# Or use Makefile from project root
make services-up
```

## Services

### Fuseki (Custom Build with Auto-Init)

**Image**: Custom build from `Dockerfile.fuseki` 
**Port**: 3030 
**Features**:
- Automatic dataset creation (`contracts`)
- Automatic ontology loading (`ontology/procurement.owl`)
- Text indexing configuration
- Reasoning rules preparation
- Idempotent initialization (safe to restart)

**What's Included**:
- Base ontology embedded in image
- Reasoning rules embedded in image
- Initialization script runs on startup
- Verifies and reports status

**Access**:
- UI: http://localhost:3030
- Query: http://localhost:3030/contracts/query
- Update: http://localhost:3030/contracts/update
- Credentials: `admin` / `admin123`

### Milvus (Vector Database)

**Image**: milvusdb/milvus:v2.3.4 
**Port**: 19530 
**Features**:
- Vector similarity search
- Auto-creates collections on first use
- Persistent storage

### Phoenix (Observability)

**Image**: arizephoenix/phoenix:latest 
**Ports**: 6006 (UI), 4317 (gRPC), 4318 (HTTP) 
**Features**:
- LLM tracing and observability
- Experiment tracking
- Dataset management

### Agents API (Optional)

**Build**: `../agents/Dockerfile` 
**Port**: 8001 
**Features**:
- FastAPI service for ingestion/retrieval
- Automatic ontology initialization
- Health checks

## Configuration Files

### `Dockerfile.fuseki`

Custom Fuseki image that:
1. Embeds ontology and rules files
2. Installs initialization script
3. Configures automatic startup

**Key Features**:
- Based on `stain/jena-fuseki:latest`
- Runs `init-fuseki.sh` on startup
- Creates necessary directories
- Sets proper permissions

### `init-fuseki.sh`

Initialization script that:
1. Waits for Fuseki to be ready (max 30 retries)
2. Checks if dataset exists
3. Creates dataset if needed (TDB2 backend)
4. Loads ontology if not already loaded
5. Verifies triple count
6. Reports status and service info

**Idempotent**: Safe to run multiple times - won't duplicate data.

### `fuseki-config.ttl`

Advanced configuration for:
- Text indexing with Lucene
- Custom entity mappings
- Multi-lingual support
- Performance tuning

**Note**: Currently embedded but not actively used. Dataset is created via API for simplicity.

### `docker-compose.yml`

Orchestrates all services:
- Custom Fuseki build with auto-init
- Milvus with dependencies (etcd, minio)
- Phoenix for observability
- Optional: Agents API, Attu UI, MkDocs

## Initialization Flow

```
Container Start
↓
Fuseki Starts
↓
init-fuseki.sh Runs
↓
Wait for Fuseki Ready (max 60s)
↓
Check Dataset Exists?
Yes → Skip creation
No → Create with TDB2
↓
Check Ontology Loaded?
Yes (>100 triples) → Skip
No → Load procurement.owl
↓
Verify & Report
↓
Ready for Use
```

## Verification

### Check Initialization Logs

```bash
# View Fuseki logs
docker-compose logs fuseki

# Look for:
# Fuseki is ready!
# Dataset 'contracts' created successfully
# Ontology loaded successfully
# Total triples: 500+
# Fuseki Initialization Complete!
```

### Query Dataset

```bash
# Check if dataset exists
curl -u admin:admin123 http://localhost:3030/$/datasets

# Query triple count
curl -u admin:admin123 \
"http://localhost:3030/contracts/query" \
-H "Accept: application/sparql-results+json" \
--data-urlencode "query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
```

### System Health Check

```bash
# From project root
make health

# Expected:
# Fuseki: healthy (500+ triples)
# Milvus: healthy
# Ontology Manager: healthy
```

## Troubleshooting

### Fuseki Not Starting

```bash
# Check logs
docker-compose logs fuseki

# Common issues:
# - Port 3030 already in use
# - Insufficient memory (needs 2GB)
# - Volume permission issues
```

### Ontology Not Loading

```bash
# Verify ontology file exists
ls -lh ../ontology/procurement.owl

# Check if it's valid RDF
rapper -i rdfxml ../ontology/procurement.owl -o turtle > /dev/null

# Rebuild container
docker-compose build fuseki
docker-compose up -d fuseki
```

### Dataset Already Exists

This is **normal** and **expected**! The initialization script:
- Detects existing dataset
- Skips creation
- Verifies ontology
- Continues normally

### Reset Everything

```bash
# Stop and remove containers + volumes
docker-compose down -v

# Rebuild and restart
docker-compose build
docker-compose up -d
```

## Rebuilding

### Rebuild Fuseki Only

```bash
# After updating ontology or rules
docker-compose build fuseki
docker-compose up -d fuseki
```

### Rebuild All Services

```bash
docker-compose build
docker-compose up -d
```

## Volume Mounts

| Volume | Purpose | Persistence |
|--------|---------|-------------|
| `fuseki-data` | Fuseki databases | Persistent |
| `milvus-data` | Vector embeddings | Persistent |
| `phoenix-data` | Observability data | Persistent |
| `etcd-data` | Milvus metadata | Persistent |
| `minio-data` | Milvus storage | Persistent |

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Fuseki UI | http://localhost:3030 | SPARQL interface |
| Milvus | localhost:19530 | Vector DB (gRPC) |
| Phoenix | http://localhost:6006 | Observability UI |
| Agents API | http://localhost:8001 | REST API |
| Attu (optional) | http://localhost:8080 | Milvus UI |
| MkDocs | http://localhost:8000 | Documentation |

## Related Documentation

- [Setup Guide](../docs/getting-started/setup-guide.md) - Detailed setup instructions
- [Configuration](../docs/getting-started/configuration.md) - Environment variables
- [Architecture](../docs/architecture/overview.md) - System design

## Getting Help

1. Check logs: `docker-compose logs <service>`
2. Verify health: `make health` (from project root)
3. See [Troubleshooting Guide](../docs/troubleshooting.md)
4. Open an issue with logs

---

**Key Takeaway**: Everything is automatic! Just run `docker-compose up -d` and the system initializes itself.