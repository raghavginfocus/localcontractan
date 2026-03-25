# Artifact Store API Reference

Comprehensive API documentation for managing generated artifacts during document ingestion with async file I/O and object storage support.

## Overview

The Artifact Store module manages storage of all generated artifacts during the ingestion pipeline, including RDF data, ontology extensions, inference rules, and ingestion logs. It supports both local filesystem and object storage backends (MinIO/IBM COS) with async file operations for better performance.

**Key Features:**
- Async file I/O for high performance
- Local filesystem storage
- Optional object storage backend (MinIO/IBM COS)
- Organized directory structure
- Automatic timestamping
- Metadata embedding in files
- Object storage upload with cleanup
- Artifact retrieval and listing
- Cleanup of old artifacts

---

## ArtifactStore

Main class for managing generated artifacts.

### Class Definition

```python
from artifact_store import ArtifactStore

class ArtifactStore:
    """
    Manages storage of all generated artifacts during ingestion.
    
    Directory Structure:
    data/generated/
    ├── rdf/                    # Generated RDF for each document
    │   ├── doc_001_20240110.ttl
    │   └── doc_002_20240110.ttl
    ├── ontology/               # Generated OWL extensions
    │   ├── dataprotectionclause_20240110.ttl
    │   └── extensions_combined_20240110.ttl
    ├── rules/                  # Generated Jena rules and SPARQL
    │   ├── highdataretentionrisk_20240110.rules
    │   └── highdataretentionrisk_20240110.sparql
    └── logs/                   # Ingestion logs and metadata
        ├── doc_001_20240110.json
        └── doc_002_20240110.json
    """
```

### Constructor

```python
def __init__(
    self,
    base_dir: Path | str | None = None,
    *,
    settings: Any | None = None
)
```

Initialize the artifact store.

**Parameters:**

- **base_dir** : `Path | str | None`, default=`None`
  - Base directory for all artifacts
  - If None, uses default: `/app/data/generated` (container) or `agents/data/generated` (local)
  
- **settings** : `Any | None`, default=`None`
  - Application settings for object storage configuration
  - If provided and `artifact_store_backend=object_storage`, enables object storage

**Attributes:**

- **base_dir** : `Path`
  - Base directory for artifacts
  
- **rdf_dir** : `Path`
  - Directory for RDF files
  
- **ontology_dir** : `Path`
  - Directory for ontology extensions
  
- **rules_dir** : `Path`
  - Directory for inference rules
  
- **extractions_dir** : `Path`
  - Directory for extraction results
  
- **log_dir** : `Path`
  - Directory for ingestion logs

**Example:**

```python
from artifact_store import ArtifactStore
from config import get_settings

# Use default directory
store = ArtifactStore()

# Use custom directory
store = ArtifactStore(base_dir="/custom/path/artifacts")

# With object storage
settings = get_settings()
settings.artifact_store_backend = "object_storage"
store = ArtifactStore(settings=settings)

print(f"Base directory: {store.base_dir}")
print(f"RDF directory: {store.rdf_dir}")
```

**Performance:**
- Initialization: ~10ms
- Directory creation: ~50ms (first time)
- Object storage init: +100-500ms (if enabled)

---

## RDF Storage

### save_rdf

```python
async def save_rdf(
    self,
    document_id: str,
    rdf_data: str,
    metadata: dict[str, Any] | None = None
) -> Path
```

Save generated RDF for a document (async).

**Parameters:**

- **document_id** : `str`
  - Document identifier
  - Used in filename
  
- **rdf_data** : `str`
  - RDF data in Turtle format
  
- **metadata** : `dict[str, Any] | None`, default=`None`
  - Optional metadata to include as comments in file

**Returns:**

- **file_path** : `Path`
  - Path to saved RDF file

**Example:**

```python
import asyncio

# Generate RDF
rdf_data = """
@prefix proc: <http://procurement.kg/ontology#> .
@prefix contract: <http://procurement.kg/contract#> .

contract:ABC123 a proc:Contract ;
    proc:contractId "ABC123" ;
    proc:contractValue "150000.00"^^xsd:decimal .
"""

# Save RDF
metadata = {
    "source": "contract_ABC123.pdf",
    "clauses_extracted": 15,
    "entities_extracted": 8
}

file_path = await store.save_rdf(
    document_id="ABC123",
    rdf_data=rdf_data,
    metadata=metadata
)

print(f"RDF saved to: {file_path}")
# Output: data/generated/rdf/ABC123_20240110_143022.ttl
```

