"""
DEPRECATED: Real-time File Logger for Contract KG Pipeline.

This module is deprecated. Use the new logging system instead:

    from logger import get_module_logger
    logger = get_module_logger(__name__)

This file is kept for backward compatibility only.
"""

import warnings
from pathlib import Path
from typing import Any

from logger import get_module_logger

# Issue deprecation warning
warnings.warn(
    "file_logger module is deprecated. Use logger.get_module_logger instead.",
    DeprecationWarning,
    stacklevel=2
)


def setup_file_logging(
    log_dir: Path | str | None = None,
    session_id: str | None = None,
    log_level: str = "INFO",
) -> Path:
    """
    DEPRECATED: Setup file-based logging with real-time output.
    
    Use get_module_logger(__name__) instead.
    """
    logger = get_module_logger("ingestion", log_level=log_level)
    log_file = logger.get_log_file()
    if log_file:
        logger.info("=" * 70)
        logger.info(f"INGESTION SESSION STARTED: {session_id or 'default'}")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 70)
        return log_file
        from logging_config import get_module_log_dir
        return get_module_log_dir("ingestion") / "ingestion.log"


class ProgressLogger:
    """
    DEPRECATED: Logger for tracking progress of long-running operations.
    
    Use get_module_logger(__name__) with log_performance() instead.
    """
    
    def __init__(
        self,
        operation: str,
        total_items: int | None = None,
        log_file: Path | None = None,
    ):
        warnings.warn(
            "ProgressLogger is deprecated. Use get_module_logger with log_performance instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.operation = operation
        self.total_items = total_items
        self.logger = get_module_logger("progress")
        
        self.logger.info(f"[START] {operation}")
        if total_items:
            self.logger.info(f"Processing {total_items} items...")
    
    def update(self, current: int, message: str = ""):
        """Update progress."""
        import time
        elapsed = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        
        if self.total_items:
            pct = (current / self.total_items) * 100
            eta = (elapsed / current) * (self.total_items - current) if current > 0 else 0
            self.logger.info(
                f"[{current}/{self.total_items}] {pct:.0f}% | "
                f"Elapsed: {elapsed:.0f}s | ETA: {eta:.0f}s | {message}"
            )
        else:
            self.logger.info(f"[{current}] Elapsed: {elapsed:.0f}s | {message}")
    
    def log(self, message: str, level: str = "info"):
        """Log a message."""
        getattr(self.logger, level.lower())(message)
    
    def complete(self, message: str = ""):
        """Mark operation as complete."""
        import time
        elapsed = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        self.logger.info(f"[DONE] {self.operation} completed in {elapsed:.1f}s. {message}")
    
    def error(self, message: str):
        """Log an error."""
        import time
        elapsed = time.time() - self.start_time if hasattr(self, 'start_time') else 0
        self.logger.error(f"[FAIL] {self.operation} failed after {elapsed:.1f}s: {message}")


def log_step_start(step_name: str, **kwargs: Any) -> None:
    """DEPRECATED: Log the start of a pipeline step."""
    logger = get_module_logger("pipeline")
    logger.info(f"STEP: {step_name}", **kwargs)


def log_step_complete(step_name: str, duration_ms: float, **kwargs: Any) -> None:
    """DEPRECATED: Log the completion of a pipeline step."""
    logger = get_module_logger("pipeline")
    logger.log_performance(step_name, duration_ms, **kwargs)


def log_step_error(step_name: str, error: str) -> None:
    """DEPRECATED: Log a step error."""
    logger = get_module_logger("pipeline")
    logger.error(f"{step_name} FAILED: {error}")


def log_llm_call(agent: str, prompt_preview: str = "", max_preview: int = 100) -> None:
    """DEPRECATED: Log an LLM call."""
    logger = get_module_logger("llm")
    preview = prompt_preview[:max_preview] + "..." if len(prompt_preview) > max_preview else prompt_preview
    logger.info(f"[LLM] {agent} calling LLM...", prompt_preview=preview)


def log_llm_response(agent: str, response_preview: str = "", tokens: int = 0) -> None:
    """DEPRECATED: Log an LLM response."""
    logger = get_module_logger("llm")
    logger.info(f"[LLM] {agent} received response", tokens=tokens)
