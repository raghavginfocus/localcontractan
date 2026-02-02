"""
Validation Agent - Validates RDF data against syntax and SHACL shapes.
"""

from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class ValidationError(BaseModel):
    """Represents a validation error."""
    
    error_type: str = Field(description="Type: SyntaxError, SHACLViolation, SchemaError")
    severity: str = Field(default="Error", description="Severity: Error, Warning, Info")
    message: str = Field(description="Human-readable error message")
    focus_node: str | None = Field(default=None, description="URI of the node with the error")
    property_path: str | None = Field(default=None, description="Property that caused the error")
    value: str | None = Field(default=None, description="Value that caused the error")
    source_constraint: str | None = Field(default=None, description="SHACL constraint that was violated")


class ValidationResult(BaseModel):
    """Result of RDF validation."""
    
    is_valid: bool = Field(description="Whether the RDF is valid")
    syntax_valid: bool = Field(default=True, description="Whether syntax is valid")
    shacl_valid: bool = Field(default=True, description="Whether SHACL constraints pass")
    errors: list[ValidationError] = Field(default_factory=list, description="List of errors")
    warnings: list[ValidationError] = Field(default_factory=list, description="List of warnings")
    triple_count: int = Field(default=0, description="Number of triples validated")
    validated_classes: list[str] = Field(default_factory=list, description="Classes found in data")


class ValidationAgent(BaseAgent):
    """
    Agent for validating RDF data.
    
    Performs:
    - Syntax validation (parseable Turtle/RDF)
    - SHACL constraint validation
    - Schema consistency checks
    """

    # Basic SHACL shapes embedded (for when no external shapes file)
    DEFAULT_SHAPES = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix proc: <http://procurement.kg/ontology#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Contract must have at least one clause
proc:ContractShape a sh:NodeShape ;
    sh:targetClass proc:Contract ;
    sh:property [
        sh:path proc:hasClause ;
        sh:minCount 1 ;
        sh:message "Contract must have at least one clause" ;
        sh:severity sh:Warning ;
    ] ;
    sh:property [
        sh:path rdfs:label ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
        sh:message "Contract should have a label" ;
        sh:severity sh:Warning ;
    ] .

# Termination clause should have notice period
proc:TerminationClauseShape a sh:NodeShape ;
    sh:targetClass proc:TerminationClause ;
    sh:property [
        sh:path proc:noticePeriod ;
        sh:datatype xsd:integer ;
        sh:minInclusive 1 ;
        sh:message "Notice period must be a positive integer" ;
        sh:severity sh:Warning ;
    ] ;
    sh:property [
        sh:path proc:rawText ;
        sh:minCount 1 ;
        sh:message "Clause should have raw text" ;
        sh:severity sh:Warning ;
    ] .

# Payment clause validation
proc:PaymentClauseShape a sh:NodeShape ;
    sh:targetClass proc:PaymentClause ;
    sh:property [
        sh:path proc:paymentDays ;
        sh:datatype xsd:integer ;
        sh:minInclusive 1 ;
        sh:maxInclusive 365 ;
        sh:message "Payment days should be between 1 and 365" ;
        sh:severity sh:Warning ;
    ] .

# Penalty clause validation
proc:PenaltyClauseShape a sh:NodeShape ;
    sh:targetClass proc:PenaltyClause ;
    sh:property [
        sh:path proc:penaltyPercentage ;
        sh:datatype xsd:decimal ;
        sh:minInclusive 0 ;
        sh:maxInclusive 100 ;
        sh:message "Penalty percentage should be between 0 and 100" ;
        sh:severity sh:Warning ;
    ] .
