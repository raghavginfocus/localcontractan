# Object Storage API Reference

Comprehensive API documentation for S3-compatible object storage supporting MinIO and IBM Cloud Object Storage.

## Overview

The Object Storage module provides a unified interface for storing and retrieving files using the S3 API protocol. It supports both MinIO (local development) and IBM Cloud Object Storage (production), enabling seamless switching between providers through configuration.

**Key Features:**
- S3-compatible API (MinIO, IBM COS)
- Unified interface for multiple providers
- Bucket management with auto-creation
- Upload/download with content type support
- Object metadata retrieval
- Prefix-based listing
- Lazy client initialization
- Configuration-based setup

---

## S3CompatibleStorage

Main class for S3-compatible object storage operations.

### Class Definition

```python
from storage.object_storage import S3CompatibleStorage

class S3CompatibleStorage:
    """
    Object storage for MinIO and IBM COS (S3 API protocol).

    Configure via:
    - OBJECT_STORAGE_ENDPOINT: e.g. http://minio:9000 (MinIO) or
      https://s3.us-south.cloud-object-storage.appdomain.cloud (IBM COS)
    - OBJECT_STORAGE_ACCESS_KEY, OBJECT_STORAGE_SECRET_KEY
    - OBJECT_STORAGE_BUCKET
    - OBJECT_STORAGE_REGION: for IBM COS; MinIO typically uses us-east-1
    """
```

### Constructor

```python
def __init__(
    self,
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "us-east-1"
)
```

Initialize S3-compatible storage client.

**Parameters:**

- **endpoint_url** : `str`
  - S3 endpoint URL
  - MinIO: `http://minio:9000`
  - IBM COS: `https://s3.{region}.cloud-object-storage.appdomain.cloud`
  
- **access_key** : `str`
  - S3 access key ID
  - MinIO default: `minioadmin`
  - IBM COS: HMAC credentials access key
  
- **secret_key** : `str`
  - S3 secret access key
  - MinIO default: `minioadmin`
  - IBM COS: HMAC credentials secret key
  
- **bucket** : `str`
  - Bucket name for storing objects
  - Must be globally unique for IBM COS
  
- **region** : `str`, default=`"us-east-1"`
  - AWS region identifier
  - MinIO: typically `us-east-1`
  - IBM COS: e.g., `us-south`, `eu-gb`, `ap-tokyo`

**Example:**

```python
from storage.object_storage import S3CompatibleStorage

# MinIO (local development)
storage = S3CompatibleStorage(
    endpoint_url="http://minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    bucket="procurement-contracts",
    region="us-east-1"
)

# IBM Cloud Object Storage (production)
storage = S3CompatibleStorage(
    endpoint_url="https://s3.us-south.cloud-object-storage.appdomain.cloud",
    access_key="your_access_key",
    secret_key="your_secret_key",
    bucket="my-contracts-bucket",
    region="us-south"
)

# Ensure bucket exists
storage.ensure_bucket_exists()
```

**Performance:**
- Initialization: ~10ms (lazy client creation)
- First operation: +100-500ms (client initialization)
- Subsequent operations: Fast (client reused)

---

## Bucket Management

### ensure_bucket_exists

```python
def ensure_bucket_exists(self) -> None
```

Create bucket if it does not exist.

**Returns:**

- None

**Raises:**

- **Exception**
  - If bucket creation fails due to permissions or other errors

**Example:**

```python
# Create bucket if needed
storage.ensure_bucket_exists()

# Safe to call multiple times
storage.ensure_bucket_exists()  # No-op if exists
```

**Use Cases:**
- Application startup initialization
- Automated deployment scripts
- Testing setup

**Performance:**
- Bucket exists: 50-100ms (HEAD request)
- Bucket creation: 200-500ms

---

## Upload Operations

### upload

```python
def upload(
    self,
    key: str,
    data: bytes | IO[bytes],
    content_type: str = "application/octet-stream"
) -> str
```

Upload data to object storage.

**Parameters:**

- **key** : `str`
  - Object key (path) in bucket
  - Can include prefixes: `"artifacts/doc_001.ttl"`
  
- **data** : `bytes | IO[bytes]`
  - Data to upload as bytes or file-like object
  - File objects are read completely
  
