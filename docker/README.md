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

## Testing Automatic Initialization

### Prerequisites

- Docker and Docker Compose installed
- Git repository cloned
- No existing Fuseki containers running on port 3030

### Testing Steps

#### 1. Clean Environment

```bash
# Stop any existing containers
cd docker
docker-compose down -v

# Remove any existing Fuseki images
docker rmi $(docker images | grep fuseki | awk '{print $3}') 2>/dev/null || true

# Verify port 3030 is free
lsof -i :3030
```

#### 2. Build and Start Services

```bash
# Build the custom Fuseki image
docker-compose build fuseki

# Start Fuseki service
docker-compose up -d fuseki

# Watch the initialization logs
docker-compose logs -f fuseki
```

#### 3. Expected Log Output

```
==========================================
Contract KG - Fuseki Initialization
==========================================
[INFO] Waiting for Fuseki to start...
[SUCCESS] Fuseki is ready!
[INFO] Creating 'contracts' dataset with TDB2 backend...
[SUCCESS] Dataset 'contracts' created successfully
[INFO] Loading procurement ontology...
[SUCCESS] Ontology loaded successfully
          Total triples: 500+
[SUCCESS] Fuseki Initialization Complete!
```

#### 4. Verify Dataset Creation

```bash
# Check if dataset exists
curl -u admin:admin123 http://localhost:3030/$/datasets
```

#### 5. Verify Ontology Loading

```bash
# Query triple count
curl -u admin:admin123 \
  "http://localhost:3030/contracts/query" \
  -H "Accept: application/sparql-results+json" \
  --data-urlencode "query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"

# Expected: Should return count > 500 triples
```

#### 6. Test Idempotency (Restart Container)

```bash
# Restart the container
docker-compose restart fuseki

# Watch logs again
docker-compose logs -f fuseki

# Expected output should show:
# [SUCCESS] Dataset 'contracts' already exists (skipping creation)
# [SUCCESS] Ontology already loaded (XXX triples found)
```

#### 7. Test with Fresh Start

```bash
# Stop and remove volumes
docker-compose down -v

# Start again
docker-compose up -d fuseki

# Watch logs - should create dataset and load ontology again
docker-compose logs -f fuseki
```

#### 8. Access Fuseki UI

Open browser to http://localhost:3030
- Login with: admin / admin123
- Verify dataset 'contracts' is listed
- Can run SPARQL queries
- Triple count matches logs

#### 9. Test with Full Stack

```bash
# Start all services
docker-compose up -d

# Check health of all services
docker-compose ps

# All services should show "healthy" status
```

### Success Criteria

- Fuseki container starts successfully
- Initialization script runs without errors
- Dataset 'contracts' is created
- Ontology is loaded (500+ triples)
- Reasoning rules file is detected
- Container restart is idempotent (no duplicate data)
- Fuseki UI is accessible at http://localhost:3030
- SPARQL queries work correctly

### Performance Expectations

- Container startup: < 30 seconds
- Dataset creation: < 5 seconds
- Ontology loading: < 10 seconds
- Total initialization: < 45 seconds

### Troubleshooting Tests

**Container fails to start:**
```bash
docker-compose logs fuseki
# Common causes: Port 3030 in use, insufficient memory, permission issues
```

**Dataset not created:**
```bash
curl http://localhost:3030/$/ping
docker-compose exec fuseki cat /docker-entrypoint.d/init-fuseki.sh
docker-compose exec fuseki ls -lh /staging/ontology/
```

**Ontology not loading:**
```bash
docker-compose exec fuseki cat /staging/ontology/procurement.owl | head -20
# Try manual load if needed
```

### Cleanup After Testing

```bash
# Stop all services
docker-compose down -v

# Remove images
docker rmi $(docker images | grep contract-kg | awk '{print $3}')
```

## Related Documentation

- [Setup Guide](../docs/getting-started/setup-guide.md) - Detailed setup instructions
- [Configuration](../docs/getting-started/configuration.md) - Environment variables
- [Architecture](../docs/architecture/overview.md) - System design

## Getting Help

1. Check logs: `docker-compose logs <service>`
2. Verify health: `make health` (from project root)
3. See [Troubleshooting Guide](../docs/troubleshooting.md)
4. Open an issue with logs

## Notes for Container Deployment

This implementation is specifically designed for Docker container deployment:
- All initialization happens inside the container
- No external scripts or manual steps required
- Idempotent and safe for orchestration tools (Kubernetes, Docker Swarm)
- Logs provide clear visibility into initialization process
- Health checks ensure container is ready before accepting traffic

---

**Key Takeaway**: Everything is automatic! Just run `docker-compose up -d` and the system initializes itself.