"""
Centralized logging configuration for Contract KG.

All logs are organized under a single logs/ directory with only two categories:
- logs/ingestion/     - All ingestion-related logs
  - ingestion.log                    # Main ingestion log file
  - agent_explanations/              # Agent explanations
  - doc_*_alignment_*.json          # Document alignment results
  - doc_*_validation_*.json         # Document validation results
  - doc_*_reasoning_*.json           # Document reasoning results
  - doc_*_extractions_*.json        # Document extraction results
- logs/retrieval/     - All retrieval-related logs
  - retrieval.log                    # Main retrieval log file
  - agent_explanations/              # Agent explanations
  - sessions/                        # RAG session logs
  - unanswered/                      # Unanswered query explanations
"""

from pathlib import Path
from typing import Optional

# Central logs directory (relative to agents directory)
# Calculate from this file's location: src/logging_config.py -> agents/logs
LOGS_ROOT = Path(__file__).parent.parent / "logs"


def ensure_log_dirs():
    """Ensure log directories exist."""
    LOGS_ROOT.mkdir(parents=True, exist_ok=True)


def get_module_log_dir(module_name: str) -> Path:
    """
    Get the log directory for a specific module.
    
    Each category gets its own directory under logs/.
    All logs for a category go into one file: logs/{category}/{category}.log
    
    Args:
        module_name: Name of the module/category (e.g., "ingestion", "retrieval")
        
    Returns:
        Path to the module's log directory (e.g., logs/ingestion/)
    """
    ensure_log_dirs()
    
    # Sanitize module name (remove invalid characters)
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in module_name)
    
    module_dir = LOGS_ROOT / safe_name
    module_dir.mkdir(parents=True, exist_ok=True)
    
    return module_dir


def ensure_module_log_dir(module_name: str) -> Path:
    """
    Ensure a module's log directory exists.
    
    Args:
        module_name: Name of the module
        
    Returns:
        Path to the module's log directory
    """
    return get_module_log_dir(module_name)


def get_log_dir(category: str) -> Path:
    """
    DEPRECATED: Get the log directory for a specific category.
    
    Use get_module_log_dir() instead. This is kept for backward compatibility.
    
    Args:
        category: Category name
        
    Returns:
        Path to the log directory
    """
    ensure_log_dirs()
    # Return category directory directly under logs/
    return LOGS_ROOT / category.lower()


# Initialize directories on import
ensure_log_dirs()
