# Ingestion Pipeline Improvements

## Overview

This document describes the recent improvements to the ingestion pipeline, including MinIO integration, Docling support, and enhanced progress tracking.

## Key Changes

### 1. MinIO Object Storage Integration

**What Changed:**
- Added `object_storage.py` module for S3-compatible storage (MinIO/IBM COS)
- Documents are now stored in MinIO after parsing
- Supports both raw files and parsed DocTags JSON

**Configuration:**
```bash
# .env file
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1
```

**Benefits:**
- Centralized document storage
- Better scalability
- Supports distributed processing
- Preserves original files and parsed data

### 2. Docling Integration

**What Changed:**
- Added `docling_parser.py` for advanced document parsing
- Added `docling_document_ingestion.py` for Docling-based pipeline
- Added `doctags_preprocessor.py` for structured section extraction
- Added `doctags_storage.py` for MinIO storage operations

**How It Works:**
```
PDF/DOCX → Docling Parser → DocTags JSON → Preprocessor → Structured Sections
                                ↓
                          MinIO Storage (raw + parsed + metadata)
                                ↓
                          Downstream Agents (with structured input)
```

**Advantages over Legacy Pipeline:**
- Better layout analysis (tables, headers, lists)
- Structured sections instead of flat text
- Preserves document structure
- Better table extraction
- More accurate text extraction

**Usage:**
```bash
# Use Docling pipeline
export INGESTION_SOURCE=docling

# Or use legacy pipeline (default)
export INGESTION_SOURCE=legacy
```

### 3. Enhanced Progress Tracking

**What Changed:**
- Added `tqdm` library for visual progress bars
- Enhanced `batch_processor.py` with real-time progress
- Created `run_ingestion_with_progress.py` script

**Features:**
- Visual progress bar with file count
- Real-time status updates (✓/✗)
- Current file being processed
- Estimated time remaining
- Success/failure indicators

**Example Output:**
```
Processing documents: 100%|████████████| 10/10 [02:15<00:00, 13.5s/doc]
```

### 4. Dual Pipeline Support

**Configuration:**
The system now supports two ingestion pipelines:

**Legacy Pipeline (PyPDF2/python-docx):**
- Uses: `fuseki_dataset` and `milvus_collection_v2`
- Good for: Simple documents, backward compatibility
- Faster but less accurate

**Docling Pipeline (Docling + MinIO):**
- Uses: `docling_fuseki_dataset` and `docling_milvus_collection`
- Good for: Complex documents, tables, structured data
- Slower but more accurate

**Switching Pipelines:**
```bash
# Legacy
export INGESTION_SOURCE=legacy

# Docling
export INGESTION_SOURCE=docling
```

## Architecture

### Ingestion Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Input                            │
│                  (PDF, DOCX, DOC)                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Pipeline Selection   │
         │  (Legacy vs Docling)  │
         └───────┬───────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────────┐
│   Legacy     │  │    Docling       │
│  Pipeline    │  │   Pipeline       │
│              │  │                  │
│ PyPDF2/docx  │  │ Docling Parser   │
│              │  │      +           │
│ Flat Text    │  │ DocTags Preproc  │
│              │  │      +           │
│              │  │  MinIO Storage   │
└──────┬───────┘  └────────┬─────────┘
       │                   │
       └─────────┬─────────┘
                 │
                 ▼
    ┌────────────────────────┐
    │  Clause Extraction     │
    │  (LLM-based)          │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  Entity Extraction     │
    │  (Parallel)           │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  Obligation/Risk       │
    │  Analysis             │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  Ontology Alignment    │
    │  + Schema Evolution   │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  RDF Generation        │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  SHACL Validation      │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  Fuseki Loading        │
    │  + Reasoning          │
    └────────┬───────────────┘
             │
             ▼
    ┌────────────────────────┐
    │  Vector Indexing       │
    │  (Milvus)             │
    └────────────────────────┘
```

### MinIO Storage Structure

```
procurement-contracts/
├── raw/
│   └── {document_id}/
│       └── original.{ext}
├── parsed/
│   └── {document_id}/
│       └── doctags.json
└── metadata/
    └── {document_id}/
        └── metadata.json
