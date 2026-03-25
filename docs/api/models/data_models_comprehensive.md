# Data Models API Reference

Comprehensive API documentation for Pydantic data models used throughout the Contract Knowledge Graph system.

## Overview

The system uses Pydantic models for data validation, serialization, and type safety. These models represent contracts, clauses, entities, and extraction results.

**Key Features:**
- Type validation with Pydantic
- Automatic serialization/deserialization
- Field validators for data normalization
- JSON schema generation
- Default value handling

---

## Clause Models

### ExtractedClause

Represents an extracted clause from a contract with comprehensive metadata.

```python
from agents.ingestion.clause_extraction import ExtractedClause

class ExtractedClause(BaseModel):
    """Represents an extracted clause from a contract."""
    
    clause_id: str
    clause_type: str
    section_number: str | None
    title: str | None
    raw_text: str
    summary: str
    key_points: list[str]
    structured_summary: dict[str, Any]
    attributes: dict[str, Any]
    section_title: str
    has_table: bool
    page_range: str
    source_section_id: str
```

**Fields:**

- **clause_id** : `str`
  - Unique identifier for the clause
  - Auto-generated if not provided (format: `cl_<8-char-hex>`)
  
- **clause_type** : `str`
  - Type of clause (e.g., `TerminationClause`, `PaymentClause`)
  - Defaults to `"UnknownClause"` if not provided
  - Common types: `TerminationClause`, `PaymentClause`, `ConfidentialityClause`, `PenaltyClause`, `IndemnificationClause`, `ForceMajeure`, `GoverningLawClause`, `DisputeResolutionClause`, `WarrantyClause`, `InsuranceClause`, `ComplianceClause`
  
- **section_number** : `str | None`
  - Section number if present (e.g., `"12.1"`, `"5.3.2"`)
  
- **title** : `str | None`
  - Clause title if present
  
- **raw_text** : `str`
  - Original text of the clause
  - Full verbatim text from document
  
- **summary** : `str`
  - Brief 5-10 sentence summary of the clause
  - Human-readable explanation
  
- **key_points** : `list[str]`
  - Key points (5-10 bullets) capturing important terms
  - Highlights critical information
  
- **structured_summary** : `dict[str, Any]`
  - Structured key-value summary (JSON) for filters/audit
  - Common keys: `notice_period_days`, `payment_days`, `liability_limit`, `governing_law`, `jurisdiction`, `venue`, `limitation_period_days`, `renewal_terms`, `confidentiality_duration`, `termination_conditions`
  
- **attributes** : `dict[str, Any]`
  - Extracted attributes specific to clause type
  - See clause-specific attributes below
  
- **section_title** : `str`
  - DocTags section heading this clause was found under
  
- **has_table** : `bool`
  - Whether this clause contains a table (from DocTags)
  
- **page_range** : `str`
  - Source page range from DocTags provenance (e.g., `"5-6"`)
  
- **source_section_id** : `str`
  - DocTags section ID for traceability

**Clause-Specific Attributes:**

**TerminationClause:**
```python
attributes = {
    "notice_period": 30,  # Days of notice required
    "notice_period_days": 30,  # Alternative field name
    "termination_conditions": ["convenience", "breach", "default"],
    "termination_method": "written notice",
    "cancellation_charge": 5000.00
}
```

**PaymentClause:**
```python
attributes = {
    "payment_terms": "Net 30 days from invoice date",
    "payment_days": 30,  # Number of days for payment
    "payment_schedule": "monthly",
    "late_fee": "1.5% per month",
    "payment_method": "wire transfer"
}
```

**ConfidentialityClause:**
```python
attributes = {
    "confidentiality_scope": "all business information",
    "disclosure_exceptions": ["legal requirement", "prior knowledge"],
    "duration": "5 years",
    "return_obligation": True
}
```

**PenaltyClause:**
```python
attributes = {
    "penalty_amount": 10000.00,
    "penalty_percentage": 5.0,
    "penalty_conditions": ["late delivery", "breach of warranty"]
}
```

**LiabilityClause:**
```python
attributes = {
    "liability_limit": 1000000.00,
    "liability_exclusions": ["indirect damages", "lost profits"],
    "indemnification": "mutual indemnification"
}
```

**Example:**