- **content_type** : `str`, default=`"application/octet-stream"`
  - MIME type of the content
  - Common types: `text/turtle`, `application/json`, `application/pdf`

**Returns:**

- **key** : `str`
  - The object key (same as input)

**Example:**

```python
# Upload bytes
data = b"RDF data content"
key = storage.upload(
    key="rdf/contract_001.ttl",
    data=data,
    content_type="text/turtle"
)

print(f"Uploaded to: {key}")

# Upload from file
with open("contract.pdf", "rb") as f:
    key = storage.upload(
        key="documents/contract_001.pdf",
        data=f,
        content_type="application/pdf"
    )

# Upload JSON
import json
data = json.dumps({"contract_id": "ABC123"}).encode()
storage.upload(
    key="metadata/contract_001.json",
    data=data,
    content_type="application/json"
)
```

**Content Type Examples:**

| File Type | Content Type |
|-----------|-------------|
| Turtle RDF | text/turtle |
| JSON | application/json |
| PDF | application/pdf |
| DOCX | application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| Text | text/plain |
| SPARQL | application/sparql-query |
| Binary | application/octet-stream |

**Performance:**
- Small files (<1MB): 100-300ms
- Medium files (1-10MB): 500-2000ms
- Large files (>10MB): 2-10 seconds

---

## Download Operations

### download

```python
def download(
    self,
    key: str
) -> bytes
```

Download object content from storage.

**Parameters:**

- **key** : `str`
  - Object key to download

**Returns:**

- **data** : `bytes`
  - Object content as bytes

**Raises:**

- **Exception**
  - If object does not exist or download fails

**Example:**

```python
# Download file
data = storage.download("rdf/contract_001.ttl")
print(f"Downloaded {len(data)} bytes")

# Save to file
with open("local_copy.ttl", "wb") as f:
    f.write(data)

# Download and parse JSON
import json
data = storage.download("metadata/contract_001.json")
metadata = json.loads(data.decode())
print(f"Contract ID: {metadata['contract_id']}")

# Download and parse RDF
from rdflib import Graph
data = storage.download("rdf/contract_001.ttl")
graph = Graph()
graph.parse(data=data.decode(), format="turtle")
print(f"Loaded {len(graph)} triples")
```

**Error Handling:**

```python
try:
    data = storage.download("nonexistent.txt")
except Exception as e:
    print(f"Download failed: {e}")
    # Handle missing file
```

**Performance:**
- Small files (<1MB): 100-300ms
- Medium files (1-10MB): 500-2000ms
- Large files (>10MB): 2-10 seconds

---

## Object Operations

### exists

```python
def exists(
    self,
    key: str
) -> bool
```

Check if object exists in storage.

**Parameters:**

- **key** : `str`
  - Object key to check

**Returns:**

- **exists** : `bool`
  - True if object exists, False otherwise

**Example:**

```python
# Check before download
if storage.exists("rdf/contract_001.ttl"):
    data = storage.download("rdf/contract_001.ttl")
    print("File exists and downloaded")
else:
    print("File not found")

# Conditional upload
key = "artifacts/new_file.json"
if not storage.exists(key):
    storage.upload(key, data, "application/json")
    print("File uploaded")
else:
    print("File already exists, skipping upload")
```

**Performance:**
- Execution time: 50-150ms (HEAD request)

---

### delete

```python
def delete(
    self,
    key: str
) -> None
```

Delete object from storage.

**Parameters:**

- **key** : `str`
  - Object key to delete

**Returns:**

- None

**Example:**

```python
# Delete single file
storage.delete("rdf/old_contract.ttl")
print("File deleted")

# Delete with confirmation
key = "important_file.json"
if storage.exists(key):
    confirm = input(f"Delete {key}? (yes/no): ")
    if confirm.lower() == "yes":
        storage.delete(key)
        print("Deleted")

# Batch delete
keys_to_delete = [
    "temp/file1.txt",
    "temp/file2.txt",
    "temp/file3.txt"
]

for key in keys_to_delete:
    try:
        storage.delete(key)
        print(f"Deleted: {key}")
    except Exception as e:
        print(f"Failed to delete {key}: {e}")
```

**Warning:**
- Deletion is permanent and cannot be undone
- No confirmation prompt
- Use with caution in production

