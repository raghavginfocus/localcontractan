"""
SPARQL Template System for Fast Query Generation

Provides intent-based SPARQL generation using templates for common patterns.
Falls back to LLM generation for complex queries.
"""

import re
from dataclasses import dataclass
from typing import Optional, Any
from enum import Enum
from logger import get_module_logger

logger = get_module_logger(__name__)


class QueryAction(Enum):
    """Common query actions."""
    LIST = "list"
    COUNT = "count"
    FIND = "find"
    GET = "get"
    COMPARE = "compare"
    AGGREGATE = "aggregate"
    EXISTS = "exists"
    FILTER = "filter"


class EntityType(Enum):
    """Contract domain entities."""
    CONTRACT = "Contract"
    PARTY = "Party"
    CLAUSE = "Clause"
    OBLIGATION = "Obligation"
    RISK = "Risk"
    TERM = "Term"
    PAYMENT = "Payment"


@dataclass
class QueryIntent:
    """Structured representation of query intent."""
    action: QueryAction
    entity: EntityType
    property: Optional[str] = None
    filters: list[dict[str, Any]] = None
    complexity: str = "simple"  # simple, medium, complex
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = []


class IntentClassifier:
    """Fast intent classification using patterns and rules."""
    
    # Action patterns
    ACTION_PATTERNS = {
        QueryAction.LIST: [
            r'\b(list|show|display|what are|give me|get all)\b',
            r'\b(all|every)\b.*\b(contract|agreement|clause)',
        ],
        QueryAction.COUNT: [
            r'\b(count|how many|number of|total)\b',
        ],
        QueryAction.FIND: [
            r'\b(find|search|locate|which|who)\b',
        ],
        QueryAction.GET: [
            r'\b(what is|get|retrieve|fetch)\b.*\b(the|a)\b',
        ],
        QueryAction.COMPARE: [
            r'\b(compare|difference|versus|vs|between)\b',
        ],
        QueryAction.AGGREGATE: [
            r'\b(sum|total|average|mean|max|min|maximum|minimum)\b',
        ],
        QueryAction.EXISTS: [
            r'\b(is there|are there|does|do|has|have)\b',
        ],
    }
    
    # Entity patterns
    ENTITY_PATTERNS = {
        EntityType.CONTRACT: [
            r'\b(contract|agreement|deal|arrangement)\b',
        ],
        EntityType.PARTY: [
            r'\b(party|parties|supplier|vendor|customer|client|organization)\b',
        ],
        EntityType.CLAUSE: [
            r'\b(clause|section|provision|term|condition)\b',
        ],
        EntityType.OBLIGATION: [
            r'\b(obligation|duty|responsibility|requirement|must)\b',
        ],
        EntityType.RISK: [
            r'\b(risk|liability|penalty|consequence)\b',
        ],
        EntityType.TERM: [
            r'\b(term|duration|period|length|time|date)\b',
        ],
        EntityType.PAYMENT: [
            r'\b(payment|price|cost|fee|amount|value)\b',
        ],
    }
    
    # Property patterns
    PROPERTY_PATTERNS = {
        "title": [r'\b(title|name)\b'],
        "effectiveDate": [r'\b(effective date|start date|commencement)\b'],
        "expirationDate": [r'\b(expiration|end date|termination date)\b'],
        "term": [r'\b(term|duration|period)\b'],
        "value": [r'\b(value|amount|price|cost)\b'],
        "jurisdiction": [r'\b(jurisdiction|governing law|venue)\b'],
        "paymentTerms": [r'\b(payment terms|payment period|net \d+)\b'],
        "noticeperiod": [r'\b(notice period|notice|notification)\b'],
        "riskLevel": [r'\b(risk level|risk|severity)\b'],
    }
    
    def classify(self, question: str) -> QueryIntent:
        """
        Classify question intent using pattern matching.
        
        Args:
            question: User question
            
        Returns:
            QueryIntent with classified components
        """
        q_lower = question.lower()
        
        # Detect action
        action = self._detect_action(q_lower)
        
        # Detect entity
        entity = self._detect_entity(q_lower)
        
        # Detect property
        property_name = self._detect_property(q_lower)
        
        # Detect filters
        filters = self._detect_filters(q_lower)
        
        # Assess complexity
        complexity = self._assess_complexity(action, filters, q_lower)
        
        # Calculate confidence
        confidence = self._calculate_confidence(action, entity, property_name)
        
        intent = QueryIntent(
            action=action,
            entity=entity,
            property=property_name,
            filters=filters,
            complexity=complexity,
            confidence=confidence,
        )
        
        logger.debug(
            "Intent classified",
            action=action.value,
            entity=entity.value,
            property=property_name,
            complexity=complexity,
            confidence=f"{confidence:.2f}",
        )
        
        return intent
    
    def _detect_action(self, question: str) -> QueryAction:
        """Detect query action from question."""
        for action, patterns in self.ACTION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    return action
        return QueryAction.LIST  # Default
    
    def _detect_entity(self, question: str) -> EntityType:
        """Detect entity type from question."""
        for entity, patterns in self.ENTITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    return entity
        return EntityType.CONTRACT  # Default
    
    def _detect_property(self, question: str) -> Optional[str]:
        """Detect property name from question."""
        for prop, patterns in self.PROPERTY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, question, re.IGNORECASE):
                    return prop
        return None
    
    def _detect_filters(self, question: str) -> list[dict[str, Any]]:
        """Detect filter conditions from question."""
        filters = []
        
        # Detect party filters
        party_match = re.search(r'\b(with|from|by)\s+([A-Z][a-zA-Z\s]+)', question)
        if party_match:
            filters.append({
                "property": "hasParty",
                "value": party_match.group(2).strip(),
                "operator": "contains"
            })
        
        # Detect date filters
        year_match = re.search(r'\b(in|during|from)\s+(\d{4})\b', question)
        if year_match:
            filters.append({
                "property": "effectiveDate",
                "value": year_match.group(2),
                "operator": "year"
            })
        
        # Detect value filters
        value_match = re.search(r'\b(over|above|more than|greater than)\s+\$?(\d+)', question)
        if value_match:
            filters.append({
                "property": "value",
                "value": value_match.group(2),
                "operator": ">"
            })
        
        return filters
    
    def _assess_complexity(self, action: QueryAction, filters: list, question: str) -> str:
        """Assess query complexity."""
        # Complex indicators
        if action == QueryAction.COMPARE:
            return "complex"
        if len(filters) > 2:
            return "complex"
        if any(word in question for word in ["analyze", "explain", "why", "how"]):
            return "complex"
        
        # Medium indicators
        if len(filters) > 0:
            return "medium"
        if action in [QueryAction.AGGREGATE, QueryAction.FILTER]:
            return "medium"
        
        return "simple"
    
    def _calculate_confidence(self, action: QueryAction, entity: EntityType, 
                             property_name: Optional[str]) -> float:
        """Calculate classification confidence."""
        confidence = 0.5  # Base confidence
        
        # Boost for detected components
        if action:
            confidence += 0.2
        if entity:
            confidence += 0.2
        if property_name:
            confidence += 0.1
        
        return min(confidence, 1.0)


