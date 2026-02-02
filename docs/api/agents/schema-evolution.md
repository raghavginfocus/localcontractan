# Schema Evolution Agents API Reference

API documentation for schema evolution and ontology management agents.

## PatternDetectionAgent

Detects new concepts and patterns in ingested data.

### Class Definition

```python
from agents.schema_evolution.pattern_detection import PatternDetectionAgent

class PatternDetectionAgent(BaseAgent):
    """
    Detect new concepts and patterns not in current ontology.
    
    Analyzes extracted entities to identify frequently occurring
    concepts that should be added to the ontology.
    """
```

### Constructor

```python
def __init__(
    self,
    settings: Settings | None = None,
    min_frequency: int = 3,
    similarity_threshold: float = 0.7,
    confidence_threshold: float = 0.8,
    **kwargs
)
```

**Parameters:**

- `settings` (Settings, optional): Application settings
- `min_frequency` (int): Minimum occurrences to suggest concept
- `similarity_threshold` (float): Semantic similarity cutoff
- `confidence_threshold` (float): Minimum confidence score

### Methods

#### detect_patterns

```python
def detect_patterns(
    self,
    entities: list[dict],
    existing_ontology: Graph,
    document_context: dict[str, Any] | None = None
) -> list[OntologySuggestion]
```

Detect new patterns in entities.

**Parameters:**

- `entities` (list): Extracted entities from documents
- `existing_ontology` (Graph): Current ontology graph
- `document_context` (dict, optional): Document metadata

**Returns:**

- `list[OntologySuggestion]`: Detected patterns

**Example:**

```python
agent = PatternDetectionAgent(
    min_frequency=3,
    confidence_threshold=0.8
)

patterns = agent.detect_patterns(
    entities=extracted_entities,
    existing_ontology=ontology_graph
)

for pattern in patterns:
    print(f"New concept: {pattern.name}")
    print(f"Frequency: {pattern.frequency}")
    print(f"Suggested parent: {pattern.parent_class}")
```

#### Result Model

```python
class OntologySuggestion(BaseModel):
    name: str
    suggestion_type: str  # "class", "property", "individual"
    description: str
    parent_class: str
    frequency: int
    confidence: float
    examples: list[str]
    metadata: dict[str, Any]
```

## OntologyDesignerAgent

Generates OWL definitions for new concepts.

### Class Definition

```python
from agents.schema_evolution.ontology_designer import OntologyDesignerAgent

class OntologyDesignerAgent(BaseAgent):
    """
    Generate OWL ontology extensions for new concepts.
    
    Creates class definitions, properties, and relationships
    for concepts discovered during ingestion.
    """
```

### Methods

#### generate_owl

```python
def generate_owl(
    self,
    suggestion: dict[str, Any]
) -> OWLGenerationResult
```

Generate OWL definition for concept.

**Parameters:**

- `suggestion` (dict): Concept suggestion with metadata

**Returns:**

- `OWLGenerationResult`: Generated OWL triples

**Example:**

```python
agent = OntologyDesignerAgent()

result = agent.generate_owl(
    suggestion={
        "name": "DataProtectionClause",
        "type": "class",
        "description": "Clause related to data protection",
        "parent_class": "proc:Clause",
        "examples": ["GDPR compliance", "data retention"]
    }
)

print(result.owl_triples)
print(f"Saved to: {result.file_path}")
```

#### extend_ontology

```python
def extend_ontology(
    self,
    suggestions: list[dict],
    load_to_fuseki: bool = False,
    graph_uri: str | None = None
) -> OntologyExtensionResult
```

Generate and optionally load multiple extensions.

**Parameters:**

- `suggestions` (list): List of concept suggestions
- `load_to_fuseki` (bool): Load to Fuseki after generation
- `graph_uri` (str, optional): Target graph URI

**Returns:**

- `OntologyExtensionResult`: Extension results

**Example:**

```python
result = agent.extend_ontology(
    suggestions=[
        {"name": "DataProtectionClause", ...},
        {"name": "ComplianceObligation", ...}
    ],
    load_to_fuseki=True,
    graph_uri="http://example.org/ontology"
)

print(f"Generated {len(result.extensions)} extensions")
print(f"Total triples: {result.total_triples}")
```

