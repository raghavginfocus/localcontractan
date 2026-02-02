"""
Query Classifier - Determines optimal retrieval strategy.

Classifies queries to route to:
- Fuseki text index (exact keywords, numbers, dates)
- Milvus vector search (semantic/fuzzy queries)
- Fuseki SPARQL (structured queries)
- Hybrid (combine multiple sources)
"""

import re
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class RetrievalRoute(str, Enum):
    """Retrieval route types."""
    TEXT_INDEX = "text_index"  # Fuseki text index (fast keyword search)
    VECTOR = "vector"  # Milvus semantic search
    SPARQL = "sparql"  # Fuseki structured SPARQL
    HYBRID = "hybrid"  # Combine text + vector + SPARQL


class QueryClassification(BaseModel):
    """Classification result for a query."""
    
    query: str = Field(description="Original query")
    primary_route: RetrievalRoute = Field(description="Primary retrieval route")
    secondary_routes: list[RetrievalRoute] = Field(
        default_factory=list,
        description="Additional routes to try",
    )
    confidence: float = Field(description="Confidence in classification (0-1)")
    reasoning: str = Field(description="Why this route was chosen")
    
    # Detected features
    has_exact_terms: bool = Field(default=False, description="Has exact keywords/numbers")
    has_semantic_intent: bool = Field(default=False, description="Needs semantic understanding")
    has_structured_intent: bool = Field(default=False, description="Needs structured data")
    detected_keywords: list[str] = Field(default_factory=list, description="Exact terms found")
    detected_numbers: list[str] = Field(default_factory=list, description="Numbers/dates found")


