"""
Base Logger Interface

Defines the abstract interface for all loggers in the system.
Follows SOLID principles - specifically Interface Segregation
and Dependency Inversion.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
from pathlib import Path


class BaseLogger(ABC):
    """
    Abstract base class for all loggers.
    
    This interface ensures all loggers provide consistent functionality
    while allowing different implementations (file, JSON, structured, etc.).
    
    Follows:
    - Single Responsibility: Logging only
    - Open/Closed: Open for extension, closed for modification
    - Dependency Inversion: Depend on abstraction, not concrete classes
    """
    
    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message."""
        ...

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message."""
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error message."""
        ...

    @abstractmethod
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a critical message."""
        ...

    @abstractmethod
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        ...
    
    @abstractmethod
    def bind(self, **kwargs: Any) -> "BaseLogger":
        """
        Create a new logger instance with bound context.

        Args:
            **kwargs: Context to bind to all subsequent log messages

        Returns:
            New logger instance with bound context
        """
        ...

    @abstractmethod
    def get_log_file(self) -> Optional[Path]:
        """
        Get the path to the log file for this logger.

        Returns:
            Path to log file, or None if not file-based
        """
        ...

    @abstractmethod
    def set_level(self, level: str) -> None:
        """
        Set the logging level.

        Args:
            level: One of DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        ...
