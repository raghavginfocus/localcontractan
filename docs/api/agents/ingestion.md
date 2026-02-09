# Ingestion Agents API Reference

Complete API reference for document ingestion agents with examples.

---

## EnhancedDocumentIngestionAgent

Extract text and metadata from various document formats.

### Class Definition

```python
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

agent = EnhancedDocumentIngestionAgent(settings=get_settings())
```

### Supported Formats

| Format | Extensions | Features |
|--------|-----------|----------|
| PDF | `.pdf` | Text extraction, page count, metadata |
| Word | `.docx` | Text, tables, metadata |
| Excel | `.xlsx`, `.xls` | All sheets, cell values |
| Email | `.eml` | Subject, body, attachments |

### Methods

#### `process(file_path: str | Path) -> ExtractedDocument`

Extract content from a document file.

**Parameters:**

- `file_path` (str | Path): Path to the document file

**Returns:**

- `ExtractedDocument`: Object containing extracted text and metadata

**Example:**

```python
from pathlib import Path
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

# Initialize agent
agent = EnhancedDocumentIngestionAgent(settings=get_settings())

# Extract from PDF
result = await agent.process("contracts/agreement.pdf")

print(f"Document ID: {result.document_id}")
print(f"Filename: {result.filename}")
print(f"Pages: {result.page_count}")
print(f"Text length: {len(result.text)} characters")
print(f"Confidence: {result.confidence}")
print(f"Method: {result.extraction_method}")
```

**Output:**

```
Document ID: 8f3a9b2c1d4e5f6a
Filename: agreement.pdf
Pages: 15
Text length: 12450 characters
Confidence: 0.95
Method: pdfplumber
```

### ExtractedDocument Model

```python
class ExtractedDocument(BaseModel):
    document_id: str          # Unique identifier (SHA-256 hash)
    filename: str             # Original filename
    text: str                 # Extracted text content
    page_count: int          # Number of pages (default: 1)
    metadata: dict           # Document metadata
    extraction_method: str   # Method used (pdfplumber, docx, etc.)
    confidence: float        # Extraction quality (0.0-1.0)
```

### Complete Example

```python
import asyncio
from pathlib import Path
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

async def extract_documents():
    agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    
    # Process multiple documents
    files = [
        "contracts/master_agreement.pdf",
        "contracts/amendment_001.docx",
        "contracts/pricing_sheet.xlsx",
        "contracts/approval_email.eml"
    ]
    
    results = []
    for file_path in files:
        try:
            result = await agent.process(file_path)
            results.append({
                "file": result.filename,
                "success": True,
                "text_length": len(result.text),
                "confidence": result.confidence
            })
        except Exception as e:
            results.append({
                "file": Path(file_path).name,
                "success": False,
                "error": str(e)
            })
    
    return results

# Run extraction
results = asyncio.run(extract_documents())
for r in results:
    print(r)
```

---

## DirectoryScannerAgent

Recursively discover and classify contract documents in a directory.

### Class Definition

```python
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from config import get_settings

agent = DirectoryScannerAgent(settings=get_settings())
```

### Methods

#### `process(directory: str | Path) -> ScanResult`

Scan directory for contract documents.

**Parameters:**

- `directory` (str | Path): Root directory to scan

**Returns:**

- `ScanResult`: Object containing discovered files and statistics

**Example:**

```python
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from config import get_settings

# Initialize agent
agent = DirectoryScannerAgent(settings=get_settings())

# Scan directory
result = await agent.process("examples/contracts")

print(f"Total files: {result.total_files}")
print(f"Supported: {result.supported_files}")
print(f"Unsupported: {result.unsupported_files}")
print(f"\nBy type: {result.files_by_type}")
print(f"By supplier: {result.files_by_supplier}")
```

**Output:**

```
Total files: 127
Supported: 115
Unsupported: 12

By type: {'contract': 45, 'amendment': 23, 'attachment': 47}
By supplier: {'Adobe': 15, 'Salesforce': 28, 'George P Johnson': 72}
```

### File Classification

The agent automatically classifies files based on:

- **Filename patterns**: "amendment", "attachment", "terms", etc.
- **Directory structure**: parent_contracts/, child_contracts/
- **File extensions**: .pdf, .docx, .xlsx, .eml
- **LLM classification** (optional): Uses LLM for ambiguous cases

### DiscoveredFile Model

```python
@dataclass
class DiscoveredFile:
    path: Path                    # Full file path
    filename: str                 # Filename only
    extension: str                # File extension
    size_bytes: int              # File size
    document_type: DocumentType  # contract, amendment, etc.
    category: FileCategory       # primary, secondary, reference
    supplier: Optional[str]      # Detected supplier name
    batch_id: Optional[str]      # Batch identifier
    parent_path: Optional[Path]  # Parent contract path
```

