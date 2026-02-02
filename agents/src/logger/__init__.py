"""
Production-Grade Logging System

Provides unified, modular logging for all modules in the Contract KG system.

Features:
- Per-module log files in dedicated directories
- Log rotation and management
- Structured logging (JSON and text formats)
- Analytics-ready format
- Context binding for correlation
- Performance metrics
- Follows SOLID principles
- Factory pattern for extensibility

Usage:
    from logger import get_module_logger
    
    logger = get_module_logger(__name__)
    logger.info("Operation started", operation="load_graph")
    
    # With context
    logger = logger.bind(component="GraphManager", graph_id="doc123")
    logger.info("Graph loaded")
"""

from .base import BaseLogger
from .module_logger import ModuleLogger
from .factory import LoggerFactory, create_logger

__all__ = [
    "BaseLogger",
    "ModuleLogger",
    "LoggerFactory",
    "create_logger",
    "get_module_logger",
]


def get_module_logger(
    module_name: str | None = None,
    **kwargs,
) -> BaseLogger:
    """
    Get a logger for a module (convenience function).
    
    This is the recommended way to get a logger in any module.
    It automatically extracts the module name from __name__ if not provided.
    
    Args:
        module_name: Name of the module (defaults to extracting from caller's __name__)
        **kwargs: Additional logger configuration options
        
    Returns:
        BaseLogger instance
        
    Examples:
        # In a module file
        logger = get_module_logger(__name__)
        logger.info("Starting operation")
        
        # With custom name
        logger = get_module_logger("custom_module")
        
        # With options
        logger = get_module_logger(__name__, enable_json=True, log_level="DEBUG")
    """
    import inspect
    
    # Extract module name from caller if not provided
    if module_name is None:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_frame = frame.f_back
            module_name = caller_frame.f_globals.get("__name__", "unknown")
    
    # Clean up module name - always simplify
    # Map all modules to just two categories: ingestion or retrieval
    # Check call stack to determine context for shared modules
    import inspect
    frame = inspect.currentframe()
    is_retrieval_context = False
    is_ingestion_context = False
    
    # Walk up the call stack to find context (check up to 15 frames)
    if frame:
        current = frame.f_back
        depth = 0
        while current and depth < 15:
            frame_name = current.f_globals.get("__name__", "")
            frame_name_lower = frame_name.lower()
            if "retrieval" in frame_name_lower or "rag" in frame_name_lower or "sparql_generator" in frame_name_lower:
                is_retrieval_context = True
                break
            elif "ingestion" in frame_name_lower or "ingest" in frame_name_lower or "vector_index" in frame_name_lower:
                is_ingestion_context = True
                break
            current = current.f_back
            depth += 1
    
    if module_name.startswith("agents.ingestion"):
        module_name = "ingestion"
    elif module_name.startswith("agents.retrieval"):
        module_name = "retrieval"
    elif module_name.startswith("agents.schema_evolution"):
        # Schema evolution happens during ingestion
        module_name = "ingestion"
    elif module_name.startswith("storage.sparql"):
        # SPARQL store - check context, default to retrieval
        module_name = "retrieval" if (is_retrieval_context or not is_ingestion_context) else "ingestion"
    elif module_name.startswith("storage.vector"):
        # Vector store - check context, default to retrieval
        module_name = "retrieval" if (is_retrieval_context or not is_ingestion_context) else "ingestion"
    elif module_name in ["vector_store", "fuseki_client"]:
        # Shared modules - route based on context
        # Default to retrieval since they're primarily used in retrieval operations
        # This ensures all retrieval-related logs go to retrieval.log
        module_name = "retrieval" if (is_retrieval_context or not is_ingestion_context) else "ingestion"
    elif module_name in ["artifact_store", "ontology_manager", "schema_governance", 
                         "graph_manager", "fuseki_loader", "reasoning_agent", 
                         "vector_index", "validation_agent", "rdf_generator",
                         "clause_extraction", "entity_extraction", "obligation_risk",
                         "ontology_alignment", "document_ingestion", "ingestion_orchestrator",
                         "base", "pipeline", "batch_processor"]:
        # All ingestion-related modules
        module_name = "ingestion"
    elif module_name in ["rag_orchestrator", "sparql_generator", "retrieval_orchestrator",
                         "logging_utils"]:
        # All retrieval-related modules
        module_name = "retrieval"
    elif "." in module_name:
        # For other modules, check if they contain ingestion/retrieval keywords
        module_lower = module_name.lower()
        if "ingestion" in module_lower or "ingest" in module_lower:
            module_name = "ingestion"
        elif "retrieval" in module_lower or "retrieve" in module_lower or "rag" in module_lower:
            module_name = "retrieval"
        else:
            # Default to ingestion for unknown modules (most are ingestion-related)
            module_name = "ingestion"
    
    if not module_name or module_name == "__main__":
        module_name = "ingestion"  # Default to ingestion
    
    return create_logger(module_name, **kwargs)
