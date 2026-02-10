# Setup Guide - Automatic Initialization

This guide explains how the Contract Knowledge Graph system automatically initializes itself, eliminating manual setup steps for developers.

## [INFO] Quick Start (Fully Automatic)

```bash
# 1. Clone and install dependencies
git clone <repository-url>
cd procurement_grag
make install

# 2. Setup environment
make setup-env
# Edit agents/.env with your API keys

# 3. Start all services (automatic initialization!)
make services-up

# 4. Verify everything is ready
make health
```

That's it! The system automatically:
- [INFO] Creates the Fuseki dataset
- [INFO] Loads the base ontology
- [INFO] Configures text indexing
- [INFO] Prepares reasoning rules
- [INFO] Initializes Milvus collections

## [INFO] What Happens Automatically

### 1. Fuseki Initialization (Automatic)

When you run `make services-up`, the custom Fuseki container:

1. **Builds with embedded files**:
- Base ontology: `ontology/procurement.owl`
- Reasoning rules: `rules/procurement.rules`
- Configuration: `docker/fuseki-config.ttl`

2. **Runs initialization script** (`docker/init-fuseki.sh`):
- Waits for Fuseki to be ready
- Creates `contracts` dataset with TDB2 backend
- Loads base ontology (if not already loaded)
- Verifies triple count
- Displays service information

3. **Result**: Fuseki is ready with:
- Dataset: `contracts`
- Base ontology loaded (~500+ triples)
- Query endpoint: `http://localhost:3030/contracts/query`
- Update endpoint: `http://localhost:3030/contracts/update`

### 2. Ontology Loading (Automatic)

**Base Ontology** (`ontology/procurement.owl`):
- [INFO] Loaded into Fuseki during container startup
- [INFO] Loaded into memory during ingestion pipeline startup
- Contains core classes: Contract, Clause, Party, Obligation, Risk, etc.

**Generated Extensions** (created during ingestion):
- [INFO] Auto-generated when new patterns are detected
- [INFO] Auto-synced to Fuseki's ontology graph
- [INFO] Auto-reloaded into OntologyManager
- Examples: New clause types, custom properties, domain-specific concepts

### 3. Reasoning Rules (Automatic)

**Base Rules** (`rules/procurement.rules`):
- [INFO] Available in container at `/staging/rules/`
- [INFO] Loaded during ingestion when reasoning is enabled
- Contains inference rules for risk detection, compliance checking

**Generated Rules** (created during ingestion):
- [INFO] Auto-generated based on patterns
- [INFO] Auto-synced to Fuseki
- [INFO] Applied during reasoning phase

## Verification

### Check Fuseki Status

```bash
# View Fuseki logs
make services-logs-fuseki

# Check if dataset exists
curl -u admin:admin123 http://localhost:3030/$/datasets

# Query triple count
curl -u admin:admin123 \
"http://localhost:3030/contracts/query" \
-H "Accept: application/sparql-results+json" \
--data-urlencode "query=SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
```

### Check System Health

```bash
# Comprehensive health check
make health

# Expected output:
# [INFO] Fuseki: healthy (500+ triples)
# [INFO] Milvus: healthy
# [INFO] Ontology Manager: healthy (50+ classes)
# [INFO] LLM: healthy
```

## [INFO] Manual Operations (Optional)

While everything is automatic, you can still perform manual operations:

### Rebuild Fuseki Container

```bash
# Rebuild with latest ontology/rules
cd docker
docker-compose build fuseki
docker-compose up -d fuseki
```

### Manually Load Ontology

```bash
# Only needed if you want to pre-load before ingestion
make data-load-ontology
```

### Reset Dataset

```bash
# Delete and recreate dataset
cd agents
uv run python ../scripts/setup/setup_fuseki.py --delete
uv run python ../scripts/setup/setup_fuseki.py
```

## [INFO] What Gets Created

### During Container Startup

| Component | Location | Status |
|-----------|----------|--------|
| Fuseki Dataset | `contracts` | [INFO] Auto-created |
| Base Ontology | Fuseki graph | [INFO] Auto-loaded |
| Reasoning Rules | `/staging/rules/` | [INFO] Available |
| Text Index Config | Fuseki config | [INFO] Configured |

### During First Ingestion

| Component | Location | Status |
|-----------|----------|--------|
| Milvus Collection | `contract_clauses` | [INFO] Auto-created |
| Document Registry | SQLite DB | [INFO] Auto-created |
| Generated Extensions | `data/ontology_extensions/` | [INFO] Auto-generated |
| SHACL Shapes | `data/shacl_shapes/` | [INFO] Auto-generated |
| Generated Rules | `data/reasoning_rules/` | [INFO] Auto-generated |

## Key Benefits

### For Developers

1. **Zero Manual Setup**: No need to run separate initialization scripts
2. **Idempotent**: Safe to restart containers - won't duplicate data
3. **Self-Healing**: Automatically detects and loads missing components
4. **Transparent**: Clear logs show what's happening

### For Production

1. **Consistent**: Same initialization across all environments
2. **Reliable**: Automatic verification and error handling
3. **Documented**: All steps logged for debugging
4. **Scalable**: Works with Docker Swarm/Kubernetes

## Troubleshooting

### Fuseki Not Initializing

```bash
# Check logs
make services-logs-fuseki

# Common issues:
# - Ontology file not found: Check ontology/procurement.owl exists
# - Permission denied: Check file permissions
# - Port conflict: Check if port 3030 is available
```

### Ontology Not Loading

```bash
# Verify ontology file
ls -lh ontology/procurement.owl

# Check if it's valid RDF/XML
rapper -i rdfxml ontology/procurement.owl -o turtle > /dev/null

# Manually load
curl -X POST http://localhost:3030/contracts/data \
-u admin:admin123 \
-H "Content-Type: application/rdf+xml" \
--data-binary @ontology/procurement.owl
```

### Dataset Already Exists Error

This is normal! The initialization script is idempotent:
- [INFO] Detects existing dataset
- [INFO] Skips creation
- [INFO] Verifies ontology is loaded
- [INFO] Continues normally

## [INFO] Related Documentation

- [Installation Guide](installation.md) - Initial setup
- [Configuration Guide](configuration.md) - Environment variables
- [Architecture Overview](../architecture/overview.md) - System design
- [Ingestion Pipeline](../guide/enhanced-ingestion.md) - How ingestion works

## Getting Help

If automatic initialization fails:

1. Check logs: `make services-logs-fuseki`
2. Verify files exist: `ls -lh ontology/ rules/`
3. Check health: `make health`
4. See [Troubleshooting Guide](../troubleshooting.md)
5. Open an issue with logs

---

**Next Steps**: Once services are up, proceed to [Running Ingestion](../guide/enhanced-ingestion.md)