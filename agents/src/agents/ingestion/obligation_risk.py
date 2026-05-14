"""
Obligation and Risk Extraction Agent.
"""

import json
import re
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.ingestion.clause_extraction import ExtractedClause


class Obligation(BaseModel):
    """Represents a contractual obligation."""
    
    obligation_id: str = Field(description="Unique identifier")
    obligation_type: str = Field(description="Type: Payment, Delivery, Performance, Reporting, etc.")
    obligor: str = Field(description="Party who must fulfill the obligation")
    obligee: str = Field(description="Party who benefits from the obligation")
    description: str | None = Field(default=None, description="Description of the obligation")
    deadline: str | None = Field(default=None, description="Deadline if applicable")
    conditions: list[str] | None = Field(default=None, description="Conditions for the obligation")
    source_clause_id: str | None = Field(default=None, description="ID of the clause creating this obligation")


class Risk(BaseModel):
    """Represents a contract risk."""
    
    risk_id: str = Field(description="Unique identifier")
    risk_type: str = Field(
        description="Type: TerminationRisk, FinancialRisk, ComplianceRisk, OperationalRisk, etc."
    )
    severity: str = Field(description="Severity: Low, Medium, High, Critical")
    description: str | None = Field(default=None, description="Description of the risk")
    likelihood: str = Field(default="Unknown", description="Likelihood: Low, Medium, High")
    mitigation_strategies: list[str] | None = Field(
        default=None,
        description="Possible mitigation strategies",
    )
    source_clause_id: str | None = Field(default=None, description="ID of the clause introducing this risk")
    affected_party: str | None = Field(default=None, description="Party most affected by this risk")


class ObligationRiskResult(BaseModel):
    """Result of obligation and risk extraction."""
    
    document_id: str
    obligations: list[Obligation] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    summary: str = Field(default="", description="Executive summary of obligations and risks")


class ObligationRiskAgent(BaseAgent):
    """
    Agent for extracting obligations and risks from contract clauses.
    
    Analyzes clause text to identify:
    - Obligations (who must do what, when)
    - Risks (what could go wrong, how severe)
    - Conditions and triggers
    - Mitigation possibilities
    """

    EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert contract analyst specializing in obligation and risk assessment.

Analyze the provided contract clauses and extract:

1. OBLIGATIONS:
   - obligation_type: Payment, Delivery, Performance, Reporting, Compliance, Notification, Insurance, etc.
   - obligor: Party who must fulfill (Buyer, Seller, Supplier, Contractor, etc.)
   - obligee: Party who benefits
   - deadline: When it must be done (if specified)
   - conditions: Any conditions or triggers

2. RISKS:
   - risk_type: TerminationRisk, FinancialRisk, ComplianceRisk, OperationalRisk, ReputationalRisk, LegalRisk
   - severity: 
     * Critical: Could cause major financial loss or contract failure
     * High: Significant impact on operations or finances
     * Medium: Moderate impact, manageable
     * Low: Minor impact
   - likelihood: Low, Medium, High
   - mitigation_strategies: Practical ways to reduce the risk

Return as JSON:
{{
    "obligations": [...],
    "risks": [...],
    "summary": "Executive summary..."
}}
"""),
        ("human", """Analyze these contract clauses for obligations and risks:

Document ID: {document_id}

Clauses:
{clauses_text}