**Performance:**
- Execution time: 100-300ms per object

---

### list_objects

```python
def list_objects(
    self,
    prefix: str
) -> list[str]
```

List object keys with given prefix.

**Parameters:**

- **prefix** : `str`
  - Prefix to filter objects
  - Empty string lists all objects
  - Use "/" for directory-like structure

**Returns:**

- **keys** : `list[str]`
  - List of object keys matching prefix

**Example:**

```python
# List all RDF files
rdf_files = storage.list_objects("rdf/")
print(f"Found {len(rdf_files)} RDF files:")
for key in rdf_files:
    print(f"  - {key}")

# List all objects
all_objects = storage.list_objects("")
print(f"Total objects: {len(all_objects)}")

# List by date prefix
files_2024 = storage.list_objects("artifacts/2024/")

# Count files by type
json_files = [k for k in all_objects if k.endswith(".json")]
ttl_files = [k for k in all_objects if k.endswith(".ttl")]
print(f"JSON files: {len(json_files)}")
print(f"Turtle files: {len(ttl_files)}")
```

**Pagination:**

```python
# For large buckets, results are automatically paginated
# All pages are fetched and combined
all_keys = storage.list_objects("artifacts/")
print(f"Total keys: {len(all_keys)}")
```

**Performance:**
- Small buckets (<1000 objects): 100-500ms
- Medium buckets (1000-10000 objects): 500-2000ms
- Large buckets (>10000 objects): 2-10 seconds

---

### get_object_metadata

```python
def get_object_metadata(
    self,
    key: str
) -> dict[str, str]
```

Return lightweight object metadata without downloading the object.

**Parameters:**

- **key** : `str`
  - Object key

**Returns:**

- **metadata** : `dict[str, str]`
  - Dictionary with keys:
    - `etag`: ETag (content hash)
    - `size`: Object size in bytes
    - `last_modified`: Last modification timestamp

**Example:**

```python
# Get metadata
metadata = storage.get_object_metadata("rdf/contract_001.ttl")

print(f"ETag: {metadata['etag']}")
print(f"Size: {metadata['size']} bytes")
print(f"Last Modified: {metadata['last_modified']}")

# Check file size before download
metadata = storage.get_object_metadata("large_file.pdf")
size_mb = int(metadata['size']) / (1024 * 1024)

if size_mb > 100:
    print(f"Warning: Large file ({size_mb:.1f} MB)")
    confirm = input("Download anyway? (yes/no): ")
    if confirm.lower() != "yes":
        print("Download cancelled")
        exit()

data = storage.download("large_file.pdf")
```

**Use Cases:**
- Check file size before download
- Verify file existence and properties
- Compare ETags for change detection
- List files with metadata

**Performance:**
- Execution time: 50-150ms (HEAD request)

---

## Factory Functions

### create_object_storage

```python
def create_object_storage(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    region: str = "us-east-1"
) -> ObjectStorageBackend
```

Create object storage client (MinIO / IBM COS).

**Parameters:**

- Same as `S3CompatibleStorage.__init__`

**Returns:**

- **storage** : `ObjectStorageBackend`
  - Storage client implementing the protocol

**Example:**

```python
from storage.object_storage import create_object_storage

# Create storage
storage = create_object_storage(
    endpoint_url="http://minio:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    bucket="my-bucket",
    region="us-east-1"
)

# Use storage
storage.ensure_bucket_exists()
storage.upload("test.txt", b"Hello", "text/plain")
```

---

### get_object_storage_from_config

```python
def get_object_storage_from_config() -> ObjectStorageBackend | None
```

Create object storage from application config.

**Returns:**

- **storage** : `ObjectStorageBackend | None`
  - Storage client if configured, None otherwise

**Example:**

```python
from storage.object_storage import get_object_storage_from_config

# Get storage from config
storage = get_object_storage_from_config()

if storage:
    print("✅ Object storage configured")
    storage.upload("test.txt", b"Hello", "text/plain")
else:
    print("❌ Object storage not configured")
    # Fall back to local storage
```

**Configuration:**

```python
# .env file
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1
```

---

## Usage Patterns

### Basic Upload/Download

