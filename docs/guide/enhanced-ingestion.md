# Enhanced Ingestion Pipeline

The enhanced ingestion pipeline provides production-ready capabilities for processing large volumes of contract documents with advanced features like recursive directory scanning, batch processing, and agentic reasoning.

## Overview

The enhanced pipeline consists of three main components:

1. **Directory Scanner Agent** - Discovers all contract files (PDF/DOCX/DOC)
2. **Batch Processor Agent** - Processes multiple documents in parallel through full ingestion pipeline
3. **Enhanced Document Ingestion Agent** - Extracts text with LLM reasoning

This guide focuses on *how to scale ingestion*. For the most up-to-date end-to-end architecture (including **Docling**, **MinIO prefixes**, **async jobs**, **ETag skip**, **manifests**, and **schema evolution/governance**), see:

- `docs/guide/ingestion.md`

## Features

### 1. Recursive Directory Scanning

Automatically discovers all contract documents in a directory tree:

```python
from agents.ingestion.directory_scanner import DirectoryScannerAgent

scanner = DirectoryScannerAgent(settings=settings)
scan_result = await scanner.process("examples/")

print(f"Found {scan_result.supported_files} processable files")
print(f"By supplier: {scan_result.files_by_supplier}")
```

**Capabilities:**
- Recursive traversal of nested directories
- Simple path-based file classification (no LLM)
- Relationship detection (parent/child contracts)
- Batch organization by supplier
- Metadata extraction from file paths

### 2. Supported File Types

Currently supports the following document formats:

| Format | Extension | Library | Use Case |
|--------|-----------|---------|----------|
| PDF | `.pdf` | pdfplumber | Standard contracts |
| Word | `.docx`, `.doc` | python-docx | Editable contracts |

> Note: When `INGESTION_SOURCE=docling`, parsing is handled by **Docling** and the supported extensions are controlled by Docling (commonly `.pdf`, `.docx`, `.doc`, `.pptx`). See `docs/guide/ingestion.md` for details and MinIO usage.

### 3. Batch Processing

Process multiple documents in parallel with resource management:

```python
from agents.ingestion.batch_processor import BatchProcessorAgent

processor = BatchProcessorAgent(
    settings=settings,
    max_concurrent=5,  # Process 5 files at once
    max_retries=2,     # Retry failed files
    retry_delay_ms=1000
)

result = await processor.process({
    "files": discovered_files,
    "processor_fn": process_document,
    "progress_callback": track_progress
})

print(f"Processed: {result.successful}/{result.total_files}")
```

**Features:**
- Configurable concurrency limits
- Automatic retry logic
- Progress tracking
- Error handling and reporting
- Resource management

### 4. Agentic Document Processing

Uses LLM reasoning for intelligent document analysis:

```python
from agents.ingestion.enhanced_document_ingestion import (
    EnhancedDocumentIngestionAgent
)

agent = EnhancedDocumentIngestionAgent(settings=settings)
doc = await agent.process("contract.pdf")

print(f"Quality: {doc.confidence:.2f}")
print(f"Method: {doc.extraction_method}")
print(f"Analysis: {doc.metadata.get('llm_analysis')}")
```

**LLM Analysis Provides:**
- Document quality assessment (1-10 score)
- Key sections identification
- Extraction issue detection
- Processing recommendations
- Chain-of-thought reasoning

## Usage

### Quick Start

Process a single directory:

```bash
# Recommended: use Makefile targets (runs inside the ingestion container)
make ingest DIR=examples

# Force reprocess all documents (ignore registry/duplicate detection)
make ingest-override DIR=examples
```

### Full Pipeline

Process all documents with full pipeline:

```bash
make ingest DIR=examples
```

### Docling + MinIO (Async)

When running structure-aware ingestion from MinIO prefixes, use the async job API via Makefile:

```bash
# Submit async Docling ingestion from MinIO (default: minio://input/examples)
make ingest-async-minio

# Custom prefix
make ingest-async-minio PREFIX=input/examples/Adobe/child_contracts

# Track progress and get per-file results when complete
make ingest-status JOB_ID=<job-id>
```

### Programmatic Usage

