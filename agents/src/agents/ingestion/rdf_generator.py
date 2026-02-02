"""
RDF Generator Agent - Converts extracted contract data to RDF/Turtle format.

NOW USES DYNAMIC ONTOLOGY MANAGER for class/property URIs.

Generates:
- Contract entities with proper OWL types
- Clause entities with rdfs:label and proc:rawText
- Structured properties (notice periods, values, dates)
- Relationships (hasClause, hasParty, etc.)
"""

from datetime import datetime
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, XSD, OWL

from agents.shared.base import BaseAgent
from agents.ingestion.clause_extraction import (
    ExtractedClause,
    ClauseExtractionResult
)
from agents.ingestion.obligation_risk import (
    ObligationRiskResult,
    Obligation,
    Risk
)
from ontology_manager import get_ontology_manager


# Namespaces
PROC = Namespace("http://procurement.kg/ontology#")
CONTRACT = Namespace("http://procurement.kg/contract#")


class RDFGenerationResult(BaseModel):
    """Result of RDF generation."""
    
    document_id: str = Field(description="Source document ID")
    turtle: str = Field(description="Generated Turtle/RDF content")
    triple_count: int = Field(description="Number of triples generated")
    entity_counts: dict[str, int] = Field(default_factory=dict, description="Count of each entity type")
    validation_errors: list[str] = Field(default_factory=list, description="Any validation issues")


