"""
Pattern Detection Agent - Detects patterns in clauses for rule generation.

Detects:
- Risk patterns (termination risk, financial risk, etc.)
- Compliance patterns (EU requirements, US federal requirements, etc.)
- Obligation patterns (payment obligations, delivery obligations, etc.)
- Contract classification patterns (high value, high risk, etc.)
"""

from typing import Any
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.schema_evolution.rule_generator import RulePattern
from logger import get_module_logger

logger = get_module_logger(__name__)


class DetectedPattern(BaseModel):
    """Represents a detected pattern that should become a rule."""
    
    pattern_type: str = Field(description="Type: Risk, Compliance, Obligation, Classification")
    pattern_name: str = Field(description="Name of the pattern")
    condition_class: str = Field(description="Class to check (e.g., proc:TerminationClause)")
    condition_property: str = Field(description="Property to check (e.g., proc:noticePeriod)")
    condition_operator: str = Field(description="Operator: lessThan, greaterThan, equal, exists, in")
    condition_value: Any = Field(description="Value to compare against")
    inferred_property: str = Field(description="Property to set (e.g., proc:hasRiskLevel)")
    inferred_value: Any = Field(description="Value to infer")
    description: str = Field(description="Human-readable description")
    confidence: float = Field(default=0.8, description="Confidence in pattern (0-1)")
    occurrences: int = Field(default=1, description="Number of times pattern was seen")


class PatternDetectionResult(BaseModel):
    """Result of pattern detection."""
    
    patterns: list[DetectedPattern] = Field(default_factory=list)
    total_patterns: int = Field(default=0)