```python
from storage.object_storage import get_object_storage_from_config

# Initialize
storage = get_object_storage_from_config()
if not storage:
    raise ValueError("Object storage not configured")

storage.ensure_bucket_exists()

# Upload
data = b"Contract RDF data"
storage.upload(
    key="contracts/ABC123.ttl",
    data=data,
    content_type="text/turtle"
)

# Download
downloaded = storage.download("contracts/ABC123.ttl")
assert downloaded == data
```

### File Management

```python
# List all contracts
contracts = storage.list_objects("contracts/")
print(f"Found {len(contracts)} contracts")

# Get metadata for each
for key in contracts:
    metadata = storage.get_object_metadata(key)
    size_kb = int(metadata['size']) / 1024
    print(f"{key}: {size_kb:.1f} KB")

# Delete old contracts
for key in contracts:
    if "2023" in key:  # Example: delete 2023 contracts
        storage.delete(key)
        print(f"Deleted: {key}")
```

### Artifact Storage

```python
# Upload generated artifacts
artifacts = {
    "rdf": "contract_001.ttl",
    "owl": "extensions.owl",
    "rules": "inference.rules"
}

for artifact_type, filename in artifacts.items():
    with open(filename, "rb") as f:
        key = f"artifacts/{artifact_type}/{filename}"
        storage.upload(key, f, "text/turtle")
        print(f"Uploaded: {key}")

# List all artifacts
all_artifacts = storage.list_objects("artifacts/")
print(f"Total artifacts: {len(all_artifacts)}")
```

### Backup and Restore

```python
# Backup: Download all objects
backup_dir = Path("backup")
backup_dir.mkdir(exist_ok=True)

all_keys = storage.list_objects("")
for key in all_keys:
    data = storage.download(key)
    
    # Create local directory structure
    local_path = backup_dir / key
    local_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save file
    with open(local_path, "wb") as f:
        f.write(data)
    
    print(f"Backed up: {key}")

# Restore: Upload all files
for file_path in backup_dir.rglob("*"):
    if file_path.is_file():
        key = str(file_path.relative_to(backup_dir))
        
        with open(file_path, "rb") as f:
            storage.upload(key, f)
        
        print(f"Restored: {key}")
```

---

## Provider-Specific Configuration

### MinIO (Local Development)

```python
# .env file
OBJECT_STORAGE_ENDPOINT=http://minio:9000
OBJECT_STORAGE_ACCESS_KEY=minioadmin
OBJECT_STORAGE_SECRET_KEY=minioadmin
OBJECT_STORAGE_BUCKET=procurement-contracts
OBJECT_STORAGE_REGION=us-east-1

# Docker Compose
services:
  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data
```

**MinIO Console:**
- URL: http://localhost:9001
- Username: minioadmin
- Password: minioadmin

---

### IBM Cloud Object Storage (Production)

```python
# .env file
OBJECT_STORAGE_ENDPOINT=https://s3.us-south.cloud-object-storage.appdomain.cloud
OBJECT_STORAGE_ACCESS_KEY=your_hmac_access_key
OBJECT_STORAGE_SECRET_KEY=your_hmac_secret_key
OBJECT_STORAGE_BUCKET=my-contracts-bucket
OBJECT_STORAGE_REGION=us-south
```

**Setup Steps:**

1. Create IBM COS instance
2. Create bucket with unique name
3. Generate HMAC credentials
4. Configure endpoint for region

**Regions:**

| Region | Endpoint |
|--------|----------|
| US South | s3.us-south.cloud-object-storage.appdomain.cloud |
| US East | s3.us-east.cloud-object-storage.appdomain.cloud |
| EU GB | s3.eu-gb.cloud-object-storage.appdomain.cloud |
| EU DE | s3.eu-de.cloud-object-storage.appdomain.cloud |
| AP Tokyo | s3.jp-tok.cloud-object-storage.appdomain.cloud |

---

## Best Practices

### 1. Use Meaningful Key Prefixes

```python
# ❌ Flat structure
storage.upload("file1.ttl", data)
storage.upload("file2.ttl", data)

# ✅ Organized structure
storage.upload("contracts/2024/01/ABC123.ttl", data)
storage.upload("artifacts/rdf/ABC123.ttl", data)
storage.upload("metadata/ABC123.json", data)
```

### 2. Set Appropriate Content Types

