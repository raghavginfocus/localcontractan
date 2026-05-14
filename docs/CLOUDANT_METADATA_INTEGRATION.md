# CloudAnt Metadata Integration - Code Changes Summary

## Overview
This document details all code changes made to integrate CloudAnt metadata from `cached_view.json` into the ingestion pipeline. The solution is **generic** and works with ANY metadata structure without hardcoding specific field names.

## Problem Statement
During the ingestion pipeline, documents are processed but their CloudAnt metadata (supplier name, contract type, parent contract relationships, etc.) was not being captured or used. This metadata is valuable for:
1. Enriching LLM extraction with additional context
2. Storing metadata as queryable RDF triples in the knowledge graph
3. Providing complete document information in ingestion results

## Solution Architecture

### Design Principles
1. **Generic Metadata Handling**: Accept any dict structure from `cached_view.json` without hardcoding field mappings
2. **Minimal Changes**: Add metadata support without disrupting existing pipeline
3. **Backward Compatible**: Metadata is optional (defaults to empty dict)
4. **Flow Through Pipeline**: Metadata available at all pipeline steps

### Data Flow
```
cached_view.json → load_cloudant_metadata() → ingest() → IngestionResult → Knowledge Graph
```

---

## Code Changes

### 1. IngestionResult Model Update
**File**: `agents/src/agents/ingestion/ingestion_orchestrator.py`

**Change**: Added `cloudant_metadata` field to store document metadata

```python
class IngestionResult(BaseModel):
    """Result of the complete ingestion pipeline."""
    
    document_id: str = Field(description="ID of the ingested document")
    success: bool = Field(description="Whether ingestion completed successfully")
    steps: list[IngestionStep] = Field(default_factory=list, description="Details of each step")
    
    # CloudAnt metadata (NEW)
    cloudant_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="CloudAnt metadata for this document (all fields from cached_view.json)"
    )
    
    # ... rest of fields remain unchanged
```

**Why**: This field stores ALL metadata from CloudAnt for the document, making it available in the final ingestion result.

---

### 2. Load CloudAnt Metadata Function
**File**: `agents/src/api/ingestion_service.py`

**Change**: Added new function to load metadata for a specific document

```python
def load_cloudant_metadata(doc_path: str) -> dict[str, Any]:
    """
    Load CloudAnt metadata for a specific document from cached view.
    
    Returns complete metadata dict for the document, or empty dict if not found.
    This is a generic solution that works with ANY metadata structure.
    """
    if not os.path.exists(CACHE_FILE):
        logger.warning(f"Cache file not found: {CACHE_FILE}")
        return {}

    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # Search for the document in cached view
        for row in data.get("rows", []):
            for item in row.get("value", []):
                if item.get("Doc_Path") == doc_path:
                    # Return the complete item dict (all metadata fields)
                    logger.info(
                        f"Loaded CloudAnt metadata for document",
                        doc_path=doc_path,
                        metadata_fields=list(item.keys())
                    )
                    return item

        logger.warning(f"No CloudAnt metadata found for doc_path: {doc_path}")
        return {}

    except Exception as e:
        logger.error(f"Error loading CloudAnt metadata: {e}", exc_info=True)
        return {}
```

**Why**: 
- **Generic**: Returns the complete item dict without hardcoding field names
- **Safe**: Returns empty dict if file not found or document not in cache
- **Logged**: Tracks which metadata fields were loaded for debugging

**Example Return Value**:
```python
{
    "_id": "abc123",
    "Doc_Name": "contract.pdf",
    "Doc_Path": "suppliers/contract.pdf",
    "Supplier_Name": "Acme Corp",
    "Contract_Type": "MSA",
    "Parent_Contract_ID": "parent_123",
    # ... any other fields present in cached_view.json
}
```

---

### 3. Update Orchestrator ingest() Method Signature
**File**: `agents/src/agents/ingestion/ingestion_orchestrator.py`

**Change**: Added `cloudant_metadata` parameter to ingest() method

```python
async def ingest(
    self,
    file_path: str | None = None,
    text: str | None = None,
    document_id: str | None = None,
    override: bool = False,
    job_id: str | None = None,
    cloudant_metadata: dict[str, Any] | None = None,  # NEW PARAMETER
) -> IngestionResult:
    """
    Process a contract document through the full pipeline.
    
    Args:
        file_path: Path to the contract file
        text: Or raw text content
        document_id: Optional ID (auto-generated if not provided)
        override: If True, reprocess even if document was already processed
        job_id: Optional job ID for tracking
        cloudant_metadata: Optional CloudAnt metadata for this document (all fields)
        
    Returns:
        IngestionResult with complete status
    """
```

