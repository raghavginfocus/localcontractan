"""
Contract Knowledge Graph Agents

This package provides LLM-powered agents for:
- Document ingestion and text extraction
- Semantic clause extraction
- Ontology evolution and governance
- SPARQL query generation
- Hybrid RAG orchestration with Milvus vector search
"""

__version__ = "1.0.0"

from config import Settings
from fuseki_client import FusekiClient
from vector_store import MilvusVectorStore
from health import HealthChecker, check_health, SystemHealth
from ontology_manager import get_ontology_manager, initialize_ontology

__all__ = [
    "Settings",
    "FusekiClient",
    "MilvusVectorStore",
    "HealthChecker",
    "check_health",
    "SystemHealth",
    "get_ontology_manager",
    "initialize_ontology",
    "__version__",
]