```python
import asyncio
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from agents.ingestion.batch_processor import BatchProcessorAgent
from agents.ingestion.enhanced_document_ingestion import (
    EnhancedDocumentIngestionAgent
)
from config import get_settings

async def main():
    settings = get_settings()
    
    # Step 1: Scan directory
    scanner = DirectoryScannerAgent(settings=settings)
    scan_result = await scanner.process("examples/")
    
    # Step 2: Filter supported files
    files = [
        f for f in scan_result.discovered_files
        if f.category != "unsupported"
    ]
    
    # Step 3: Process in batches
    async def process_file(file):
        agent = EnhancedDocumentIngestionAgent(settings=settings)
        return await agent.process(file.path)
    
    processor = BatchProcessorAgent(settings=settings)
    result = await processor.process({
        "files": files,
        "processor_fn": process_file
    })
    
    print(f"Success: {result.successful}/{result.total_files}")

asyncio.run(main())
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Enhanced Ingestion Pipeline             │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────────┐                                   │
│  │ Directory Scanner │  Discovers all PDF/DOCX/DOC      │
│  └────────┬─────────┘                                   │
│           │                                              │
│           ▼                                              │
│  ┌──────────────────┐                                   │
│  │ Batch Processor  │  Runs files through full          │
│  │                  │  ingestion pipeline agents        │
│  └────────┬─────────┘                                   │
│           │                                              │
│           ▼                                              │
│  ┌──────────────────┐                                   │
│  │ Enhanced Doc     │  Extract with LLM reasoning       │
│  │ Ingestion        │                                   │
│  └────────┬─────────┘                                   │
│           │                                              │
│           ▼                                              │
│  ┌──────────────────┐                                   │
│  │ Ingestion        │  Full pipeline (clauses,          │
│  │ Orchestrator     │  entities, RDF, Fuseki)           │
│  └──────────────────┘                                   │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Discovery Phase**
   - Scan directory recursively
   - Classify files by type and supplier
   - Detect parent/child relationships
   - Organize into batches

2. **Extraction Phase**
   - Extract text based on file type
   - Use LLM to analyze quality
   - Assess confidence score
   - Generate metadata

3. **Processing Phase**
   - Extract clauses and entities
   - Generate RDF triples
   - Validate with SHACL
   - Load to Fuseki
   - Index vectors

4. **Ontology Evolution**
   - Detect new concepts
   - Generate OWL extensions
   - Update Fuseki ontology
   - Sync with retrieval agents

5. **Operational Reliability (MinIO jobs)**
   - ETag-based skip/re-ingest (identity = `bucket:key:etag`)
   - Per-job manifests in object storage (`ingestion_manifests/<job_id>.json`)
   - Async job progress (0–100) via `/api/v1/ingest/status/<job_id>`

## Configuration

### Environment Variables

```bash
# LLM Configuration
LLM_PROVIDER=watsonx
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_API_KEY=your_key
WATSONX_PROJECT_ID=your_project

# Fuseki Configuration
FUSEKI_URL=http://fuseki:3030
FUSEKI_DATASET=contracts

# Milvus Configuration
MILVUS_HOST=milvus
MILVUS_PORT=19530
```

### Ingestion Config

```python
from agents.ingestion.ingestion_orchestrator import IngestionConfig

config = IngestionConfig(
    ontology_evolution_mode="adaptive",  # Auto-extend ontology
    enable_shacl_validation=True,        # Validate RDF
    enable_reasoning=True,               # Infer new facts
    enable_vector_indexing=True,         # Index for retrieval
    enable_pattern_detection=True,       # Detect patterns
    enable_schema_governance=True        # Version control
)
```

## Performance

### Benchmarks

Processing 150+ contract files from examples folder:

| Metric | Value |
|--------|-------|
| Scan time | ~2-3 seconds |
| Avg extraction time | ~5-10 seconds/file |
| Parallel processing | 3-5 files concurrently |
| Total throughput | ~30-50 files/minute |

### Optimization Tips

1. **Increase Concurrency**
   ```python
   processor = BatchProcessorAgent(max_concurrent=10)
   ```

2. **Disable Optional Features**
   ```python
   config = IngestionConfig(
       enable_reasoning=False,  # Skip if not needed
       enable_vector_indexing=False
   )
   ```

3. **Use Batch Processing**
   - Process files in groups by supplier
   - Prioritize important documents first

## Error Handling

The pipeline includes comprehensive error handling:

```python
# Automatic retry for transient failures
processor = BatchProcessorAgent(
    max_retries=2,
    retry_delay_ms=1000
)

# Detailed error reporting
result = await processor.process(...)
for error in result.errors:
    print(f"Failed: {error['file']}: {error['error']}")
```

## Monitoring

Track progress in real-time:

```python
async def progress_callback(progress):
    print(f"Progress: {progress.progress_percent:.1f}%")
    print(f"Completed: {progress.completed}/{progress.total_tasks}")
    print(f"Failed: {progress.failed}")

result = await processor.process({
    "files": files,
    "processor_fn": process_fn,
    "progress_callback": progress_callback
})
```

## Next Steps

- [Ontology Evolution](./schema-evolution.md) - Dynamic ontology updates
- [Vector Indexing](./retrieval.md) - Semantic search setup
- [SPARQL Queries](./sparql-queries.md) - Query the knowledge graph

## Troubleshooting

### Common Issues

**Issue: Low extraction confidence**
- Check document quality (scanned vs digital)
- Verify LLM is configured correctly
- Review extraction logs for issues

**Issue: Slow processing**
- Increase `max_concurrent` setting
- Disable optional features
- Use faster LLM model

## API Reference

See [API Documentation](../api/agents/ingestion.md) for detailed API reference.