**Why**: Allows caller to pass metadata into the ingestion pipeline.

---

### 4. Store Metadata in Result
**File**: `agents/src/agents/ingestion/ingestion_orchestrator.py`

**Change**: Initialize IngestionResult with metadata

```python
result = IngestionResult(
    document_id=document_id,
    success=False,
    started_at=datetime.now(),
    cloudant_metadata=cloudant_metadata or {},  # NEW: Store metadata
)
```

**Why**: Ensures metadata is captured in the result from the start of ingestion.

---

### 5. Pass Metadata from Ingestion Service
**File**: `agents/src/api/ingestion_service.py`

**Change**: Load and pass metadata when calling orchestrator

```python
try:
    cos_obj = cos.get_object(Bucket=SOURCE_BUCKET, Key=doc_path)
    file_data = cos_obj["Body"].read()

    suffix = os.path.splitext(doc_path)[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    try:
        # Load CloudAnt metadata for this document (NEW)
        cloudant_metadata = load_cloudant_metadata(doc_path)
        
        result = await orchestrator.ingest(
            file_path=tmp_path,
            override=override,
            job_id=job_id,
            cloudant_metadata=cloudant_metadata,  # NEW: Pass metadata
        )
        results.append({
            "doc_id": doc_id,
            "Doc_Name": doc_name,
            "Doc_Path": doc_path,
            "status": "success",
            "ingestion_result": (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump") else result
            ),
        })
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

**Why**: This is where the metadata flows from CloudAnt cache into the ingestion pipeline.

---

## How It Works

### Step-by-Step Flow

1. **Document Processing Starts**
   - Ingestion service receives document from COS
   - Document has a `Doc_Path` (e.g., "suppliers/contract.pdf")

2. **Metadata Loading**
   - `load_cloudant_metadata(doc_path)` is called
   - Function searches `cached_view.json` for matching `Doc_Path`
   - Returns complete metadata dict for that document

3. **Metadata Passed to Orchestrator**
   - Metadata passed as parameter to `orchestrator.ingest()`
   - Orchestrator stores it in `IngestionResult.cloudant_metadata`

4. **Metadata Available Throughout Pipeline**
   - All pipeline steps can access `result.cloudant_metadata`
   - Can be used to enrich LLM prompts
   - Can be converted to RDF triples for knowledge graph

5. **Metadata in Final Result**
   - `IngestionResult` includes complete metadata
   - Returned to caller via API response
   - Available for downstream processing

---

## Example Usage

### Example cached_view.json Structure
```json
{
  "rows": [
    {
      "value": [
        {
          "_id": "doc123",
          "Doc_Name": "MSA_Agreement.pdf",
          "Doc_Path": "suppliers/acme/MSA_Agreement.pdf",
          "Supplier_Name": "Acme Corporation",
          "Contract_Type": "Master Service Agreement",
          "Parent_Contract_ID": "parent_456",
          "Effective_Date": "2024-01-01",
          "Expiry_Date": "2025-12-31",
          "Contract_Value": 1000000,
          "Currency": "USD"
        }
      ]
    }
  ]
}
```

### Example Ingestion Result
```json
{
  "document_id": "doc_abc123",
  "success": true,
  "cloudant_metadata": {
    "_id": "doc123",
    "Doc_Name": "MSA_Agreement.pdf",
    "Doc_Path": "suppliers/acme/MSA_Agreement.pdf",
    "Supplier_Name": "Acme Corporation",
    "Contract_Type": "Master Service Agreement",
    "Parent_Contract_ID": "parent_456",
    "Effective_Date": "2024-01-01",
    "Expiry_Date": "2025-12-31",
    "Contract_Value": 1000000,
    "Currency": "USD"
  },
  "clauses_extracted": 45,
  "entities_extracted": 23,
  "triples_generated": 156,
  "vectors_indexed": 45
}
```

---

## Benefits

### 1. Generic Solution
- Works with ANY metadata structure
- No hardcoded field names
- Easy to extend with new metadata fields

### 2. Enriched Extraction
- LLM can use metadata as context
- Example: "This is a Master Service Agreement with Acme Corporation"
- Improves extraction accuracy

### 3. Queryable Metadata
- Metadata can be converted to RDF triples
- Example queries:
  - "Find all contracts with Acme Corporation"
  - "Show contracts expiring in 2025"
  - "List all Master Service Agreements"

### 4. Complete Audit Trail
- Every ingestion result includes source metadata
- Traceability from CloudAnt to knowledge graph
- Debugging and compliance support

---

## Future Enhancements

### 1. Use Metadata in LLM Prompts
**Location**: `agents/src/agents/ingestion/clause_extraction.py`

```python
# Add metadata context to extraction prompt
metadata_context = ""
if result.cloudant_metadata:
    supplier = result.cloudant_metadata.get("Supplier_Name", "Unknown")
    contract_type = result.cloudant_metadata.get("Contract_Type", "Unknown")
    metadata_context = f"\nDocument Metadata:\n- Supplier: {supplier}\n- Type: {contract_type}\n"

