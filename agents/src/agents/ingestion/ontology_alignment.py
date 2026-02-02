"""
Ontology Alignment Agent - Maps extracted entities to ontology concepts.

Now uses dynamic OntologyManager instead of hardcoded mappings.
"""

from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.ingestion.clause_extraction import ExtractedClause
from agents.ingestion.entity_extraction import EntityExtractionResult
from ontology_manager import get_ontology_manager


class OntologyMapping(BaseModel):
    """Represents a mapping from extracted entity to ontology concept."""
    
    source_id: str = Field(description="ID of the source entity")
    source_type: str = Field(description="Type of source entity")
    target_class: str = Field(description="Target ontology class URI")
    target_properties: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of extracted attributes to ontology properties"
    )
    confidence: float = Field(default=1.0, description="Confidence score 0-1")
    notes: str | None = Field(default=None, description="Alignment notes")
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OntologyMapping":
        """Create OntologyMapping from dict with type coercion."""
        # Coerce target_properties values to strings
        if "target_properties" in data:
            props = data["target_properties"]
            if isinstance(props, dict):
                coerced_props = {}
                for key, value in props.items():
                    if value is None:
                        continue  # Skip None values
                    elif isinstance(value, (list, tuple)):
                        coerced_props[key] = ", ".join(str(v) for v in value)
                    elif isinstance(value, bool):
                        coerced_props[key] = "true" if value else "false"
                    else:
                        coerced_props[key] = str(value)
                data["target_properties"] = coerced_props
        return cls(**data)


class OntologySuggestion(BaseModel):
    """Suggestion for extending the ontology."""
    
    suggestion_type: str = Field(description="Type: NewClass, NewProperty, NewRelation")
    name: str = Field(description="Suggested name for the concept")
    description: str = Field(description="Description of what this would represent")
    parent_class: str | None = Field(default=None, description="Parent class for new classes")
    domain: str | None = Field(default=None, description="Domain for new properties")
    range: str | None = Field(default=None, description="Range for new properties")
    occurrences: int = Field(default=1, description="How many times this was needed")
    examples: list[str] = Field(default_factory=list, description="Example values")


class AlignmentResult(BaseModel):
    """Result of ontology alignment."""
    
    document_id: str = Field(description="ID of the source document")
    mappings: list[OntologyMapping] = Field(default_factory=list, description="Successful mappings")
    unmapped_entities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Entities that couldn't be mapped"
    )
    suggestions: list[OntologySuggestion] = Field(
        default_factory=list,
        description="Suggestions for ontology extension"
    )
    alignment_score: float = Field(default=0.0, description="Overall alignment score 0-1")