**File Format:**

```turtle
# Generated RDF for document: ABC123
# Generated: 2024-01-10T14:30:22.123456
# source: contract_ABC123.pdf
# clauses_extracted: 15
# entities_extracted: 8

@prefix proc: <http://procurement.kg/ontology#> .
@prefix contract: <http://procurement.kg/contract#> .

contract:ABC123 a proc:Contract ;
    proc:contractId "ABC123" ;
    proc:contractValue "150000.00"^^xsd:decimal .
```

**Performance:**
- Small files (<100KB): 10-50ms
- Medium files (100KB-1MB): 50-200ms
- Large files (>1MB): 200-1000ms

---

### save_rdf_sync

```python
def save_rdf_sync(
    self,
    document_id: str,
    rdf_data: str,
    metadata: dict[str, Any] | None = None
) -> Path
```

Synchronous version of save_rdf (for backward compatibility).

**Parameters:**

- Same as `save_rdf`

**Returns:**

- **file_path** : `Path`
  - Path to saved RDF file

**Example:**

```python
# Synchronous usage
file_path = store.save_rdf_sync(
    document_id="ABC123",
    rdf_data=rdf_data,
    metadata=metadata
)
```

**Note:** Prefer using `save_rdf` (async) for better performance in async contexts.

---

## Ontology Extensions

### save_ontology_extension

```python
async def save_ontology_extension(
    self,
    name: str,
    owl_data: str,
    description: str = ""
) -> Path
```

Save generated OWL ontology extension (async).

**Parameters:**

- **name** : `str`
  - Name of the concept/extension
  - Used in filename (lowercased, spaces replaced with underscores)
  
- **owl_data** : `str`
  - OWL data in Turtle format
  
- **description** : `str`, default=`""`
  - Description of the extension

**Returns:**

- **file_path** : `Path`
  - Path to saved OWL file

**Example:**

```python
# Generate OWL extension
owl_data = """
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix proc: <http://procurement.kg/ontology#> .

proc:DataProtectionClause a owl:Class ;
    rdfs:subClassOf proc:Clause ;
    rdfs:label "Data Protection Clause" ;
    rdfs:comment "Clause related to data protection and privacy" .
"""

# Save extension
file_path = await store.save_ontology_extension(
    name="DataProtectionClause",
    owl_data=owl_data,
    description="New clause type for data protection requirements"
)

print(f"OWL extension saved to: {file_path}")
# Output: data/generated/ontology/dataprotectionclause_20240110_143022.ttl
```

**File Format:**

```turtle
# Generated OWL Extension: DataProtectionClause
# Generated: 2024-01-10T14:30:22.123456
# Description: New clause type for data protection requirements

@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix proc: <http://procurement.kg/ontology#> .

proc:DataProtectionClause a owl:Class ;
    rdfs:subClassOf proc:Clause ;
    rdfs:label "Data Protection Clause" .
```

**Performance:**
- Execution time: 10-100ms

---

## Inference Rules

### save_rule

```python
async def save_rule(
    self,
    rule_name: str,
    jena_rule: str,
    sparql_rule: str,
    description: str = ""
) -> tuple[Path, Path]
```

Save generated inference rule (both Jena and SPARQL formats, async).

**Parameters:**

- **rule_name** : `str`
  - Name of the rule
  - Used in filenames
  
- **jena_rule** : `str`
  - Jena rule syntax
  
- **sparql_rule** : `str`
  - SPARQL INSERT equivalent
  
- **description** : `str`, default=`""`
  - Description of the rule

**Returns:**

- **paths** : `tuple[Path, Path]`
  - Tuple of (jena_path, sparql_path)

**Example:**

