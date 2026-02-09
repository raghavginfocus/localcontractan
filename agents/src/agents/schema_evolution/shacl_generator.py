"""
SHACL Generator Agent - Generates SHACL validation shapes for ontology classes.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

from agents.shared.base import BaseAgent
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)

# Default output directory for generated artifacts
GENERATED_DIR = Path("data/generated")


class SHACLShapeResult(BaseModel):
    """Result of SHACL shape generation."""
    
    class_name: str = Field(description="Name of the ontology class")
    shacl_triples: str = Field(description="Generated SHACL in Turtle format")
    triple_count: int = Field(default=0, description="Number of triples generated")
    is_valid: bool = Field(default=False, description="Whether SHACL is syntactically valid")
    file_path: str | None = Field(default=None, description="Path where SHACL was saved")
    error: str | None = Field(default=None, description="Error if generation failed")


class SHACLGenerationResult(BaseModel):
    """Result of generating multiple SHACL shapes."""
    
    shapes: list[SHACLShapeResult] = Field(default_factory=list)
    total_triples: int = Field(default=0)
    combined_shacl_path: str | None = Field(default=None)


class SHACLGeneratorAgent(BaseAgent):
    """
    Agent for generating SHACL validation shapes for ontology classes.
    
    When new ontology classes are created, this agent:
    1. Analyzes the class and its properties
    2. Determines appropriate validation constraints
    3. Generates SHACL NodeShape definitions
    4. Validates the generated SHACL
    5. Saves to file for review/loading
    """

    GENERATION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert SHACL shape designer for procurement contract knowledge graphs.
Generate SHACL validation shapes for ontology classes.

EXISTING SHACL PATTERNS:
- Contract must have at least one clause (sh:minCount)
- TerminationClause must have noticePeriod (sh:minCount, sh:datatype, sh:minInclusive)
- PaymentClause paymentDays must be 1-365 (sh:minInclusive, sh:maxInclusive)
- Risk severity must be in enum: Low, Medium, High, Critical (sh:in)

SHACL SEVERITY LEVELS:
- sh:Violation - Critical error, data is invalid
- sh:Warning - Data quality issue, should be fixed
- sh:Info - Informational constraint

REQUIRED OUTPUT FORMAT (valid Turtle):
```turtle
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix proc: <http://procurement.kg/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

proc:ClassNameShape a sh:NodeShape ;
    sh:targetClass proc:ClassName ;
    sh:property [
        sh:path proc:propertyName ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Property description" ;
        sh:severity sh:Warning ;
    ] ;
    sh:property [
        sh:path proc:numericProperty ;
        sh:datatype xsd:integer ;
        sh:minInclusive 0 ;
        sh:maxInclusive 100 ;
        sh:message "Numeric property description" ;
        sh:severity sh:Warning ;
    ] .
```

Generate ONLY valid Turtle. No explanations outside the Turtle block."""),
        ("human", """Generate SHACL validation shape for this ontology class:

Class Name: {class_name}
Parent Class: {parent_class}
Properties: {properties}
Description: {description}

Output valid SHACL/Turtle:"""),
    ])

    def __init__(self, output_dir: Path | None = None, **kwargs: Any):
        """
        Initialize the SHACL generator.
        
        Args:
            output_dir: Directory for generated SHACL files
        """
        super().__init__(**kwargs)
        self.output_dir = output_dir or GENERATED_DIR / "shacl"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()
        self.PROC = Namespace(self.settings.procurement_namespace)

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> SHACLShapeResult:
        """
        Generate SHACL shape for a single ontology class.
        
        Args:
            input_data: Dict with:
                - class_name: str - Name of the class (e.g., "DataProtectionClause")
                - parent_class: str - Parent class (e.g., "proc:Clause")
                - properties: list[dict] - List of property definitions with:
                    - name: str - Property name
                    - type: str - Datatype (xsd:string, xsd:integer, etc.)
                    - required: bool - Whether property is required
                    - min_value: float | None - Minimum value for numeric
                    - max_value: float | None - Maximum value for numeric
                    - enum_values: list[str] | None - Enum values if applicable
                - description: str - Description of the class
        
        Returns:
            SHACLShapeResult with generated SHACL
        """
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation()
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        
        class_name = input_data.get("class_name", "")
        parent_class = input_data.get("parent_class", "proc:Clause")
        properties = input_data.get("properties", [])
        description = input_data.get("description", "")
        
        self.log_start("shacl_generation", class_name=class_name)
        
        try:
            # Format properties for prompt
            properties_text = self._format_properties(properties)
            
            # Generate SHACL using LLM
            chain = self.GENERATION_PROMPT | self.llm | StrOutputParser()
            
            shacl_text = await chain.ainvoke({
                "class_name": class_name,
                "parent_class": parent_class,
                "properties": properties_text,
                "description": description,
            })
            
            # Clean up the output (extract Turtle from markdown if needed)
            shacl_text = self._extract_turtle(shacl_text)
            
            # Add prefixes if missing
            shacl_text = self._ensure_prefixes(shacl_text)
            
            # Post-process to fix common issues
            shacl_text = self._post_process_shacl(shacl_text, class_name)
            
            # Validate SHACL syntax
            is_valid, triple_count = self._validate_shacl(shacl_text)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{class_name.lower()}_shape_{timestamp}.ttl"
            file_path = self.output_dir / filename
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Generated SHACL Shape\n")
                f.write(f"# Class: {class_name}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Description: {description}\n\n")
                f.write(shacl_text)
            
            result = SHACLShapeResult(
                class_name=class_name,
                shacl_triples=shacl_text,
                triple_count=triple_count,
                is_valid=is_valid,
                file_path=str(file_path),
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("class_name", class_name)
                self.explanation_builder.add_metadata("triple_count", triple_count)
                self.explanation_builder.add_metadata("is_valid", is_valid)
                self.explanation_builder.add_metadata("file_path", str(file_path))
                self.explanation_builder.set_process_description(
                    f"Generated SHACL validation shape for class '{class_name}' with {triple_count} triples. "
                    f"Shape is {'valid' if is_valid else 'invalid'} and saved to {file_path}."
                )
                self._save_explanation()
            
            self.log_complete(
                "shacl_generation",
                class_name=class_name,
                triple_count=triple_count,
                is_valid=is_valid,
                file_path=str(file_path),
            )
            
            return result
            
        except Exception as e:
            self.log_error("shacl_generation", e, class_name=class_name)
            return SHACLShapeResult(
                class_name=class_name,
                shacl_triples="",
                error=str(e),
            )

    async def generate_for_owl_class(
        self,
        owl_class_name: str,
        owl_triples: str,
        parent_class: str = "proc:Clause",
    ) -> SHACLShapeResult:
        """
        Generate SHACL shape by analyzing OWL class definition.
        
        Args:
            owl_class_name: Name of the OWL class
            owl_triples: OWL definition in Turtle format
            parent_class: Parent class for context
        
        Returns:
            SHACLShapeResult with generated SHACL
        """
        # Parse OWL to extract properties
        try:
            g = Graph()
            g.parse(data=owl_triples, format="turtle")
            
            class_uri = self.PROC[owl_class_name]
            properties = []
            
            # Find properties with this class as domain
            # Look for triples where the object is our class and predicate is rdfs:domain
            for prop_uri, pred, domain_obj in g.triples((None, RDFS.domain, None)):
                # Check if this property's domain is our class
                if domain_obj == class_uri or str(domain_obj) == str(class_uri):
                    # Extract property name
                    prop_uri_str = str(prop_uri)
                    if "#" in prop_uri_str:
                        prop_name = prop_uri_str.split("#")[-1]
                    elif "/" in prop_uri_str:
                        prop_name = prop_uri_str.split("/")[-1]
                    else:
                        prop_name = prop_uri_str
                    
                    # Find the range of this property
                    range_obj = None
                    for s2, p2, o2 in g.triples((prop_uri, RDFS.range, None)):
                        range_obj = o2
                        break
                    
                    # Determine property type
                    prop_type = "xsd:string"  # default
                    if range_obj:
                        range_str = str(range_obj)
                        if "string" in range_str.lower():
                            prop_type = "xsd:string"
                        elif "integer" in range_str.lower() or "int" in range_str.lower():
                            prop_type = "xsd:integer"
                        elif "decimal" in range_str.lower() or "double" in range_str.lower() or "float" in range_str.lower():
                            prop_type = "xsd:decimal"
                        elif "date" in range_str.lower():
                            prop_type = "xsd:date"
                        elif "boolean" in range_str.lower() or "bool" in range_str.lower():
                            prop_type = "xsd:boolean"
                    
                    properties.append({
                        "name": prop_name,
                        "type": prop_type,
                        "required": True,  # Assume required if in domain
                    })
            
            # Generate SHACL
            return await self.process({
                "class_name": owl_class_name,
                "parent_class": parent_class,
                "properties": properties,
                "description": f"SHACL validation shape for {owl_class_name}",
            })
            
        except Exception as e:
            logger.error(f"Failed to parse OWL for SHACL generation: {e}")
            return SHACLShapeResult(
                class_name=owl_class_name,
                shacl_triples="",
                error=f"OWL parsing failed: {e}",
            )

    async def generate_shapes(
        self,
        classes: list[dict[str, Any]],
    ) -> SHACLGenerationResult:
        """
        Generate SHACL shapes for multiple classes.
        
        Args:
            classes: List of class definitions (same format as process input_data)
        
        Returns:
            SHACLGenerationResult with all generated shapes
        """
        self.log_start("shacl_generation_batch", class_count=len(classes))
        
        shapes = []
        combined_graph = Graph()
        combined_graph.bind("sh", Namespace("http://www.w3.org/ns/shacl#"))
        combined_graph.bind("proc", self.PROC)
        combined_graph.bind("xsd", XSD)
        combined_graph.bind("rdfs", RDFS)
        
        for class_def in classes:
            result = await self.process(class_def)
            shapes.append(result)
            
            # Add valid SHACL to combined graph
            if result.is_valid and result.shacl_triples:
                try:
                    temp_graph = Graph()
                    temp_graph.parse(data=result.shacl_triples, format="turtle")
                    for triple in temp_graph:
                        combined_graph.add(triple)
                except Exception as e:
                    logger.warning(f"Failed to add {result.class_name} to combined graph: {e}")
        
        # Save combined SHACL
        total_triples = len(combined_graph)
        combined_path = None
        
        if total_triples > 0:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_path = self.output_dir / f"shapes_combined_{timestamp}.ttl"
            
            with open(combined_path, "w", encoding="utf-8") as f:
                f.write(f"# Combined SHACL Shapes\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Classes: {', '.join(s.class_name for s in shapes)}\n\n")
                f.write(combined_graph.serialize(format="turtle"))
        
        self.log_complete(
            "shacl_generation_batch",
            shapes=len(shapes),
            total_triples=total_triples,
        )
        
        return SHACLGenerationResult(
            shapes=shapes,
            total_triples=total_triples,
            combined_shacl_path=str(combined_path) if combined_path else None,
        )

    def _format_properties(self, properties: list[dict[str, Any]]) -> str:
        """Format properties for the LLM prompt."""
        if not properties:
            return "No specific properties defined."
        
        lines = []
        for prop in properties:
            prop_str = f"- {prop.get('name', 'unknown')}: {prop.get('type', 'xsd:string')}"
            if prop.get("required"):
                prop_str += " (required)"
            if prop.get("min_value") is not None:
                prop_str += f", min: {prop.get('min_value')}"
            if prop.get("max_value") is not None:
                prop_str += f", max: {prop.get('max_value')}"
            if prop.get("enum_values"):
                prop_str += f", enum: {', '.join(prop.get('enum_values', []))}"
            lines.append(prop_str)
        
        return "\n".join(lines)

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
        
        # Clean up common LLM artifacts
        text = text.strip()
        
        # Remove invalid wildcard patterns like proc:*
        import re
        text = re.sub(r'proc:\*', '', text)
        text = re.sub(r'sh:path\s+proc:\*', '', text)
        
        # Remove empty property blocks
        text = re.sub(r'sh:property\s+\[\s*\];', '', text)
        text = re.sub(r'sh:property\s+\[\s*\]\s*;', '', text)
        
        return text.strip()

    def _ensure_prefixes(self, shacl_text: str) -> str:
        """Ensure required prefixes are present."""
        import re
        
        # Check if prefixes are already present
        has_prefixes = "@prefix" in shacl_text.lower()
        
        # Required prefixes
        required_prefixes = {
            "sh": "@prefix sh: <http://www.w3.org/ns/shacl#> .",
            "proc": "@prefix proc: <http://procurement.kg/ontology#> .",
            "xsd": "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "rdfs": "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "rdf": "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
        }
        
        if not has_prefixes:
            # Add all prefixes at the beginning
            prefix_block = "\n".join(required_prefixes.values()) + "\n\n"
            return prefix_block + shacl_text
        else:
            # Check each required prefix and add missing ones
            prefix_lines = []
            for prefix_name, prefix_decl in required_prefixes.items():
                # Check if this prefix is declared
                pattern = rf'@prefix\s+{prefix_name}:\s*<[^>]+>'
                if not re.search(pattern, shacl_text, re.IGNORECASE):
                    prefix_lines.append(prefix_decl)
            
            if prefix_lines:
                # Insert missing prefixes after existing prefixes
                # Find the end of existing prefix block
                last_prefix_match = None
                for match in re.finditer(r'@prefix\s+\w+:\s*<[^>]+>', shacl_text):
                    last_prefix_match = match
                
                if last_prefix_match:
                    insert_pos = shacl_text.find('\n', last_prefix_match.end())
                    if insert_pos > 0:
                        shacl_text = shacl_text[:insert_pos] + '\n' + '\n'.join(prefix_lines) + shacl_text[insert_pos:]
                else:
                    # No existing prefixes found, prepend
                    shacl_text = '\n'.join(prefix_lines) + '\n\n' + shacl_text
        
        return shacl_text

    def _post_process_shacl(self, shacl_text: str, class_name: str) -> str:
        """Post-process SHACL to fix common LLM generation issues."""
        import re
        
        # Fix line breaks in URIs (critical fix for WatsonX output)
        # Pattern: <http://www.\nw3.\norg/...> -> <http://www.w3.org/...>
        def fix_uri_linebreaks(match):
            uri = match.group(0)
            # Remove all newlines and extra spaces within URIs
            uri = uri.replace('\n', '').replace('\r', '')
            uri = re.sub(r'\s+', '', uri)
            return uri
        
        # Fix URIs in angle brackets
        shacl_text = re.sub(r'<[^>]*\n[^>]*>', fix_uri_linebreaks, shacl_text, flags=re.MULTILINE)
        
        # Fix malformed prefix declarations (remove weird characters before xsd:)
        shacl_text = re.sub(r"'[^']*'xsd:", 'xsd:', shacl_text)
        shacl_text = re.sub(r'[^a-zA-Z:]xsd:', ' xsd:', shacl_text)
        shacl_text = re.sub(r'\^[a-z]\'xsd:', 'xsd:', shacl_text)
        
        # Ensure xsd prefix is properly declared
        if 'xsd:' in shacl_text and '@prefix xsd:' not in shacl_text:
            # Add xsd prefix if missing
            if '@prefix' in shacl_text:
                # Insert after first prefix line
                first_prefix_end = shacl_text.find('@prefix', shacl_text.find('@prefix') + 1)
                if first_prefix_end == -1:
                    first_prefix_end = shacl_text.find('\n', shacl_text.find('@prefix'))
                if first_prefix_end > 0:
                    shacl_text = shacl_text[:first_prefix_end] + '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n' + shacl_text[first_prefix_end:]
        
        # Remove invalid wildcard patterns
        shacl_text = re.sub(r'sh:path\s+proc:\*\s*;', '', shacl_text)
        shacl_text = re.sub(r'sh:path\s+proc:\*', '', shacl_text)
        
        # Remove empty property blocks
        shacl_text = re.sub(r'sh:property\s+\[\s*\];', '', shacl_text, flags=re.MULTILINE)
        shacl_text = re.sub(r'sh:property\s+\[\s*\]\s*\.', '', shacl_text, flags=re.MULTILINE)
        
        # Ensure proper property blocks if we have properties
        # If no valid properties found, add a basic one
        if "sh:property" not in shacl_text or "sh:path proc:" not in shacl_text:
            # Add a basic property constraint for rawText (common for clauses)
            basic_property = f"""
    sh:property [
        sh:path proc:rawText ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "{class_name} should have raw text content" ;
        sh:severity sh:Warning ;
    ]"""
            # Insert before the closing period
            if shacl_text.rstrip().endswith('.'):
                shacl_text = shacl_text.rstrip()[:-1] + ' ;' + basic_property + ' .'
            else:
                shacl_text = shacl_text.rstrip() + basic_property + ' .'
        
        # Clean up multiple semicolons
        shacl_text = re.sub(r';\s*;+', ';', shacl_text)
        
        # Ensure proper line breaks
        shacl_text = re.sub(r'\.\s*([a-zA-Z])', r'.\n\1', shacl_text)
        
        return shacl_text.strip()
    
    def _validate_shacl(self, shacl_text: str) -> tuple[bool, int]:
        """Validate SHACL syntax by parsing."""
        try:
            g = Graph()
            g.parse(data=shacl_text, format="turtle")
            return True, len(g)
        except Exception as e:
            logger.warning(f"SHACL validation failed: {e}")
            return False, 0

    def get_generated_shapes(self) -> list[Path]:
        """List all generated SHACL shape files."""
        return list(self.output_dir.glob("*.ttl"))
