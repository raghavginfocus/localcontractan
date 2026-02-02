"""
Schema Evolution Agents

These agents handle ontology and schema evolution:
1. Ontology Designer - Generates OWL extensions for new concepts
2. Rule Generator - Generates Jena inference rules
3. SHACL Generator - Generates SHACL validation shapes
"""

from agents.schema_evolution.ontology_designer import (
    OntologyDesignerAgent,
    OWLGenerationResult,
    OntologyExtensionResult,
)
from agents.schema_evolution.rule_generator import (
    RuleGeneratorAgent,
    RulePattern,
    RuleGenerationResult,
    RuleSetResult,
)
from agents.schema_evolution.shacl_generator import (
    SHACLGeneratorAgent,
    SHACLShapeResult,
    SHACLGenerationResult,
)
from agents.schema_evolution.pattern_detection import (
    PatternDetectionAgent,
    DetectedPattern,
    PatternDetectionResult,
)

__all__ = [
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
    "PatternDetectionAgent",
    "DetectedPattern",
    "PatternDetectionResult",
]
