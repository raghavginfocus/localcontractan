"""
Ingestion Pipeline Agents

These agents handle the complete ingestion flow from raw documents to knowledge graph:
1. Document intake
2. Semantic extraction (clauses, entities, obligations, risks)
3. Ontology alignment
4. RDF generation
5. Validation
6. Knowledge graph loading (Fuseki, reasoning, vector indexing)
"""

# Document Intake
from agents.ingestion.document_ingestion import DocumentIngestionAgent, ExtractedDocument

# Semantic Extraction
from agents.ingestion.clause_extraction import (
    ClauseExtractionAgent,
    ExtractedClause,
    ClauseExtractionResult,
)
from agents.ingestion.entity_extraction import (
    EntityExtractionAgent,
    EntityExtractionResult,
    Party,
    ContractDate,
    MonetaryAmount,
    Jurisdiction,
)
from agents.ingestion.obligation_risk import (
    ObligationRiskAgent,
    ObligationRiskResult,
    Obligation,
    Risk,
)

# Ontology Alignment
from agents.ingestion.ontology_alignment import (
    OntologyAlignmentAgent,
    OntologyMapping,
    OntologySuggestion,
    AlignmentResult,
)

# RDF Generation
from agents.ingestion.rdf_generator import (
    RDFGeneratorAgent,
    RDFGenerationResult,
)

# Validation
from agents.ingestion.validation_agent import (
    ValidationAgent,
    ValidationResult,
    ValidationError,
)

# Knowledge Graph Loading
from agents.ingestion.fuseki_loader import (
    FusekiLoaderAgent,
    LoadResult,
)
from agents.ingestion.reasoning_agent import (
    ReasoningAgent,
    ReasoningResult,
)
from agents.ingestion.vector_index import (
    VectorIndexAgent,
    IndexResult,
)

# Orchestration
from agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionResult,
    IngestionConfig,
    IngestionStep,
    OntologyEvolutionMode,
)

__all__ = [
    # Document Intake
    "DocumentIngestionAgent",
    "ExtractedDocument",
    # Semantic Extraction
    "ClauseExtractionAgent",
    "ExtractedClause",
    "ClauseExtractionResult",
    "EntityExtractionAgent",
    "EntityExtractionResult",
    "Party",
    "ContractDate",
    "MonetaryAmount",
    "Jurisdiction",
    "ObligationRiskAgent",
    "ObligationRiskResult",
    "Obligation",
    "Risk",
    # Ontology Alignment
    "OntologyAlignmentAgent",
    "OntologyMapping",
    "OntologySuggestion",
    "AlignmentResult",
    # RDF Generation
    "RDFGeneratorAgent",
    "RDFGenerationResult",
    # Validation
    "ValidationAgent",
    "ValidationResult",
    "ValidationError",
    # Knowledge Graph Loading
    "FusekiLoaderAgent",
    "LoadResult",
    "ReasoningAgent",
    "ReasoningResult",
    "InferredFact",
    "VectorIndexAgent",
    "IndexResult",
    # Orchestration
    "IngestionOrchestrator",
    "IngestionResult",
    "IngestionConfig",
    "IngestionStep",
    "OntologyEvolutionMode",
]