### Complete Example

```python
import asyncio
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from config import get_settings

async def scan_and_filter():
    agent = DirectoryScannerAgent(settings=get_settings())
    
    # Scan directory
    result = await agent.process("examples/contracts")
    
    # Filter by type
    contracts = [f for f in result.discovered_files 
                 if f.document_type.value == "contract"]
    
    amendments = [f for f in result.discovered_files 
                  if f.document_type.value == "amendment"]
    
    # Filter by supplier
    adobe_files = [f for f in result.discovered_files 
                   if f.supplier == "Adobe"]
    
    print(f"Contracts: {len(contracts)}")
    print(f"Amendments: {len(amendments)}")
    print(f"Adobe files: {len(adobe_files)}")
    
    # Show first 5 contracts
    print("\nFirst 5 contracts:")
    for file in contracts[:5]:
        print(f"  - {file.filename} ({file.size_bytes} bytes)")

# Run scan
asyncio.run(scan_and_filter())
```

---

## BatchProcessorAgent

Process multiple documents in parallel with progress tracking.

### Class Definition

```python
from agents.ingestion.batch_processor import BatchProcessorAgent
from config import get_settings

agent = BatchProcessorAgent(
    settings=get_settings(),
    max_concurrent=3,    # Process 3 files at once
    max_retries=2        # Retry failed files twice
)
```

### Methods

#### `process(input_data: dict) -> BatchResult`

Process multiple files in parallel.

**Parameters:**

- `input_data` (dict): Dictionary with:
    - `files`: List of DiscoveredFile objects
    - `processor_fn`: Async function to process each file
    - `progress_callback`: Optional callback for progress updates

**Returns:**

- `BatchResult`: Object containing processing results and statistics

**Example:**

```python
from agents.ingestion.batch_processor import BatchProcessorAgent
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

async def process_file(discovered_file):
    """Process a single file"""
    doc_agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    result = await doc_agent.process(discovered_file.path)
    return {
        "file": discovered_file.filename,
        "success": True,
        "text_length": len(result.text)
    }

async def progress_callback(progress):
    """Track progress"""
    print(f"Progress: {progress.completed}/{progress.total_tasks} "
          f"({progress.progress_percent:.1f}%)")

async def batch_process():
    settings = get_settings()
    
    # Scan directory
    scanner = DirectoryScannerAgent(settings=settings)
    scan_result = await scanner.process("examples/contracts")
    
    # Process in batches
    batch_processor = BatchProcessorAgent(
        settings=settings,
        max_concurrent=3,
        max_retries=1
    )
    
    result = await batch_processor.process({
        "files": scan_result.discovered_files[:10],  # First 10 files
        "processor_fn": process_file,
        "progress_callback": progress_callback
    })
    
    print(f"\nBatch complete!")
    print(f"Total: {result.total_files}")
    print(f"Successful: {result.successful}")
    print(f"Failed: {result.failed}")
    print(f"Duration: {result.total_duration_ms:.0f}ms")

# Run batch processing
asyncio.run(batch_process())
```

**Output:**

```
Progress: 3/10 (30.0%)
Progress: 6/10 (60.0%)
Progress: 9/10 (90.0%)
Progress: 10/10 (100.0%)

Batch complete!
Total: 10
Successful: 9
Failed: 1
Duration: 15234ms
```

### BatchResult Model

```python
class BatchResult(BaseModel):
    total_files: int              # Total files processed
    successful: int               # Successfully processed
    failed: int                   # Failed to process
    skipped: int                  # Skipped files
    total_duration_ms: float      # Total processing time
    tasks: List[ProcessingTask]   # Individual task results
    errors: List[dict]            # Error details
```

---

## ClauseExtractionAgent

Extract and classify contract clauses using LLM.

### Class Definition

```python
from agents.ingestion.clause_extraction import ClauseExtractionAgent
from config import get_settings

agent = ClauseExtractionAgent(settings=get_settings())
```

### Methods

#### `process(input_data: dict) -> ClauseExtractionResult`

Extract clauses from contract text.

**Parameters:**

- `input_data` (dict): Dictionary with:
    - `document_id`: Document identifier
    - `text`: Contract text to analyze

**Returns:**

- `ClauseExtractionResult`: Object containing extracted clauses

**Example:**

