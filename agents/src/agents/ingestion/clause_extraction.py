"""
Clause Extraction Agent - Identifies and classifies contract clauses.
"""

from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator

from agents.shared.base import BaseAgent


class ExtractedClause(BaseModel):
    """Represents an extracted clause from a contract."""
    
    clause_id: str = Field(description="Unique identifier for the clause")
    clause_type: str = Field(description="Type of clause (e.g., TerminationClause, PaymentClause)")
    section_number: str | None = Field(default=None, description="Section number if present")
    title: str | None = Field(default=None, description="Clause title if present")
    raw_text: str = Field(description="Original text of the clause")
    summary: str = Field(description="Brief 5-10 sentence summary of the clause")
    key_points: list[str] = Field(
        default_factory=list,
        description="Key points (5-10 bullets) capturing important terms",
    )
    structured_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value summary (JSON) for filters/audit",
    )
    attributes: dict[str, Any] = Field(default_factory=dict, description="Extracted attributes")
    
    @field_validator("structured_summary", "attributes", mode="before")
    @classmethod
    def normalize_dict_fields(cls, v: Any) -> dict[str, Any]:
        """Convert None to empty dict for dict fields."""
        if v is None:
            return {}
        return v if isinstance(v, dict) else {}
    
    @field_validator("key_points", mode="before")
    @classmethod
    def normalize_list_fields(cls, v: Any) -> list[str]:
        """Convert None to empty list for list fields."""
        if v is None:
            return []
        return v if isinstance(v, list) else []


class ClauseExtractionResult(BaseModel):
    """Result of clause extraction."""
    
    document_id: str = Field(description="ID of the source document")
    clauses: list[ExtractedClause] = Field(default_factory=list, description="Extracted clauses")
    unclassified_sections: list[str] = Field(
        default_factory=list, 
        description="Sections that couldn't be classified"
    )


class ClauseExtractionAgent(BaseAgent):
    """
    Agent for identifying and classifying clauses in procurement contracts.
    
    Clause Types Recognized:
    - TerminationClause: Contract termination conditions
    - PaymentClause: Payment terms and conditions
    - PenaltyClause: Penalties for breach or delay
    - ConfidentialityClause: Non-disclosure provisions
    - IndemnificationClause: Liability and indemnification
    - ForceMAjEURE: Force majeure provisions
    - GoverningLawClause: Jurisdiction and governing law
    - DisputeResolutionClause: Dispute handling procedures
    - WarrantyClause: Warranties and guarantees
    - InsuranceClause: Insurance requirements
    - ComplianceClause: Regulatory compliance requirements
    
    Attributes Extracted:
    - notice_period: Days of notice required
    - payment_terms: Payment schedule
    - penalty_amount: Financial penalties
    - jurisdiction: Governing jurisdiction
    """

    EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert legal analyst specializing in contract analysis.
Your task is to extract and classify clauses from ANY type of contract document.

CRITICAL: You must be THOROUGH and extract ALL information. Missing information is a critical failure.

For each clause you identify, provide:
1. A descriptive clause_type (e.g., "TerminationClause", "PaymentClause", "ConfidentialityClause", "IndemnityClause", etc.)
   - Use clear, semantic names that describe the clause's purpose
   - Follow PascalCase naming convention (e.g., "IntellectualPropertyClause")
   - IMPORTANT: If a clause mentions data protection, privacy, or confidentiality, classify it as "ConfidentialityClause" NOT "GeneralClause"
   - IMPORTANT: If a clause mentions payment, fees, or billing, classify it as "PaymentClause"
2. The section number if present
3. The title if present
4. The full raw text of the clause
5. A brief 4-8 sentence summary explaining what the clause does
6. Key points as 5-10 bullet strings capturing key terms, numbers, dates, thresholds
7. A structured_summary JSON object with key fields (use null if unknown). Include:
   - notice_period_days, payment_days, liability_limit, governing_law, jurisdiction, venue,
     limitation_period_days, renewal_terms, confidentiality_duration, termination_conditions