class SPARQLTemplateEngine:
    """Generate SPARQL queries from templates."""
    
    # SPARQL prefixes
    PREFIXES = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX proc: <http://procurement.kg/ontology#>
        PREFIX contract: <http://procurement.kg/contract#>
    """
    
    # Template definitions
    TEMPLATES = {
        # List templates
        "list_entity": """
            SELECT DISTINCT ?entity
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                }}
            }}
        """,
        
        "list_entity_property": """
            SELECT DISTINCT ?{property}
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{property} ?{property} .
                }}
            }}
        """,
        
        "list_entity_with_filter": """
            SELECT DISTINCT ?entity ?{return_property}
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{filter_property} ?filter_val .
                    FILTER(CONTAINS(LCASE(STR(?filter_val)), "{filter_value}"))
                    ?entity proc:{return_property} ?{return_property} .
                }}
            }}
        """,
        
        # Count templates
        "count_entity": """
            SELECT (COUNT(DISTINCT ?entity) as ?count)
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                }}
            }}
        """,
        
        "count_entity_with_filter": """
            SELECT (COUNT(DISTINCT ?entity) as ?count)
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{filter_property} ?filter_val .
                    FILTER(CONTAINS(LCASE(STR(?filter_val)), "{filter_value}"))
                }}
            }}
        """,
        
        # Get specific property
        "get_property": """
            SELECT ?entity ?{property}
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{property} ?{property} .
                }}
            }}
            LIMIT 1
        """,
        
        # Find with filter
        "find_by_property": """
            SELECT ?entity ?title
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{property} ?prop_val .
                    FILTER(CONTAINS(LCASE(STR(?prop_val)), "{value}"))
                    OPTIONAL {{ ?entity proc:title ?title }}
                }}
            }}
        """,
        
        # Exists check
        "exists_entity": """
            ASK {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                }}
            }}
        """,
        
        # Aggregate templates
        "aggregate_property": """
            SELECT ({aggregate}(?{property}) as ?result)
            WHERE {{
                GRAPH ?g {{
                    ?entity a proc:{entity} .
                    ?entity proc:{property} ?{property} .
                }}
            }}
        """,
    }
    
    def generate(self, intent: QueryIntent) -> Optional[str]:
        """
        Generate SPARQL query from intent using templates.
        
        Args:
            intent: Classified query intent
            
        Returns:
            SPARQL query string or None if no template matches
        """
        try:
            # Select template based on intent
            template_key = self._select_template(intent)
            if not template_key:
                logger.debug("No template match", action=intent.action.value)
                return None
            
            template = self.TEMPLATES[template_key]
            
            # Fill template with intent parameters
            sparql = self._fill_template(template, intent)
            
            # Add prefixes
            sparql = self.PREFIXES + "\n" + sparql
            
            logger.info(
                "SPARQL generated from template",
                template=template_key,
                entity=intent.entity.value,
                property=intent.property,
            )
            
            return sparql
            
        except Exception as e:
            logger.error("Template generation failed", error=str(e))
            return None
    
    def _select_template(self, intent: QueryIntent) -> Optional[str]:
        """Select appropriate template for intent."""
        action = intent.action
        has_property = intent.property is not None
        has_filters = len(intent.filters) > 0
        
        # List actions
        if action == QueryAction.LIST:
            if has_filters:
                return "list_entity_with_filter"
            elif has_property:
                return "list_entity_property"
            else:
                return "list_entity"
        
        # Count actions
        elif action == QueryAction.COUNT:
            if has_filters:
                return "count_entity_with_filter"
            else:
                return "count_entity"
        
        # Get actions
        elif action == QueryAction.GET:
            if has_property:
                return "get_property"
            else:
                return "list_entity"
        
        # Find actions
        elif action == QueryAction.FIND:
            if has_filters:
                return "find_by_property"
            else:
                return "list_entity"
        
        # Exists actions
        elif action == QueryAction.EXISTS:
            return "exists_entity"
        
        # Aggregate actions
        elif action == QueryAction.AGGREGATE:
            if has_property:
                return "aggregate_property"
        
        return None
    
    def _fill_template(self, template: str, intent: QueryIntent) -> str:
        """Fill template with intent parameters."""
        params = {
            "entity": intent.entity.value,
            "property": intent.property or "title",
            "return_property": intent.property or "title",
        }
        
        # Add filter parameters
        if intent.filters:
            filter_info = intent.filters[0]  # Use first filter
            params["filter_property"] = filter_info.get("property", "title")
            params["filter_value"] = str(filter_info.get("value", "")).lower()
        
        # Add aggregate function
        if intent.action == QueryAction.AGGREGATE:
            # Detect aggregate function from property or default to COUNT
            params["aggregate"] = "SUM"  # Could be enhanced
        
        # Fill template
        try:
            sparql = template.format(**params)
            return sparql
        except KeyError as e:
            logger.warning("Missing template parameter", param=str(e))
            return template


class TemplateSPARQLGenerator:
    """
    Main interface for template-based SPARQL generation.
    
    Combines intent classification and template generation with
    fallback to LLM for complex queries.
    """
    
    def __init__(self):
        self.classifier = IntentClassifier()
        self.template_engine = SPARQLTemplateEngine()
        self.stats = {
            "template_hits": 0,
            "template_misses": 0,
            "total_queries": 0,
        }
    
    async def generate_sparql(self, question: str, 
                             use_templates: bool = True) -> tuple[Optional[str], bool]:
        """
        Generate SPARQL query using templates or return None for LLM fallback.
        
        Args:
            question: User question
            use_templates: Whether to attempt template matching
            
        Returns:
            Tuple of (sparql_query, used_template)
        """
        self.stats["total_queries"] += 1
        
        if not use_templates:
            return None, False
        
        # Classify intent
        intent = self.classifier.classify(question)
        
        # Skip templates for complex queries
        if intent.complexity == "complex" or intent.confidence < 0.6:
            logger.info(
                "Skipping templates (complexity/confidence)",
                complexity=intent.complexity,
                confidence=f"{intent.confidence:.2f}",
            )
            self.stats["template_misses"] += 1
            return None, False
        
        # Try template generation
        sparql = self.template_engine.generate(intent)
        
        if sparql:
            self.stats["template_hits"] += 1
            logger.info(
                "Template match successful",
                hit_rate=f"{self.get_hit_rate():.1%}",
            )
            return sparql, True
        else:
            self.stats["template_misses"] += 1
            return None, False
    
    def get_hit_rate(self) -> float:
        """Calculate template hit rate."""
        total = self.stats["total_queries"]
        if total == 0:
            return 0.0
        return self.stats["template_hits"] / total
    
    def get_stats(self) -> dict:
        """Get generation statistics."""
        return {
            **self.stats,
            "hit_rate": self.get_hit_rate(),
        }


