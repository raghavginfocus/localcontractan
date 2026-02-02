# Scripts Directory

This directory contains utility scripts organized by functionality.

## Directory Structure

### 📊 `evaluation/`
Evaluation and benchmarking scripts:
- `evaluate_enhanced.py` - Enhanced evaluation script with Phoenix observability
- `run_phoenix_experiments.py` - Phoenix experiments runner

### 📥 `ingestion/`
Document ingestion and processing scripts:
- `run_ingestion.py` - Run single ingestion
- `run_ingestion_pipeline.py` - Full ingestion pipeline
- `ingest_single_document.py` - Ingest a single document
- `monitor_ingestion.py` - Monitor ingestion progress
- `pre_ingestion_check.py` - Pre-flight checks before ingestion

### ⚙️ `setup/`
System setup and configuration scripts:
- `setup_fuseki.py` - Setup Fuseki SPARQL server
- `setup_fuseki_with_text_index.py` - Setup Fuseki with text indexing
- `setup_text_index.py` - Setup text index for Fuseki
- `migrate_milvus_schema.py` - Migrate Milvus schema

### 📈 `analysis/`
Log analysis and data querying scripts:
- `analyze_ingestion_logs.py` - Analyze ingestion logs
- `analyze_retrieval_logs.py` - Analyze retrieval logs
- `view_logs.py` - View and filter logs
- `view_diagrams.py` - View architecture diagrams
- `query_data.py` - Query data from stores

### 💾 `data/`
Data management and verification scripts:
- `check_milvus_data.py` - Check Milvus collection data
- `check_fuseki_data.py` - Check Fuseki triple store data
- `verify_complete_pipeline.py` - Verify complete pipeline
- `verify_fuseki_data.py` - Verify Fuseki data integrity
- `verify_milvus_fuseki_connection.py` - Verify connection between stores
- `load_data.py` - Load sample/ontology data
- `load_saved_rdf.py` - Load saved RDF files

### 🛠️ `utilities/`
General utility scripts:
- `health_check.py` - System health check
- `centralize_logs.py` - Centralize logs from multiple sources
- `export_diagrams.py` - Export architecture diagrams
- `start_services.sh` - Start Docker services

## Test Scripts

All test scripts have been moved to `agents/tests/` directory:
- `test_*.py` - All test scripts are now in `agents/tests/`

## Usage

Most scripts are run via the Makefile. See `make help` for available commands.

For direct execution:
```bash
cd agents
PYTHONPATH=src uv run python ../scripts/<category>/<script>.py [args]
```
