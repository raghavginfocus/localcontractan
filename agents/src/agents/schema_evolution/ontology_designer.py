"""
Ontology Designer Agent - Generates OWL definitions for new ontology concepts.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL, XSD

from agents.shared.base import BaseAgent
from agents.ingestion.ontology_alignment import OntologySuggestion
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)

# Default output directory for generated artifacts
GENERATED_DIR = Path("data/generated")


class OWLGenerationResult(BaseModel):
    """Result of OWL generation."""
    
    suggestion_name: str = Field(description="Name of the concept")
    owl_triples: str = Field(description="Generated OWL in Turtle format")
    triple_count: int = Field(default=0, description="Number of triples generated")
    is_valid: bool = Field(default=False, description="Whether OWL is syntactically valid")
    file_path: str | None = Field(default=None, description="Path where OWL was saved")
    error: str | None = Field(default=None, description="Error if generation failed")


class OntologyExtensionResult(BaseModel):
    """Result of extending the ontology."""
    
    extensions: list[OWLGenerationResult] = Field(default_factory=list)
    total_triples: int = Field(default=0)
    combined_owl_path: str | None = Field(default=None)
    loaded_to_fuseki: bool = Field(default=False)


class OntologyDesignerAgent(BaseAgent):
    """
    Agent for designing and generating OWL ontology extensions.
    
    When new concepts are discovered during ingestion that don't exist
    in the current ontology, this agent:
    1. Analyzes the concept and its usage context
    2. Determines the appropriate parent class
    3. Generates OWL class and property definitions
    4. Validates the generated OWL
    5. Saves to file for review/loading
    """

    DESIGN_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert ontology designer for procurement contracts.
Generate OWL/Turtle definitions for new ontology concepts.

EXISTING ONTOLOGY STRUCTURE:
- proc:Contract - Root class for contracts
- proc:Clause - Base class for all clauses
  - proc:TerminationClause, proc:PaymentClause, proc:PenaltyClause, etc.
- proc:Party - Base class for parties (proc:Buyer, proc:Supplier)
- proc:Obligation - Contractual obligations
- proc:Risk - Identified risks

NAMING CONVENTIONS:
- Classes: PascalCase (e.g., DataProtectionClause)
- Properties: camelCase (e.g., dataRetentionPeriod)
- Use proc: prefix for ontology namespace

REQUIRED OUTPUT FORMAT (valid Turtle):
```turtle
# Class definition
proc:NewClassName a owl:Class ;
    rdfs:subClassOf proc:ParentClass ;
    rdfs:label "Human Readable Label" ;
    rdfs:comment "Description of what this class represents" .

# Property definitions (if applicable)
proc:propertyName a owl:DatatypeProperty ;
    rdfs:domain proc:NewClassName ;
    rdfs:range xsd:string ;
    rdfs:label "property label" ;
    rdfs:comment "What this property represents" .
```

Generate ONLY valid Turtle. No explanations outside the Turtle block."""),
        ("human", """Generate OWL definitions for this new concept:

Name: {name}
Type: {suggestion_type}
Description: {description}
Parent Class: {parent_class}
Example Values: {examples}

Output valid Turtle/OWL:"""),
    ])

    def __init__(self, output_dir: Path | None = None, **kwargs: Any):
        """
        Initialize the ontology designer.
        
        Args:
            output_dir: Directory for generated OWL files
        """
        super().__init__(**kwargs)
        self.output_dir = output_dir or GENERATED_DIR / "ontology"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()
        self.PROC = Namespace(self.settings.procurement_namespace)

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> OWLGenerationResult:
        """
        Generate OWL for a single ontology suggestion.
        
        Args:
            input_data: Dict with OntologySuggestion fields or OntologySuggestion object
            
        Returns:
            OWLGenerationResult with generated OWL
        """
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation()
        
        # Extract suggestion data
        if isinstance(input_data, OntologySuggestion):
            suggestion = input_data
        else:
            suggestion = OntologySuggestion(**input_data)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data if isinstance(input_data, dict) else suggestion.model_dump())
        
        self.log_start("owl_generation", name=suggestion.name)
        
        try:
            # Generate OWL using LLM
            chain = self.DESIGN_PROMPT | self.llm | StrOutputParser()
            
            owl_text = await chain.ainvoke({
                "name": suggestion.name,
                "suggestion_type": suggestion.suggestion_type,
                "description": suggestion.description,
                "parent_class": suggestion.parent_class or "proc:Clause",
                "examples": ", ".join(suggestion.examples) if suggestion.examples else "N/A",
            })
            
            # Clean up the output (extract Turtle from markdown if needed)
            owl_text = self._extract_turtle(owl_text)
            
            # Add prefixes if missing
            owl_text = self._ensure_prefixes(owl_text)
            
            # Validate OWL syntax
            is_valid, triple_count = self._validate_owl(owl_text)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{suggestion.name.lower()}_{timestamp}.ttl"
            file_path = self.output_dir / filename
            
            with open(file_path, "w") as f:
                f.write(f"# Generated OWL Extension\n")
                f.write(f"# Concept: {suggestion.name}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Description: {suggestion.description}\n\n")
                f.write(owl_text)
            
            result = OWLGenerationResult(
                suggestion_name=suggestion.name,
                owl_triples=owl_text,
                triple_count=triple_count,
                is_valid=is_valid,
                file_path=str(file_path),
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("name", suggestion.name)
                self.explanation_builder.add_metadata("triple_count", triple_count)
                self.explanation_builder.add_metadata("is_valid", is_valid)
                self.explanation_builder.add_metadata("file_path", str(file_path))
                self.explanation_builder.set_process_description(
                    f"Generated OWL extension for concept '{suggestion.name}' ({suggestion.suggestion_type}) "
                    f"with {triple_count} triples. Extension is {'valid' if is_valid else 'invalid'} "
                    f"and saved to {file_path}."
                )
                self._save_explanation()
            
            self.log_complete(
                "owl_generation",
                name=suggestion.name,
                triple_count=triple_count,
                is_valid=is_valid,
                file_path=str(file_path),
            )
            
            return result
            
        except Exception as e:
            self.log_error("owl_generation", e, name=suggestion.name)
            return OWLGenerationResult(
                suggestion_name=suggestion.name,
                owl_triples="",
                error=str(e),
            )

    async def extend_ontology(
        self,
        suggestions: list[OntologySuggestion],
        load_to_fuseki: bool = False,
    ) -> OntologyExtensionResult:
        """
        Generate OWL for multiple suggestions and optionally load to Fuseki.
        
        Args:
            suggestions: List of ontology suggestions
            load_to_fuseki: Whether to load the combined OWL into Fuseki
            
        Returns:
            OntologyExtensionResult with all generated OWL
        """
        self.log_start("ontology_extension", suggestion_count=len(suggestions))
        
        extensions = []
        combined_graph = Graph()
        combined_graph.bind("proc", self.PROC)
        combined_graph.bind("owl", OWL)
        combined_graph.bind("rdfs", RDFS)
        combined_graph.bind("xsd", XSD)
        
        for suggestion in suggestions:
            result = await self.process(suggestion)
            extensions.append(result)
            
            # Add valid OWL to combined graph
            if result.is_valid and result.owl_triples:
                try:
                    temp_graph = Graph()
                    temp_graph.parse(data=result.owl_triples, format="turtle")
                    for triple in temp_graph:
                        combined_graph.add(triple)
                except Exception as e:
                    logger.warning(f"Failed to add {suggestion.name} to combined graph: {e}")
        
        # Save combined OWL
        total_triples = len(combined_graph)
        combined_path = None
        
        if total_triples > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_path = self.output_dir / f"extensions_combined_{timestamp}.ttl"
            
            with open(combined_path, "w") as f:
                f.write(f"# Combined OWL Extensions\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Concepts: {', '.join(s.name for s in suggestions)}\n\n")
                f.write(combined_graph.serialize(format="turtle"))
        
        # Load to Fuseki if requested
        loaded = False
        if load_to_fuseki and total_triples > 0:
            try:
                from agents.ingestion.fuseki_loader import FusekiLoaderAgent
                loader = FusekiLoaderAgent(settings=self.settings)
                load_result = await loader.process({
                    "graph": combined_graph,
                    "graph_uri": f"{self.settings.procurement_namespace}extensions",
                })
                loaded = load_result.success
            except Exception as e:
                logger.error(f"Failed to load to Fuseki: {e}")
        
        self.log_complete(
            "ontology_extension",
            extensions=len(extensions),
            total_triples=total_triples,
            loaded=loaded,
        )
        
        return OntologyExtensionResult(
            extensions=extensions,
            total_triples=total_triples,
            combined_owl_path=str(combined_path) if combined_path else None,
            loaded_to_fuseki=loaded,
        )

    def _extract_turtle(self, text: str) -> str:
        """Extract Turtle content from LLM output."""
        # Remove markdown code blocks if present
        if "```turtle" in text:
            start = text.find("```turtle") + len("```turtle")
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end]
        
        return text.strip()

    def _ensure_prefixes(self, owl_text: str) -> str:
        """Ensure required prefixes are present."""
        prefixes = """@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix proc: <http://procurement.kg/ontology#> .

"""
        if "@prefix" not in owl_text.lower():
            return prefixes + owl_text
        return owl_text

    def _validate_owl(self, owl_text: str) -> tuple[bool, int]:
        """Validate OWL syntax by parsing."""
        try:
            g = Graph()
            g.parse(data=owl_text, format="turtle")
            return True, len(g)
        except Exception as e:
            logger.warning(f"OWL validation failed: {e}")
            return False, 0

    def get_generated_extensions(self) -> list[Path]:
        """List all generated extension files."""
        return list(self.output_dir.glob("*.ttl"))
