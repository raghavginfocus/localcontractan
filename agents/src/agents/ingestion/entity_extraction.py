"""
Entity Extraction Agent - Extracts parties, dates, amounts, and jurisdictions from contracts.
"""

from typing import Any
from datetime import datetime

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field, field_validator

from agents.shared.base import BaseAgent


class Party(BaseModel):
    """Represents a party to a contract."""
    
    party_id: str = Field(description="Unique identifier for the party")
    name: str = Field(description="Full legal name of the party")
    role: str = Field(description="Role in contract: Buyer, Supplier, Contractor, etc.")
    address: str | None = Field(default=None, description="Address if mentioned")
    contact_info: dict[str, str] = Field(
        default_factory=dict, description="Contact information"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names or abbreviations"
    )
    
    @field_validator("contact_info", mode="before")
    @classmethod
    def normalize_contact_info(cls, v: Any) -> dict[str, str]:
        """Convert None values and nested structures in contact_info dict to strings."""
        if v is None:
            return {}
        if isinstance(v, dict):
            # Flatten nested structures to strings
            result = {}
            for k, val in v.items():
                if val is None:
                    result[k] = ""
                elif isinstance(val, (list, dict)):
                    # Convert complex types to JSON string
                    import json
                    result[k] = json.dumps(val)
                else:
                    result[k] = str(val)
            return result
        return {}
    
    @field_validator("aliases", mode="before")
    @classmethod
    def normalize_aliases(cls, v: Any) -> list[str]:
        """Convert None to empty list for aliases."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            return [v]  # Single string becomes list
        return []


class ContractDate(BaseModel):
    """Represents a significant date in a contract."""
    
    date_type: str = Field(description="Type: EffectiveDate, ExpirationDate, SigningDate, etc.")
    date_value: str | None = Field(default=None, description="ISO format date if specific")
    date_description: str = Field(description="Human-readable description")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring date")
    reference_clause: str | None = Field(default=None, description="Clause that defines this date")


class MonetaryAmount(BaseModel):
    """Represents a monetary value in a contract."""
    
    amount_id: str = Field(description="Unique identifier")
    amount_type: str = Field(
        description="Type: ContractValue, PenaltyAmount, Threshold, etc."
    )
    value: float | str | None = Field(
        default=None, description="Numeric value if extractable, or text description if not"
    )
    currency: str = Field(default="USD", description="Currency code")
    description: str = Field(description="Context of the amount")
    is_estimate: bool = Field(
        default=False, description="Whether this is an estimate"
    )
    reference_clause: str | None = Field(default=None, description="Source clause")
    
    @field_validator('value', mode='before')
    @classmethod
    def parse_value(cls, v):
        """Parse value - accept float, string, or None."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        # If it's a string that can't be parsed as number, keep it as string
        # This handles cases like "double of the contract value"
        if isinstance(v, str):
            try:
                return float(v.replace(',', '').replace('$', '').strip())
            except (ValueError, AttributeError):
                # Keep as string if not parseable
                return v
        return v
    
    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, v: Any) -> str:
        """Ensure currency is always a string, default to USD."""
        if v is None or v == "":
            return "USD"
        if isinstance(v, str):
            return v.upper()  # Normalize to uppercase
        return "USD"


class Jurisdiction(BaseModel):
    """Represents a jurisdiction or governing law."""
    
    jurisdiction_id: str = Field(description="Unique identifier")
    name: str = Field(
        description="Jurisdiction name (e.g., State of Delaware)"
    )
    jurisdiction_type: str = Field(
        default="Unknown",
        description="Type: State, Country, Federal, etc."
    )
    applies_to: str = Field(
        default="GoverningLaw",
        description="What this jurisdiction governs"
    )
    
    @field_validator("jurisdiction_type", mode="before")
    @classmethod
    def normalize_jurisdiction_type(cls, v: Any) -> str:
        """Ensure jurisdiction_type is never None."""
        if v is None or v == "":
            return "Unknown"
        return str(v)


