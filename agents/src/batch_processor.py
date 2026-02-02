"""
Batch Processor - Handles concurrent processing of multiple documents.

Enables scalable ingestion with:
- Concurrent document processing
- Progress tracking
- Error handling and retry logic
- Resource management
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from enum import Enum

from pydantic import BaseModel, Field

from agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig,
    IngestionResult,
)
from config import Settings, get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class BatchStatus(str, Enum):
    """Status of batch processing."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DocumentTask(BaseModel):
    """Represents a single document processing task."""
    
    task_id: str = Field(description="Unique task identifier")
    file_path: str | None = Field(default=None, description="Path to document")
    text: str | None = Field(default=None, description="Or raw text content")
    document_id: str | None = Field(default=None, description="Document ID")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    status: BatchStatus = Field(
        default=BatchStatus.PENDING,
        description="Task status"
    )
    result: IngestionResult | None = Field(
        default=None,
        description="Result if completed"
    )
    error: str | None = Field(default=None, description="Error if failed")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0


class BatchResult(BaseModel):
    """Result of batch processing."""
    
    batch_id: str = Field(description="Batch identifier")
    total_tasks: int = Field(description="Total number of tasks")
    completed: int = Field(default=0, description="Successfully completed")
    failed: int = Field(default=0, description="Failed tasks")
    status: BatchStatus = Field(description="Overall batch status")
    tasks: list[DocumentTask] = Field(
        default_factory=list,
        description="All tasks"
    )
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_ms: float = 0.0
    
    # Aggregated metrics
    total_clauses: int = 0
    total_entities: int = 0
    total_triples: int = 0
    total_risks: int = 0