```python
from agents.ingestion.clause_extraction import ExtractedClause

# Create clause
clause = ExtractedClause(
    clause_id="cl_abc123",
    clause_type="TerminationClause",
    section_number="12.1",
    title="Termination for Convenience",
    raw_text="Either party may terminate this Agreement...",
    summary="Allows either party to terminate with 30 days notice.",
    key_points=[
        "Either party may terminate",
        "30 days written notice required",
        "No penalty for termination"
    ],
    structured_summary={
        "notice_period_days": 30,
        "termination_conditions": ["convenience"]
    },
    attributes={
        "notice_period": 30,
        "termination_conditions": ["convenience"],
        "termination_method": "written notice"
    },
    section_title="Termination",
    has_table=False,
    page_range="15-16",
    source_section_id="sec_5"
)

# Access fields
print(f"Type: {clause.clause_type}")
print(f"Notice period: {clause.attributes.get('notice_period')} days")
print(f"Summary: {clause.summary}")

# Serialize to JSON
clause_json = clause.model_dump_json()

# Deserialize from JSON
clause_restored = ExtractedClause.model_validate_json(clause_json)
```

**Validation:**

```python
# Auto-generates clause_id if missing
clause = ExtractedClause(
    clause_type="PaymentClause",
    raw_text="Payment due within 30 days",
    summary="Payment terms"
)
print(clause.clause_id)  # Output: cl_a1b2c3d4

# Defaults clause_type if missing
clause = ExtractedClause(
    raw_text="Some text",
    summary="Summary"
)
print(clause.clause_type)  # Output: UnknownClause

# Normalizes None to empty dict/list
clause = ExtractedClause(
    clause_type="TerminationClause",
    raw_text="Text",
    summary="Summary",
    attributes=None,  # Becomes {}
    key_points=None   # Becomes []
)
```

---

### ClauseExtractionResult

Result of clause extraction from a document.

```python
from agents.ingestion.clause_extraction import ClauseExtractionResult

class ClauseExtractionResult(BaseModel):
    """Result of clause extraction."""
    
    document_id: str
    clauses: list[ExtractedClause]
    unclassified_sections: list[str]
```

**Fields:**

- **document_id** : `str`
  - ID of the source document
  
- **clauses** : `list[ExtractedClause]`
  - Extracted clauses
  
- **unclassified_sections** : `list[str]`
  - Sections that couldn't be classified

**Example:**

```python
result = ClauseExtractionResult(
    document_id="ABC123",
    clauses=[clause1, clause2, clause3],
    unclassified_sections=["Boilerplate section 25"]
)

print(f"Document: {result.document_id}")
print(f"Clauses: {len(result.clauses)}")
print(f"Unclassified: {len(result.unclassified_sections)}")

# Filter by type
termination_clauses = [
    c for c in result.clauses 
    if c.clause_type == "TerminationClause"
]
```

---

## Entity Models

### Party

Represents a party to a contract.

```python
from agents.ingestion.entity_extraction import Party

class Party(BaseModel):
    """Represents a party to a contract."""
    
    party_id: str
    name: str
    role: str
    address: str | None
    contact_info: dict[str, str]
    aliases: list[str]
```

**Fields:**

- **party_id** : `str`
  - Unique identifier for the party
  
- **name** : `str`
  - Full legal name of the party
  
- **role** : `str`
  - Role in contract: `Buyer`, `Supplier`, `Contractor`, `Vendor`, `Client`, etc.
  
- **address** : `str | None`
  - Address if mentioned
  
- **contact_info** : `dict[str, str]`
  - Contact information (email, phone, etc.)
  - Nested structures flattened to strings
  
- **aliases** : `list[str]`
  - Alternative names or abbreviations

**Example:**

```python
party = Party(
    party_id="party_1",
    name="ABC Corporation",
    role="Buyer",
    address="123 Main St, City, State 12345",
    contact_info={
        "email": "contact@abc.com",
        "phone": "+1-555-0100"
    },
    aliases=["ABC", "ABC Corp", "the Company"]
)

print(f"Party: {party.name}")
print(f"Role: {party.role}")
print(f"Email: {party.contact_info.get('email')}")
print(f"Aliases: {', '.join(party.aliases)}")
```

**Validation:**

```python
# Normalizes None to empty dict/list
party = Party(
    party_id="party_1",
    name="Company A",
    role="Buyer",
    contact_info=None,  # Becomes {}
    aliases=None        # Becomes []
)

# Flattens nested structures
party = Party(
    party_id="party_1",
    name="Company A",
    role="Buyer",
    contact_info={
        "emails": ["a@example.com", "b@example.com"]  # Becomes JSON string
    }
)
```

