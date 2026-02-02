"""
Rule Generator Agent - Generates Jena inference rules for new patterns.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)

# Default output directory for generated rules
GENERATED_DIR = Path("data/generated")


class RulePattern(BaseModel):
    """Describes a pattern for rule generation."""
    
    pattern_name: str = Field(description="Name for the rule")
    condition_class: str = Field(description="Class to match (e.g., proc:DataProtectionClause)")
    condition_property: str = Field(description="Property to check (e.g., proc:dataRetentionPeriod)")
    condition_operator: str = Field(description="Comparison: lessThan, greaterThan, equals")
    condition_value: Any = Field(description="Value to compare against")
    inferred_property: str = Field(description="Property to add when rule fires")
    inferred_value: str = Field(description="Value to set")
    description: str = Field(default="", description="Human description of the rule")


class RuleGenerationResult(BaseModel):
    """Result of rule generation."""
    
    rule_name: str = Field(description="Name of the rule")
    rule_text: str = Field(description="Generated Jena rule syntax")
    sparql_equivalent: str = Field(description="Equivalent SPARQL INSERT for Fuseki")
    is_valid: bool = Field(default=False, description="Whether rule syntax is valid")
    file_path: str | None = Field(default=None, description="Path where rule was saved")
    error: str | None = Field(default=None, description="Error if generation failed")


class RuleSetResult(BaseModel):
    """Result of generating multiple rules."""
    
    rules: list[RuleGenerationResult] = Field(default_factory=list)
    combined_rules_path: str | None = Field(default=None)
    combined_sparql_path: str | None = Field(default=None)
    applied_to_fuseki: bool = Field(default=False)


class RuleGeneratorAgent(BaseAgent):
    """
    Agent for generating Jena inference rules.
    
    When new risk patterns or compliance requirements are identified,
    this agent generates:
    1. Jena rule syntax (for native Jena reasoning)
    2. SPARQL INSERT equivalent (for Fuseki HTTP API)
    
    Rules are saved to files for review and can be applied to Fuseki.
    """

    RULE_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert in Jena inference rules and SPARQL.
Generate inference rules for contract risk analysis.

EXISTING RULE PATTERNS:
```
[HighTerminationRisk:
    (?clause rdf:type proc:TerminationClause)
    (?clause proc:noticePeriod ?days)
    lessThan(?days, 30)
    ->
    (?clause proc:hasRiskLevel proc:HighTerminationRisk)
]
```

SPARQL EQUIVALENT:
```sparql
PREFIX proc: <http://procurement.kg/ontology#>
INSERT {{
    ?clause proc:hasRiskLevel proc:HighTerminationRisk .
}}
WHERE {{
    ?clause a proc:TerminationClause .
    ?clause proc:noticePeriod ?days .
    FILTER(?days < 30)
    FILTER NOT EXISTS {{ ?clause proc:hasRiskLevel proc:HighTerminationRisk }}
}}
```

Generate BOTH formats for the requested rule."""),
        ("human", """Generate a Jena rule and SPARQL equivalent for:

Rule Name: {rule_name}
Description: {description}
Condition: IF {condition_class} has {condition_property} {condition_operator} {condition_value}
Result: THEN add {inferred_property} = {inferred_value}

Output the Jena rule syntax first, then the SPARQL INSERT."""),
    ])

    def __init__(self, output_dir: Path | None = None, **kwargs: Any):
        """
        Initialize the rule generator.
        
        Args:
            output_dir: Directory for generated rule files
        """
        super().__init__(**kwargs)
        self.output_dir = output_dir or GENERATED_DIR / "rules"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings()

    async def process(
        self,
        input_data: dict[str, Any] | RulePattern,
        **kwargs: Any,
    ) -> RuleGenerationResult:
        """
        Generate a single inference rule.
        
        Args:
            input_data: RulePattern or dict with pattern fields
            
        Returns:
            RuleGenerationResult with generated rule
        """
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation()
        
        # Extract pattern
        if isinstance(input_data, RulePattern):
            pattern = input_data
        else:
            pattern = RulePattern(**input_data)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data if isinstance(input_data, dict) else pattern.model_dump())
        
        self.log_start("rule_generation", name=pattern.pattern_name)
        
        try:
            # Generate rule using LLM
            chain = self.RULE_PROMPT | self.llm | StrOutputParser()
            
            response = await chain.ainvoke({
                "rule_name": pattern.pattern_name,
                "description": pattern.description,
                "condition_class": pattern.condition_class,
                "condition_property": pattern.condition_property,
                "condition_operator": pattern.condition_operator,
                "condition_value": pattern.condition_value,
                "inferred_property": pattern.inferred_property,
                "inferred_value": pattern.inferred_value,
            })
            
            # Parse response to extract Jena rule and SPARQL
            jena_rule, sparql_rule = self._parse_response(response, pattern.pattern_name)
            
            # Validate syntax (basic check)
            is_valid = self._validate_rule(jena_rule, sparql_rule)
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rule_filename = f"{pattern.pattern_name.lower()}_{timestamp}.rules"
            sparql_filename = f"{pattern.pattern_name.lower()}_{timestamp}.sparql"
            
            rule_path = self.output_dir / rule_filename
            sparql_path = self.output_dir / sparql_filename
            
            with open(rule_path, "w") as f:
                f.write(f"# Generated Rule: {pattern.pattern_name}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Description: {pattern.description}\n\n")
                f.write(jena_rule)
            
            with open(sparql_path, "w") as f:
                f.write(f"# Generated SPARQL: {pattern.pattern_name}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Description: {pattern.description}\n\n")
                f.write(sparql_rule)
            
            result = RuleGenerationResult(
                rule_name=pattern.pattern_name,
                rule_text=jena_rule,
                sparql_equivalent=sparql_rule,
                is_valid=is_valid,
                file_path=str(rule_path),
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("name", pattern.pattern_name)
                self.explanation_builder.add_metadata("is_valid", is_valid)
                self.explanation_builder.add_metadata("file_path", str(rule_path))
                self.explanation_builder.set_process_description(
                    f"Generated inference rule '{pattern.pattern_name}' from pattern. "
                    f"Rule is {'valid' if is_valid else 'invalid'} and saved to {rule_path}. "
                    f"Rule infers {pattern.inferred_property} = {pattern.inferred_value} "
                    f"when {pattern.condition_class}.{pattern.condition_property} {pattern.condition_operator} {pattern.condition_value}."
                )
                self._save_explanation()
            
            self.log_complete(
                "rule_generation",
                name=pattern.pattern_name,
                is_valid=is_valid,
                file_path=str(rule_path),
            )
            
            return result
            
        except Exception as e:
            self.log_error("rule_generation", e, name=pattern.pattern_name)
            return RuleGenerationResult(
                rule_name=pattern.pattern_name,
                rule_text="",
                sparql_equivalent="",
                error=str(e),
            )

    async def generate_rules(
        self,
        patterns: list[RulePattern],
        apply_to_fuseki: bool = False,
    ) -> RuleSetResult:
        """
        Generate multiple rules and optionally apply to Fuseki.
        
        Args:
            patterns: List of rule patterns
            apply_to_fuseki: Whether to apply SPARQL rules to Fuseki
            
        Returns:
            RuleSetResult with all generated rules
        """
        self.log_start("rule_set_generation", pattern_count=len(patterns))
        
        rules = []
        combined_jena = []
        combined_sparql = []
        
        for pattern in patterns:
            result = await self.process(pattern)
            rules.append(result)
            
            if result.is_valid:
                combined_jena.append(result.rule_text)
                combined_sparql.append(result.sparql_equivalent)
        
        # Save combined files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        combined_rules_path = None
        if combined_jena:
            combined_rules_path = self.output_dir / f"combined_rules_{timestamp}.rules"
            with open(combined_rules_path, "w") as f:
                f.write(f"# Combined Generated Rules\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Rules: {len(combined_jena)}\n\n")
                f.write("\n\n".join(combined_jena))
        
        combined_sparql_path = None
        if combined_sparql:
            combined_sparql_path = self.output_dir / f"combined_rules_{timestamp}.sparql"
            with open(combined_sparql_path, "w") as f:
                f.write(f"# Combined Generated SPARQL Rules\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Rules: {len(combined_sparql)}\n\n")
                f.write("\n\n".join(combined_sparql))
        
        # Apply to Fuseki if requested
        applied = False
        if apply_to_fuseki and combined_sparql:
            applied = await self._apply_sparql_rules(combined_sparql)
        
        self.log_complete(
            "rule_set_generation",
            rules=len(rules),
            valid=[r.is_valid for r in rules].count(True),
            applied=applied,
        )
        
        return RuleSetResult(
            rules=rules,
            combined_rules_path=str(combined_rules_path) if combined_rules_path else None,
            combined_sparql_path=str(combined_sparql_path) if combined_sparql_path else None,
            applied_to_fuseki=applied,
        )

    async def generate_risk_rule(
        self,
        clause_type: str,
        property_name: str,
        threshold: Any,
        risk_level: str,
        comparison: str = "lessThan",
    ) -> RuleGenerationResult:
        """
        Convenience method to generate a risk classification rule.
        
        Args:
            clause_type: Type of clause (e.g., "DataProtectionClause")
            property_name: Property to check (e.g., "dataRetentionPeriod")
            threshold: Threshold value
            risk_level: Risk level to assign (e.g., "HighDataRetentionRisk")
            comparison: Comparison operator
            
        Returns:
            RuleGenerationResult
        """
        pattern = RulePattern(
            pattern_name=f"{risk_level}Rule",
            condition_class=f"proc:{clause_type}",
            condition_property=f"proc:{property_name}",
            condition_operator=comparison,
            condition_value=threshold,
            inferred_property="proc:hasRiskLevel",
            inferred_value=f"proc:{risk_level}",
            description=f"Classify {clause_type} as {risk_level} when {property_name} {comparison} {threshold}",
        )
        
        return await self.process(pattern)

    def _parse_response(self, response: str, rule_name: str) -> tuple[str, str]:
        """Parse LLM response to extract Jena rule and SPARQL."""
        jena_rule = ""
        sparql_rule = ""
        
        # Try to extract Jena rule
        if "[" in response and "]" in response:
            start = response.find("[")
            # Find matching ]
            bracket_count = 0
            end = start
            for i, char in enumerate(response[start:], start):
                if char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1
                    if bracket_count == 0:
                        end = i + 1
                        break
            jena_rule = response[start:end]
        
        # Try to extract SPARQL
        sparql_markers = ["INSERT", "PREFIX"]
        for marker in sparql_markers:
            if marker in response.upper():
                # Find the SPARQL block
                idx = response.upper().find(marker)
                # Extract from PREFIX or INSERT to end or next block
                sparql_text = response[idx:]
                
                # Clean up - find end of SPARQL (next blank line or end)
                lines = sparql_text.split("\n")
                sparql_lines = []
                in_sparql = True
                for line in lines:
                    if line.strip() and in_sparql:
                        sparql_lines.append(line)
                    elif not line.strip() and sparql_lines:
                        # Check if we're done (no more SPARQL keywords expected)
                        if "}" in sparql_lines[-1]:
                            break
                
                sparql_rule = "\n".join(sparql_lines)
                break
        
        # If parsing failed, create default templates
        if not jena_rule:
            jena_rule = f"""[{rule_name}:
    # Auto-generated rule template
    # Please review and customize
    (?subject ?predicate ?object)
    ->
    (?subject proc:hasRule proc:{rule_name})
]"""
        
        if not sparql_rule:
            sparql_rule = f"""PREFIX proc: <http://procurement.kg/ontology#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

# Auto-generated SPARQL template for {rule_name}
# Please review and customize
INSERT {{
    ?subject proc:hasRule proc:{rule_name} .
}}
WHERE {{
    ?subject ?predicate ?object .
    FILTER NOT EXISTS {{ ?subject proc:hasRule proc:{rule_name} }}
}}"""
        
        return jena_rule, sparql_rule

    def _validate_rule(self, jena_rule: str, sparql_rule: str) -> bool:
        """Basic validation of rule syntax."""
        # Check Jena rule has basic structure
        jena_valid = "[" in jena_rule and "]" in jena_rule and "->" in jena_rule
        
        # Check SPARQL has basic structure
        sparql_valid = "INSERT" in sparql_rule.upper() and "WHERE" in sparql_rule.upper()
        
        return jena_valid and sparql_valid

    async def _apply_sparql_rules(self, sparql_rules: list[str]) -> bool:
        """Apply SPARQL INSERT rules to Fuseki."""
        try:
            import httpx
            
            update_endpoint = self.settings.sparql_update_endpoint
            success_count = 0
            
            auth = None
            if self.settings.fuseki_user and self.settings.fuseki_password:
                auth = (self.settings.fuseki_user, self.settings.fuseki_password)
            
            async with httpx.AsyncClient(timeout=60.0, auth=auth) as client:
                for sparql in sparql_rules:
                    try:
                        response = await client.post(
                            update_endpoint,
                            data={"update": sparql},
                        )
                        if response.status_code in (200, 204):
                            success_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to apply rule: {e}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Failed to apply SPARQL rules: {e}")
            return False

    def get_generated_rules(self) -> list[Path]:
        """List all generated rule files."""
        return list(self.output_dir.glob("*.rules"))

    def get_generated_sparql(self) -> list[Path]:
        """List all generated SPARQL files."""
        return list(self.output_dir.glob("*.sparql"))