8. Key attributes as a dictionary - THIS IS CRITICAL - extract ALL structured data:

   FOR TerminationClause:
   - notice_period: MUST extract the number of days (e.g., 15, 30, 90)
   - notice_period_days: Alternative field name
   - termination_conditions: List of conditions (convenience, breach, default, etc.)
   - termination_method: How termination is executed
   - cancellation_charge: Any fees for termination
   
   FOR PaymentClause:
   - payment_terms: Full payment terms description
   - payment_days: Number of days for payment (e.g., "net 30" = 30)
   - payment_schedule: When payments are due
   - late_fee: Late payment penalties
   - payment_method: How payment is made
   
   FOR ConfidentialityClause:
   - confidentiality_scope: What information is confidential
   - disclosure_exceptions: When disclosure is allowed
   - duration: How long confidentiality lasts
   - return_obligation: Whether information must be returned
   
   FOR PenaltyClause:
   - penalty_amount: Monetary penalty amount
   - penalty_percentage: Percentage-based penalty
   - penalty_conditions: When penalty applies
   
   FOR LiabilityClause:
   - liability_limit: Maximum liability amount
   - liability_exclusions: What's excluded
   - indemnification: Indemnification requirements

Guidelines:
- Discover clause types dynamically based on the document content
- Don't limit yourself to predefined categories - identify ALL meaningful clauses
- BE THOROUGH: Extract ALL structured attributes - missing notice periods, payment terms, etc. is a critical error
- If text mentions "days", "weeks", "months" in context of notice/termination, extract it as notice_period
- If text mentions payment terms like "net 30", "within 15 days", extract it as payment_days
- If text mentions data protection, privacy, confidentiality, non-disclosure, classify as ConfidentialityClause
- If a section doesn't constitute a meaningful clause, note it in unclassified_sections
- Double-check your extraction - missing structured data is worse than no extraction

Return your response as a JSON object with this structure:
{{
    "clauses": [
        {{
            "clause_id": "cl_1",
            "clause_type": "TerminationClause",
            "section_number": "12.1",
            "title": "Termination for Convenience",
            "raw_text": "Either party may terminate...",
            "summary": "Allows either party to terminate with 30 days notice",
            "key_points": [
                "Either party may terminate",
                "30 days written notice required"
            ],
            "structured_summary": {{
                "notice_period_days": 30,
                "termination_conditions": ["convenience", "breach"]
            }},
            "attributes": {{
                "notice_period": 30,
                "notice_period_days": 30,
                "termination_conditions": ["convenience", "breach"]
            }}
        }}
    ],
    "unclassified_sections": ["Section 25 appears to be boilerplate..."]
}}
"""),
        ("human", """Extract and classify clauses from this contract text:

Document ID: {document_id}

Contract Text:
{contract_text}