---

### ContractDate

Represents a significant date in a contract.

```python
from agents.ingestion.entity_extraction import ContractDate

class ContractDate(BaseModel):
    """Represents a significant date in a contract."""
    
    date_type: str
    date_value: str | None
    date_description: str
    is_recurring: bool
    reference_clause: str | None
```

**Fields:**

- **date_type** : `str`
  - Type: `EffectiveDate`, `ExpirationDate`, `SigningDate`, `MilestoneDate`, `DeadlineDate`, `PaymentDueDate`
  
- **date_value** : `str | None`
  - ISO format date if specific (e.g., `"2024-01-01"`)
  
- **date_description** : `str`
  - Human-readable description
  
- **is_recurring** : `bool`
  - Whether this is a recurring date
  
- **reference_clause** : `str | None`
  - Clause that defines this date

**Example:**

```python
date = ContractDate(
    date_type="EffectiveDate",
    date_value="2024-01-01",
    date_description="Contract becomes effective January 1, 2024",
    is_recurring=False,
    reference_clause="Section 2.1"
)

print(f"Type: {date.date_type}")
print(f"Date: {date.date_value}")
print(f"Description: {date.date_description}")

# Recurring date example
payment_date = ContractDate(
    date_type="PaymentDueDate",
    date_value=None,  # Not a specific date
    date_description="Payment due on the 15th of each month",
    is_recurring=True,
    reference_clause="Section 4.2"
)
```

---

### MonetaryAmount

Represents a monetary value in a contract.

```python
from agents.ingestion.entity_extraction import MonetaryAmount

class MonetaryAmount(BaseModel):
    """Represents a monetary value in a contract."""
    
    amount_id: str
    amount_type: str
    value: float | None
    currency: str
    description: str
    is_estimate: bool
    reference_clause: str | None
```

**Fields:**

- **amount_id** : `str`
  - Unique identifier
  
- **amount_type** : `str`
  - Type: `ContractValue`, `PenaltyAmount`, `Threshold`, `InsuranceCoverage`, `LiabilityLimit`
  
- **value** : `float | None`
  - Numeric value if extractable
  
- **currency** : `str`, default=`"USD"`
  - Currency code (ISO 4217)
  - Auto-normalized to uppercase
  
- **description** : `str`
  - Context of the amount
  
- **is_estimate** : `bool`, default=`False`
  - Whether this is an estimate
  
- **reference_clause** : `str | None`
  - Source clause

**Example:**

```python
amount = MonetaryAmount(
    amount_id="amt_1",
    amount_type="ContractValue",
    value=500000.00,
    currency="USD",
    description="Total contract value for 12-month term",
    is_estimate=False,
    reference_clause="Section 4.1"
)

print(f"Type: {amount.amount_type}")
print(f"Value: {amount.currency} {amount.value:,.2f}")
print(f"Description: {amount.description}")

# Penalty amount example
penalty = MonetaryAmount(
    amount_id="amt_2",
    amount_type="PenaltyAmount",
    value=1000.00,
    currency="USD",
    description="Late delivery penalty per day",
    is_estimate=False,
    reference_clause="Section 8.3"
)
```

**Validation:**

```python
# Normalizes currency to uppercase
amount = MonetaryAmount(
    amount_id="amt_1",
    amount_type="ContractValue",
    value=100000.00,
    currency="usd",  # Becomes "USD"
    description="Contract value"
)

# Defaults to USD if None
amount = MonetaryAmount(
    amount_id="amt_1",
    amount_type="ContractValue",
    value=100000.00,
    currency=None,  # Becomes "USD"
    description="Contract value"
)
```

---

### Jurisdiction

Represents a jurisdiction or governing law.

```python
from agents.ingestion.entity_extraction import Jurisdiction

class Jurisdiction(BaseModel):
    """Represents a jurisdiction or governing law."""
    
    jurisdiction_id: str
    name: str
    jurisdiction_type: str
    applies_to: str
```

**Fields:**

- **jurisdiction_id** : `str`
  - Unique identifier
  
- **name** : `str`
  - Jurisdiction name (e.g., `"State of Delaware"`, `"United Kingdom"`)
  