prompt = f"""Extract clauses from this contract.
{metadata_context}
Contract Text:
{doc_text}
"""
```

### 2. Generate RDF Triples from Metadata
**Location**: `agents/src/agents/ingestion/rdf_generator.py`

```python
def generate_metadata_triples(document_id: str, metadata: dict) -> list:
    """Convert CloudAnt metadata to RDF triples."""
    triples = []
    
    for key, value in metadata.items():
        if key.startswith("_"):
            continue  # Skip internal fields
        
        predicate = f"contract:{key}"
        triples.append((
            f"contract:{document_id}",
            predicate,
            value
        ))
    
    return triples
```

### 3. Metadata-Based Validation
**Location**: `agents/src/agents/ingestion/validation_agent.py`

```python
def validate_against_metadata(clauses: list, metadata: dict):
    """Validate extracted data against CloudAnt metadata."""
    
    # Example: Check if extracted parties match metadata
    if "Supplier_Name" in metadata:
        expected_party = metadata["Supplier_Name"]
        extracted_parties = [c.parties for c in clauses]
        
        if expected_party not in extracted_parties:
            return ValidationWarning(
                f"Expected party '{expected_party}' not found in extracted clauses"
            )
```

---

## Testing

### Test Metadata Loading
```python
from api.ingestion_service import load_cloudant_metadata

# Test with valid document
metadata = load_cloudant_metadata("suppliers/acme/contract.pdf")
assert "Supplier_Name" in metadata
assert metadata["Doc_Path"] == "suppliers/acme/contract.pdf"

# Test with non-existent document
metadata = load_cloudant_metadata("nonexistent.pdf")
assert metadata == {}
```

### Test Ingestion with Metadata
```python
from agents.ingestion.ingestion_orchestrator import IngestionOrchestrator

orchestrator = IngestionOrchestrator()

metadata = {
    "Supplier_Name": "Test Corp",
    "Contract_Type": "MSA"
}

result = await orchestrator.ingest(
    file_path="test_contract.pdf",
    cloudant_metadata=metadata
)

assert result.cloudant_metadata == metadata
assert result.success == True
```

---

## Summary

### Files Modified
1. `agents/src/agents/ingestion/ingestion_orchestrator.py`
   - Added `cloudant_metadata` field to `IngestionResult`
   - Added `cloudant_metadata` parameter to `ingest()` method
   - Store metadata in result initialization

2. `agents/src/api/ingestion_service.py`
   - Added `load_cloudant_metadata()` function
   - Updated `run_cloudant_cache_pipeline_job()` to load and pass metadata

### Key Features
- ✅ Generic solution (works with any metadata structure)
- ✅ Backward compatible (metadata optional)
- ✅ Minimal code changes
- ✅ Metadata flows through entire pipeline
- ✅ Available in final ingestion result
- ✅ Ready for LLM enrichment and RDF generation

### Next Steps
1. Rebuild Docker image with changes
2. Deploy to OpenShift
3. Test with real documents
4. Verify metadata appears in results
5. Implement LLM prompt enrichment (optional)
6. Implement RDF triple generation from metadata (optional)

---

## Questions?

For questions or issues, refer to:
- Main documentation: `docs/index.md`
- Ingestion pipeline: `docs/api/agents/ingestion.md`
- API reference: `docs/api/index.md`