#### Result Models

```python
class OWLGenerationResult(BaseModel):
    suggestion_name: str
    owl_triples: str  # Turtle format
    triple_count: int
    is_valid: bool
    file_path: str | None
    error: str | None

class OntologyExtensionResult(BaseModel):
    extensions: list[OWLGenerationResult]
    total_triples: int
    combined_owl_path: str | None
    loaded_to_fuseki: bool
```

## SHACLGeneratorAgent

Creates SHACL validation shapes for new concepts.

### Class Definition

```python
from agents.schema_evolution.shacl_generator import SHACLGeneratorAgent

class SHACLGeneratorAgent(BaseAgent):
    """
    Generate SHACL shapes for data validation.
    
    Creates constraint definitions to ensure data quality
    for new ontology concepts.
    """
```

### Methods

#### generate_shacl

```python
def generate_shacl(
    self,
    class_name: str,
    properties: list[str] | None = None,
    constraints: dict[str, Any] | None = None
) -> SHACLGenerationResult
```

Generate SHACL shapes for class.

**Parameters:**

- `class_name` (str): Class to generate shapes for
- `properties` (list, optional): Properties to validate
- `constraints` (dict, optional): Custom constraints

**Returns:**

- `SHACLGenerationResult`: Generated SHACL shapes

**Example:**

```python
agent = SHACLGeneratorAgent()

result = agent.generate_shacl(
    class_name="DataProtectionClause",
    properties=["dataRetentionPeriod", "encryptionRequired"],
    constraints={
        "dataRetentionPeriod": {
            "datatype": "xsd:duration",
            "minCount": 1
        },
        "encryptionRequired": {
            "datatype": "xsd:boolean"
        }
    }
)

print(result.shacl_shapes)
```

#### Result Model

```python
class SHACLGenerationResult(BaseModel):
    class_name: str
    shacl_shapes: str  # Turtle format
    shape_count: int
    is_valid: bool
    file_path: str | None
    error: str | None
```

## RuleGeneratorAgent

Generates Jena inference rules for new concepts.

### Class Definition

```python
from agents.schema_evolution.rule_generator import RuleGeneratorAgent

class RuleGeneratorAgent(BaseAgent):
    """
    Generate Jena rules for automated reasoning.
    
    Creates inference rules to derive new facts from
    existing data based on domain patterns.
    """
```

### Methods

#### generate_rules

```python
def generate_rules(
    self,
    class_name: str,
    domain_context: str | None = None,
    rule_patterns: list[RulePattern] | None = None
) -> RuleGenerationResult
```

Generate inference rules for class.

**Parameters:**

- `class_name` (str): Class to generate rules for
- `domain_context` (str, optional): Domain description
- `rule_patterns` (list, optional): Predefined patterns

**Returns:**

- `RuleGenerationResult`: Generated rules

**Example:**

```python
agent = RuleGeneratorAgent()

result = agent.generate_rules(
    class_name="DataProtectionClause",
    domain_context="procurement contracts",
    rule_patterns=[
        RulePattern(
            name="dataProtectionRisk",
            condition="encryptionRequired = false",
            consequence="hasRisk DataProtectionRisk"
        )
    ]
)

print(result.rules)
```

#### Result Models

```python
class RulePattern(BaseModel):
    name: str
    condition: str
    consequence: str
    priority: int = 0

class RuleGenerationResult(BaseModel):
    class_name: str
    rules: str  # Jena rules format
    rule_count: int
    is_valid: bool
    file_path: str | None
    error: str | None
```

## SchemaGovernance

Manages schema versions and conflict resolution.

### Class Definition

```python
from schema_governance import SchemaGovernance

class SchemaGovernance:
    """
    Manage ontology versions and resolve conflicts.
    
    Tracks schema changes, detects conflicts, and
    provides rollback capabilities.
    """
```

### Methods

#### create_version

```python
def create_version(
    self,
    changes: list[dict],
    description: str,
    author: str
) -> SchemaVersion
```

Create new schema version.

**Parameters:**