- **jurisdiction_type** : `str`, default=`"Unknown"`
  - Type: `State`, `Country`, `Federal`, `International`
  
- **applies_to** : `str`, default=`"GoverningLaw"`
  - What this jurisdiction governs: `GoverningLaw`, `DisputeResolution`, `Arbitration`

**Example:**

```python
jurisdiction = Jurisdiction(
    jurisdiction_id="jur_1",
    name="State of Delaware",
    jurisdiction_type="State",
    applies_to="GoverningLaw"
)

print(f"Jurisdiction: {jurisdiction.name}")
print(f"Type: {jurisdiction.jurisdiction_type}")
print(f"Applies to: {jurisdiction.applies_to}")

# Arbitration venue example
venue = Jurisdiction(
    jurisdiction_id="jur_2",
    name="London, United Kingdom",
    jurisdiction_type="International",
    applies_to="Arbitration"
)
```

---

### EntityExtractionResult

Result of entity extraction from a document.

```python
from agents.ingestion.entity_extraction import EntityExtractionResult

class EntityExtractionResult(BaseModel):
    """Result of entity extraction."""
    
    document_id: str
    parties: list[Party]
    dates: list[ContractDate]
    amounts: list[MonetaryAmount]
    jurisdictions: list[Jurisdiction]
    contract_title: str | None
    contract_type: str | None
```

**Fields:**

- **document_id** : `str`
  - ID of the source document
  
- **parties** : `list[Party]`
  - Extracted parties
  
- **dates** : `list[ContractDate]`
  - Extracted dates
  
- **amounts** : `list[MonetaryAmount]`
  - Extracted amounts
  
- **jurisdictions** : `list[Jurisdiction]`
  - Extracted jurisdictions
  
- **contract_title** : `str | None`
  - Title of the contract
  
- **contract_type** : `str | None`
  - Type of contract (e.g., `"Services Agreement"`, `"Purchase Order"`)

**Example:**

```python
result = EntityExtractionResult(
    document_id="ABC123",
    parties=[buyer, supplier],
    dates=[effective_date, expiration_date],
    amounts=[contract_value, penalty],
    jurisdictions=[governing_law],
    contract_title="IT Services Agreement",
    contract_type="Services Agreement"
)

print(f"Document: {result.document_id}")
print(f"Title: {result.contract_title}")
print(f"Type: {result.contract_type}")
print(f"Parties: {len(result.parties)}")
print(f"Dates: {len(result.dates)}")
print(f"Amounts: {len(result.amounts)}")
print(f"Jurisdictions: {len(result.jurisdictions)}")

# Access specific entities
buyer = next((p for p in result.parties if p.role == "Buyer"), None)
contract_value = next((a for a in result.amounts if a.amount_type == "ContractValue"), None)
effective_date = next((d for d in result.dates if d.date_type == "EffectiveDate"), None)
```

---

## Usage Patterns

### Creating Models

```python
from agents.ingestion.clause_extraction import ExtractedClause
from agents.ingestion.entity_extraction import Party, MonetaryAmount

# Create clause
clause = ExtractedClause(
    clause_type="PaymentClause",
    raw_text="Payment due within 30 days",
    summary="Payment terms specify net 30 days",
    key_points=["Net 30 days", "Wire transfer"],
    attributes={"payment_days": 30}
)

# Create party
party = Party(
    party_id="party_1",
    name="ABC Corporation",
    role="Buyer"
)

# Create amount
amount = MonetaryAmount(
    amount_id="amt_1",
    amount_type="ContractValue",
    value=500000.00,
    currency="USD",
    description="Total contract value"
)
```

### Serialization

```python
# To JSON
clause_json = clause.model_dump_json(indent=2)
print(clause_json)

# To dict
clause_dict = clause.model_dump()
print(clause_dict)

# From JSON
clause_restored = ExtractedClause.model_validate_json(clause_json)

# From dict
clause_restored = ExtractedClause(**clause_dict)
```

### Validation

```python
from pydantic import ValidationError

try:
    # Missing required fields
    clause = ExtractedClause(
        clause_type="PaymentClause"
        # Missing raw_text and summary
    )
except ValidationError as e:
    print(f"Validation error: {e}")

# Valid with defaults
clause = ExtractedClause(
    clause_type="PaymentClause",
    raw_text="Text",
    summary="Summary"
    # Other fields use defaults
)
```