class EntityExtractionResult(BaseModel):
    """Result of entity extraction."""
    
    document_id: str = Field(description="ID of the source document")
    parties: list[Party] = Field(
        default_factory=list, description="Extracted parties"
    )
    dates: list[ContractDate] = Field(
        default_factory=list, description="Extracted dates"
    )
    amounts: list[MonetaryAmount] = Field(
        default_factory=list, description="Extracted amounts"
    )
    jurisdictions: list[Jurisdiction] = Field(
        default_factory=list, description="Extracted jurisdictions"
    )
    contract_title: str | None = Field(
        default=None, description="Title of the contract"
    )
    contract_type: str | None = Field(
        default=None, description="Type of contract"
    )
    
    @field_validator("parties", "dates", "amounts", "jurisdictions", mode="before")
    @classmethod
    def normalize_lists(cls, v: Any) -> list:
        """Convert None to empty list for all list fields."""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []


class EntityExtractionAgent(BaseAgent):
    """
    Agent for extracting named entities from procurement contracts.
    
    Extracts:
    - Parties: Buyer, Supplier, Contractors, Third parties
    - Dates: Effective, Expiration, Deadlines, Milestones
    - Amounts: Contract value, Penalties, Thresholds
    - Jurisdictions: Governing law, Dispute resolution venues
    """

    EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert legal analyst specializing in contract entity extraction.
Extract all named entities from the contract text.

For PARTIES, identify:
- Full legal names
- Roles (Buyer, Supplier, Contractor, Vendor, Client, etc.)
- Addresses and contact info if present
- Any aliases or abbreviated names used

For DATES, identify:
- Effective date (when contract starts)
- Expiration date (when contract ends)
- Signing date
- Milestone dates
- Deadline dates
- Payment due dates

For MONETARY AMOUNTS, identify:
- Total contract value
- Payment amounts
- Penalty amounts
- Thresholds and limits
- Insurance coverage amounts

For JURISDICTIONS, identify:
- Governing law (which state/country law applies)
- Arbitration venue
- Court jurisdiction for disputes

Return your response as a JSON object with this structure:
{{
    "contract_title": "IT Services Agreement",
    "contract_type": "Services Agreement",
    "parties": [
        {{
            "party_id": "party_1",
            "name": "ABC Corporation",
            "role": "Buyer",
            "address": "123 Main St, City, State 12345",
            "contact_info": {{"email": "contact@abc.com"}},
            "aliases": ["ABC", "the Company"]
        }}
    ],
    "dates": [
        {{
            "date_type": "EffectiveDate",
            "date_value": "2024-01-01",
            "date_description": "Contract becomes effective January 1, 2024",
            "is_recurring": false,
            "reference_clause": "Section 2.1"
        }}
    ],
    "amounts": [
        {{
            "amount_id": "amt_1",
            "amount_type": "ContractValue",
            "value": 500000.00,
            "currency": "USD",
            "description": "Total contract value for 12-month term",
            "is_estimate": false,
            "reference_clause": "Section 4.1"
        }}
    ],
    "jurisdictions": [
        {{
            "jurisdiction_id": "jur_1",
            "name": "State of Delaware",
            "jurisdiction_type": "State",
            "applies_to": "GoverningLaw"
        }}
    ]
}}
"""),
        ("human", """Extract all entities from this contract text:

Document ID: {document_id}
{structural_hints_block}
Contract Text:
{contract_text}