```python
# Generate rule
jena_rule = """
[HighDataRetentionRisk:
    (?clause rdf:type proc:DataRetentionClause)
    (?clause proc:retentionPeriod ?period)
    greaterThan(?period, 365)
    ->
    (?clause proc:introducesRisk proc:HighDataRetentionRisk)
]
"""

sparql_rule = """
INSERT {
    ?clause proc:introducesRisk proc:HighDataRetentionRisk .
}
WHERE {
    ?clause a proc:DataRetentionClause ;
            proc:retentionPeriod ?period .
    FILTER(?period > 365)
}
"""

# Save rule
jena_path, sparql_path = await store.save_rule(
    rule_name="HighDataRetentionRisk",
    jena_rule=jena_rule,
    sparql_rule=sparql_rule,
    description="Identifies clauses with excessive data retention periods"
)

print(f"Jena rule: {jena_path}")
print(f"SPARQL rule: {sparql_path}")
```

**File Format (Jena):**

```
# Generated Jena Rule: HighDataRetentionRisk
# Generated: 2024-01-10T14:30:22.123456
# Description: Identifies clauses with excessive data retention periods

[HighDataRetentionRisk:
    (?clause rdf:type proc:DataRetentionClause)
    (?clause proc:retentionPeriod ?period)
    greaterThan(?period, 365)
    ->
    (?clause proc:introducesRisk proc:HighDataRetentionRisk)
]
```

**Performance:**
- Execution time: 20-150ms (two files)

---

## Ingestion Logs

### save_ingestion_log

```python
async def save_ingestion_log(
    self,
    document_id: str,
    result: dict[str, Any]
) -> Path
```

Save structured ingestion result for a single document.

**Parameters:**

- **document_id** : `str`
  - Document identifier
  
- **result** : `dict[str, Any]`
  - Full ingestion result as dictionary

**Returns:**

- **file_path** : `Path`
  - Path to saved JSON log file

**Example:**

```python
# Ingestion result
result = {
    "document_id": "ABC123",
    "status": "success",
    "clauses_extracted": 15,
    "entities_extracted": 8,
    "risks_identified": 3,
    "processing_time_seconds": 12.5,
    "rdf_triples": 234,
    "errors": [],
    "warnings": ["Long processing time"]
}

# Save log
file_path = await store.save_ingestion_log(
    document_id="ABC123",
    result=result
)

print(f"Log saved to: {file_path}")
# Output: data/generated/logs/ABC123_20240110_143022.json
```

**File Format:**

```json
{
  "document_id": "ABC123",
  "status": "success",
  "clauses_extracted": 15,
  "entities_extracted": 8,
  "risks_identified": 3,
  "processing_time_seconds": 12.5,
  "rdf_triples": 234,
  "errors": [],
  "warnings": ["Long processing time"]
}
```

**Performance:**
- Execution time: 10-50ms

---

## Extraction Results

### save_extraction_results

```python
async def save_extraction_results(
    self,
    document_id: str,
    clauses: list[dict[str, Any]],
    entities: dict[str, Any],
    obligations: list[dict[str, Any]],
    risks: list[dict[str, Any]]
) -> Path
```

Save extraction results (clauses, entities, obligations, risks) for a document.

**Parameters:**

- **document_id** : `str`
  - Document identifier
  
- **clauses** : `list[dict[str, Any]]`
  - Extracted clauses
  
- **entities** : `dict[str, Any]`
  - Extracted entities
  
- **obligations** : `list[dict[str, Any]]`
  - Extracted obligations
  
- **risks** : `list[dict[str, Any]]`
  - Extracted risks

**Returns:**

- **file_path** : `Path`
  - Path to saved JSON file

**Example:**

```python
# Extraction results
clauses = [
    {
        "id": "TERM_001",
        "type": "TerminationClause",
        "text": "Either party may terminate with 30 days notice.",
        "notice_period": 30
    },
    {
        "id": "PAY_001",
        "type": "PaymentClause",
        "text": "Payment due within 30 days of invoice.",
        "payment_terms": "Net 30"
    }
]

entities = {
    "parties": ["Company A", "Company B"],
    "dates": ["2024-01-01", "2025-01-01"],
    "amounts": [150000.00]
}

obligations = [
    {
        "type": "payment",
        "description": "Pay within 30 days",
        "deadline": "30 days"
    }
]

risks = [
    {
        "type": "ShortNoticeRisk",
        "severity": "medium",
        "description": "30-day notice period is short"
    }
]

# Save extraction results
file_path = await store.save_extraction_results(
    document_id="ABC123",
    clauses=clauses,
    entities=entities,
    obligations=obligations,
    risks=risks
)

print(f"Extraction results saved to: {file_path}")
```

