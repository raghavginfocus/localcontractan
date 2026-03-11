"""
Document Registry - Tracks processed documents to prevent duplicate processing.

This module provides a scalable solution for tracking which documents have been
processed, preventing unnecessary reprocessing of the same documents.

For production with millions of documents:
- Uses Redis for fast O(1) lookups (recommended)
- Falls back to SQLite for development/small scale
- Can use Fuseki for metadata storage (alternative)

Features:
- Content-based duplicate detection (SHA256 hash)
- Processing status tracking
- Override flag for forced reprocessing
- Metadata storage (timestamp, document_id, status)
- Batch operations for efficiency
"""

import hashlib
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from logger import get_module_logger

logger = get_module_logger(__name__)


class ProcessingStatus(str, Enum):
    """Status of document processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentRecord:
    """Record of a processed document."""
    
    def __init__(
        self,
        content_hash: str,
        document_id: str,
        filename: str,
        status: ProcessingStatus,
        processed_at: datetime,
        metadata: dict[str, Any] | None = None,
    ):
        self.content_hash = content_hash
        self.document_id = document_id
        self.filename = filename
        self.status = status
        self.processed_at = processed_at
        self.metadata = metadata or {}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "content_hash": self.content_hash,
            "document_id": self.document_id,
            "filename": self.filename,
            "status": self.status.value,
            "processed_at": self.processed_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentRecord":
        """Create from dictionary."""
        return cls(
            content_hash=data["content_hash"],
            document_id=data["document_id"],
            filename=data["filename"],
            status=ProcessingStatus(data["status"]),
            processed_at=datetime.fromisoformat(data["processed_at"]),
            metadata=data.get("metadata", {}),
        )


class DocumentRegistry:
    """
    Registry for tracking processed documents.
    
    Supports multiple backends:
    - Redis (production, scalable)
    - SQLite (development, small scale)
    - Fuseki (alternative, uses existing infrastructure)
    """
    
    def __init__(
        self,
        backend: str = "sqlite",  # "redis", "sqlite", "fuseki"
        redis_url: str | None = None,
        db_path: Path | None = None,
        settings: Any = None,
    ):
        """
        Initialize document registry.
        
        Args:
            backend: Storage backend ("redis", "sqlite", "fuseki")
            redis_url: Redis connection URL (for redis backend)
            db_path: SQLite database path (for sqlite backend)
            settings: Settings object (for fuseki backend)
        """
        self.backend = backend.lower()
        self.settings = settings
        
        if self.backend == "redis":
            self._init_redis(redis_url)
        elif self.backend == "sqlite":
            self._init_sqlite(db_path)
        elif self.backend == "fuseki":
            self._init_fuseki()
        else:
            raise ValueError(f"Unknown backend: {backend}")
        
        logger.info(f"DocumentRegistry initialized with backend: {self.backend}")
    
    def _init_redis(self, redis_url: str | None):
        """Initialize Redis backend."""
        try:
            import redis
            self.redis_client = redis.from_url(
                redis_url or "redis://localhost:6379/0",
                decode_responses=True,
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis for document registry")
        except ImportError:
            raise ImportError("redis package required. Install with: pip install redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Falling back to SQLite.")
            self.backend = "sqlite"
            self._init_sqlite(None)
    
    def _init_sqlite(self, db_path: Path | None):
        """Initialize SQLite backend."""
        import sqlite3
        import os
        
        if db_path is None:
            # Detect if running in container or locally
            if os.path.exists("/app/checkpoints"):
                # Running in container
                db_path = Path("/app/checkpoints/document_registry.db")
            else:
                # Running locally - use relative path
                db_path = Path("agents/checkpoints/document_registry.db")
        
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        
        # Create table
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                content_hash TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                status TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_document_id ON documents(document_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON documents(status)
        """)
        conn.commit()
        conn.close()
        
        logger.info(f"SQLite registry initialized at: {db_path}")
    
    def _init_fuseki(self):
        """Initialize Fuseki backend (uses existing SPARQL store)."""
        from storage.sparql.factory import create_sparql_store
        
        if not self.settings:
            raise ValueError("Settings required for Fuseki backend")
        
        self.sparql_store = create_sparql_store(settings=self.settings)
        logger.info("Fuseki registry initialized")
    
    def compute_hash(self, file_path: Path | str) -> str:
        """
        Compute SHA256 hash of document content.
        
        Args:
            file_path: Path to document file
            
        Returns:
            SHA256 hash as hex string
        """
        hasher = hashlib.sha256()
        file_path = Path(file_path)
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()

    @staticmethod
    def compute_identity_hash(identity: str) -> str:
        """Compute SHA256 hash for a stable identity string (e.g., key+etag)."""
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    def register_by_hash(
        self,
        *,
        content_hash: str,
        filename: str,
        document_id: str,
        status: ProcessingStatus = ProcessingStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentRecord:
        """Register a processed document when you already have a hash."""
        record = DocumentRecord(
            content_hash=content_hash,
            document_id=document_id,
            filename=filename,
            status=status,
            processed_at=datetime.now(),
            metadata=metadata or {},
        )

        if self.backend == "redis":
            self.redis_client.set(
                f"doc:{content_hash}",
                json.dumps(record.to_dict()),
            )
            self.redis_client.set(f"docid:{document_id}", content_hash)

        elif self.backend == "sqlite":
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                (content_hash, document_id, filename, status, processed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    content_hash,
                    document_id,
                    filename,
                    status.value,
                    record.processed_at.isoformat(),
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
            conn.close()

        elif self.backend == "fuseki":
            update = f"""
            PREFIX reg: <http://procurement.kg/registry#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            INSERT DATA {{
                GRAPH <http://procurement.kg/registry#documents> {{
                    reg:doc_{content_hash[:16]}
                        reg:contentHash "{content_hash}" ;
                        reg:documentId "{document_id}" ;
                        reg:filename "{filename}" ;
                        reg:status "{status.value}" ;
                        reg:processedAt "{record.processed_at.isoformat()}"^^xsd:dateTime ;
                        reg:metadata "{json.dumps(metadata or {})}" .
                }}
            }}
            """
            self.sparql_store.execute_update(update)

        logger.info(
            "Registered document by hash",
            document_id=document_id,
            status=status.value,
            backend=self.backend,
        )
        return record
    
    def is_processed(
        self,
        file_path: Path | str | None = None,
        content_hash: str | None = None,
    ) -> tuple[bool, DocumentRecord | None]:
        """
        Check if document has been processed.
        
        Args:
            file_path: Path to document (if hash not provided)
            content_hash: Pre-computed hash (optional)
            
        Returns:
            Tuple of (is_processed, record_if_exists)
        """
        if not content_hash:
            if not file_path:
                raise ValueError("Either file_path or content_hash required")
            content_hash = self.compute_hash(file_path)
        
        if self.backend == "redis":
            data = self.redis_client.get(f"doc:{content_hash}")
            if data:
                record = DocumentRecord.from_dict(json.loads(data))
                return True, record
            return False, None
        
        elif self.backend == "sqlite":
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute(
                "SELECT document_id, filename, status, processed_at, metadata FROM documents WHERE content_hash = ?",
                (content_hash,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                record = DocumentRecord(
                    content_hash=content_hash,
                    document_id=row[0],
                    filename=row[1],
                    status=ProcessingStatus(row[2]),
                    processed_at=datetime.fromisoformat(row[3]),
                    metadata=json.loads(row[4]) if row[4] else {},
                )
                return True, record
            return False, None
        
        elif self.backend == "fuseki":
            query = f"""
            PREFIX reg: <http://procurement.kg/registry#>
            SELECT ?docId ?filename ?status ?processedAt ?metadata
            WHERE {{
                GRAPH <http://procurement.kg/registry#documents> {{
                    ?doc reg:contentHash "{content_hash}" ;
                         reg:documentId ?docId ;
                         reg:filename ?filename ;
                         reg:status ?status ;
                         reg:processedAt ?processedAt .
                    OPTIONAL {{ ?doc reg:metadata ?metadata }}
                }}
            }}
            """
            results = self.sparql_store.execute_select(query)
            if results:
                r = results[0]
                record = DocumentRecord(
                    content_hash=content_hash,
                    document_id=r["docId"]["value"],
                    filename=r["filename"]["value"],
                    status=ProcessingStatus(r["status"]["value"]),
                    processed_at=datetime.fromisoformat(r["processedAt"]["value"]),
                    metadata=json.loads(r.get("metadata", {}).get("value", "{}")),
                )
                return True, record
            return False, None
        
        return False, None
    
    def register(
        self,
        file_path: Path | str,
        document_id: str,
        status: ProcessingStatus = ProcessingStatus.COMPLETED,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentRecord:
        """
        Register a processed document.
        
        Args:
            file_path: Path to document file
            document_id: Document ID from pipeline
            status: Processing status
            metadata: Additional metadata
            
        Returns:
            DocumentRecord
        """
        file_path = Path(file_path)
        content_hash = self.compute_hash(file_path)
        
        record = DocumentRecord(
            content_hash=content_hash,
            document_id=document_id,
            filename=file_path.name,
            status=status,
            processed_at=datetime.now(),
            metadata=metadata or {},
        )
        
        if self.backend == "redis":
            self.redis_client.set(
                f"doc:{content_hash}",
                json.dumps(record.to_dict()),
            )
            # Also index by document_id for reverse lookup
            self.redis_client.set(f"docid:{document_id}", content_hash)
        
        elif self.backend == "sqlite":
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                INSERT OR REPLACE INTO documents 
                (content_hash, document_id, filename, status, processed_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    content_hash,
                    document_id,
                    file_path.name,
                    status.value,
                    record.processed_at.isoformat(),
                    json.dumps(metadata or {}),
                )
            )
            conn.commit()
            conn.close()
        
        elif self.backend == "fuseki":
            # Store in Fuseki as RDF
            update = f"""
            PREFIX reg: <http://procurement.kg/registry#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            INSERT DATA {{
                GRAPH <http://procurement.kg/registry#documents> {{
                    reg:doc_{content_hash[:16]} 
                        reg:contentHash "{content_hash}" ;
                        reg:documentId "{document_id}" ;
                        reg:filename "{file_path.name}" ;
                        reg:status "{status.value}" ;
                        reg:processedAt "{record.processed_at.isoformat()}"^^xsd:dateTime ;
                        reg:metadata "{json.dumps(metadata or {})}" .
                }}
            }}
            """
            self.sparql_store.execute_update(update)
        
        logger.info(
            f"Registered document: {file_path.name}",
            document_id=document_id,
            status=status.value,
            backend=self.backend,
        )
        
        return record
    
    def update_status(
        self,
        content_hash: str,
        status: ProcessingStatus,
        metadata: dict[str, Any] | None = None,
    ):
        """Update processing status of a document."""
        if self.backend == "redis":
            data = self.redis_client.get(f"doc:{content_hash}")
            if data:
                record_dict = json.loads(data)
                record_dict["status"] = status.value
                if metadata:
                    record_dict["metadata"].update(metadata)
                self.redis_client.set(f"doc:{content_hash}", json.dumps(record_dict))
        
        elif self.backend == "sqlite":
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            update_sql = "UPDATE documents SET status = ?"
            params = [status.value]
            
            if metadata:
                # Get existing metadata
                cursor = conn.execute(
                    "SELECT metadata FROM documents WHERE content_hash = ?",
                    (content_hash,)
                )
                row = cursor.fetchone()
                existing_metadata = json.loads(row[0]) if row and row[0] else {}
                existing_metadata.update(metadata)
                update_sql += ", metadata = ?"
                params.append(json.dumps(existing_metadata))
            
            update_sql += " WHERE content_hash = ?"
            params.append(content_hash)
            
            conn.execute(update_sql, params)
            conn.commit()
            conn.close()
        
        elif self.backend == "fuseki":
            # Delete and re-insert with updated status
            delete = f"""
            PREFIX reg: <http://procurement.kg/registry#>
            DELETE {{
                GRAPH <http://procurement.kg/registry#documents> {{
                    ?doc reg:status ?oldStatus .
                }}
            }}
            WHERE {{
                GRAPH <http://procurement.kg/registry#documents> {{
                    ?doc reg:contentHash "{content_hash}" ;
                         reg:status ?oldStatus .
                }}
            }}
            """
            self.sparql_store.execute_update(delete)
            
            # Re-insert with new status (simplified - would need full record)
            # For production, use a proper UPDATE query
    
    def get_stats(self) -> dict[str, Any]:
        """Get statistics about processed documents."""
        if self.backend == "redis":
            # Count keys
            keys = self.redis_client.keys("doc:*")
            total = len(keys)
            # Count by status (would need to scan all records)
            return {"total": total, "backend": "redis"}
        
        elif self.backend == "sqlite":
            import sqlite3
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM documents")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM documents GROUP BY status"
            )
            by_status = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            
            return {
                "total": total,
                "by_status": by_status,
                "backend": "sqlite",
            }
        
        elif self.backend == "fuseki":
            query = """
            PREFIX reg: <http://procurement.kg/registry#>
            SELECT (COUNT(*) as ?total) ?status (COUNT(?status) as ?count)
            WHERE {
                GRAPH <http://procurement.kg/registry#documents> {
                    ?doc reg:status ?status .
                }
            }
            GROUP BY ?status
            """
            results = self.sparql_store.execute_select(query)
            by_status = {r["status"]["value"]: int(r["count"]["value"]) for r in results}
            total = sum(by_status.values())
            
            return {
                "total": total,
                "by_status": by_status,
                "backend": "fuseki",
            }
        
        return {"total": 0, "backend": self.backend}