Extract all parties, dates, amounts, and jurisdictions. Return as JSON."""),
    ])

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs: Any,
    ) -> EntityExtractionResult:
        """
        Extract entities from contract text.
        
        Args:
            input_data: Dict with 'document_id' and 'text' keys
            
        Returns:
            EntityExtractionResult with extracted entities
        """
        document_id = input_data.get("document_id", "unknown")
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=document_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(input_data)
        text = input_data.get("text", "")
        structural_hints = input_data.get("structural_hints", {})
        
        self.log_start("entity_extraction", document_id=document_id, text_length=len(text))
        
        # Build structural hints block for the prompt (empty string if no hints)
        hints_block = self._format_structural_hints(structural_hints)
        
        # Create the chain
        parser = JsonOutputParser()
        chain = self.EXTRACTION_PROMPT | self.llm | parser
        
        try:
            result = await chain.ainvoke({
                "document_id": document_id,
                "contract_text": text[:30000],
                "structural_hints_block": hints_block,
            })
            
            # Parse entities
            parties = [
                Party(**p) for p in result.get("parties", [])
            ]
            dates = [
                ContractDate(**d) for d in result.get("dates", [])
            ]
            amounts = [
                MonetaryAmount(**a) for a in result.get("amounts", [])
            ]
            jurisdictions = [
                Jurisdiction(**j) for j in result.get("jurisdictions", [])
            ]
            
            extraction_result = EntityExtractionResult(
                document_id=document_id,
                parties=parties,
                dates=dates,
                amounts=amounts,
                jurisdictions=jurisdictions,
                contract_title=result.get("contract_title"),
                contract_type=result.get("contract_type"),
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(extraction_result)
                entity_count = len(parties) + len(dates) + len(amounts) + len(jurisdictions)
                self.explanation_builder.add_metadata("parties_count", len(parties))
                self.explanation_builder.add_metadata("dates_count", len(dates))
                self.explanation_builder.add_metadata("amounts_count", len(amounts))
                self.explanation_builder.add_metadata("jurisdictions_count", len(jurisdictions))
                self.explanation_builder.add_metadata("total_entities", entity_count)
                
                # Add process description
                process_desc = (
                    f"Extracted {entity_count} entities from document: "
                    f"{len(parties)} parties, {len(dates)} dates, "
                    f"{len(amounts)} monetary amounts, {len(jurisdictions)} jurisdictions."
                )
                self.explanation_builder.set_process_description(process_desc)
                
                # Add coverage analysis
                items_covered = []
                if len(parties) > 0:
                    items_covered.append(f"{len(parties)} parties")
                if len(dates) > 0:
                    items_covered.append(f"{len(dates)} dates")
                if len(amounts) > 0:
                    items_covered.append(f"{len(amounts)} monetary amounts")
                if len(jurisdictions) > 0:
                    items_covered.append(f"{len(jurisdictions)} jurisdictions")
                
                items_missed = []
                if len(amounts) == 0:
                    items_missed.append("Monetary amounts (contract value, penalties, etc.)")
                
                self.explanation_builder.set_coverage_analysis({
                    "items_covered": items_covered,
                    "items_missed": items_missed,
                    "coverage_percentage": (entity_count / max(1, entity_count)) * 100 if entity_count > 0 else 0,
                })
                
                # Save explanation
                self._save_explanation()
            
            self.log_complete(
                "entity_extraction",
                document_id=document_id,
                parties=len(parties),
                dates=len(dates),
                amounts=len(amounts),
                jurisdictions=len(jurisdictions),
            )
            
            return extraction_result
            
        except Exception as e:
            self.log_error("entity_extraction", e, document_id=document_id)
            raise

    def get_buyer(self, result: EntityExtractionResult) -> Party | None:
        """Get the buyer party from extraction result."""
        for party in result.parties:
            if party.role.lower() in ["buyer", "client", "customer", "purchaser"]:
                return party
        return None

    def get_supplier(self, result: EntityExtractionResult) -> Party | None:
        """Get the supplier party from extraction result."""
        for party in result.parties:
            if party.role.lower() in ["supplier", "vendor", "contractor", "provider", "seller"]:
                return party
        return None

    def get_contract_value(self, result: EntityExtractionResult) -> MonetaryAmount | None:
        """Get the main contract value from extraction result."""
        for amount in result.amounts:
            if amount.amount_type.lower() in ["contractvalue", "contract_value", "total_value", "totalvalue"]:
                return amount
        return None

    def get_effective_date(self, result: EntityExtractionResult) -> ContractDate | None:
        """Get the effective date from extraction result."""
        for date in result.dates:
            if date.date_type.lower() in ["effectivedate", "effective_date", "start_date", "startdate"]:
                return date
        return None

    def get_expiration_date(self, result: EntityExtractionResult) -> ContractDate | None:
        """Get the expiration date from extraction result."""
        for date in result.dates:
            if date.date_type.lower() in ["expirationdate", "expiration_date", "end_date", "enddate", "termination_date"]:
                return date
        return None

    @staticmethod
    def _format_structural_hints(hints: dict[str, Any]) -> str:
        """Format DocTags structural hints into a prompt block."""
        if not hints:
            return ""

        parts: list[str] = ["\nDocument Structure Hints (from layout analysis):"]
        titles = hints.get("section_titles", [])
        if titles:
            parts.append(f"  Section headings found: {', '.join(titles)}")

        bold_terms = hints.get("bold_terms", [])
        if bold_terms:
            parts.append(f"  Bold/emphasized terms: {', '.join(bold_terms[:15])}")

        table_summaries = hints.get("table_summaries", [])
        if table_summaries:
            parts.append(f"  Tables: {'; '.join(table_summaries)}")

        total = hints.get("total_sections", 0)
        if total:
            parts.append(f"  Total sections: {total}")

        if len(parts) == 1:
            return ""
        return "\n".join(parts) + "\n"