**Performance:**
- Execution time: 20-100ms

---

## Object Storage Integration

### upload_file

```python
async def upload_file(
    self,
    file_path: Path,
    *,
    job_id: str | None,
    document_id: str,
    category: str
) -> str | None
```

Upload a local artifact file to object storage (if configured).

**Parameters:**

- **file_path** : `Path`
  - Local file path to upload
  
- **job_id** : `str | None`
  - Optional job identifier for grouping
  
- **document_id** : `str`
  - Document identifier
  
- **category** : `str`
  - Artifact category: "rdf", "ontology", "rules", "misc"

**Returns:**

- **uri** : `str | None`
  - MinIO URI (`minio://bucket/key`) if uploaded, None otherwise

**Example:**

```python
# Upload RDF file
uri = await store.upload_file(
    file_path=Path("data/generated/rdf/ABC123.ttl"),
    job_id="batch_001",
    document_id="ABC123",
    category="rdf"
)

if uri:
    print(f"Uploaded to: {uri}")
    # Output: minio://procurement-contracts/ingestion_artifacts/batch_001/ABC123/rdf/ABC123.ttl
else:
    print("Object storage not configured")
```

**Object Key Structure:**

```
{prefix}/{job_id}/{document_id}/{category}/{filename}

Example:
ingestion_artifacts/batch_001/ABC123/rdf/ABC123_20240110.ttl
```

**Performance:**
- Small files (<1MB): 100-300ms
- Medium files (1-10MB): 500-2000ms

---

### maybe_upload_artifact_paths

```python
async def maybe_upload_artifact_paths(
    self,
    artifact_paths: dict[str, str],
    *,
    document_id: str,
    job_id: str | None = None
) -> dict[str, str]
```

Upload any local artifact files referenced in artifact_paths to object storage.

**Parameters:**

- **artifact_paths** : `dict[str, str]`
  - Dictionary mapping artifact names to local paths
  
- **document_id** : `str`
  - Document identifier
  
- **job_id** : `str | None`, default=`None`
  - Optional job identifier

**Returns:**

- **updated_paths** : `dict[str, str]`
  - Updated dictionary with MinIO URIs for uploaded files

**Example:**

```python
# Artifact paths from ingestion
artifact_paths = {
    "rdf": "data/generated/rdf/ABC123.ttl",
    "owl_extension": "data/generated/ontology/dataprotection.ttl",
    "rule_jena": "data/generated/rules/highrisk.rules",
    "rule_sparql": "data/generated/rules/highrisk.sparql"
}

# Upload to object storage
updated_paths = await store.maybe_upload_artifact_paths(
    artifact_paths=artifact_paths,
    document_id="ABC123",
    job_id="batch_001"
)

# Updated paths contain MinIO URIs
print(updated_paths["rdf"])
# Output: minio://procurement-contracts/ingestion_artifacts/batch_001/ABC123/rdf/ABC123.ttl

# Local files optionally cleaned up if configured
# ARTIFACT_STORE_CLEANUP_LOCAL=true
```

**Performance:**
- Depends on number and size of files
- Uploads in sequence (not parallel)

---

## Artifact Retrieval

### get_all_rdf_files

```python
def get_all_rdf_files(self) -> list[Path]
```

List all generated RDF files.

**Returns:**

- **files** : `list[Path]`
  - List of RDF file paths, sorted by modification time (newest first)

**Example:**

```python
# Get all RDF files
rdf_files = store.get_all_rdf_files()

print(f"Found {len(rdf_files)} RDF files:")
for file_path in rdf_files[:5]:  # Show first 5
    print(f"  - {file_path.name}")
```

---

### get_all_ontology_files

```python
def get_all_ontology_files(self) -> list[Path]
```

List all generated ontology extension files.

