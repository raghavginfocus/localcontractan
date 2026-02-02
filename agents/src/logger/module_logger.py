"""
Module Logger - Production-Grade Logger Implementation

Provides structured logging with:
- Per-module log files
- Log rotation
- JSON and text formats
- Analytics-ready structured data
- Performance metrics
- Context binding
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import structlog

# Import stdlib logging - must use __import__ to avoid conflict with our logger module
import importlib
_stdlib_logging = importlib.import_module('logging')
from logging.handlers import RotatingFileHandler

from .base import BaseLogger
from logging_config import (
    get_module_log_dir,
    ensure_module_log_dir,
)


class ModuleLogger(BaseLogger):
    """
    Production-grade logger for individual modules.
    
    Features:
    - Dedicated log file per module in module-specific directory
    - Log rotation (configurable size and backup count)
    - Structured logging with JSON support
    - Console output (optional)
    - Context binding for correlation
    - Analytics-ready format
    
    Usage:
        logger = ModuleLogger("graph_manager")
        logger.info("Operation started", operation="load_graph")
        
        # With context
        logger = logger.bind(component="GraphManager", graph_id="doc123")
        logger.info("Graph loaded")
    """
    
    def __init__(
        self,
        module_name: str,
        log_dir: Optional[Path] = None,
        log_level: str = "INFO",
        enable_console: bool = True,
        enable_json: bool = False,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        settings: Any = None,
    ):
        """
        Initialize module logger.
        
        Args:
            module_name: Name of the module
                (e.g., "graph_manager", "ingestion_orchestrator")
            log_dir: Optional custom log directory
                (defaults to logs/{module_name}/)
            log_level: Logging level
                (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console: Whether to output to console
            enable_json: Whether to use JSON format (for analytics)
            max_bytes: Maximum log file size before rotation
            backup_count: Number of backup files to keep
            settings: Optional settings object
        """
        self.module_name = module_name
        self.log_level = log_level.upper()
        self.enable_console = enable_console
        self.enable_json = enable_json
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.settings = settings
        
        # Get log directory for this module
        if log_dir is None:
            log_dir = get_module_log_dir(module_name)
        else:
            log_dir = Path(log_dir)
        
        ensure_module_log_dir(module_name)
        self.log_dir = log_dir
        self.log_file = self.log_dir / f"{module_name}.log"
        
        # Bound context (for correlation)
        self._context: dict[str, Any] = {}
        
        # Setup Python logging
        self._setup_logging()
        
        # Setup structlog
        self._setup_structlog()
        
        # Get the logger instances
        self._logger = _stdlib_logging.getLogger(f"module.{module_name}")
        self._structlogger = structlog.get_logger(module_name)
    
    def _setup_logging(self) -> None:
        """Setup Python's logging module."""
        logger = _stdlib_logging.getLogger(f"module.{self.module_name}")
        logger.setLevel(getattr(_stdlib_logging, self.log_level))
        
        # Remove existing handlers to avoid duplicates
        logger.handlers.clear()
        logger.propagate = False
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            self.log_file,
            mode="a",
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(getattr(_stdlib_logging, self.log_level))
        
        if self.enable_json:
            # JSON formatter for analytics
            file_handler.setFormatter(self._create_json_formatter())
        else:
            # Human-readable formatter
            file_handler.setFormatter(
                _stdlib_logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | "
                    "%(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
            )
        
        logger.addHandler(file_handler)
        
        # Console handler (optional)
        if self.enable_console:
            console_handler = _stdlib_logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(_stdlib_logging, self.log_level))
            console_handler.setFormatter(
                _stdlib_logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%H:%M:%S"
                )
            )
            logger.addHandler(console_handler)
    
    def _setup_structlog(self) -> None:
        """Setup structlog for structured logging."""
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]
        
        if self.enable_json:
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())
        
        processors.append(structlog.stdlib.ProcessorFormatter.wrap_for_formatter)
        
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    def _create_json_formatter(self) -> _stdlib_logging.Formatter:
        """Create a JSON formatter for analytics."""
        class JSONFormatter(_stdlib_logging.Formatter):
            def format(self, record: _stdlib_logging.LogRecord) -> str:
                log_data = {
                    "timestamp": datetime.fromtimestamp(
                        record.created
                    ).isoformat(),
                    "level": record.levelname,
                    "module": record.name,
                    "message": record.getMessage(),
                    "pathname": record.pathname,
                    "lineno": record.lineno,
                    "funcName": record.funcName,
                }

                # Add context if available
                if hasattr(record, "context"):
                    log_data["context"] = record.context

                # Add exception info if present
                if record.exc_info:
                    log_data["exception"] = self.formatException(
                        record.exc_info
                    )

                return json.dumps(log_data, default=str)

        return JSONFormatter()
    
    def _log(self, level: str, message: str, **kwargs: Any) -> None:
        """Internal logging method."""
        # Merge context with kwargs
        log_kwargs = {**self._context, **kwargs}
        
        # Log to standard logger
        log_method = getattr(self._logger, level.lower())
        log_method(message, extra={"context": log_kwargs})
        
        # Log to structlog
        structlog_method = getattr(self._structlogger, level.lower())
        structlog_method(message, **log_kwargs)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log("debug", message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        self._log("info", message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log("warning", message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        self._log("error", message, **kwargs)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a critical message."""
        self._log("critical", message, **kwargs)
    
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        self._log(
            "error",
            message,
            exc_info=(exc_type, exc_value, exc_traceback),
            **kwargs
        )
    
    def bind(self, **kwargs: Any) -> "ModuleLogger":
        """
        Create a new logger instance with bound context.
        
        Args:
            **kwargs: Context to bind to all subsequent log messages
            
        Returns:
            New logger instance with bound context
        """
        new_logger = ModuleLogger(
            module_name=self.module_name,
            log_dir=self.log_dir,
            log_level=self.log_level,
            enable_console=self.enable_console,
            enable_json=self.enable_json,
            max_bytes=self.max_bytes,
            backup_count=self.backup_count,
            settings=self.settings,
        )
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def get_log_file(self) -> Optional[Path]:
        """Get the path to the log file for this logger."""
        return self.log_file
    
    def set_level(self, level: str) -> None:
        """
        Set the logging level.
        
        Args:
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        self.log_level = level.upper()
        self._logger.setLevel(getattr(_stdlib_logging, self.log_level))
        for handler in self._logger.handlers:
            handler.setLevel(getattr(_stdlib_logging, self.log_level))
    
    def log_metric(
        self, metric_name: str, value: float, **kwargs: Any
    ) -> None:
        """
        Log a metric for analytics.

        Args:
            metric_name: Name of the metric
            value: Metric value
            **kwargs: Additional metric metadata
        """
        self.info(
            f"METRIC: {metric_name}",
            metric_name=metric_name,
            metric_value=value,
            **kwargs
        )

    def log_performance(
        self, operation: str, duration_ms: float, **kwargs: Any
    ) -> None:
        """
        Log performance metrics.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            **kwargs: Additional performance metadata
        """
        self.info(
            f"PERFORMANCE: {operation}",
            operation=operation,
            duration_ms=duration_ms,
            **kwargs
        )