class PatternDetectionAgent(BaseAgent):
    """
    Agent for detecting patterns in contract clauses that should become inference rules.
    
    Analyzes:
    - Clause attributes and values
    - Contract properties
    - Relationships between clauses and contracts
    - Compliance requirements
    - Obligation structures
    """
    
    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.logger = logger.bind(component="PatternDetectionAgent")
    
    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> PatternDetectionResult:
        """
        Process input data to detect patterns (implements BaseAgent interface).
        
        Args:
            input_data: Dict with 'clauses' and optionally 'contracts'
        
        Returns:
            PatternDetectionResult
        """
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation()
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        
        clauses = input_data.get("clauses", [])
        contracts = input_data.get("contracts", [])
        return await self.detect_patterns(clauses=clauses, contracts=contracts)
    
    async def detect_patterns(
        self,
        clauses: list[dict[str, Any]],
        contracts: list[dict[str, Any]] | None = None,
    ) -> PatternDetectionResult:
        """
        Detect patterns in clauses and contracts.
        
        Args:
            clauses: List of clause dictionaries with:
                - clause_type: str
                - attributes: dict[str, Any]
                - raw_text: str
            contracts: Optional list of contract dictionaries with:
                - contract_id: str
                - contract_value: float | None
                - governed_by: str | None
                - clauses: list[str] (clause IDs)
        
        Returns:
            PatternDetectionResult with detected patterns
        """
        self.log_start("pattern_detection", clause_count=len(clauses))
        
        patterns: list[DetectedPattern] = []
        
        # 1. Risk Patterns
        risk_patterns = self._detect_risk_patterns(clauses)
        patterns.extend(risk_patterns)
        
        # 2. Compliance Patterns
        compliance_patterns = self._detect_compliance_patterns(clauses, contracts or [])
        patterns.extend(compliance_patterns)
        
        # 3. Obligation Patterns
        obligation_patterns = self._detect_obligation_patterns(clauses)
        patterns.extend(obligation_patterns)
        
        # 4. Classification Patterns
        classification_patterns = self._detect_classification_patterns(contracts or [])
        patterns.extend(classification_patterns)
        
        result = PatternDetectionResult(
            patterns=patterns,
            total_patterns=len(patterns),
        )
        
        # Record output for explanation
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("total_patterns", len(patterns))
            self.explanation_builder.add_metadata("risk_patterns_count", len(risk_patterns))
            self.explanation_builder.add_metadata("compliance_patterns_count", len(compliance_patterns))
            self.explanation_builder.add_metadata("obligation_patterns_count", len(obligation_patterns))
            self.explanation_builder.add_metadata("classification_patterns_count", len(classification_patterns))
            self.explanation_builder.set_process_description(
                f"Detected {len(patterns)} patterns across {len(clauses)} clauses: "
                f"{len(risk_patterns)} risk, {len(compliance_patterns)} compliance, "
                f"{len(obligation_patterns)} obligation, {len(classification_patterns)} classification patterns."
            )
            self._save_explanation()
        
        self.log_complete(
            "pattern_detection",
            total_patterns=len(patterns),
            risk_patterns=len(risk_patterns),
            compliance_patterns=len(compliance_patterns),
            obligation_patterns=len(obligation_patterns),
            classification_patterns=len(classification_patterns),
        )
        
        return result
    
    def _detect_risk_patterns(self, clauses: list[dict[str, Any]]) -> list[DetectedPattern]:
        """Detect risk-related patterns."""
        patterns = []
        
        for clause in clauses:
            clause_type = clause.get("clause_type", "")
            attributes = clause.get("attributes", {})
            
            # Termination Risk Pattern
            if "Termination" in clause_type and "notice_period" in attributes:
                notice_period = attributes.get("notice_period")
                if isinstance(notice_period, (int, float)):
                    if notice_period < 30:
                        patterns.append(DetectedPattern(
                            pattern_type="Risk",
                            pattern_name="HighTerminationRisk",
                            condition_class=f"proc:{clause_type}",
                            condition_property="proc:noticePeriod",
                            condition_operator="lessThan",
                            condition_value=30,
                            inferred_property="proc:introducesRisk",
                            inferred_value="proc:HighTerminationRisk",
                            description=f"Termination clause with notice period < 30 days indicates high risk",
                            confidence=0.9,
                        ))
                    elif notice_period >= 90:
                        patterns.append(DetectedPattern(
                            pattern_type="Risk",
                            pattern_name="LowTerminationRisk",
                            condition_class=f"proc:{clause_type}",
                            condition_property="proc:noticePeriod",
                            condition_operator="greaterThanOrEqual",
                            condition_value=90,
                            inferred_property="proc:introducesRisk",
                            inferred_value="proc:LowTerminationRisk",
                            description=f"Termination clause with notice period >= 90 days indicates low risk",
                            confidence=0.85,
                        ))
            
            # Financial Risk Pattern
            if "Penalty" in clause_type and "penalty_amount" in attributes:
                penalty_amount = attributes.get("penalty_amount")
                if isinstance(penalty_amount, (int, float)) and penalty_amount > 100000:
                    patterns.append(DetectedPattern(
                        pattern_type="Risk",
                        pattern_name="HighFinancialRisk",
                        condition_class=f"proc:{clause_type}",
                        condition_property="proc:penaltyAmount",
                        condition_operator="greaterThan",
                        condition_value=100000,
                        inferred_property="proc:introducesRisk",
                        inferred_value="proc:HighFinancialRisk",
                        description=f"Penalty clause with amount > $100,000 indicates high financial risk",
                        confidence=0.9,
                    ))
            
            # Data Protection Risk
            if "Data" in clause_type and "data_residency" in attributes:
                requires_eu = attributes.get("requires_eu_data_residency", False)
                if not requires_eu:
                    patterns.append(DetectedPattern(
                        pattern_type="Risk",
                        pattern_name="DataResidencyRisk",
                        condition_class=f"proc:{clause_type}",
                        condition_property="proc:requiresEUDataResidency",
                        condition_operator="equal",
                        condition_value=False,
                        inferred_property="proc:introducesRisk",
                        inferred_value="proc:DataResidencyRisk",
                        description="Data clause without EU residency requirement may indicate compliance risk",
                        confidence=0.75,
                    ))
        
        return patterns
    
    def _detect_compliance_patterns(
        self,
        clauses: list[dict[str, Any]],
        contracts: list[dict[str, Any]],
    ) -> list[DetectedPattern]:
        """Detect compliance-related patterns."""
        patterns = []
        
        # Build contract lookup
        contract_lookup = {c.get("contract_id"): c for c in contracts}
        
        for clause in clauses:
            clause_type = clause.get("clause_type", "")
            attributes = clause.get("attributes", {})
            contract_id = clause.get("contract_id")
            contract = contract_lookup.get(contract_id) if contract_id else None
            
            # EU Termination Compliance
            if contract and contract.get("governed_by") == "EU":
                if "Termination" in clause_type and "notice_period" in attributes:
                    notice_period = attributes.get("notice_period")
                    if isinstance(notice_period, (int, float)) and notice_period < 30:
                        patterns.append(DetectedPattern(
                            pattern_type="Compliance",
                            pattern_name="EUTerminationCompliance",
                            condition_class="proc:Contract",
                            condition_property="proc:governedBy",
                            condition_operator="equal",
                            condition_value="proc:EU",
                            inferred_property="proc:hasComplianceIssue",
                            inferred_value="proc:EUTerminationNotice",
                            description="EU contracts require minimum 30 days termination notice",
                            confidence=0.95,
                        ))
            
            # US Federal Indemnification Requirement
            if contract and contract.get("governed_by") == "US":
                contract_value = contract.get("contract_value")
                if contract_value and contract_value >= 250000:
                    # Check if contract has indemnification clause
                    has_indemnification = any(
                        "Indemnification" in c.get("clause_type", "")
                        for c in clauses
                        if c.get("contract_id") == contract_id
                    )
                    if not has_indemnification:
                        patterns.append(DetectedPattern(
                            pattern_type="Compliance",
                            pattern_name="USFederalIndemnificationRequired",
                            condition_class="proc:Contract",
                            condition_property="proc:contractValue",
                            condition_operator="greaterThanOrEqual",
                            condition_value=250000,
                            inferred_property="proc:hasComplianceIssue",
                            inferred_value="proc:USIndemnificationRequired",
                            description="US federal contracts >= $250k require indemnification clause",
                            confidence=0.9,
                        ))
        
        return patterns
    
    def _detect_obligation_patterns(self, clauses: list[dict[str, Any]]) -> list[DetectedPattern]:
        """Detect obligation-related patterns."""
        patterns = []
        
        for clause in clauses:
            clause_type = clause.get("clause_type", "")
            
            # Payment Obligation Pattern
            if "Payment" in clause_type:
                patterns.append(DetectedPattern(
                    pattern_type="Obligation",
                    pattern_name="PaymentObligationDerivation",
                    condition_class=f"proc:{clause_type}",
                    condition_property="rdf:type",
                    condition_operator="exists",
                    condition_value=True,
                    inferred_property="proc:createsObligation",
                    inferred_value="proc:PaymentObligation",
                    description=f"{clause_type} creates payment obligation",
                    confidence=0.95,
                ))
            
            # Delivery Obligation Pattern
            if "Delivery" in clause_type or "Service" in clause_type:
                patterns.append(DetectedPattern(
                    pattern_type="Obligation",
                    pattern_name="DeliveryObligationDerivation",
                    condition_class=f"proc:{clause_type}",
                    condition_property="rdf:type",
                    condition_operator="exists",
                    condition_value=True,
                    inferred_property="proc:createsObligation",
                    inferred_value="proc:DeliveryObligation",
                    description=f"{clause_type} creates delivery/service obligation",
                    confidence=0.85,
                ))
        
        return patterns
    
    def _detect_classification_patterns(
        self,
        contracts: list[dict[str, Any]],
    ) -> list[DetectedPattern]:
        """Detect contract classification patterns."""
        patterns = []
        
        # High Value Contract Pattern
        high_value_count = sum(
            1 for c in contracts
            if c.get("contract_value") and c.get("contract_value") >= 1000000
        )
        if high_value_count > 0:
            patterns.append(DetectedPattern(
                pattern_type="Classification",
                pattern_name="HighValueContract",
                condition_class="proc:Contract",
                condition_property="proc:contractValue",
                condition_operator="greaterThanOrEqual",
                condition_value=1000000,
                inferred_property="rdf:type",
                inferred_value="proc:HighValueContract",
                description="Contract with value >= $1M is classified as high value",
                confidence=0.95,
                occurrences=high_value_count,
            ))
        
        # Medium Value Contract Pattern
        medium_value_count = sum(
            1 for c in contracts
            if c.get("contract_value")
            and 100000 <= c.get("contract_value") < 1000000
        )
        if medium_value_count > 0:
            patterns.append(DetectedPattern(
                pattern_type="Classification",
                pattern_name="MediumValueContract",
                condition_class="proc:Contract",
                condition_property="proc:contractValue",
                condition_operator="greaterThanOrEqual",
                condition_value=100000,
                inferred_property="rdf:type",
                inferred_value="proc:MediumValueContract",
                description="Contract with value between $100k and $1M is classified as medium value",
                confidence=0.9,
                occurrences=medium_value_count,
            ))
        
        return patterns
    
    def patterns_to_rule_patterns(
        self,
        patterns: list[DetectedPattern],
    ) -> list[RulePattern]:
        """Convert DetectedPattern to RulePattern for rule generation."""
        rule_patterns = []
        
        for pattern in patterns:
            rule_patterns.append(RulePattern(
                pattern_name=pattern.pattern_name,
                condition_class=pattern.condition_class,
                condition_property=pattern.condition_property,
                condition_operator=pattern.condition_operator,
                condition_value=pattern.condition_value,
                inferred_property=pattern.inferred_property,
                inferred_value=pattern.inferred_value,
                description=pattern.description,
            ))
        
        return rule_patterns