**Returns:**

- **files** : `list[Path]`
  - List of ontology file paths, sorted by modification time (newest first)

---

### get_all_rule_files

```python
def get_all_rule_files(self) -> list[Path]
```

List all generated rule files.

**Returns:**

- **files** : `list[Path]`
  - List of rule file paths (both .rules and .sparql), sorted by modification time

---

### get_all_logs

```python
def get_all_logs(self) -> list[Path]
```

List all ingestion log files.

**Returns:**

- **files** : `list[Path]`
  - List of log file paths, sorted by modification time (newest first)

---

### get_document_artifacts

```python
def get_document_artifacts(
    self,
    document_id: str
) -> dict[str, list[Path]]
```

Get all artifacts for a specific document.

**Parameters:**

- **document_id** : `str`
  - Document identifier

**Returns:**

- **artifacts** : `dict[str, list[Path]]`
  - Dictionary with lists of artifact paths by type

**Example:**

```python
# Get all artifacts for a document
artifacts = store.get_document_artifacts("ABC123")

print(f"RDF files: {len(artifacts['rdf'])}")
print(f"Log files: {len(artifacts['logs'])}")

# Display artifacts
for rdf_file in artifacts['rdf']:
    print(f"  RDF: {rdf_file}")

for log_file in artifacts['logs']:
    print(f"  Log: {log_file}")
```

---

## Maintenance

### cleanup_old_artifacts

```python
def cleanup_old_artifacts(
    self,
    days: int = 30
) -> int
```

Remove artifacts older than specified days.

**Parameters:**

- **days** : `int`, default=`30`
  - Age threshold in days

**Returns:**

- **removed** : `int`
  - Number of files removed

**Example:**

```python
# Remove artifacts older than 30 days
removed = store.cleanup_old_artifacts(days=30)
print(f"Removed {removed} old artifacts")

# Remove artifacts older than 7 days
removed = store.cleanup_old_artifacts(days=7)
print(f"Removed {removed} artifacts from last week")

# Scheduled cleanup
import schedule

def cleanup_job():
    removed = store.cleanup_old_artifacts(days=30)
    logger.info(f"Cleanup: removed {removed} artifacts")

# Run daily at 2 AM
schedule.every().day.at("02:00").do(cleanup_job)
```

**Warning:**
- Deletion is permanent
- Use with caution in production
- Consider backup before cleanup

**Performance:**
- Depends on number of files
- Typical: 100-1000ms for 1000 files

---

### get_summary

```python
def get_summary(self) -> dict[str, Any]
```

Get summary of all stored artifacts.

**Returns:**

- **summary** : `dict[str, Any]`
  - Dictionary with artifact counts by type

**Example:**

```python
# Get summary
summary = store.get_summary()

print(f"Base directory: {summary['base_dir']}")
print(f"RDF files: {summary['rdf_files']}")
print(f"Ontology files: {summary['ontology_files']}")
print(f"Rule files: {summary['rule_files']}")
print(f"SPARQL files: {summary['sparql_files']}")
print(f"Log files: {summary['log_files']}")

# Output:
# Base directory: /app/data/generated
# RDF files: 234
# Ontology files: 12
# Rule files: 8
# SPARQL files: 8
# Log files: 234
```

---

## Usage Patterns

### Basic Ingestion Workflow

```python
from artifact_store import ArtifactStore
from config import get_settings
import asyncio

async def ingest_document(document_id: str, document_path: str):
    # Initialize
    settings = get_settings()
    store = ArtifactStore(settings=settings)
    
    # Process document (simplified)
    rdf_data = generate_rdf(document_path)
    clauses = extract_clauses(document_path)
    entities = extract_entities(document_path)
    
    # Save RDF
    rdf_path = await store.save_rdf(
        document_id=document_id,
        rdf_data=rdf_data,
        metadata={"source": document_path}
    )
    
    # Save extraction results
    extraction_path = await store.save_extraction_results(
        document_id=document_id,
        clauses=clauses,
        entities=entities,
        obligations=[],
        risks=[]
    )
    
    # Save ingestion log
    result = {
        "document_id": document_id,
        "status": "success",
        "clauses_extracted": len(clauses),
        "rdf_path": str(rdf_path),
        "extraction_path": str(extraction_path)
    }
    
    log_path = await store.save_ingestion_log(
        document_id=document_id,
        result=result
    )
    
    return result

# Run ingestion
result = asyncio.run(ingest_document("ABC123", "contract.pdf"))
print(f"Ingestion complete: {result}")
```

