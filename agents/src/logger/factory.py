"""
Logger Factory

Factory for creating logger instances based on module names.
Follows the same pattern as SPARQLStoreFactory and VectorStoreFactory.
"""

from typing import Dict, Type, Optional, Any
from pathlib import Path

from .base import BaseLogger
from .module_logger import ModuleLogger


class LoggerFactory:
    """
    Factory for creating logger instances.
    
    Usage:
        logger = LoggerFactory.create_logger("graph_manager")
        logger.info("Operation started")
    """
    
    _logger_types: Dict[str, Type[BaseLogger]] = {
        "module": ModuleLogger,
    }
    
    # Cache of logger instances (singleton per module)
    _loggers: Dict[str, BaseLogger] = {}
    
    @classmethod
    def create_logger(
        cls,
        module_name: str,
        logger_type: str = "module",
        log_dir: Optional[Path] = None,
        log_level: str = "INFO",
        enable_console: bool = True,
        enable_json: bool = False,
        settings: Any = None,
        **kwargs: Any,
    ) -> BaseLogger:
        """
        Create or get a logger instance for a module.
        
        Uses singleton pattern - same module name returns same logger instance.
        
        Args:
            module_name: Name of the module (e.g., "graph_manager", "ingestion_orchestrator")
            logger_type: Type of logger (default: "module")
            log_dir: Optional custom log directory
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console: Whether to output to console
            enable_json: Whether to use JSON format (for analytics)
            settings: Optional settings object
            **kwargs: Additional logger-specific arguments
            
        Returns:
            BaseLogger instance
            
        Raises:
            ValueError: If logger type is not recognized
        """
        # Create cache key
        cache_key = f"{logger_type}:{module_name}"
        
        # Return cached logger if exists
        if cache_key in cls._loggers:
            return cls._loggers[cache_key]
        
        # Get logger class
        logger_class = cls._logger_types.get(logger_type.lower())
        if not logger_class:
            available = ", ".join(cls._logger_types.keys())
            raise ValueError(
                f"Unknown logger type: '{logger_type}'. "
                f"Available types: {available}"
            )
        
        # Create logger instance
        logger = logger_class(
            module_name=module_name,
            log_dir=log_dir,
            log_level=log_level,
            enable_console=enable_console,
            enable_json=enable_json,
            settings=settings,
            **kwargs,
        )
        
        # Cache it
        cls._loggers[cache_key] = logger
        
        return logger
    
    @classmethod
    def register_logger_type(cls, name: str, logger_class: Type[BaseLogger]):
        """
        Register a new logger type (for extensibility).
        
        Args:
            name: Logger type identifier
            logger_class: Logger class implementing BaseLogger
        """
        cls._logger_types[name.lower()] = logger_class
    
    @classmethod
    def list_logger_types(cls) -> list[str]:
        """List all registered logger types."""
        return list(cls._logger_types.keys())
    
    @classmethod
    def clear_cache(cls):
        """Clear the logger cache (useful for testing)."""
        cls._loggers.clear()
    
    @classmethod
    def get_cached_logger(cls, module_name: str, logger_type: str = "module") -> Optional[BaseLogger]:
        """
        Get a cached logger instance if it exists.
        
        Args:
            module_name: Name of the module
            logger_type: Type of logger
            
        Returns:
            Cached logger or None
        """
        cache_key = f"{logger_type}:{module_name}"
        return cls._loggers.get(cache_key)


def create_logger(
    module_name: str,
    logger_type: str = "module",
    **kwargs: Any,
) -> BaseLogger:
    """
    Convenience function to create a logger.
    
    Args:
        module_name: Name of the module
        logger_type: Type of logger (default: "module")
        **kwargs: Additional logger arguments
        
    Returns:
        BaseLogger instance
    """
    return LoggerFactory.create_logger(module_name, logger_type, **kwargs)