"""

    def __init__(self, shapes_path: str | None = None, **kwargs: Any):
        """
        Initialize the validation agent.
        
        Args:
            shapes_path: Optional path to SHACL shapes file
        """
        super().__init__(**kwargs)
        self.shapes_graph = self._load_shapes(shapes_path)
        self.settings = get_settings()
        self.PROC = Namespace(self.settings.procurement_namespace)

    def _load_shapes(self, shapes_path: str | None) -> Graph:
        """Load SHACL shapes from file or use defaults."""
        shapes = Graph()
        
        if shapes_path and Path(shapes_path).exists():
            shapes.parse(shapes_path, format="turtle")
            logger.info("Loaded SHACL shapes from file", path=shapes_path)
        else:
            shapes.parse(data=self.DEFAULT_SHAPES, format="turtle")
            logger.info("Using default SHACL shapes")
        
        return shapes

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> ValidationResult:
        """
        Validate RDF data.
        
        Args:
            input_data: Dict with 'rdf_data' (Turtle string) or 'graph' (RDFLib Graph)
            
        Returns:
            ValidationResult with errors and warnings
        """
        document_id = input_data.get("document_id", "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            input_summary = {
                "has_rdf_data": bool(input_data.get("rdf_data")),
                "has_graph": bool(input_data.get("graph")),
            }
            if input_data.get("rdf_data"):
                input_summary["rdf_data_length"] = len(str(input_data.get("rdf_data")))
            self.explanation_builder.set_input(input_summary)
        
        rdf_data = input_data.get("rdf_data")
        graph = input_data.get("graph")
        
        self.log_start("rdf_validation")
        
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []
        syntax_valid = True
        
        # Step 1: Parse RDF (syntax validation)
        if rdf_data and not graph:
            graph, syntax_errors = self._validate_syntax(rdf_data)
            if syntax_errors:
                syntax_valid = False
                errors.extend(syntax_errors)
        
        if not graph:
            return ValidationResult(
                is_valid=False,
                syntax_valid=False,
                shacl_valid=False,
                errors=errors,
                warnings=warnings,
                triple_count=0,
                validated_classes=[],
            )
        
        # Step 2: SHACL validation
        shacl_errors, shacl_warnings = self._validate_shacl(graph)
        errors.extend(shacl_errors)
        warnings.extend(shacl_warnings)
        shacl_valid = len(shacl_errors) == 0
        
        # Step 3: Schema consistency checks
        schema_errors = self._validate_schema_consistency(graph)
        errors.extend(schema_errors)
        
        # Get validated classes
        validated_classes = self._get_classes(graph)
        
        result = ValidationResult(
            is_valid=syntax_valid and shacl_valid and len(schema_errors) == 0,
            syntax_valid=syntax_valid,
            shacl_valid=shacl_valid,
            errors=errors,
            warnings=warnings,
            triple_count=len(graph),
            validated_classes=validated_classes,
        )
        
        # Record output for explanation
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("error_count", len(errors))
            self.explanation_builder.add_metadata("warning_count", len(warnings))
            self.explanation_builder.add_metadata("validated_classes_count", len(validated_classes))
            self._save_explanation()
        
        self.log_complete(
            "rdf_validation",
            is_valid=result.is_valid,
            error_count=len(errors),
            warning_count=len(warnings),
            triple_count=result.triple_count,
        )
        
        return result

    def _validate_syntax(self, rdf_data: str) -> tuple[Graph | None, list[ValidationError]]:
        """Validate RDF syntax by attempting to parse."""
        errors = []
        graph = Graph()
        
        try:
            graph.parse(data=rdf_data, format="turtle")
            return graph, []
        except Exception as e:
            errors.append(ValidationError(
                error_type="SyntaxError",
                severity="Error",
                message=f"Failed to parse Turtle: {str(e)}",
            ))
            return None, errors

    def _validate_shacl(self, graph: Graph) -> tuple[list[ValidationError], list[ValidationError]]:
        """Validate graph against SHACL shapes."""
        errors = []
        warnings = []
        
        try:
            # Try to use pyshacl if available
            from pyshacl import validate
            
            conforms, results_graph, results_text = validate(
                graph,
                shacl_graph=self.shapes_graph,
                inference="rdfs",
                abort_on_first=False,
            )
            
            if not conforms:
                # Parse SHACL results
                SH = Namespace("http://www.w3.org/ns/shacl#")
                
                for result in results_graph.subjects(RDF.type, SH.ValidationResult):
                    severity = str(results_graph.value(result, SH.resultSeverity) or "")
                    message = str(results_graph.value(result, SH.resultMessage) or "Unknown violation")
                    focus = str(results_graph.value(result, SH.focusNode) or "")
                    path = str(results_graph.value(result, SH.resultPath) or "")
                    value = str(results_graph.value(result, SH.value) or "")
                    
                    error = ValidationError(
                        error_type="SHACLViolation",
                        severity="Warning" if "Warning" in severity else "Error",
                        message=message,
                        focus_node=focus if focus else None,
                        property_path=path if path else None,
                        value=value if value else None,
                    )
                    
                    if "Warning" in severity:
                        warnings.append(error)
                    else:
                        errors.append(error)
                        
        except ImportError:
            # pyshacl not installed, do basic validation
            logger.warning("pyshacl not installed, skipping SHACL validation")
            warnings.append(ValidationError(
                error_type="SHACLViolation",
                severity="Warning",
                message="SHACL validation skipped - pyshacl not installed",
            ))
        except Exception as e:
            logger.error("SHACL validation error", error=str(e))
            warnings.append(ValidationError(
                error_type="SHACLViolation",
                severity="Warning",
                message=f"SHACL validation error: {str(e)}",
            ))
        
        return errors, warnings

    def _validate_schema_consistency(self, graph: Graph) -> list[ValidationError]:
        """Check for basic schema consistency issues."""
        errors = []
        
        # Check for contracts without clauses
        contract_query = """
            SELECT ?contract WHERE {
                ?contract a <http://procurement.kg/ontology#Contract> .
                FILTER NOT EXISTS { ?contract <http://procurement.kg/ontology#hasClause> ?clause }
            }
        """
        
        try:
            results = list(graph.query(contract_query))
            for row in results:
                errors.append(ValidationError(
                    error_type="SchemaError",
                    severity="Warning",
                    message="Contract has no clauses",
                    focus_node=str(row[0]),
                ))
        except Exception:
            pass  # Query failed, skip this check
        
        # Check for clauses without contracts
        orphan_query = """
            SELECT ?clause WHERE {
                ?clause a ?type .
                FILTER(CONTAINS(STR(?type), "Clause"))
                FILTER NOT EXISTS { ?contract <http://procurement.kg/ontology#hasClause> ?clause }
            }
        """
        
        try:
            results = list(graph.query(orphan_query))
            for row in results:
                errors.append(ValidationError(
                    error_type="SchemaError",
                    severity="Warning",
                    message="Clause is not linked to any contract",
                    focus_node=str(row[0]),
                ))
        except Exception:
            pass
        
        return errors

    def _get_classes(self, graph: Graph) -> list[str]:
        """Get all RDF types used in the graph."""
        query = """
            SELECT DISTINCT ?type WHERE {
                ?s a ?type .
            }
        """
        
        classes = []
        try:
            for row in graph.query(query):
                class_uri = str(row[0])
                # Extract local name
                if "#" in class_uri:
                    classes.append(class_uri.split("#")[-1])
                elif "/" in class_uri:
                    classes.append(class_uri.split("/")[-1])
                else:
                    classes.append(class_uri)
        except Exception:
            pass
        
        return classes

    def load_shacl_shape(self, shapes_path: str) -> None:
        """
        Load additional SHACL shape from file and merge with existing shapes.
        
        Args:
            shapes_path: Path to SHACL shapes file in Turtle format
        """
        try:
            from pathlib import Path
            if Path(shapes_path).exists():
                additional_shapes = Graph()
                additional_shapes.parse(shapes_path, format="turtle")
                
                # Merge with existing shapes
                for triple in additional_shapes:
                    self.shapes_graph.add(triple)
                
                logger.info("Loaded additional SHACL shape", path=shapes_path, total_triples=len(self.shapes_graph))
            else:
                logger.warning("SHACL shape file not found", path=shapes_path)
        except Exception as e:
            logger.error("Failed to load SHACL shape", path=shapes_path, error=str(e))
            raise

    def validate_turtle_string(self, turtle_data: str) -> ValidationResult:
        """Synchronous helper to validate a Turtle string."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.process({"rdf_data": turtle_data})
        )
