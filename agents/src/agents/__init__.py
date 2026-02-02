"""
LLM Agents for Contract Knowledge Graph.

This module provides specialized agents organized by pipeline:

INGESTION PIPELINE (agents/ingestion/):
- Document intake, semantic extraction, ontology alignment, RDF generation,
  validation, and knowledge graph loading

RETRIEVAL PIPELINE (agents/retrieval/):
- SPARQL generation, hybrid RAG orchestration, answer generation

SCHEMA EVOLUTION (agents/schema_evolution/):
- Ontology design, rule generation, SHACL shape generation

SHARED (agents/shared/):
- Base agent class and common utilities
"""

# Import from organized subdirectories for backward compatibility
from agents.ingestion import (
    # Document Intake
    DocumentIngestionAgent,
    ExtractedDocument,
    # Semantic Extraction
    ClauseExtractionAgent,
    ExtractedClause,
    ClauseExtractionResult,
    EntityExtractionAgent,
    EntityExtractionResult,
    Party,
    ContractDate,
    MonetaryAmount,
    Jurisdiction,
    ObligationRiskAgent,
    ObligationRiskResult,
    Obligation,
    Risk,
    # Ontology Alignment
    OntologyAlignmentAgent,
    OntologyMapping,
    OntologySuggestion,
    AlignmentResult,
    # RDF Generation
    RDFGeneratorAgent,
    RDFGenerationResult,
    # Validation
    ValidationAgent,
    ValidationResult,
    ValidationError,
    # Knowledge Graph Loading
    FusekiLoaderAgent,
    LoadResult,
    ReasoningAgent,
    ReasoningResult,
    VectorIndexAgent,
    IndexResult,
    # Orchestration
    IngestionOrchestrator,
    IngestionResult,
    IngestionConfig,
    IngestionStep,
    OntologyEvolutionMode,
)

from agents.retrieval import (
    SPARQLGeneratorAgent,
    SPARQLQuery,
    RAGOrchestratorAgent,
    RAGResponse,
    RetrievalOrchestrator,
    RetrievalResult,
    RetrievalStep,
    RetrievalStrategy,
)

from agents.schema_evolution import (
    OntologyDesignerAgent,
    OWLGenerationResult,
    OntologyExtensionResult,
    RuleGeneratorAgent,
    RulePattern,
    RuleGenerationResult,
    RuleSetResult,
    SHACLGeneratorAgent,
    SHACLShapeResult,
    SHACLGenerationResult,
)

from agents.shared import BaseAgent

__all__ = [
    # Ingestion Pipeline
    "DocumentIngestionAgent",
    "ExtractedDocument",
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
    "OntologyAlignmentAgent",
    "OntologyMapping",
    "OntologySuggestion",
    "AlignmentResult",
    "RDFGeneratorAgent",
    "RDFGenerationResult",
    "ValidationAgent",
    "ValidationResult",
    "ValidationError",
    "FusekiLoaderAgent",
    "LoadResult",
    "ReasoningAgent",
    "ReasoningResult",
    "InferredFact",
    "VectorIndexAgent",
    "IndexResult",
    "IngestionOrchestrator",
    "IngestionResult",
    "IngestionConfig",
    "IngestionStep",
    "OntologyEvolutionMode",
    # Retrieval Pipeline
    "SPARQLGeneratorAgent",
    "SPARQLQuery",
    "RAGOrchestratorAgent",
    "RAGResponse",
    "RetrievalOrchestrator",
    "RetrievalResult",
    "RetrievalStep",
    "RetrievalStrategy",
    # Schema Evolution
    "OntologyDesignerAgent",
    "OWLGenerationResult",
    "OntologyExtensionResult",
    "RuleGeneratorAgent",
    "RulePattern",
    "RuleGenerationResult",
    "RuleSetResult",
    "SHACLGeneratorAgent",
    "SHACLShapeResult",
    "SHACLGenerationResult",
    # Shared
    "BaseAgent",
]