- `changes` (list): List of schema changes
- `description` (str): Version description
- `author` (str): Change author

**Returns:**

- `SchemaVersion`: New version metadata

**Example:**

```python
governance = SchemaGovernance()

version = governance.create_version(
    changes=[
        {"type": "add_class", "name": "DataProtectionClause"},
        {"type": "add_property", "name": "dataRetentionPeriod"}
    ],
    description="Add data protection concepts",
    author="system"
)

print(f"Version: {version.version_number}")
```

#### detect_conflicts

```python
def detect_conflicts(
    self,
    proposed_changes: list[dict]
) -> list[SchemaConflict]
```

Detect conflicts in proposed changes.

**Parameters:**

- `proposed_changes` (list): Proposed schema changes

**Returns:**

- `list[SchemaConflict]`: Detected conflicts

**Example:**

```python
conflicts = governance.detect_conflicts(
    proposed_changes=[
        {"type": "add_class", "name": "Contract"}  # Already exists
    ]
)

for conflict in conflicts:
    print(f"Conflict: {conflict.description}")
    print(f"Resolution: {conflict.suggested_resolution}")
```

#### rollback_version

```python
def rollback_version(
    self,
    target_version: str
) -> bool
```

Rollback to previous version.

**Parameters:**

- `target_version` (str): Version to rollback to

**Returns:**

- `bool`: Success status

**Example:**

```python
success = governance.rollback_version("1.0.0")
print(f"Rollback successful: {success}")
```

#### Result Models

```python
class SchemaVersion(BaseModel):
    version_number: str
    timestamp: datetime
    changes: list[dict]
    description: str
    author: str
    parent_version: str | None

class SchemaConflict(BaseModel):
    conflict_type: str
    description: str
    affected_elements: list[str]
    severity: str  # "low", "medium", "high"
    suggested_resolution: str
```

## OntologyManager

Manages ontology loading and querying.

### Class Definition

```python
from ontology_manager import OntologyManager

class OntologyManager:
    """
    Manage ontology lifecycle and queries.
    
    Handles loading, caching, and querying of
    ontology definitions.
    """
```

### Methods

#### load_ontology

```python
def load_ontology(
    self,
    ontology_path: str | Path
) -> Graph
```

Load ontology from file.

**Parameters:**

- `ontology_path` (str | Path): Path to ontology file

**Returns:**

- `Graph`: Loaded ontology graph

**Example:**

```python
manager = OntologyManager()

ontology = manager.load_ontology("ontology/procurement.owl")
print(f"Loaded {len(ontology)} triples")
```

#### get_class_hierarchy

```python
def get_class_hierarchy(
    self,
    root_class: str | None = None
) -> dict[str, list[str]]
```

Get class hierarchy.

**Parameters:**

- `root_class` (str, optional): Root class URI

**Returns:**

- `dict`: Class hierarchy mapping

**Example:**

```python
hierarchy = manager.get_class_hierarchy("proc:Clause")

for parent, children in hierarchy.items():
    print(f"{parent}:")
    for child in children:
        print(f"  - {child}")
```

#### get_properties

```python
def get_properties(
    self,
    class_uri: str
) -> list[dict[str, Any]]
```

Get properties for class.

**Parameters:**

- `class_uri` (str): Class URI

**Returns:**

- `list[dict]`: Property definitions

**Example:**

```python
properties = manager.get_properties("proc:Contract")

for prop in properties:
    print(f"{prop['name']}: {prop['range']}")
```

#### validate_concept

```python
def validate_concept(
    self,
    concept_name: str,
    concept_type: str
) -> bool
```

Validate if concept exists in ontology.

**Parameters:**

- `concept_name` (str): Concept name
- `concept_type` (str): "class" or "property"

**Returns:**

- `bool`: True if concept exists

**Example:**

```python
exists = manager.validate_concept("Contract", "class")
print(f"Contract exists: {exists}")
```

## See Also

- [Ingestion Agents API](../api/agents/ingestion.md)
- [Retrieval Agents API](../api/agents/retrieval.md)
- [Schema Evolution Guide](../../guide/schema-evolution.md)
- [Knowledge Graph Architecture](../../architecture/knowledge-graph.md)