class BatchProcessor:
    """
    Processes multiple documents concurrently.
    
    Features:
    - Concurrent processing with configurable concurrency limit
    - Progress tracking and callbacks
    - Automatic retry on transient failures
    - Resource pooling
    - Graceful error handling
    """
    
    def __init__(
        self,
        config: IngestionConfig | None = None,
        settings: Settings | None = None,
        max_concurrent: int = 5,
        max_retries: int = 2,
    ):
        """
        Initialize batch processor.
        
        Args:
            config: Ingestion configuration
            settings: Application settings
            max_concurrent: Maximum concurrent document processing
            max_retries: Maximum retry attempts for failed tasks
        """
        self.config = config or IngestionConfig()
        self.settings = settings or get_settings()
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.logger = logger.bind(component="BatchProcessor")
        
        # Create orchestrator pool
        self._orchestrators: list[IngestionOrchestrator] = []
        for _ in range(max_concurrent):
            self._orchestrators.append(
                IngestionOrchestrator(config=self.config, settings=self.settings)
            )
        
        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self,
        tasks: list[DocumentTask],
        batch_id: str | None = None,
        progress_callback: Callable[[BatchResult], None] | None = None,
    ) -> BatchResult:
        """
        Process a batch of documents concurrently.
        
        Args:
            tasks: List of document tasks to process
            batch_id: Optional batch identifier
            progress_callback: Optional callback for progress updates
            
        Returns:
            BatchResult with all task results
        """
        if not batch_id:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(
            "Starting batch processing",
            batch_id=batch_id,
            total_tasks=len(tasks),
            max_concurrent=self.max_concurrent,
        )
        
        batch_result = BatchResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            status=BatchStatus.RUNNING,
            tasks=tasks,
            started_at=datetime.now(),
        )
        
        # Process tasks concurrently
        task_coroutines = [
            self._process_task(task, batch_result, progress_callback)
            for task in tasks
        ]
        
        await asyncio.gather(*task_coroutines, return_exceptions=True)
        
        # Finalize batch result
        batch_result.completed_at = datetime.now()
        batch_result.total_duration_ms = (
            (batch_result.completed_at - batch_result.started_at).total_seconds()
            * 1000
        )
        
        # Count successes and failures
        batch_result.completed = sum(
            1 for t in tasks if t.status == BatchStatus.COMPLETED
        )
        batch_result.failed = sum(
            1 for t in tasks if t.status == BatchStatus.FAILED
        )
        
        # Aggregate metrics
        for task in tasks:
            if task.result and task.result.success:
                batch_result.total_clauses += task.result.clauses_extracted
                batch_result.total_entities += task.result.entities_extracted
                batch_result.total_triples += task.result.triples_loaded
                batch_result.total_risks += task.result.risks_extracted
        
        # Determine final status
        if batch_result.failed == 0:
            batch_result.status = BatchStatus.COMPLETED
        elif batch_result.completed == 0:
            batch_result.status = BatchStatus.FAILED
        else:
            batch_result.status = BatchStatus.PARTIAL
        
        self.logger.info(
            "Batch processing completed",
            batch_id=batch_id,
            status=batch_result.status,
            completed=batch_result.completed,
            failed=batch_result.failed,
            duration_ms=batch_result.total_duration_ms,
        )
        
        return batch_result
    
    async def _process_task(
        self,
        task: DocumentTask,
        batch_result: BatchResult,
        progress_callback: Callable[[BatchResult], None] | None,
    ) -> None:
        """Process a single task with retry logic."""
        async with self._semaphore:
            task.status = BatchStatus.RUNNING
            task.started_at = datetime.now()
            
            # Get an orchestrator from the pool
            orchestrator = self._orchestrators[0]  # Simple round-robin
            
            for attempt in range(self.max_retries + 1):
                try:
                    self.logger.debug(
                        "Processing task",
                        task_id=task.task_id,
                        attempt=attempt + 1,
                    )
                    
                    # Process document
                    result = await orchestrator.ingest(
                        file_path=task.file_path,
                        text=task.text,
                        document_id=task.document_id,
                    )
                    
                    task.result = result
                    task.status = (
                        BatchStatus.COMPLETED if result.success
                        else BatchStatus.FAILED
                    )
                    task.error = result.error
                    task.completed_at = datetime.now()
                    
                    if result.success:
                        break
                    
                    # Retry on failure
                    if attempt < self.max_retries:
                        task.retry_count += 1
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
                except Exception as e:
                    self.logger.error(
                        "Task processing failed",
                        task_id=task.task_id,
                        error=str(e),
                        attempt=attempt + 1,
                    )
                    
                    task.error = str(e)
                    task.status = BatchStatus.FAILED
                    task.completed_at = datetime.now()
                    
                    if attempt < self.max_retries:
                        task.retry_count += 1
                        await asyncio.sleep(2 ** attempt)
                    else:
                        break
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(batch_result)
                except Exception as e:
                    self.logger.warning(
                        f"Progress callback failed: {e}"
                    )
    
    async def process_directory(
        self,
        directory: str | Path,
        file_pattern: str = "*.pdf",
        batch_id: str | None = None,
        progress_callback: Callable[[BatchResult], None] | None = None,
    ) -> BatchResult:
        """
        Process all files in a directory matching a pattern.
        
        Args:
            directory: Directory path
            file_pattern: Glob pattern for files (e.g., "*.pdf", "*.docx")
            batch_id: Optional batch identifier
            progress_callback: Optional progress callback
            
        Returns:
            BatchResult
        """
        directory = Path(directory)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        # Find all matching files
        files = list(directory.glob(file_pattern))
        
        if not files:
            self.logger.warning(
                f"No files found matching pattern: {file_pattern}"
            )
            return BatchResult(
                batch_id=batch_id or "empty_batch",
                total_tasks=0,
                status=BatchStatus.COMPLETED,
                started_at=datetime.now(),
                completed_at=datetime.now(),
            )
        
        # Create tasks
        tasks = [
            DocumentTask(
                task_id=f"task_{i:04d}",
                file_path=str(file),
                document_id=file.stem,
            )
            for i, file in enumerate(files)
        ]
        
        self.logger.info(
            f"Processing directory",
            directory=str(directory),
            pattern=file_pattern,
            files_found=len(files),
        )
        
        return await self.process_batch(tasks, batch_id, progress_callback)
    
    def get_task_status(self, batch_result: BatchResult, task_id: str) -> DocumentTask | None:
        """Get status of a specific task."""
        for task in batch_result.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_failed_tasks(self, batch_result: BatchResult) -> list[DocumentTask]:
        """Get all failed tasks from a batch."""
        return [t for t in batch_result.tasks if t.status == BatchStatus.FAILED]
    
    async def retry_failed_tasks(
        self,
        batch_result: BatchResult,
        progress_callback: Callable[[BatchResult], None] | None = None,
    ) -> BatchResult:
        """Retry all failed tasks from a previous batch."""
        failed_tasks = self.get_failed_tasks(batch_result)
        
        if not failed_tasks:
            self.logger.info("No failed tasks to retry")
            return batch_result
        
        # Reset task status
        for task in failed_tasks:
            task.status = BatchStatus.PENDING
            task.error = None
            task.result = None
        
        retry_batch_id = f"{batch_result.batch_id}_retry"
        
        return await self.process_batch(
            failed_tasks,
            batch_id=retry_batch_id,
            progress_callback=progress_callback,
        )