```python
from agents.ingestion.clause_extraction import ClauseExtractionAgent
from config import get_settings

async def extract_clauses():
    agent = ClauseExtractionAgent(settings=get_settings())
    
    contract_text = """
    PAYMENT TERMS
    
    Payment shall be made within 30 days of invoice date.
    Late payments will incur a 2% monthly interest charge.
    
    LIABILITY
    
    The total liability under this agreement shall not exceed
    the total contract value paid in the preceding 12 months.
    """
    
    result = await agent.process({
        "document_id": "contract_001",
        "text": contract_text
    })
    
    print(f"Extracted {len(result.clauses)} clauses:")
    for clause in result.clauses:
        print(f"\n{clause.clause_type.upper()}")
        print(f"  Text: {clause.text[:100]}...")
        print(f"  Confidence: {clause.confidence}")
        print(f"  Risk: {clause.risk_level}")

# Run extraction
asyncio.run(extract_clauses())
```

**Output:**

```
Extracted 3 clauses:

PAYMENT
  Text: Payment shall be made within 30 days of invoice date...
  Confidence: 0.92
  Risk: low

PAYMENT
  Text: Late payments will incur a 2% monthly interest charge...
  Confidence: 0.88
  Risk: medium

LIABILITY
  Text: The total liability under this agreement shall not exceed...
  Confidence: 0.95
  Risk: high
```

### Clause Types

Supported clause types:

- `payment` - Payment terms and conditions
- `liability` - Liability and indemnification
- `termination` - Contract termination clauses
- `confidentiality` - Confidentiality and NDA terms
- `warranty` - Warranties and guarantees
- `intellectual_property` - IP rights and ownership
- `dispute_resolution` - Dispute resolution mechanisms
- `force_majeure` - Force majeure provisions
- `governing_law` - Governing law and jurisdiction

---

## Complete Pipeline Example

Putting it all together:

```python
import asyncio
from pathlib import Path
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from agents.ingestion.batch_processor import BatchProcessorAgent
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from agents.ingestion.clause_extraction import ClauseExtractionAgent
from config import get_settings

async def full_pipeline(directory: str):
    """Complete ingestion pipeline"""
    settings = get_settings()
    
    # Step 1: Scan directory
    print("Step 1: Scanning directory...")
    scanner = DirectoryScannerAgent(settings=settings)
    scan_result = await scanner.process(directory)
    print(f"  Found {scan_result.total_files} files")
    
    # Step 2: Extract documents
    print("\nStep 2: Extracting documents...")
    doc_agent = EnhancedDocumentIngestionAgent(settings=settings)
    
    async def extract_doc(file):
        return await doc_agent.process(file.path)
    
    batch_processor = BatchProcessorAgent(settings=settings, max_concurrent=3)
    extract_result = await batch_processor.process({
        "files": scan_result.discovered_files[:5],  # First 5 files
        "processor_fn": extract_doc
    })
    print(f"  Extracted {extract_result.successful} documents")
    
    # Step 3: Extract clauses
    print("\nStep 3: Extracting clauses...")
    clause_agent = ClauseExtractionAgent(settings=settings)
    
    total_clauses = 0
    for task in extract_result.tasks:
        if task.status == "completed" and task.result:
            doc = task.result
            clause_result = await clause_agent.process({
                "document_id": doc.document_id,
                "text": doc.text
            })
            total_clauses += len(clause_result.clauses)
    
    print(f"  Extracted {total_clauses} clauses")
    
    print("\n✓ Pipeline complete!")

# Run pipeline
asyncio.run(full_pipeline("examples/contracts"))
```

---

## Error Handling

All agents support comprehensive error handling:

```python
from agents.ingestion.enhanced_document_ingestion import EnhancedDocumentIngestionAgent
from config import get_settings

async def safe_extraction():
    agent = EnhancedDocumentIngestionAgent(settings=get_settings())
    
    try:
        result = await agent.process("contract.pdf")
        print(f"Success: {result.filename}")
    except FileNotFoundError:
        print("File not found")
    except ValueError as e:
        print(f"Invalid file format: {e}")
    except Exception as e:
        print(f"Extraction failed: {e}")

asyncio.run(safe_extraction())
```

---

## Performance Tips

### 1. Batch Processing

Process multiple files in parallel:

```python
# Good: Parallel processing
batch_processor = BatchProcessorAgent(max_concurrent=5)

# Avoid: Sequential processing
for file in files:
    await agent.process(file)  # Slow!
```

### 2. Disable LLM Classification

For faster scanning without LLM:

```python
scanner = DirectoryScannerAgent(settings=settings)
scanner.llm = None  # Disable LLM classification
result = await scanner.process(directory)
```

### 3. Limit File Size

Skip very large files:

```python
files = [f for f in scan_result.discovered_files 
         if f.size_bytes < 10_000_000]  # < 10MB
```

---

## See Also

- [Enhanced Ingestion Guide](../../guide/enhanced-ingestion.md)
- [Retrieval Agents API](retrieval.md)
- [Storage API](../storage/sparql.md)