class QueryClassifier(BaseAgent):
    """
    Classifies queries to determine optimal retrieval strategy.
    
    Rules:
    - Exact terms/numbers → TEXT_INDEX (fast keyword search)
    - Semantic queries → VECTOR (fuzzy similarity)
    - Structured queries → SPARQL (counts, lists, joins)
    - Complex queries → HYBRID (combine all)
    """
    
    # Patterns for exact term detection
    NUMBER_PATTERN = re.compile(r'\b\d+\s*(days?|weeks?|months?|years?|%|percent|dollars?|\$)\b', re.IGNORECASE)
    EXACT_TERM_PATTERNS = [
        re.compile(r'\b(net\s+\d+|within\s+\d+|after\s+\d+)\b', re.IGNORECASE),
        re.compile(r'\b(termination|payment|liability|penalty|confidentiality)\s+(notice|terms|clause|period)\b', re.IGNORECASE),
        re.compile(r'\b(governing\s+law|jurisdiction|venue|arbitration)\b', re.IGNORECASE),
    ]
    
    # Semantic intent indicators
    SEMANTIC_INDICATORS = [
        'similar', 'like', 'related', 'compare', 'analyze', 'risk', 'risky',
        'short', 'long', 'high', 'low', 'best', 'worst', 'most', 'least',
        'understand', 'explain', 'what does', 'how does', 'why',
    ]
    
    # Structured query indicators
    STRUCTURED_INDICATORS = [
        'list', 'count', 'how many', 'show all', 'all contracts',
        'group by', 'aggregate', 'sum', 'average', 'total',
    ]

    # KG-answerable: questions that ask for contracts/entities by a KG attribute.
    # These should use SPARQL (hasRisk, severity, contractValue, governedBy), not vector.
    KG_ANSWERABLE_INDICATORS = [
        'high-risk', 'high risk', 'risk level', 'by risk', 'contracts with risk',
        'risk severity', 'severity', 'high-value', 'high value contracts',
        'by jurisdiction', 'contracts by', 'find contracts', 'list contracts',
        'show contracts', 'which contracts', 'contracts that have',
    ]

    def _is_kg_answerable(self, query_lower: str) -> bool:
        """True if the query asks for contracts/entities by a KG attribute (risk, value, jurisdiction)."""
        return any(ind in query_lower for ind in self.KG_ANSWERABLE_INDICATORS)

    def classify(self, query: str) -> QueryClassification:
        """
        Classify a query to determine retrieval strategy.
        
        Args:
            query: User query string
            
        Returns:
            QueryClassification with route and reasoning
        """
        query_lower = query.lower()
        
        # Detect features
        has_exact_terms = self._has_exact_terms(query)
        has_semantic_intent = self._has_semantic_intent(query_lower)
        has_structured_intent = self._has_structured_intent(query_lower)
        
        keywords = self._extract_keywords(query)
        numbers = self._extract_numbers(query)
        
        # KG-answerable override: "find high-risk contracts" etc. should use SPARQL
        is_kg_answerable = self._is_kg_answerable(query_lower)

        # Determine primary route
        primary_route, secondary_routes, reasoning = self._determine_route(
            has_exact_terms,
            has_semantic_intent,
            has_structured_intent,
            keywords,
            numbers,
            is_kg_answerable,
        )
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            has_exact_terms,
            has_semantic_intent,
            has_structured_intent,
        )
        
        return QueryClassification(
            query=query,
            primary_route=primary_route,
            secondary_routes=secondary_routes,
            confidence=confidence,
            reasoning=reasoning,
            has_exact_terms=has_exact_terms,
            has_semantic_intent=has_semantic_intent,
            has_structured_intent=has_structured_intent,
            detected_keywords=keywords,
            detected_numbers=numbers,
        )
    
    def _has_exact_terms(self, query: str) -> bool:
        """Check if query contains exact terms suitable for text index."""
        # Check for numbers with units
        if self.NUMBER_PATTERN.search(query):
            return True
        
        # Check for exact term patterns
        for pattern in self.EXACT_TERM_PATTERNS:
            if pattern.search(query):
                return True
        
        return False
    
    def _has_semantic_intent(self, query_lower: str) -> bool:
        """Check if query needs semantic understanding."""
        return any(indicator in query_lower for indicator in self.SEMANTIC_INDICATORS)
    
    def _has_structured_intent(self, query_lower: str) -> bool:
        """Check if query needs structured data."""
        return any(indicator in query_lower for indicator in self.STRUCTURED_INDICATORS)
    
    def _extract_keywords(self, query: str) -> list[str]:
        """Extract potential keywords for text search."""
        keywords = []
        
        # Extract exact term patterns - use finditer to get full match strings
        for pattern in self.EXACT_TERM_PATTERNS:
            for match in pattern.finditer(query):
                keywords.append(match.group(0))  # Get the full matched string
        
        return keywords
    
    def _extract_numbers(self, query: str) -> list[str]:
        """Extract numbers/dates from query."""
        numbers = []
        # Use finditer to get full match strings
        for match in self.NUMBER_PATTERN.finditer(query):
            numbers.append(match.group(0))  # Get the full matched string
        return numbers
    
    def _determine_route(
        self,
        has_exact_terms: bool,
        has_semantic_intent: bool,
        has_structured_intent: bool,
        keywords: list[str],
        numbers: list[str],
        is_kg_answerable: bool = False,
    ) -> tuple[RetrievalRoute, list[RetrievalRoute], str]:
        """Determine primary route and fallbacks."""

        # Strong exact term signal → text index first
        if has_exact_terms and len(keywords + numbers) >= 2:
            reasoning = f"Query contains exact terms ({keywords + numbers}), using fast text index"
            return RetrievalRoute.TEXT_INDEX, [RetrievalRoute.VECTOR], reasoning

        # KG-answerable: "find high-risk contracts", "contracts by risk", etc. → SPARQL
        if is_kg_answerable:
            reasoning = "Query asks for contracts by KG attribute (risk/severity/value/jurisdiction), using SPARQL"
            return RetrievalRoute.SPARQL, [], reasoning

        # Structured query → SPARQL
        if has_structured_intent and not has_semantic_intent:
            reasoning = "Structured query (count/list), using SPARQL"
            return RetrievalRoute.SPARQL, [], reasoning

        # Semantic query → vector search
        if has_semantic_intent and not has_exact_terms:
            reasoning = "Semantic query, using vector search"
            return RetrievalRoute.VECTOR, [], reasoning
        
        # Hybrid: has both exact terms and semantic intent
        if has_exact_terms and has_semantic_intent:
            reasoning = f"Hybrid query (exact terms + semantic), using text index + vector search"
            return RetrievalRoute.HYBRID, [], reasoning
        
        # Default: hybrid (safe fallback)
        reasoning = "Defaulting to hybrid retrieval (text + vector + SPARQL)"
        return RetrievalRoute.HYBRID, [RetrievalRoute.TEXT_INDEX, RetrievalRoute.VECTOR], reasoning
    
    def _calculate_confidence(
        self,
        has_exact_terms: bool,
        has_semantic_intent: bool,
        has_structured_intent: bool,
    ) -> float:
        """Calculate confidence in classification."""
        signals = sum([has_exact_terms, has_semantic_intent, has_structured_intent])
        
        if signals == 0:
            return 0.3  # Low confidence, default route
        elif signals == 1:
            return 0.7  # Medium confidence, clear signal
        else:
            return 0.9  # High confidence, multiple signals
    
    async def process(self, input_data: Any) -> QueryClassification:
        """
        Process input query and return classification.
        
        This method satisfies the BaseAgent abstract method requirement.
        
        Args:
            input_data: Query string or dict with 'query' key
            
        Returns:
            QueryClassification result
        """
        if isinstance(input_data, dict):
            query = input_data.get("query", "")
        elif isinstance(input_data, str):
            query = input_data
        else:
            raise ValueError(f"Expected str or dict with 'query' key, got {type(input_data)}")
        
        return self.classify(query)
