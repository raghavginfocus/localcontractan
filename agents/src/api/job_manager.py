"""
Job Manager for Async Ingestion Tasks.

Manages job state using SQLite database for persistence.
Supports job creation, status tracking, progress updates, and result storage.
"""

import json
import sqlite3
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STOPPING  = "stopping"
    STOPPED   = "stopped"


class JobInfo(BaseModel):
    """Job information model."""
    job_id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)


class IngestionJobManager:
    """Manages ingestion jobs using SQLite database."""
    
    def __init__(self, db_path: str = "/app/data/jobs.db"):
        """Initialize job manager with SQLite database."""
        self.db_path = db_path
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    input_data TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    progress INTEGER DEFAULT 0
                )
            """)
            conn.commit()
    
    def create_job(self, input_data: Dict[str, Any]) -> str:
        """Create a new job and return job ID."""
        job_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO ingestion_jobs 
                (job_id, status, created_at, input_data, progress)
                VALUES (?, ?, ?, ?, ?)
            """, (
                job_id,
                JobStatus.PENDING.value,
                created_at,
                json.dumps(input_data),
                0
            ))
            conn.commit()
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[JobInfo]:
        """Get job information by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return JobInfo(
                job_id=row["job_id"],
                status=JobStatus(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                input_data=json.loads(row["input_data"]),
                result=json.loads(row["result"]) if row["result"] else None,
                error=row["error"],
                progress=row["progress"]
            )
    
    def list_jobs(self, limit: int = 100, status: Optional[JobStatus] = None) -> List[JobInfo]:
        """List jobs with optional status filter."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if status:
                cursor = conn.execute(
                    "SELECT * FROM ingestion_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status.value, limit)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            
            jobs = []
            for row in cursor.fetchall():
                jobs.append(JobInfo(
                    job_id=row["job_id"],
                    status=JobStatus(row["status"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    input_data=json.loads(row["input_data"]),
                    result=json.loads(row["result"]) if row["result"] else None,
                    error=row["error"],
                    progress=row["progress"]
                ))
            
            return jobs
    
    def update_status(self, job_id: str, status: JobStatus):
        """Update job status."""
        timestamp = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            if status == JobStatus.RUNNING:
                conn.execute(
                    "UPDATE ingestion_jobs SET status = ?, started_at = ? WHERE job_id = ?",
                    (status.value, timestamp, job_id)
                )
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                conn.execute(
                    "UPDATE ingestion_jobs SET status = ?, completed_at = ? WHERE job_id = ?",
                    (status.value, timestamp, job_id)
                )
            else:
                conn.execute(
                    "UPDATE ingestion_jobs SET status = ? WHERE job_id = ?",
                    (status.value, job_id)
                )
            conn.commit()
    
    def update_progress(self, job_id: str, progress: int):
        """Update job progress (0-100)."""
        progress = max(0, min(100, progress))  # Clamp to 0-100
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE ingestion_jobs SET progress = ? WHERE job_id = ?",
                (progress, job_id)
            )
            conn.commit()
    
    def mark_completed(self, job_id: str, result: Dict[str, Any]):
        """Mark job as completed with result."""
        timestamp = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ingestion_jobs 
                SET status = ?, completed_at = ?, result = ?, progress = 100
                WHERE job_id = ?
            """, (
                JobStatus.COMPLETED.value,
                timestamp,
                json.dumps(result),
                job_id
            ))
            conn.commit()
    
    def mark_failed(self, job_id: str, error: str):
        """Mark job as failed with error message."""
        timestamp = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ingestion_jobs 
                SET status = ?, completed_at = ?, error = ?
                WHERE job_id = ?
            """, (
                JobStatus.FAILED.value,
                timestamp,
                error,
                job_id
            ))
            conn.commit()
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job. Returns True if deleted, False if not found."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM ingestion_jobs WHERE job_id = ?",
                (job_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        
    def mark_stopped(self, job_id: str, checkpoint: dict):
        """Mark job as stopped and persist checkpoint for resume."""
        timestamp = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE ingestion_jobs 
                SET status = ?, completed_at = ?, result = ?
                WHERE job_id = ?
            """, (
                JobStatus.STOPPED.value,
                timestamp,
                json.dumps({"__checkpoint__": checkpoint}),
                job_id
            ))
            conn.commit()