### Filtering and Querying

```python
# Filter clauses by type
termination_clauses = [
    c for c in result.clauses
    if c.clause_type == "TerminationClause"
]

# Find clauses with specific attributes
clauses_with_notice = [
    c for c in result.clauses
    if "notice_period" in c.attributes
]

# Filter parties by role
buyers = [p for p in result.parties if p.role == "Buyer"]
suppliers = [p for p in result.parties if p.role == "Supplier"]

# Filter amounts by type
contract_values = [
    a for a in result.amounts
    if a.amount_type == "ContractValue"
]

# Filter dates by type
effective_dates = [
    d for d in result.dates
    if d.date_type == "EffectiveDate"
]
```

### Updating Models

```python
# Update fields
clause.summary = "Updated summary"
clause.attributes["notice_period"] = 45

# Add to lists
clause.key_points.append("New key point")
party.aliases.append("New alias")

# Update nested dicts
clause.structured_summary["new_field"] = "value"
party.contact_info["fax"] = "+1-555-0200"
```

---

## Best Practices

### 1. Use Type Hints

```python
from agents.ingestion.clause_extraction import ExtractedClause

def process_clause(clause: ExtractedClause) -> str:
    """Process a clause and return summary."""
    return clause.summary

# Type checking catches errors
result = process_clause(clause)  # ✓ OK
result = process_clause("string")  # ✗ Type error
```

### 2. Handle Optional Fields

```python
# Check before accessing
if clause.section_number:
    print(f"Section: {clause.section_number}")

# Use get() for dicts
notice_period = clause.attributes.get("notice_period")
if notice_period:
    print(f"Notice: {notice_period} days")

# Provide defaults
title = clause.title or "Untitled"
```

### 3. Validate Input Data

```python
from pydantic import ValidationError

def safe_create_clause(data: dict) -> ExtractedClause | None:
    """Safely create clause with validation."""
    try:
        return ExtractedClause(**data)
    except ValidationError as e:
        print(f"Invalid clause data: {e}")
        return None

clause = safe_create_clause(user_data)
if clause:
    # Process valid clause
    pass
```

### 4. Use Model Methods

```python
# Serialize for storage
clause_json = clause.model_dump_json()
save_to_file(clause_json)

# Deserialize from storage
clause_json = load_from_file()
clause = ExtractedClause.model_validate_json(clause_json)

# Get schema
schema = ExtractedClause.model_json_schema()
print(schema)
```

### 5. Normalize Data

```python
# Models auto-normalize data
clause = ExtractedClause(
    clause_type="paymentclause",  # Not normalized
    raw_text="Text",
    summary="Summary",
    attributes=None,  # Becomes {}
    key_points=None   # Becomes []
)

# Access normalized values
print(clause.clause_type)  # "paymentclause" (as provided)
print(clause.attributes)   # {}
print(clause.key_points)   # []
```

---

## Advanced Usage

### Custom Validators

```python
from pydantic import field_validator

class CustomClause(ExtractedClause):
    """Extended clause with custom validation."""
    
    @field_validator("raw_text")
    @classmethod
    def validate_text_length(cls, v: str) -> str:
        """Ensure text is not too short."""
        if len(v) < 10:
            raise ValueError("Clause text too short")
        return v
```

### Model Inheritance

```python
class EnhancedClause(ExtractedClause):
    """Extended clause with additional fields."""
    
    risk_score: float = 0.0
    compliance_tags: list[str] = []
    reviewed_by: str | None = None
```

### Batch Operations

```python
# Create multiple clauses
clauses = [
    ExtractedClause(**data)
    for data in clause_data_list
]

# Serialize batch
clauses_json = [c.model_dump() for c in clauses]

# Filter and transform
high_risk = [
    c for c in clauses
    if c.clause_type in ["PenaltyClause", "LiabilityClause"]
]
```

---

## See Also

- **[Clause Extraction Agent](../agents/ingestion_comprehensive.md#clauseextractionagent)** - Agent that creates ExtractedClause models
- **[Entity Extraction Agent](../agents/ingestion_comprehensive.md#entityextractionagent)** - Agent that creates entity models
- **[Ingestion Orchestrator](../agents/orchestrators_comprehensive.md#ingestionorchestrator)** - Uses these models in pipeline
- **[Configuration](../core/config_comprehensive.md)** - System configuration