class RDFGeneratorAgent(BaseAgent):
    """
    Agent for generating RDF/Turtle from extracted contract data.
    
    NOW USES DYNAMIC ONTOLOGY MANAGER - no hardcoded class mappings!
    
    Features:
    - Generates OWL-compliant RDF
    - Creates proper entity URIs (dynamically resolved)
    - Extracts and structures attributes
    - Supports incremental generation
    - Validates output syntax
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        # Get ontology manager instance
        self.ontology_manager = get_ontology_manager()
    
    def _get_class_uri(self, class_name: str) -> URIRef:
        """Get URI for a class name from ontology manager."""
        uri = self.ontology_manager.get_active_schema().get_class_uri(class_name)
        if uri:
            return URIRef(uri)
        # Fallback to PROC namespace
        return PROC[class_name]
    
    def _get_property_uri(self, property_name: str) -> URIRef:
        """Get URI for a property name from ontology manager."""
        uri = self.ontology_manager.get_active_schema().get_property_uri(
            property_name
        )
        if uri:
            return URIRef(uri)
        # Fallback to PROC namespace
        return PROC[property_name]

    ATTRIBUTE_EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at extracting structured data from legal text.
Your task is CRITICAL - missing structured data is a serious error.

Extract ALL specific numeric and date values from the clause text. Be THOROUGH and don't miss anything.

FOR TerminationClause - MUST extract:
- notice_period or notice_period_days: Number of days for notice (e.g., "15 days" = 15, "thirty days" = 30, "2 weeks" = 14)
- termination_conditions: List of conditions (convenience, breach, default, etc.)
- cancellation_charge: Any fees

FOR PaymentClause - MUST extract:
- payment_terms: Full description (e.g., "net 30", "within 15 days")
- payment_days: Number of days (e.g., "net 30" = 30, "within 15 days" = 15)
- payment_schedule: When payments are due
- late_fee: Late payment penalties
- interest_rate: Interest on late payments

FOR PenaltyClause - MUST extract:
- penalty_amount: Monetary amount
- penalty_percentage: Percentage-based penalty
- penalty_conditions: When penalty applies

FOR LiabilityClause - MUST extract:
- liability_limit: Maximum liability amount
- liability_exclusions: What's excluded

FOR ConfidentialityClause - MUST extract:
- confidentiality_scope: What information is confidential
- duration: How long confidentiality lasts

IMPORTANT:
- Look for phrases like "X days", "X weeks", "X months" and extract the number
- Look for "net X", "within X days", "X day notice" and extract X
- Look for dollar amounts, percentages, dates
- If text says "15 days notice" extract notice_period: 15
- If text says "net 30" extract payment_days: 30
- Be thorough - missing data is worse than no extraction

Return ONLY a JSON object with the values found. Use null if not present.

Example output:
{{
    "notice_period": 30,
    "notice_period_days": 30,
    "payment_days": 45,
    "payment_terms": "net 45",
    "penalty_percentage": 1.5,
    "penalty_amount": 5000.00,
    "currency": "USD",
    "warranty_months": 24,
    "effective_date": "2024-01-01",
    "expiration_date": "2026-12-31"
}}
"""),
        ("human", """Extract ALL structured values from this {clause_type} text. Be thorough - missing data is a critical error.

{clause_text}

Return only the JSON object with extracted values. Extract EVERYTHING you can find."""),
    ])

    async def process(self, input_data: dict[str, Any]) -> RDFGenerationResult:
        """
        Generate RDF from extracted contract data.
        
        Args:
            input_data: Dict containing:
                - document_id: str
                - contract_info: dict (title, value, dates, parties)
                - clauses: ClauseExtractionResult or list[ExtractedClause]
                - obligations_risks: ObligationRiskResult (optional)
        
        Returns:
            RDFGenerationResult with Turtle content
        """
        document_id = input_data.get("document_id", "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            input_summary = {
                "document_id": document_id,
                "has_contract_info": bool(input_data.get("contract_info")),
                "has_clauses": bool(input_data.get("clauses")),
                "has_obligations_risks": bool(input_data.get("obligations_risks")),
            }
            if isinstance(input_data.get("clauses"), list):
                input_summary["clause_count"] = len(input_data.get("clauses", []))
            elif hasattr(input_data.get("clauses"), "clauses"):
                input_summary["clause_count"] = len(input_data.get("clauses").clauses)
            self.explanation_builder.set_input(input_summary)
        
        document_id = input_data.get("document_id", f"doc_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        contract_info = input_data.get("contract_info", {})
        clauses = input_data.get("clauses", [])
        # Support both old format (obligations_risks object) and new format (separate lists)
        obligations_risks = input_data.get("obligations_risks")
        obligations = input_data.get("obligations", [])
        risks = input_data.get("risks", [])
        
        # If obligations_risks object provided, extract from it
        if obligations_risks:
            obligations = getattr(obligations_risks, "obligations", obligations)
            risks = getattr(obligations_risks, "risks", risks)
        
        self.log_start("rdf_generation", document_id=document_id)
        
        # Create RDF graph
        g = Graph()
        g.bind("proc", PROC)
        g.bind("contract", CONTRACT)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)
        g.bind("owl", OWL)
        
        entity_counts = {"Contract": 0, "Clause": 0, "Party": 0, "Obligation": 0, "Risk": 0}
        validation_errors = []
        
        # Generate contract entity
        contract_uri = self._add_contract(g, document_id, contract_info)
        entity_counts["Contract"] = 1
        
        # Handle clauses (could be ClauseExtractionResult or list)
        if isinstance(clauses, ClauseExtractionResult):
            clause_list = clauses.clauses
        else:
            clause_list = clauses
        
        # Generate clause entities
        for i, clause in enumerate(clause_list):
            clause_uri = await self._add_clause(g, contract_uri, clause, i + 1)
            entity_counts["Clause"] += 1
        
        # Generate parties if present
        parties = contract_info.get("parties", [])
        for party in parties:
            self._add_party(g, contract_uri, party)
            entity_counts["Party"] += 1
        
        # Generate obligations and risks if present
        if obligations:
            for obl in obligations:
                self._add_obligation(g, contract_uri, obl)
                entity_counts["Obligation"] += 1
        
        if risks:
            for risk in risks:
                self._add_risk(g, contract_uri, risk)
                entity_counts["Risk"] += 1
        
        # Serialize to Turtle
        turtle = g.serialize(format="turtle")
        triple_count = len(g)
        
        # Validate the generated RDF
        try:
            test_graph = Graph()
            test_graph.parse(data=turtle, format="turtle")
        except Exception as e:
            validation_errors.append(f"RDF validation error: {str(e)}")
        
        result = RDFGenerationResult(
            document_id=document_id,
            turtle=turtle,
            triple_count=triple_count,
            entity_counts=entity_counts,
            validation_errors=validation_errors,
        )
        
        # Record output for explanation
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("entity_counts", entity_counts)
            self.explanation_builder.add_metadata("validation_errors_count", len(validation_errors))
            self._save_explanation()
        
        self.log_complete(
            "rdf_generation",
            document_id=document_id,
            triple_count=triple_count,
            entities=entity_counts,
        )
        
        return result

    def _add_contract(
        self,
        g: Graph,
        document_id: str,
        contract_info: dict,
    ) -> URIRef:
        """Add contract entity to graph."""
        contract_id = contract_info.get("id", document_id.replace("doc_", "Contract_"))
        contract_uri = CONTRACT[contract_id]
        
        # Type
        g.add((contract_uri, RDF.type, PROC.Contract))
        
        # Label
        title = contract_info.get("title", f"Contract {contract_id}")
        g.add((contract_uri, RDFS.label, Literal(title)))
        
        # Value
        if "value" in contract_info:
            value = self._safe_parse_number(contract_info["value"])
            if value is not None:
                g.add((contract_uri, PROC.contractValue, Literal(value, datatype=XSD.decimal)))
        
        # Dates
        if "effective_date" in contract_info:
            g.add((contract_uri, PROC.effectiveDate, Literal(contract_info["effective_date"], datatype=XSD.date)))
        if "expiration_date" in contract_info:
            g.add((contract_uri, PROC.expirationDate, Literal(contract_info["expiration_date"], datatype=XSD.date)))
        
        # Status
        status = contract_info.get("status", "Active")
        g.add((contract_uri, PROC.status, Literal(status)))
        
        # Jurisdiction
        if "jurisdiction" in contract_info:
            jurisdiction_uri = PROC[contract_info["jurisdiction"]]
            g.add((contract_uri, PROC.governedBy, jurisdiction_uri))
        
        return contract_uri

    async def _add_clause(
        self,
        g: Graph,
        contract_uri: URIRef,
        clause: ExtractedClause,
        index: int,
    ) -> URIRef:
        """Add clause entity to graph."""
        clause_id = clause.clause_id or f"Clause_{index:03d}"
        clause_uri = CONTRACT[clause_id]
        
        # Type - map to specific OWL class (dynamically)
        clause_type = clause.clause_type
        owl_class = self._get_class_uri(clause_type)
        g.add((clause_uri, RDF.type, owl_class))
        
        # Also add as general Clause subclass if different
        clause_base = self._get_class_uri("Clause")
        if owl_class != clause_base:
            g.add((clause_uri, RDF.type, clause_base))
        
        # Label
        label = clause.title or f"{clause_type} - {clause.section_number or index}"
        g.add((clause_uri, RDFS.label, Literal(label)))
        
        # Section number
        if clause.section_number:
            g.add((clause_uri, PROC.sectionNumber, Literal(clause.section_number)))
        
        # Raw text
        g.add((clause_uri, PROC.rawText, Literal(clause.raw_text)))
        
        # Summary
        if clause.summary:
            g.add((clause_uri, PROC.summary, Literal(clause.summary)))

        # Key points (repeatable)
        key_points = getattr(clause, "key_points", None) or []
        for kp in key_points:
            if kp and str(kp).strip():
                g.add((clause_uri, PROC.hasKeyPoint, Literal(str(kp).strip())))

        # Structured summary (stored as JSON string)
        structured = getattr(clause, "structured_summary", None) or {}
        if structured:
            import json

            g.add(
                (clause_uri, PROC.structuredSummary, Literal(json.dumps(structured)))
            )
        
        # Link to contract
        g.add((contract_uri, PROC.hasClause, clause_uri))
        
        # Extract and add structured attributes
        await self._add_clause_attributes(g, clause_uri, clause)
        
        return clause_uri

    def _safe_parse_number(self, value: Any, as_int: bool = False) -> float | int | None:
        """
        Safely parse a numeric value from various formats.
        
        Handles:
        - Already numeric values
        - Strings like "1.5% per month" → 1.5
        - Strings like "$500,000" → 500000
        - Strings like "30 days" → 30
        
        Returns None if parsing fails.
        """
        if value is None:
            return None
        
        # Already a number
        if isinstance(value, (int, float)):
            return int(value) if as_int else value
        
        # String parsing
        if isinstance(value, str):
            import re
            
            # Remove common currency symbols and commas
            cleaned = value.replace("$", "").replace("€", "").replace(",", "").strip()
            
            # Try to extract first number (including decimals)
            match = re.search(r"[-+]?\d*\.?\d+", cleaned)
            if match:
                try:
                    num = float(match.group())
                    return int(num) if as_int else num
                except ValueError:
                    pass
        
        return None

    def _extract_notice_period_from_text(self, text: str) -> int | None:
        """Extract notice period (in days) from clause text as fallback."""
        import re
        
        # Patterns to match notice periods
        patterns = [
            r"(\d+)\s*days?\s+notice",  # "30 days notice"
            r"notice\s+of\s+(\d+)\s*days?",  # "notice of 30 days"
            r"(\d+)\s*day\s+written\s+notice",  # "30 day written notice"
            r"(\d+)\s*weeks?\s+notice",  # "2 weeks notice" = 14 days
            r"(\d+)\s*months?\s+notice",  # "1 month notice" = 30 days
            r"(\d+)\s*days?\s+prior\s+notice",  # "30 days prior notice"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                days = int(match.group(1))
                # Convert weeks to days
                if "week" in match.group(0).lower():
                    days = days * 7
                # Convert months to days (approximate)
                elif "month" in match.group(0).lower():
                    days = days * 30
                return days
        
        return None

    async def _add_clause_attributes(
        self,
        g: Graph,
        clause_uri: URIRef,
        clause: ExtractedClause,
    ) -> None:
        """Extract and add structured attributes from clause."""
        # First use pre-extracted attributes
        attrs = clause.attributes or {}
        
        # CRITICAL: For key clause types, ALWAYS try LLM extraction if critical attributes are missing
        # This ensures we don't miss important structured data
        needs_llm_extraction = False
        
        if clause.clause_type == "TerminationClause":
            # Must have notice_period for termination clauses
            if not attrs.get("notice_period") and not attrs.get("notice_period_days"):
                needs_llm_extraction = True
                self.logger.warning(
                    "TerminationClause missing notice_period, attempting LLM extraction",
                    clause_id=clause.clause_id,
                )
        
        elif clause.clause_type == "PaymentClause":
            # Should have payment_terms or payment_days
            if not attrs.get("payment_terms") and not attrs.get("payment_days"):
                needs_llm_extraction = True
                self.logger.warning(
                    "PaymentClause missing payment information, attempting LLM extraction",
                    clause_id=clause.clause_id,
                )
        
        elif clause.clause_type in ("PenaltyClause", "LiabilityClause"):
            # Should have penalty or liability amounts
            if not attrs.get("penalty_amount") and not attrs.get("liability_limit"):
                needs_llm_extraction = True
        
        # Try LLM extraction if needed
        if needs_llm_extraction:
            try:
                llm_attrs = await self._extract_attributes_with_llm(clause)
                # Merge LLM-extracted attributes (don't overwrite existing)
                for key, value in llm_attrs.items():
                    if key not in attrs or not attrs[key]:
                        attrs[key] = value
                
                # CRITICAL: Update the clause object itself so the fix persists
                # This ensures the clause has the extracted attributes for later use
                if not clause.attributes:
                    clause.attributes = {}
                for key, value in llm_attrs.items():
                    if key not in clause.attributes or not clause.attributes[key]:
                        clause.attributes[key] = value
                
                self.logger.info(
                    "LLM attribute extraction completed and clause updated",
                    clause_type=clause.clause_type,
                    attributes_extracted=list(llm_attrs.keys()),
                    clause_id=clause.clause_id,
                )
            except Exception as e:
                self.logger.warning("LLM attribute extraction failed", error=str(e))
                # Record this as a gap in explanation if available
                if hasattr(self, 'explanation_builder') and self.explanation_builder:
                    self.explanation_builder.add_metadata(
                        f"attribute_extraction_gap_{clause.clause_type}",
                        f"LLM extraction failed: {str(e)}"
                    )
        
        # Add notice period
        if "notice_period" in attrs or "notice_period_days" in attrs:
            notice = attrs.get("notice_period") or attrs.get("notice_period_days")
            notice_val = self._safe_parse_number(notice, as_int=True)
            if notice_val is not None:
                g.add((clause_uri, PROC.noticePeriod, Literal(notice_val, datatype=XSD.integer)))
        
        # Add payment terms
        if "payment_terms" in attrs:
            g.add((clause_uri, PROC.paymentTerms, Literal(str(attrs["payment_terms"]))))
        if "payment_days" in attrs and attrs["payment_days"]:
            payment_days = self._safe_parse_number(attrs["payment_days"], as_int=True)
            if payment_days is not None:
                g.add((clause_uri, PROC.paymentDays, Literal(payment_days, datatype=XSD.integer)))
        
        # Add penalty info
        if "penalty_amount" in attrs and attrs["penalty_amount"]:
            penalty_amount = self._safe_parse_number(attrs["penalty_amount"])
            if penalty_amount is not None:
                g.add((clause_uri, PROC.penaltyAmount, Literal(penalty_amount, datatype=XSD.decimal)))
        if "penalty_percentage" in attrs and attrs["penalty_percentage"]:
            penalty_pct = self._safe_parse_number(attrs["penalty_percentage"])
            if penalty_pct is not None:
                g.add((clause_uri, PROC.penaltyPercentage, Literal(penalty_pct, datatype=XSD.decimal)))
        
        # Add interest rate (new - for late payment clauses)
        if "interest_rate" in attrs and attrs["interest_rate"]:
            interest = self._safe_parse_number(attrs["interest_rate"])
            if interest is not None:
                g.add((clause_uri, PROC.interestRate, Literal(interest, datatype=XSD.decimal)))
        
        # Add warranty period
        if "warranty_months" in attrs and attrs["warranty_months"]:
            warranty = self._safe_parse_number(attrs["warranty_months"], as_int=True)
            if warranty is not None:
                g.add((clause_uri, PROC.warrantyMonths, Literal(warranty, datatype=XSD.integer)))

    async def _extract_attributes_with_llm(self, clause: ExtractedClause) -> dict:
        """Use LLM to extract structured attributes from clause text."""
        from langchain_core.output_parsers import JsonOutputParser
        
        chain = self.ATTRIBUTE_EXTRACTION_PROMPT | self.llm | JsonOutputParser()
        
        result = await chain.ainvoke({
            "clause_type": clause.clause_type,
            "clause_text": clause.raw_text[:2000],  # Limit text length
        })
        
        return result or {}

    def _add_party(
        self,
        g: Graph,
        contract_uri: URIRef,
        party: dict,
    ) -> URIRef:
        """Add party entity to graph."""
        party_id = party.get("id", f"Party_{hash(party.get('name', ''))}")
        party_uri = CONTRACT[party_id]
        
        # Type
        party_type = party.get("type", "Party")  # Buyer, Supplier, etc.
        owl_class = PROC[party_type]
        g.add((party_uri, RDF.type, owl_class))
        
        # Label
        g.add((party_uri, RDFS.label, Literal(party.get("name", party_id))))
        
        # Link to contract
        g.add((contract_uri, PROC.hasParty, party_uri))
        
        return party_uri

    def _add_obligation(
        self,
        g: Graph,
        contract_uri: URIRef,
        obligation: Obligation,
    ) -> URIRef:
        """Add obligation entity to graph."""
        obl_uri = CONTRACT[obligation.obligation_id]
        
        g.add((obl_uri, RDF.type, PROC.Obligation))
        g.add((obl_uri, PROC.obligationType, Literal(obligation.obligation_type)))
        g.add((obl_uri, PROC.obligor, Literal(obligation.obligor)))
        g.add((obl_uri, PROC.obligee, Literal(obligation.obligee)))
        g.add((obl_uri, PROC.description, Literal(obligation.description)))
        
        if obligation.deadline:
            g.add((obl_uri, PROC.deadline, Literal(obligation.deadline)))
        
        g.add((contract_uri, PROC.hasObligation, obl_uri))
        
        return obl_uri

    def _add_risk(
        self,
        g: Graph,
        contract_uri: URIRef,
        risk: Risk,
    ) -> URIRef:
        """Add risk entity to graph."""
        risk_uri = CONTRACT[risk.risk_id]
        
        g.add((risk_uri, RDF.type, PROC.Risk))
        g.add((risk_uri, PROC.riskType, Literal(risk.risk_type)))
        g.add((risk_uri, PROC.severity, Literal(risk.severity)))
        g.add((risk_uri, PROC.description, Literal(risk.description)))
        g.add((risk_uri, PROC.likelihood, Literal(risk.likelihood)))
        
        g.add((contract_uri, PROC.hasRisk, risk_uri))
        
        return risk_uri

    def generate_from_text(
        self,
        contract_text: str,
        contract_info: dict,
    ) -> str:
        """
        Synchronous helper to generate basic RDF from contract text.
        Does not use LLM - just creates structure from provided info.
        """
        g = Graph()
        g.bind("proc", PROC)
        g.bind("contract", CONTRACT)
        
        contract_uri = self._add_contract(g, contract_info.get("id", "new_contract"), contract_info)
        
        return g.serialize(format="turtle")