Extract all obligations and risks as JSON."""),
    ])

    async def process(
        self,
        input_data: dict[str, Any],
    ) -> ObligationRiskResult:
        """
        Extract obligations and risks from clauses.
        
        Args:
            input_data: Dict with 'document_id' and 'clauses' (list of ExtractedClause)
            
        Returns:
            ObligationRiskResult with extracted obligations and risks
        """
        document_id = input_data.get("document_id", "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        clauses: list[ExtractedClause] = input_data.get("clauses", [])
        
        self.log_start("obligation_risk_extraction", document_id=document_id, clause_count=len(clauses))
        
        if not clauses:
            return ObligationRiskResult(
                document_id=document_id,
                summary="No clauses provided for analysis.",
            )
        
        # Format clauses for the prompt
        clauses_text = self._format_clauses(clauses)
        
        # Remove JsonOutputParser - we'll handle JSON extraction manually
        chain = self.EXTRACTION_PROMPT | self.llm
        
        try:
            # Get raw LLM response
            raw_response = await chain.ainvoke({
                "document_id": document_id,
                "clauses_text": clauses_text,
            })
            
            # Extract content from AIMessage if needed
            if hasattr(raw_response, 'content'):
                response_text = raw_response.content
            else:
                response_text = str(raw_response)
            
            # Extract JSON from markdown or raw text
            result = self._extract_json_from_response(response_text)
            
            # Parse obligations with robust handling
            obligations = []
            for i, obl_data in enumerate(result.get("obligations", [])):
                try:
                    # Ensure required fields with defaults
                    obl_data["obligation_id"] = f"obl_{document_id}_{i + 1}"
                    obl_data.setdefault("description", obl_data.get("obligee", "Obligation"))
                    obl_data.setdefault("source_clause_id", f"clause_{document_id}")
                    obl_data.setdefault("obligor", "Party")
                    obl_data.setdefault("obligee", "Counterparty")
                    # Fix conditions if it's a string
                    if isinstance(obl_data.get("conditions"), str):
                        obl_data["conditions"] = [obl_data["conditions"]] if obl_data["conditions"] else []
                    obligations.append(Obligation(**obl_data))
                except Exception as e:
                    self.logger.warning("Failed to parse obligation", error=str(e), data=obl_data)
            
            # Parse risks with robust handling
            risks = []
            for i, risk_data in enumerate(result.get("risks", [])):
                try:
                    risk_data["risk_id"] = f"risk_{document_id}_{i + 1}"
                    # CRITICAL FIX: Ensure risk_type is always present
                    risk_data.setdefault("risk_type", "OperationalRisk")
                    risk_data.setdefault("description", risk_data.get("risk_type", "Risk"))
                    risk_data.setdefault("source_clause_id", f"clause_{document_id}")
                    risk_data.setdefault("severity", "Medium")
                    # Fix mitigation_strategies if it's a string
                    if isinstance(risk_data.get("mitigation_strategies"), str):
                        risk_data["mitigation_strategies"] = [risk_data["mitigation_strategies"]] if risk_data["mitigation_strategies"] else []
                    risks.append(Risk(**risk_data))
                except Exception as e:
                    self.logger.warning("Failed to parse risk", error=str(e), data=risk_data, agent=self.__class__.__name__)
            
            extraction_result = ObligationRiskResult(
                document_id=document_id,
                obligations=obligations,
                risks=risks,
                summary=result.get("summary", ""),
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(extraction_result)
                self.explanation_builder.add_metadata("obligation_count", len(obligations))
                self.explanation_builder.add_metadata("risk_count", len(risks))
                self._save_explanation()
            
            self.log_complete(
                "obligation_risk_extraction",
                document_id=document_id,
                obligation_count=len(obligations),
                risk_count=len(risks),
            )
            
            return extraction_result
            
        except Exception as e:
            self.log_error("obligation_risk_extraction", e, document_id=document_id)
            raise
    
    def _extract_json_from_response(self, response_text: str) -> dict[str, Any]:
        """
        Extract JSON from LLM response, handling markdown code blocks.
        
        Args:
            response_text: Raw LLM response text
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If no valid JSON found
        """
        # Try to find JSON in markdown code block first
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON in generic code block
        json_match = re.search(r'```\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Try to find raw JSON (look for outermost braces)
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # If all else fails, raise error with helpful message
        raise ValueError(
            f"No valid JSON found in LLM response. "
            f"Response preview: {response_text[:500]}..."
        )
    
    def _format_clauses(self, clauses: list[ExtractedClause]) -> str:
        """Format clauses for the LLM prompt."""
        parts = []
        for clause in clauses:
            part = f"""
--- Clause: {clause.clause_id} ---
Type: {clause.clause_type}
Section: {clause.section_number or 'N/A'}
Title: {clause.title or 'N/A'}
Text: {clause.raw_text}
---
"""
            parts.append(part)
        return "\n".join(parts)

    def get_high_severity_risks(self, result: ObligationRiskResult) -> list[Risk]:
        """Filter for high and critical severity risks."""
        return [r for r in result.risks if r.severity in ("High", "Critical")]

    def get_payment_obligations(self, result: ObligationRiskResult) -> list[Obligation]:
        """Filter for payment-related obligations."""
        return [o for o in result.obligations if o.obligation_type == "Payment"]

    def calculate_risk_score(self, result: ObligationRiskResult) -> float:
        """
        Calculate an overall risk score for the document.
        
        Score ranges from 0 (low risk) to 100 (high risk).
        """
        severity_weights = {
            "Low": 1,
            "Medium": 2,
            "High": 4,
            "Critical": 8,
        }
        
        likelihood_weights = {
            "Low": 1,
            "Medium": 2,
            "High": 3,
            "Unknown": 1.5,
        }
        
        total_score = 0
        max_possible = 0
        
        for risk in result.risks:
            severity = severity_weights.get(risk.severity, 2)
            likelihood = likelihood_weights.get(risk.likelihood, 1.5)
            total_score += severity * likelihood
            max_possible += 8 * 3  # Max severity * max likelihood
        
        if max_possible == 0:
            return 0
        
        return min(100, (total_score / max_possible) * 100)