```

## Usage Examples

### 1. Basic Ingestion (Legacy)

```bash
cd agents
uv run python ../scripts/ingestion/run_ingestion_pipeline.py
```

### 2. Ingestion with Docling

```bash
cd agents
export INGESTION_SOURCE=docling
uv run python ../scripts/ingestion/run_ingestion_with_progress.py --directory ../examples --use-docling
```

### 3. Ingestion with Progress Bar

```bash
cd agents
uv run python ../scripts/ingestion/run_ingestion_with_progress.py \
    --directory ../examples \
    --max-concurrent 3 \
    --override
```

### 4. Test with Limited Files

```bash
cd agents
uv run python ../scripts/ingestion/run_ingestion_with_progress.py \
    --directory ../examples \
    --max-files 5
```

## Configuration Reference

### Environment Variables

```bash
# Ingestion Pipeline Selection
INGESTION_SOURCE=docling  # or 'legacy'

# MinIO Configuration
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1

# Docling Pipeline Targets
DOCLING_FUSEKI_DATASET=contracts_docling
DOCLING_MILVUS_COLLECTION=contract_clauses_docling

# Legacy Pipeline Targets (default)
FUSEKI_DATASET=contracts
MILVUS_COLLECTION_V2=contract_clauses_v2
```

## Performance Considerations

### Legacy Pipeline
- **Speed:** ~10-15s per document
- **Accuracy:** Good for simple documents
- **Memory:** Low
- **Best for:** Bulk processing, simple contracts

### Docling Pipeline
- **Speed:** ~20-30s per document
- **Accuracy:** Excellent for complex documents
- **Memory:** Higher (layout analysis)
- **Best for:** Complex contracts, tables, structured data

### Optimization Tips

1. **Parallel Processing:**
   ```bash
   --max-concurrent 5  # Process 5 docs simultaneously
   ```

2. **Skip Duplicates:**
   ```bash
   # Documents are automatically skipped if already processed
   # Use --override to force reprocessing
   ```

3. **MinIO Performance:**
   - Use local MinIO for development
   - Use IBM COS for production
   - Enable bucket versioning for safety

## Troubleshooting

### Issue: MinIO Connection Failed

**Solution:**
```bash
# Check MinIO is running
docker ps | grep minio

# Start MinIO
docker-compose up -d minio

# Test connection
curl http://localhost:9000/minio/health/live
```

### Issue: Docling Import Error

**Solution:**
```bash
# Install Docling
cd agents
uv add docling
```

### Issue: Progress Bar Not Showing

**Solution:**
```bash
# Install tqdm
cd agents
uv add tqdm
```

### Issue: Documents Not Being Processed

**Check:**
1. Document registry for duplicates
2. File permissions
3. Supported file types (PDF, DOCX, DOC)
4. MinIO bucket exists

**Debug:**
```bash
# Check document registry
sqlite3 agents/checkpoints/document_registry.db "SELECT * FROM documents;"

# Clear registry (force reprocess)
rm agents/checkpoints/document_registry.db
```

## Next Steps

1. **Test the Pipeline:**
   ```bash
   cd agents
   uv run python ../scripts/ingestion/run_ingestion_with_progress.py \
       --directory ../examples \
       --max-files 2
   ```

2. **Monitor Progress:**
   - Watch the progress bar
   - Check logs for errors
   - Verify MinIO storage

3. **Validate Results:**
   - Query Fuseki for triples
   - Check Milvus for vectors
   - Review MinIO for stored files

## Summary

The ingestion pipeline now supports:
- ✅ MinIO object storage integration
- ✅ Docling advanced document parsing
- ✅ Enhanced progress tracking with tqdm
- ✅ Dual pipeline support (Legacy + Docling)
- ✅ Better error handling and recovery
- ✅ Structured document sections
- ✅ Improved table extraction
- ✅ Real-time progress visualization

Choose the pipeline based on your needs:
- **Legacy:** Fast, simple documents
- **Docling:** Accurate, complex documents with tables