---

### Batch Ingestion with Object Storage

```python
async def batch_ingest(documents: list[tuple[str, str]], job_id: str):
    settings = get_settings()
    settings.artifact_store_backend = "object_storage"
    settings.artifact_store_cleanup_local = True
    
    store = ArtifactStore(settings=settings)
    
    for doc_id, doc_path in documents:
        # Process document
        rdf_data = generate_rdf(doc_path)
        
        # Save locally
        rdf_path = await store.save_rdf(doc_id, rdf_data)
        
        # Upload to object storage
        artifact_paths = {"rdf": str(rdf_path)}
        updated_paths = await store.maybe_upload_artifact_paths(
            artifact_paths=artifact_paths,
            document_id=doc_id,
            job_id=job_id
        )
        
        # Local file cleaned up automatically
        print(f"Uploaded: {updated_paths['rdf']}")

# Run batch
documents = [
    ("DOC001", "contract1.pdf"),
    ("DOC002", "contract2.pdf"),
    ("DOC003", "contract3.pdf")
]

asyncio.run(batch_ingest(documents, job_id="batch_20240110"))
```

---

### Artifact Analysis

```python
# Analyze stored artifacts
store = ArtifactStore()

# Get summary
summary = store.get_summary()
print(f"Total artifacts: {sum(summary.values()) - 1}")  # -1 for base_dir

# Analyze RDF files
rdf_files = store.get_all_rdf_files()
total_size = sum(f.stat().st_size for f in rdf_files)
print(f"RDF files: {len(rdf_files)}")
print(f"Total size: {total_size / (1024 * 1024):.2f} MB")

# Find recent files
from datetime import datetime, timedelta
recent_cutoff = datetime.now() - timedelta(days=7)

recent_files = [
    f for f in rdf_files
    if datetime.fromtimestamp(f.stat().st_mtime) > recent_cutoff
]

print(f"Recent files (last 7 days): {len(recent_files)}")

# Analyze by document
document_ids = set(f.stem.split('_')[0] for f in rdf_files)
print(f"Unique documents: {len(document_ids)}")
```

---

## Configuration

### Local Storage (Default)

```python
# .env file
ARTIFACT_STORE_BACKEND=local

# Usage
store = ArtifactStore()
# Artifacts stored in: agents/data/generated/
```

### Object Storage with Cleanup

```python
# .env file
ARTIFACT_STORE_BACKEND=object_storage
ARTIFACT_STORE_PREFIX=ingestion_artifacts
ARTIFACT_STORE_CLEANUP_LOCAL=true

OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts

# Usage
settings = get_settings()
store = ArtifactStore(settings=settings)

# Files uploaded to object storage and local copies deleted
```

---

## Best Practices

### 1. Use Async Methods

```python
# ❌ Synchronous (slower)
file_path = store.save_rdf_sync(doc_id, rdf_data)

# ✅ Asynchronous (faster)
file_path = await store.save_rdf(doc_id, rdf_data)
```

### 2. Include Metadata

```python
# ✅ Rich metadata
metadata = {
    "source": "contract.pdf",
    "clauses": 15,
    "entities": 8,
    "processing_time": 12.5,
    "version": "1.0"
}

await store.save_rdf(doc_id, rdf_data, metadata=metadata)
```

### 3. Use Object Storage for Production

```python
# Development: local storage
settings.artifact_store_backend = "local"

# Production: object storage with cleanup
settings.artifact_store_backend = "object_storage"
settings.artifact_store_cleanup_local = True
```

### 4. Regular Cleanup

```python
# Schedule regular cleanup
import schedule

def cleanup_job():
    removed = store.cleanup_old_artifacts(days=30)
    logger.info(f"Cleanup: {removed} files removed")

schedule.every().day.at("02:00").do(cleanup_job)
```