```python
# ❌ Generic content type
storage.upload("data.ttl", data, "application/octet-stream")

# ✅ Specific content type
storage.upload("data.ttl", data, "text/turtle")
```

### 3. Handle Errors Gracefully

```python
try:
    data = storage.download("important.json")
except Exception as e:
    logger.error(f"Download failed: {e}")
    # Fallback or retry logic
    data = None
```

### 4. Check Existence Before Operations

```python
# Avoid unnecessary uploads
if not storage.exists(key):
    storage.upload(key, data)
else:
    logger.info(f"File already exists: {key}")
```

### 5. Use Batch Operations Efficiently

```python
# ❌ Many small operations
for i in range(1000):
    storage.upload(f"file_{i}.txt", b"data")

# ✅ Batch with progress
from tqdm import tqdm

files = [(f"file_{i}.txt", b"data") for i in range(1000)]

for key, data in tqdm(files, desc="Uploading"):
    storage.upload(key, data)
```

---

## Troubleshooting

### Connection Errors

**Problem:** Cannot connect to storage

**Solutions:**
```python
# 1. Check endpoint
print(f"Endpoint: {storage.endpoint_url}")

# 2. Verify network connectivity
import requests
try:
    response = requests.get(storage.endpoint_url)
    print(f"Status: {response.status_code}")
except Exception as e:
    print(f"Connection failed: {e}")

# 3. Check credentials
print(f"Access Key: {storage.access_key[:5]}...")
```

### Permission Errors

**Problem:** Access denied errors

**Solutions:**
```python
# 1. Verify credentials are correct
# 2. Check bucket permissions
# 3. For IBM COS, ensure HMAC credentials have proper IAM roles
```

### Bucket Not Found

**Problem:** Bucket does not exist

**Solutions:**
```python
# Create bucket
storage.ensure_bucket_exists()

# Verify bucket name
print(f"Bucket: {storage.bucket}")
```

---

## Performance Optimization

### Parallel Uploads

```python
from concurrent.futures import ThreadPoolExecutor

files = [
    ("file1.txt", b"data1"),
    ("file2.txt", b"data2"),
    ("file3.txt", b"data3")
]

def upload_file(key, data):
    storage.upload(key, data)
    return key

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(upload_file, k, d) for k, d in files]
    results = [f.result() for f in futures]

print(f"Uploaded {len(results)} files")
```

### Streaming Large Files

```python
# For very large files, use streaming
import io

# Create file-like object
large_data = b"x" * (100 * 1024 * 1024)  # 100 MB
stream = io.BytesIO(large_data)

# Upload stream
storage.upload("large_file.bin", stream)
```

---

## Complete Example

```python
from storage.object_storage import get_object_storage_from_config
from pathlib import Path
import json

# Initialize
storage = get_object_storage_from_config()
if not storage:
    raise ValueError("Object storage not configured")

storage.ensure_bucket_exists()

# Upload artifacts
artifacts_dir = Path("generated/artifacts")
uploaded_count = 0

for file_path in artifacts_dir.rglob("*"):
    if file_path.is_file():
        # Determine content type
        suffix = file_path.suffix.lower()
        content_type_map = {
            ".ttl": "text/turtle",
            ".json": "application/json",
            ".rules": "text/plain",
            ".sparql": "application/sparql-query"
        }
        content_type = content_type_map.get(suffix, "application/octet-stream")
        
        # Create key
        key = f"artifacts/{file_path.relative_to(artifacts_dir)}"
        
        # Upload
        with open(file_path, "rb") as f:
            storage.upload(key, f, content_type)
        
        uploaded_count += 1
        print(f"Uploaded: {key}")

print(f"\n✅ Uploaded {uploaded_count} artifacts")

# List and verify
all_artifacts = storage.list_objects("artifacts/")
print(f"Total artifacts in storage: {len(all_artifacts)}")

# Get metadata summary
total_size = 0
for key in all_artifacts:
    metadata = storage.get_object_metadata(key)
    total_size += int(metadata['size'])

print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
```

---

## See Also

- **[Configuration](../core/config_comprehensive.md)** - Object storage configuration
- **[Artifact Store](../core/artifact_store_comprehensive.md)** - Artifact management with object storage
- **[Ingestion Agents](../agents/ingestion_comprehensive.md)** - Document ingestion pipeline