"""
Reasoning Agent - Triggers and manages Jena inference reasoning.

Integrates with Fuseki to apply OWL and custom rules for automatic fact inference.
"""

import re
from typing import Any
from pathlib import Path

from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from storage.sparql.base import SPARQLStore
from service_factory import get_service_factory
from config import Settings, get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class ReasoningResult(BaseModel):
    """Result of applying reasoning rules."""
    
    success: bool = Field(description="Whether reasoning completed successfully")
    inferred_triples: int = Field(
        default=0,
        description="Number of new triples inferred"
    )
    inferred_count: int = Field(
        default=0,
        description="Alias for inferred_triples (for backward compatibility)"
    )
    reasoning_time_ms: float = Field(
        default=0.0,
        description="Time taken for reasoning"
    )
    rules_applied: list[str] = Field(
        default_factory=list,
        description="Names of rules that fired"
    )
    error: str | None = Field(default=None, description="Error if failed")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure backward compatibility
        if "inferred_count" not in data and "inferred_triples" in data:
            self.inferred_count = self.inferred_triples
        elif "inferred_triples" not in data and "inferred_count" in data:
            self.inferred_triples = self.inferred_count


class ReasoningAgent(BaseAgent):
    """
    Agent for applying reasoning rules to infer new facts.
    
    Capabilities:
    - Apply Jena inference rules
    - Trigger OWL reasoning
    - Load custom rule files
    - Track inferred facts
    - Validate reasoning results
    """
    
    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        settings: Settings | None = None,
        **kwargs: Any,
    ):
        super().__init__(settings=settings, **kwargs)
        # Use dependency injection - get from service factory if not provided
        if sparql_store is None:
            service_factory = get_service_factory(settings=self.settings)
            sparql_store = service_factory.get_sparql_store()
        self.sparql_store = sparql_store
        # Backward compatibility (deprecated)
        self.fuseki_client = self.sparql_store
    
    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> ReasoningResult:
        """
        Apply reasoning rules to infer new facts.
        
        Args:
            input_data: Dict with:
                - graph_uri: Optional specific graph to reason over
                - rule_files: Optional list of rule file paths
                - reasoning_type: "jena" or "owl" (default: both)
                
        Returns:
            ReasoningResult with inference statistics
        """
        graph_uri = input_data.get("graph_uri")
        document_id = input_data.get("document_id", graph_uri or "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        rule_files = input_data.get("rule_files", [])
        reasoning_type = input_data.get("reasoning_type", "both")
        
        self.log_start("reasoning", graph_uri=graph_uri, type=reasoning_type)
        
        try:
            import time
            start_time = time.time()
            
            inferred_count = 0
            rules_applied = []
            
            # Apply Jena rules if requested
            if reasoning_type in ("jena", "both"):
                jena_result = await self._apply_jena_rules(
                    graph_uri, rule_files
                )
                inferred_count += jena_result["inferred"]
                rules_applied.extend(jena_result["rules"])
            
            # Apply OWL reasoning if requested
            if reasoning_type in ("owl", "both"):
                owl_result = await self._apply_owl_reasoning(graph_uri)
                inferred_count += owl_result["inferred"]
            
            reasoning_time = (time.time() - start_time) * 1000
            
            result = ReasoningResult(
                success=True,
                inferred_triples=inferred_count,
                inferred_count=inferred_count,  # For backward compatibility
                reasoning_time_ms=reasoning_time,
                rules_applied=rules_applied,
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("rules_applied_count", len(rules_applied))
                self.explanation_builder.add_metadata("reasoning_type", reasoning_type)
                self._save_explanation()
            
            self.log_complete(
                "reasoning",
                inferred=inferred_count,
                time_ms=reasoning_time,
                rules=len(rules_applied),
            )
            
            return result
            
        except Exception as e:
            self.log_error("reasoning", e)
            return ReasoningResult(
                success=False,
                error=str(e),
            )
    
    async def _apply_jena_rules(
        self,
        graph_uri: str | None,
        rule_files: list[str],
    ) -> dict[str, Any]:
        """Apply Jena inference rules."""
        # Get default rule file if none provided
        if not rule_files:
            default_rules = Path("rules/procurement.rules")
            if default_rules.exists():
                rule_files = [str(default_rules)]
        
        if not rule_files:
            # Only log if rules were expected (i.e., rule_files was explicitly provided as empty list)
            # Silent when no rules are configured at all
            return {"inferred": 0, "rules": []}
        
        inferred_count = 0
        rules_applied = []
        
        for rule_file in rule_files:
            rule_path = Path(rule_file)
            if not rule_path.exists():
                self.logger.warning(f"Rule file not found: {rule_file}")
                continue
            
            # Read rules and convert to SPARQL INSERT queries
            rules = self._parse_jena_rules(rule_path)
            
            for rule_name, sparql_query in rules.items():
                try:
                    # Execute SPARQL INSERT
                    self.sparql_store.execute_update(sparql_query)
                    rules_applied.append(rule_name)
                    
                    # Count inferred triples (approximate)
                    inferred_count += 1
                    
                except Exception as e:
                    self.logger.warning(
                        f"Failed to apply rule {rule_name}: {e}"
                    )
        
        return {"inferred": inferred_count, "rules": rules_applied}
    
    def _parse_jena_rules(self, rule_file: Path) -> dict[str, str]:
        """
        Parse Jena rules file and convert to SPARQL INSERT queries.
        
        This is a simplified parser. For production, use proper Jena API.
        """
        rules = {}
        
        with open(rule_file, 'r') as f:
            content = f.read()
        
        # Extract rule blocks [RuleName: ... -> ...]
        import re
        rule_pattern = r'\[(\w+):(.*?)->(.*?)\]'
        matches = re.findall(rule_pattern, content, re.DOTALL)
        
        for rule_name, premises, conclusions in matches:
            # Convert to SPARQL (simplified)
            sparql = self._rule_to_sparql(
                rule_name.strip(),
                premises.strip(),
                conclusions.strip()
            )
            if sparql:
                rules[rule_name.strip()] = sparql
        
        return rules
    
    def _rule_to_sparql(
        self,
        rule_name: str,
        premises: str,
        conclusions: str
    ) -> str | None:
        """
        Convert Jena rule syntax to SPARQL INSERT.
        
        This is a basic conversion. For complex rules, use Jena's native
        reasoning engine.
        """
        try:
            # Add prefixes
            sparql = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX proc: <http://procurement.kg/ontology#>

"""
            
            # Parse premises into WHERE clause
            where_patterns = []
            filters = []
            
            for line in premises.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # Handle triple patterns
                if line.startswith('(?'):
                    # Convert (?s ?p ?o) to SPARQL
                    triple = line.replace('(', '').replace(')', '')
                    where_patterns.append(f"    {triple} .")
                
                # Handle built-in predicates
                elif 'lessThan' in line:
                    # lessThan(?var, value) -> FILTER(?var < value)
                    match = re.search(r'lessThan\(\?(\w+),\s*(\d+)\)', line)
                    if match:
                        var, value = match.groups()
                        filters.append(f"    FILTER(?{var} < {value})")
                
                elif 'greaterThan' in line:
                    match = re.search(r'greaterThan\(\?(\w+),\s*(\d+)\)', line)
                    if match:
                        var, value = match.groups()
                        filters.append(f"    FILTER(?{var} > {value})")
                
                elif 'ge(' in line:
                    match = re.search(r'ge\(\?(\w+),\s*(\d+)\)', line)
                    if match:
                        var, value = match.groups()
                        filters.append(f"    FILTER(?{var} >= {value})")
            
            # Parse conclusions into INSERT clause
            insert_patterns = []
            for line in conclusions.split('\n'):
                line = line.strip()
                if line.startswith('(?'):
                    triple = line.replace('(', '').replace(')', '')
                    insert_patterns.append(f"    {triple} .")
            
            if not where_patterns or not insert_patterns:
                return None
            
            # Build complete SPARQL
            sparql += f"# Rule: {rule_name}\n"
            sparql += "INSERT {\n"
            sparql += "\n".join(insert_patterns)
            sparql += "\n}\nWHERE {\n"
            sparql += "\n".join(where_patterns)
            if filters:
                sparql += "\n" + "\n".join(filters)
            sparql += "\n    FILTER NOT EXISTS {\n"
            sparql += "\n".join(insert_patterns)
            sparql += "\n    }\n"
            sparql += "}"
            
            return sparql
            
        except Exception as e:
            self.logger.warning(
                f"Failed to convert rule {rule_name} to SPARQL: {e}"
            )
            return None
    
    async def _apply_owl_reasoning(
        self,
        graph_uri: str | None
    ) -> dict[str, Any]:
        """
        Apply OWL reasoning (RDFS+ inference).
        
        This uses SPARQL to implement basic RDFS inference.
        For full OWL reasoning, configure Fuseki with an OWL reasoner.
        """
        inferred_count = 0
        
        # Apply rdfs:subClassOf inference
        subclass_query = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

INSERT {
    ?instance rdf:type ?superClass .
}
WHERE {
    ?instance rdf:type ?subClass .
    ?subClass rdfs:subClassOf ?superClass .
    FILTER NOT EXISTS {
        ?instance rdf:type ?superClass .
    }
}
"""
        
        try:
            self.sparql_store.execute_update(subclass_query)
            inferred_count += 1
        except Exception as e:
            self.logger.warning(f"OWL reasoning failed: {e}")
        
        return {"inferred": inferred_count}
    
    def validate_reasoning(self, expected_inferences: list[dict]) -> bool:
        """
        Validate that expected inferences were made.
        
        Args:
            expected_inferences: List of dicts with 's', 'p', 'o' keys
            
        Returns:
            True if all expected inferences exist
        """
        for inference in expected_inferences:
            query = f"""
ASK {{
    <{inference['s']}> <{inference['p']}> <{inference['o']}> .
}}
"""
            result = self.sparql_store.execute_ask(query)
            if not result:
                self.logger.warning(
                    f"Expected inference not found: {inference}"
                )
                return False
        
        return True