### 5. Monitor Storage Usage

```python
# Monitor storage
summary = store.get_summary()
total_files = sum(v for k, v in summary.items() if k != 'base_dir')

if total_files > 10000:
    logger.warning(f"High artifact count: {total_files}")
    # Consider cleanup or archival
```

---

## Troubleshooting

### Permission Errors

**Problem:** Cannot write to artifact directory

**Solutions:**
```bash
# Check permissions
ls -la agents/data/generated/

# Fix permissions
chmod -R 755 agents/data/generated/

# Or use custom directory
export ARTIFACT_BASE_DIR=/tmp/artifacts
```

### Object Storage Upload Failures

**Problem:** Files not uploading to object storage

**Solutions:**
```python
# 1. Verify configuration
settings = get_settings()
print(f"Backend: {settings.artifact_store_backend}")
print(f"Endpoint: {settings.object_storage_endpoint}")

# 2. Test object storage
from storage.object_storage import get_object_storage_from_config
storage = get_object_storage_from_config()
if storage:
    storage.ensure_bucket_exists()
    print("✅ Object storage working")
else:
    print("❌ Object storage not configured")

# 3. Check logs
# Look for "artifact_object_storage_init_failed" messages
```

### Disk Space Issues

**Problem:** Running out of disk space

**Solutions:**
```python
# 1. Enable cleanup
settings.artifact_store_cleanup_local = True

# 2. Run manual cleanup
removed = store.cleanup_old_artifacts(days=7)

# 3. Use object storage
settings.artifact_store_backend = "object_storage"
```

---

## Complete Example

```python
from artifact_store import ArtifactStore
from config import get_settings
import asyncio

async def complete_ingestion_workflow():
    # Initialize
    settings = get_settings()
    settings.artifact_store_backend = "object_storage"
    settings.artifact_store_cleanup_local = True
    
    store = ArtifactStore(settings=settings)
    
    # Document processing
    document_id = "ABC123"
    
    # 1. Save RDF
    rdf_data = """
    @prefix proc: <http://procurement.kg/ontology#> .
    contract:ABC123 a proc:Contract .
    """
    
    rdf_path = await store.save_rdf(
        document_id=document_id,
        rdf_data=rdf_data,
        metadata={"source": "contract.pdf", "clauses": 15}
    )
    
    # 2. Save ontology extension
    owl_path = await store.save_ontology_extension(
        name="DataProtectionClause",
        owl_data="...",
        description="New clause type"
    )
    
    # 3. Save rule
    jena_path, sparql_path = await store.save_rule(
        rule_name="HighRisk",
        jena_rule="...",
        sparql_rule="...",
        description="Risk detection rule"
    )
    
    # 4. Save extraction results
    extraction_path = await store.save_extraction_results(
        document_id=document_id,
        clauses=[{"id": "TERM_001", "type": "Termination"}],
        entities={"parties": ["Company A", "Company B"]},
        obligations=[],
        risks=[]
    )
    
    # 5. Upload to object storage
    artifact_paths = {
        "rdf": str(rdf_path),
        "owl": str(owl_path),
        "rule_jena": str(jena_path),
        "rule_sparql": str(sparql_path)
    }
    
    updated_paths = await store.maybe_upload_artifact_paths(
        artifact_paths=artifact_paths,
        document_id=document_id,
        job_id="batch_001"
    )
    
    # 6. Save ingestion log
    result = {
        "document_id": document_id,
        "status": "success",
        "artifacts": updated_paths,
        "clauses_extracted": 15
    }
    
    log_path = await store.save_ingestion_log(
        document_id=document_id,
        result=result
    )
    
    # 7. Get summary
    summary = store.get_summary()
    print(f"Artifacts stored: {summary}")
    
    return result

# Run workflow
result = asyncio.run(complete_ingestion_workflow())
print(f"✅ Ingestion complete: {result}")
```

---

## See Also

- **[Object Storage](../storage/object_storage_comprehensive.md)** - MinIO/IBM COS integration
- **[Configuration](config_comprehensive.md)** - Artifact store configuration
- **[Ingestion Agents](../agents/ingestion_comprehensive.md)** - Document ingestion pipeline