Extract all identifiable clauses and return as JSON."""),
    ])

    async def process(
        self,
        input_data: dict[str, Any],
    ) -> ClauseExtractionResult:
        """
        Extract clauses from contract text.
        
        Args:
            input_data: Dict with 'document_id' and 'text' keys
            
        Returns:
            ClauseExtractionResult with extracted clauses
        """
        document_id = input_data.get("document_id", "unknown")
        text = input_data.get("text", "")
        
        # Auto-record input in explanation
        if self.enable_explanations:
            self._init_explanation(context_id=document_id)
            self._record_input(input_data)
        
        self.log_start("clause_extraction", document_id=document_id, text_length=len(text))
        
        # For very long documents, process in chunks
        if len(text) > 30000:
            return await self._process_long_document(document_id, text)
        
        # Create the chain
        parser = JsonOutputParser()
        chain = self.EXTRACTION_PROMPT | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "document_id": document_id,
                "contract_text": text,
            })
            
            # Parse clauses - normalize None values to empty dicts
            clauses = []
            for clause_data in result.get("clauses", []):
                # Normalize None values to empty dicts for dict fields
                if clause_data.get("structured_summary") is None:
                    clause_data["structured_summary"] = {}
                if clause_data.get("attributes") is None:
                    clause_data["attributes"] = {}
                if clause_data.get("key_points") is None:
                    clause_data["key_points"] = []
                clauses.append(ExtractedClause(**clause_data))
            
            extraction_result = ClauseExtractionResult(
                document_id=document_id,
                clauses=clauses,
                unclassified_sections=result.get("unclassified_sections", []),
            )
            
            # Auto-record output and add coverage analysis
            if self.enable_explanations and self.explanation_builder:
                self._record_output(extraction_result)
                
                # Analyze coverage - check for common clause types
                found_types = set(c.clause_type for c in clauses)
                expected_types = ["TerminationClause", "PaymentClause", "ConfidentialityClause", 
                                "WarrantyClause", "LiabilityClause", "GoverningLawClause"]
                
                for clause_type in expected_types:
                    self.explanation_builder.add_coverage(
                        clause_type,
                        clause_type in found_types,
                        f"{'Found' if clause_type in found_types else 'Not found'} in document"
                    )
                
                # Check for notice periods in termination clauses
                termination_clauses = [c for c in clauses if c.clause_type == "TerminationClause"]
                if termination_clauses:
                    has_notice = any(
                        "notice" in str(c.attributes).lower() or 
                        "period" in str(c.attributes).lower() or
                        "days" in str(c.attributes).lower()
                        for c in termination_clauses
                    )
                    if not has_notice:
                        self.explanation_builder.add_gap(
                            "Notice period extraction",
                            "Termination clauses found but notice periods not extracted from attributes"
                        )
                
                # Add reasoning
                self.explanation_builder.add_decision(
                    "Clause extraction strategy",
                    f"Used LLM-based extraction to identify {len(clauses)} clauses",
                    alternatives_considered=["Rule-based extraction", "Template matching"]
                )
                
                # Set confidence
                if len(clauses) > 0:
                    self.explanation_builder.set_confidence("high" if len(clauses) > 5 else "medium")
                else:
                    self.explanation_builder.set_confidence("low")
                
                # Save explanation
                self._save_explanation()
            
            self.log_complete(
                "clause_extraction",
                document_id=document_id,
                clause_count=len(clauses),
            )
            
            return extraction_result
            
        except Exception as e:
            self.log_error("clause_extraction", e, document_id=document_id)
            raise

    async def _process_long_document(
        self,
        document_id: str,
        text: str,
    ) -> ClauseExtractionResult:
        """Process a long document in chunks."""
        # Simple chunking by paragraphs
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            if current_length + len(para) > 25000:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = len(para)
            else:
                current_chunk.append(para)
                current_length += len(para)
        
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        # Process each chunk
        all_clauses = []
        all_unclassified = []
        
        for i, chunk in enumerate(chunks):
            chunk_result = await self.process({
                "document_id": f"{document_id}_chunk_{i}",
                "text": chunk,
            })
            
            # Renumber clause IDs to avoid conflicts
            for clause in chunk_result.clauses:
                clause.clause_id = f"cl_{document_id}_{len(all_clauses) + 1}"
                all_clauses.append(clause)
            
            all_unclassified.extend(chunk_result.unclassified_sections)
        
        return ClauseExtractionResult(
            document_id=document_id,
            clauses=all_clauses,
            unclassified_sections=all_unclassified,
        )

    def get_termination_clauses(
        self, 
        result: ClauseExtractionResult,
    ) -> list[ExtractedClause]:
        """Filter for termination clauses only."""
        return [c for c in result.clauses if c.clause_type == "TerminationClause"]

    def get_high_risk_clauses(
        self,
        result: ClauseExtractionResult,
    ) -> list[ExtractedClause]:
        """Identify clauses with potential high risk indicators."""
        high_risk_types = {
            "TerminationClause",
            "PenaltyClause",
            "IndemnificationClause",
            "LimitationOfLiabilityClause",
        }
        return [c for c in result.clauses if c.clause_type in high_risk_types]
