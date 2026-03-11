"""
Batch Processor Agent - Processes multiple documents in parallel.

Features:
- Parallel processing with resource management
- Progress tracking and reporting with tqdm
- Error handling and retry logic
- Comprehensive logging
"""

import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.ingestion.directory_scanner import (
    DiscoveredFile,
    FileCategory
)
from logger import get_module_logger

logger = get_module_logger(__name__)

# Try to import tqdm for progress bars
try:
    from tqdm.asyncio import tqdm as async_tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning("tqdm not available - progress bars disabled. Install with: uv add tqdm")


@dataclass
class ProcessingTask:
    """Represents a document processing task."""
    file: DiscoveredFile
    status: str = "pending"  # pending, processing, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retry_count: int = 0


class BatchProgress(BaseModel):
    """Progress tracking for batch processing."""
    total_tasks: int = Field(description="Total number of tasks")
    completed: int = Field(default=0, description="Completed tasks")
    failed: int = Field(default=0, description="Failed tasks")
    in_progress: int = Field(default=0, description="Tasks in progress")
    pending: int = Field(default=0, description="Pending tasks")
    progress_percent: float = Field(default=0.0, description="Progress %")
    elapsed_ms: float = Field(default=0.0, description="Elapsed time")
    estimated_remaining_ms: float = Field(
        default=0.0,
        description="Estimated remaining time"
    )


class BatchResult(BaseModel):
    """Result of batch processing."""
    total_files: int = Field(description="Total files processed")
    successful: int = Field(description="Successfully processed")
    failed: int = Field(description="Failed to process")
    skipped: int = Field(description="Skipped files")
    total_duration_ms: float = Field(description="Total processing time")
    tasks: List[ProcessingTask] = Field(
        default_factory=list,
        description="Individual task results"
    )
    errors: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Error details"
    )


class BatchProcessorAgent(BaseAgent):
    """
    Agent for processing multiple documents in parallel.
    
    Features:
    - Configurable concurrency limits
    - Progress tracking
    - Error handling with retry logic
    - Resource management
    - Comprehensive logging
    """
    
    def __init__(
        self,
        settings=None,
        llm=None,
        max_concurrent: int = 5,
        max_retries: int = 2,
        retry_delay_ms: int = 1000
    ):
        super().__init__(settings, llm)
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process(
        self,
        input_data: Dict[str, Any]
    ) -> BatchResult:
        """
        Process multiple documents in parallel.
        
        Args:
            input_data: Dict with:
                - files: List of DiscoveredFile objects
                - processor_fn: Async function to process each file
                - progress_callback: Optional callback for progress
                
        Returns:
            BatchResult with processing results
        """
        import time
        start_time = time.time()
        
        files: List[DiscoveredFile] = input_data.get("files", [])
        processor_fn = input_data.get("processor_fn")
        progress_callback = input_data.get("progress_callback")
        
        if not processor_fn:
            raise ValueError("processor_fn is required")
        
        # Filter out unsupported files
        supported_files = [
            f for f in files
            if f.category != FileCategory.UNSUPPORTED
        ]
        skipped = len(files) - len(supported_files)
        
        logger.info(
            f"Starting batch processing: {len(supported_files)} files "
            f"({skipped} skipped)"
        )
        
        # Create tasks
        tasks = [
            ProcessingTask(file=f)
            for f in supported_files
        ]
        
        # Process tasks in parallel
        await self._process_tasks(
            tasks,
            processor_fn,
            progress_callback
        )
        
        # Calculate results
        successful = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        
        errors = [
            {
                "file": t.file.filename,
                "error": t.error or "Unknown error"
            }
            for t in tasks if t.status == "failed"
        ]
        
        duration_ms = (time.time() - start_time) * 1000
        
        result = BatchResult(
            total_files=len(files),
            successful=successful,
            failed=failed,
            skipped=skipped,
            total_duration_ms=duration_ms,
            tasks=tasks,
            errors=errors
        )
        
        logger.info(
            f"Batch processing complete: {successful}/{len(supported_files)} "
            f"successful, {failed} failed, {skipped} skipped"
        )
        
        return result
    
    async def _process_tasks(
        self,
        tasks: List[ProcessingTask],
        processor_fn,
        progress_callback=None
    ):
        """Process tasks in parallel with concurrency control."""
        
        # Create progress bar if tqdm is available
        pbar = None
        if TQDM_AVAILABLE:
            pbar = async_tqdm(
                total=len(tasks),
                desc="Processing documents",
                unit="doc",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]"
            )
        
        async def process_single_task(task: ProcessingTask):
            """Process a single task with retry logic."""
            async with self.semaphore:
                for attempt in range(self.max_retries + 1):
                    try:
                        task.status = "processing"
                        task.started_at = datetime.now()
                        
                        # Update progress
                        if progress_callback:
                            await self._update_progress(
                                tasks,
                                progress_callback
                            )
                        
                        # Process the file
                        result = await processor_fn(task.file)
                        
                        # Success
                        task.status = "completed"
                        task.completed_at = datetime.now()
                        task.duration_ms = (
                            (task.completed_at - task.started_at)
                            .total_seconds() * 1000
                        )
                        task.result = result
                        
                        # Update progress bar
                        if pbar:
                            pbar.update(1)
                            pbar.set_postfix({
                                'file': task.file.filename[:30],
                                'status': '✓'
                            })
                        
                        logger.info(
                            f"✓ Processed {task.file.filename} "
                            f"in {task.duration_ms:.0f}ms"
                        )
                        break
                        
                    except Exception as e:
                        task.retry_count = attempt + 1
                        
                        if attempt < self.max_retries:
                            logger.warning(
                                f"⚠ Processing {task.file.filename} failed "
                                f"(attempt {attempt + 1}/{self.max_retries + 1}): "
                                f"{e}. Retrying..."
                            )
                            await asyncio.sleep(
                                self.retry_delay_ms / 1000
                            )
                        else:
                            # Final failure
                            task.status = "failed"
                            task.completed_at = datetime.now()
                            task.error = str(e)
                            
                            # Update progress bar
                            if pbar:
                                pbar.update(1)
                                pbar.set_postfix({
                                    'file': task.file.filename[:30],
                                    'status': '✗'
                                })
                            
                            logger.error(
                                f"✗ Processing {task.file.filename} failed "
                                f"after {self.max_retries + 1} attempts: {e}"
                            )
                
                # Final progress update
                if progress_callback:
                    await self._update_progress(tasks, progress_callback)
        
        # Process all tasks
        await asyncio.gather(
            *[process_single_task(task) for task in tasks],
            return_exceptions=True
        )
        
        # Close progress bar
        if pbar:
            pbar.close()
    
    async def _update_progress(
        self,
        tasks: List[ProcessingTask],
        callback
    ):
        """Update progress and call callback."""
        import time
        
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        in_progress = sum(1 for t in tasks if t.status == "processing")
        pending = sum(1 for t in tasks if t.status == "pending")
        
        progress = BatchProgress(
            total_tasks=len(tasks),
            completed=completed,
            failed=failed,
            in_progress=in_progress,
            pending=pending,
            progress_percent=(
                (completed + failed) / len(tasks) * 100
                if tasks else 0
            )
        )
        
        try:
            await callback(progress)
        except Exception as e:
            logger.warning(f"Progress callback failed: {e}")