class OntologyAlignmentAgent(BaseAgent):
    """
    Agent for aligning extracted entities to the procurement ontology.
    
    NOW USES DYNAMIC ONTOLOGY MANAGER - no hardcoded mappings!
    
    Responsibilities:
    - Map clause types to ontology classes (dynamically loaded)
    - Map extracted attributes to ontology properties (dynamically loaded)
    - Identify gaps where ontology extension may be needed
    - Suggest new classes/properties for unmapped concepts
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Get ontology manager instance
        self.ontology_manager = get_ontology_manager()
    
    def _get_ontology_classes(self) -> dict[str, str]:
        """Get current ontology classes from manager."""
        return self.ontology_manager.get_class_mapping()
    
    def _get_ontology_properties(self) -> dict[str, str]:
        """Get current ontology properties from manager."""
        return self.ontology_manager.get_property_mapping()

    ALIGNMENT_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert in knowledge graph ontology alignment.
Your task is to map extracted contract entities to our procurement ontology.

KNOWN ONTOLOGY CLASSES:
{ontology_classes}

KNOWN ONTOLOGY PROPERTIES:
{ontology_properties}

For each entity:
1. Find the best matching ontology class
2. Map its attributes to ontology properties
3. If no match exists, suggest an extension

CRITICAL: In target_properties, ALL values MUST be strings (ontology property URIs like "proc:noticePeriod").
- Do NOT use None, null, false, true, or arrays as values
- If an attribute doesn't map to a property, omit it from target_properties
- Example: {{"notice_period": "proc:noticePeriod"}} NOT {{"notice_period": null}}

Return JSON with:
{{
    "mappings": [
        {{
            "source_id": "clause_1",
            "source_type": "TerminationClause",
            "target_class": "proc:TerminationClause",
            "target_properties": {{
                "notice_period": "proc:noticePeriod",
                "raw_text": "proc:rawText"
            }},
            "confidence": 0.95,
            "notes": "Direct match to known clause type"
        }}
    ],
    "unmapped_entities": [
        {{
            "id": "clause_5",
            "type": "DataProtectionClause",
            "reason": "No matching class in ontology"
        }}
    ],
    "suggestions": [
        {{
            "suggestion_type": "NewClass",
            "name": "DataProtectionClause",
            "description": "Clause covering GDPR and data privacy requirements",
            "parent_class": "proc:ComplianceClause",
            "occurrences": 1,
            "examples": ["GDPR compliance", "Data retention policy"]
        }}
    ]
}}
"""),
        ("human", """Align these extracted entities to the ontology:

Document ID: {document_id}

Clauses:
{clauses}

Entities:
{entities}

Return the alignment as JSON."""),
    ])

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> AlignmentResult:
        """
        Align extracted entities to the ontology.
        
        Args:
            input_data: Dict with 'document_id', 'clauses', 'entities' keys
            
        Returns:
            AlignmentResult with mappings and suggestions
        """
        document_id = input_data.get("document_id", "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        clauses: list[ExtractedClause] = input_data.get("clauses", [])
        entities: EntityExtractionResult | None = input_data.get("entities")
        
        self.log_start("ontology_alignment", document_id=document_id)
        
        # First, do automatic mapping for known types
        auto_mappings = self._auto_align_clauses(clauses)
        
        # Format data for LLM
        clauses_str = self._format_clauses(clauses)
        entities_str = self._format_entities(entities) if entities else "No entities extracted"
        
        # Use LLM for complex alignment
        parser = JsonOutputParser()
        chain = self.ALIGNMENT_PROMPT | self.llm | parser
        
        try:
            # Get current ontology mappings dynamically
            ontology_classes = self._get_ontology_classes()
            ontology_properties = self._get_ontology_properties()
            
            result = await chain.ainvoke({
                "document_id": document_id,
                "ontology_classes": "\n".join(
                    f"- {k}: {v}" for k, v in ontology_classes.items()
                ),
                "ontology_properties": "\n".join(
                    f"- {k}: {v}" for k, v in ontology_properties.items()
                ),
                "clauses": clauses_str,
                "entities": entities_str,
            })
            
            # Parse LLM mappings with type coercion
            llm_mappings = []
            for m in result.get("mappings", []):
                try:
                    mapping = OntologyMapping.from_dict(m)
                    llm_mappings.append(mapping)
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse mapping, skipping",
                        error=str(e),
                        mapping_preview=str(m)[:200],
                    )
                    if self.explanation_builder:
                        self.explanation_builder.add_error(
                            f"Failed to parse mapping: {str(e)[:200]}"
                        )
            
            # Merge auto and LLM mappings
            all_mappings = auto_mappings + llm_mappings
            
            # Deduplicate by source_id
            seen_ids = set()
            unique_mappings = []
            for m in all_mappings:
                if m.source_id not in seen_ids:
                    unique_mappings.append(m)
                    seen_ids.add(m.source_id)
            
            suggestions = [
                OntologySuggestion(**s) for s in result.get("suggestions", [])
            ]
            
            # Calculate alignment score
            total = len(clauses) + (len(entities.parties) + len(entities.amounts) if entities else 0)
            aligned = len([m for m in unique_mappings if m.confidence > 0.5])
            alignment_score = aligned / total if total > 0 else 1.0
            
            alignment_result = AlignmentResult(
                document_id=document_id,
                mappings=unique_mappings,
                unmapped_entities=result.get("unmapped_entities", []),
                suggestions=suggestions,
                alignment_score=alignment_score,
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(alignment_result)
                self.explanation_builder.add_metadata("mappings_count", len(unique_mappings))
                self.explanation_builder.add_metadata("suggestions_count", len(suggestions))
                self.explanation_builder.add_metadata("alignment_score", alignment_score)
                self._save_explanation()
            
            self.log_complete(
                "ontology_alignment",
                document_id=document_id,
                mappings=len(unique_mappings),
                suggestions=len(suggestions),
                alignment_score=alignment_score,
            )
            
            return alignment_result
            
        except Exception as e:
            self.log_error("ontology_alignment", e, document_id=document_id)
            raise

    def _auto_align_clauses(
        self, clauses: list[ExtractedClause]
    ) -> list[OntologyMapping]:
        """Automatically align clauses with known types (dynamic)."""
        mappings = []
        ontology_classes = self._get_ontology_classes()
        ontology_properties = self._get_ontology_properties()
        
        for clause in clauses:
            if clause.clause_type in ontology_classes:
                # Map attributes to properties
                property_mappings = {}
                for attr_name in clause.attributes.keys():
                    if attr_name in ontology_properties:
                        property_mappings[attr_name] = ontology_properties[attr_name]
                
                # Always include rawText
                if "rawText" in ontology_properties:
                    property_mappings["raw_text"] = ontology_properties["rawText"]
                
                mappings.append(OntologyMapping(
                    source_id=clause.clause_id,
                    source_type=clause.clause_type,
                    target_class=ontology_classes[clause.clause_type],
                    target_properties=property_mappings,
                    confidence=1.0,
                    notes="Automatic alignment - known clause type",
                ))
        
        return mappings

    def _format_clauses(self, clauses: list[ExtractedClause]) -> str:
        """Format clauses for LLM prompt."""
        lines = []
        for c in clauses:
            attrs = ", ".join(f"{k}={v}" for k, v in c.attributes.items())
            lines.append(f"- {c.clause_id}: {c.clause_type} [{attrs}]")
        return "\n".join(lines) if lines else "No clauses"

    def _format_entities(self, entities: EntityExtractionResult) -> str:
        """Format entities for LLM prompt."""
        lines = []
        for p in entities.parties:
            lines.append(f"- Party: {p.name} ({p.role})")
        for d in entities.dates:
            lines.append(f"- Date: {d.date_type} = {d.date_value or d.date_description}")
        for a in entities.amounts:
            lines.append(f"- Amount: {a.amount_type} = {a.value} {a.currency}")
        for j in entities.jurisdictions:
            lines.append(f"- Jurisdiction: {j.name} ({j.jurisdiction_type})")
        return "\n".join(lines) if lines else "No entities"

    def get_unmapped_clause_types(self, result: AlignmentResult) -> list[str]:
        """Get list of clause types that couldn't be mapped."""
        return [
            e.get("type", "Unknown")
            for e in result.unmapped_entities
            if "Clause" in e.get("type", "")
        ]

    def should_extend_ontology(self, result: AlignmentResult, threshold: int = 3) -> bool:
        """Check if ontology extension is recommended based on suggestions."""
        for suggestion in result.suggestions:
            if suggestion.occurrences >= threshold:
                return True
        return False
