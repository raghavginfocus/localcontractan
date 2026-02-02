"""
SPARQL Generator Agent - Converts natural language to SPARQL queries.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.retrieval.query_classifier import QueryClassifier
from agents.retrieval.sparql_templates import TemplateSPARQLGenerator
from storage.sparql.base import SPARQLStore
from service_factory import get_service_factory
from ontology_manager import get_ontology_manager, initialize_ontology
from logger import get_module_logger

logger = get_module_logger(__name__)


class SPARQLQuery(BaseModel):
    """Represents a generated SPARQL query."""
    
    query: str = Field(description="The SPARQL query")
    query_type: str = Field(description="Query type: SELECT, CONSTRUCT, ASK")
    explanation: str = Field(description="Explanation of what the query does")
    natural_language: str = Field(description="Original natural language question")


class SPARQLGeneratorAgent(BaseAgent):
    """
    Agent for converting natural language questions to SPARQL queries.
    
    Features:
    - Understands the procurement ontology
    - Generates valid SPARQL queries
    - Uses text:query for fast keyword search when applicable
    - Falls back to FILTER(CONTAINS(...)) if text index unavailable
    - Explains the generated queries
    - Can execute queries against Fuseki
    """
    
    ONTOLOGY_CONTEXT = """
PROCUREMENT CONTRACT KNOWLEDGE GRAPH SCHEMA:

CLASSES:
- proc:Contract - A procurement contract
- proc:TerminationClause - Termination provisions (has notice periods)
- proc:PaymentClause - Payment terms
- proc:PenaltyClause - Penalties and liquidated damages
- proc:ConfidentialityClause - Confidentiality requirements
- proc:WarrantyClause - Warranty provisions
- proc:Party, proc:Buyer, proc:Supplier - Contract parties
- proc:Risk - A risk identified in a contract (NOT a clause; separate entity)

PROPERTIES (USE EXACTLY THESE NAMES):
- proc:contractValue - Contract value in decimal (NOT totalValue!)
- proc:noticePeriod - Termination notice in days (integer)
- proc:rawText - Full clause text (string)
- proc:summary - Clause summary (string, indexed for fast search)
- proc:hasKeyPoint - Key point bullets (string, indexed for fast search)
- proc:hasClause - Links Contract to Clause
- proc:hasParty - Links Contract to Party
- proc:governedBy - Jurisdiction (proc:EU, proc:US)
- proc:effectiveDate, proc:expirationDate - Dates
- proc:penaltyAmount - Penalty amount (decimal)
- proc:paymentTerms - Payment terms (string)
- proc:hasRisk - Links Contract to Risk (ingestion writes this)
- proc:severity - On Risk: "Low", "Medium", "High", "Critical" (string)
- proc:riskType - On Risk: e.g. TerminationRisk, FinancialRisk (string)
- proc:introducesRisk - Links Clause to Risk (only after Jena reasoning)

TEXT SEARCH (FAST KEYWORD SEARCH):
For queries with exact keywords/numbers (e.g., "30 days", "net 60", "termination notice"),
use text:query for fast indexed search instead of FILTER(CONTAINS(...)):

PREFIX text: <http://jena.apache.org/text#>

# Fast text search (preferred for keywords)
SELECT ?clause ?text WHERE {
    ?clause text:query (proc:rawText "30 days termination") .
    ?clause proc:rawText ?text .
}

# Fallback if text index unavailable (slower)
SELECT ?clause ?text WHERE {
    ?clause proc:rawText ?text .
    FILTER(CONTAINS(?text, "30 days"))
}

EXAMPLE QUERIES:

1. Find high-value contracts (>500000):
SELECT ?contract ?value WHERE {
  ?contract a proc:Contract ;
            proc:contractValue ?value .
  FILTER(?value > 500000)
}

2. Find contracts with short termination notice (<30 days):
SELECT ?contract ?clause ?noticePeriod WHERE {
  ?contract a proc:Contract ;
            proc:hasClause ?clause .
  ?clause a proc:TerminationClause ;
          proc:noticePeriod ?noticePeriod .
  FILTER(?noticePeriod < 30)
}

3. Get clause text:
SELECT ?clause ?text WHERE {
  ?clause a proc:TerminationClause ;
          proc:rawText ?text .
}

4. Find high-risk contracts (use proc:hasRisk and proc:severity; query all graphs):
SELECT DISTINCT ?contract ?risk ?severity ?riskType WHERE {
  ?contract a proc:Contract .
  ?contract proc:hasRisk ?risk .
  ?risk proc:severity ?severity .
  FILTER(LCASE(?severity) IN ("high", "critical"))
  OPTIONAL { ?risk proc:riskType ?riskType . }
}

5. One row per high-risk contract only:
SELECT DISTINCT ?contract WHERE {
  ?contract a proc:Contract .
  ?contract proc:hasRisk ?risk .
  ?risk proc:severity ?severity .
  FILTER(LCASE(?severity) IN ("high", "critical"))
}
"""

    # Hints appended after dynamic schema (text search, examples). Used when ontology is loaded.
    ONTOLOGY_STATIC_HINTS = """
TEXT SEARCH: For exact keywords/numbers use text:query when available:
PREFIX text: <http://jena.apache.org/text#>
?clause text:query (proc:rawText "30 days termination") .

CRITICAL: Do not include GRAPH clauses; the system adds them. Use proc: prefix for all class/property names from the schema above.
"""

    def _get_ontology_context(self) -> str:
        """
        Full schema for SPARQL generation: from loaded ontology, or fallback to static context.
        Ensures the LLM knows the whole schema (all classes and properties).
        """
        try:
            manager = get_ontology_manager()
            if manager.active_schema is None:
                initialize_ontology()
            return manager.get_schema_context_for_sparql() + self.ONTOLOGY_STATIC_HINTS
        except Exception as e:
            logger.warning(
                "Using fallback ontology context (ontology not loaded)",
                error=str(e),
            )
            return self.ONTOLOGY_CONTEXT

    GENERATION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert SPARQL query generator for procurement contract knowledge graphs.

{ontology_context}

Generate SPARQL queries based on natural language questions.
Use the prefixes:
- PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
- PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
- PREFIX proc: <http://procurement.kg/ontology#>
- PREFIX contract: <http://procurement.kg/contract#>
- PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

CRITICAL RULES - FOLLOW THESE EXACTLY:
1. **Balanced Braces**: Every opening brace {{ must have a matching closing brace }}
   - WHERE {{ ... }} must be properly closed with }}
   - Count braces carefully: SELECT ... WHERE {{ ... }}
   - Example: SELECT ?x WHERE {{ ?x a proc:Contract . }}
   
2. **Complete FILTER Conditions**: FILTER must have a complete condition
   - CORRECT: FILTER(?value > 30)
   - CORRECT: FILTER(?value < 100)
   - CORRECT: FILTER(?var != ?otherVar)
   - WRONG: FILTER(?value <  (incomplete!)
   - WRONG: FILTER(?value >  (missing value!)
   
3. **Proper SPARQL Syntax**:
   - Always include WHERE clause for SELECT queries
   - Use semicolons (;) to chain properties: ?var a proc:Class ; proc:property ?value .
   - Use periods (.) to end triple patterns
   - Use proper URIs: <http://procurement.kg/ontology#Class> or proc:Class (with prefix)
   
4. **URI Format**: 
   - Use angle brackets for full URIs: <http://procurement.kg/ontology#Contract>
   - Or use prefixes: proc:Contract (if PREFIX proc: is declared)
   - NEVER leave angle brackets unbalanced: <http://... (missing closing >)
   
5. **DO NOT include GRAPH clauses**: The system will automatically add GRAPH clauses if needed.
   - DO NOT write: WHERE {{ GRAPH <uri> {{ ... }} }}
   - DO write: WHERE {{ ... }}
   - The system handles graph wrapping automatically
   
6. **Return Format**: Return ONLY the SPARQL query, no markdown, no explanation, no code blocks

VALIDATION CHECKLIST (verify before returning):
✓ All braces are balanced: count {{ and }} - they must match exactly
✓ All FILTER conditions are complete with values
✓ All angle brackets in URIs are closed: <...>
✓ WHERE clause is present for SELECT queries
✓ Query ends with proper closing brace for WHERE
✓ NO GRAPH clauses in the query (we add them automatically)
"""),
        ("human", """Generate a SPARQL query for this question:

{question}

Return only the SPARQL query (no markdown, no explanation)."""),
    ])

    EXPLANATION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", "You are a SPARQL expert. Explain what this query does in simple terms."),
        ("human", """Explain this SPARQL query:

{query}

Provide a brief, clear explanation."""),
    ])

    # Class-level cache for SPARQL queries
    _query_cache: dict[str, str] = {}
    
    def __init__(self, sparql_store: SPARQLStore | None = None, enable_caching: bool = True,
                 enable_templates: bool = True, **kwargs: Any):
        """
        Initialize with optional SPARQL store (dependency injection).
        
        Args:
            sparql_store: SPARQL store instance (injected via dependency injection)
            enable_caching: Enable query caching for performance
            enable_templates: Enable template-based SPARQL generation
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(**kwargs)
        # Use dependency injection - get from service factory if not provided
        if sparql_store is None:
            service_factory = get_service_factory(settings=self.settings)
            sparql_store = service_factory.get_sparql_store()
        self.sparql_store = sparql_store
        # Backward compatibility (deprecated)
        self.fuseki_client = self.sparql_store
        # Initialize query classifier
        self.query_classifier = QueryClassifier(settings=self.settings)
        self.enable_caching = enable_caching
        # Initialize template generator
        self.enable_templates = enable_templates
        self.template_generator = TemplateSPARQLGenerator() if enable_templates else None

    async def process(self, input_data: str) -> SPARQLQuery:
        """
        Generate SPARQL from natural language question.
        
        Args:
            input_data: Natural language question
            
        Returns:
            SPARQLQuery with generated query and explanation
        """
        question = input_data
        
        # Initialize explanation builder for each new process call
        # This ensures each test case gets its own explanation file
        if self.enable_explanations:
            self._init_explanation()
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(question)
        
        self.log_start("sparql_generation", question=question[:100])
        
        # Check cache first
        cache_key = self._get_cache_key(question)
        if self.enable_caching and cache_key in self._query_cache:
            logger.info(f"Using cached SPARQL query for: {question[:50]}...")
            cached_query = self._query_cache[cache_key]
            # Still need to generate explanation (or cache that too)
            explanation_chain = self.EXPLANATION_PROMPT | self.llm | StrOutputParser()
            explanation = await explanation_chain.ainvoke({"query": cached_query})
            
            result = SPARQLQuery(
                query=cached_query,
                query_type=self._get_query_type(cached_query),
                explanation=explanation,
                natural_language=question,
            )
            self.log_complete("sparql_generation", query_type=result.query_type, cached=True)
            return result
        
        # Try template-based generation first (FAST PATH)
        query = None
        used_template = False
        
        if self.enable_templates and self.template_generator:
            query, used_template = await self.template_generator.generate_sparql(question)
            
            if used_template:
                logger.info(
                    "Template-based SPARQL generated",
                    question=question[:50],
                    template_hit_rate=f"{self.template_generator.get_hit_rate():.1%}",
                )
        
        # Fallback to LLM generation if no template match
        if query is None:
            logger.info("Using LLM for SPARQL generation (no template match)")
            generation_chain = self.GENERATION_PROMPT | self.llm | StrOutputParser()
            
            try:
                query = await generation_chain.ainvoke({
                    "ontology_context": self._get_ontology_context(),
                    "question": question,
                })
            except Exception as e:
                logger.error("LLM SPARQL generation failed", error=str(e))
                raise
        
        # Continue with existing logic
        try:
            pass  # Query already generated above
            
            # Cache the generated query
            if self.enable_caching:
                self._query_cache[cache_key] = query
                logger.debug(f"Cached SPARQL query for: {question[:50]}...")
            
            # Clean up the query
            query = self._clean_query(query)
            
            # Fix common syntax issues
            query = self._fix_common_issues(query)
            
            # Enhance with text:query if keywords detected (post-processing)
            classification = self.query_classifier.classify(question)
            if classification.has_exact_terms:
                query = self._enhance_with_text_query(query, classification, question)
            
            # Determine query type
            query_type = self._get_query_type(query)
            
            # Generate explanation (skip if cached to save time)
            # For performance, we can skip explanation generation in production
            explanation = f"SPARQL query for: {question[:100]}"
            if self.enable_explanations:
                try:
                    explanation_chain = self.EXPLANATION_PROMPT | self.llm | StrOutputParser()
                    explanation = await explanation_chain.ainvoke({"query": query})
                except Exception as e:
                    logger.warning(f"Failed to generate explanation: {e}")
                    explanation = f"SPARQL query for: {question[:100]}"
            
            result = SPARQLQuery(
                query=query,
                query_type=query_type,
                explanation=explanation,
                natural_language=question,
            )
            
            # Record output for explanation
            if self.explanation_builder:
                self._record_output(result)
                self.explanation_builder.add_metadata("query_type", query_type)
                self.explanation_builder.add_metadata("query_length", len(query))
                # Add the actual generated query to explanation for transparency
                self.explanation_builder.add_metadata("generated_query", query)
                self.explanation_builder.add_metadata("query_explanation", explanation)
                # Save explanation
                self._save_explanation()
            
            self.log_complete("sparql_generation", query_type=query_type)
            
            return result
            
        except Exception as e:
            self.log_error("sparql_generation", e, question=question[:100])
            raise

    def _get_cache_key(self, question: str) -> str:
        """Generate cache key from question."""
        # Normalize question for caching
        normalized = question.lower().strip()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _clean_query(self, query: str) -> str:
        """Clean up generated SPARQL query."""
        # Remove markdown code blocks if present
        query = query.strip()
        if query.startswith("```"):
            lines = query.split("\n")
            query = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        # Remove any trailing explanation text (common LLM mistake)
        # Look for common explanation patterns and remove them
        explanation_markers = [
            "This query",
            "The query",
            "Explanation:",
            "Note:",
            "The above",
        ]
        lines = query.split("\n")
        cleaned_lines = []
        for line in lines:
            # Stop if we hit an explanation marker
            if any(marker in line for marker in explanation_markers):
                break
            cleaned_lines.append(line)
        query = "\n".join(cleaned_lines).strip()
        
        # Fix incomplete FILTER conditions (common error)
        # Pattern: FILTER(?var <  or FILTER(?var >  without closing
        import re
        # Find incomplete FILTER patterns
        incomplete_filter = re.search(r'FILTER\s*\(\s*\?[a-zA-Z_]+\s*[<>=!]+\s*$', query, re.MULTILINE)
        if incomplete_filter:
            self.logger.warning(
                "Detected incomplete FILTER condition, removing it",
                position=incomplete_filter.start(),
            )
            # Remove the incomplete FILTER line
            query = query[:incomplete_filter.start()] + query[incomplete_filter.end():]
        
        return query.strip()
    
    def _fix_common_issues(self, query: str) -> str:
        """Fix common SPARQL syntax issues."""
        # Fix incomplete FILTER conditions
        import re
        
        # Pattern: FILTER(?var <  or FILTER(?var >  without value
        # Remove incomplete FILTERs
        query = re.sub(
            r'FILTER\s*\(\s*\?[a-zA-Z_]+\s*[<>=!]+\s*\)?\s*$',
            '',
            query,
            flags=re.MULTILINE
        )
        
        # Fix incomplete angle brackets in URIs (common error)
        # Pattern: <http://... without closing >
        # This is tricky, so we'll just log a warning if detected
        open_brackets = query.count('<')
        close_brackets = query.count('>')
        if open_brackets != close_brackets:
            self.logger.warning(
                "Unbalanced angle brackets detected in query",
                open_count=open_brackets,
                close_count=close_brackets,
            )
            # Try to fix by removing incomplete URIs at the end
            # This is a conservative fix - better to let validation catch it
        
        return query.strip()

    def _get_query_type(self, query: str) -> str:
        """Determine the SPARQL query type."""
        query_upper = query.upper().strip()
        if query_upper.startswith("SELECT"):
            return "SELECT"
        elif query_upper.startswith("CONSTRUCT"):
            return "CONSTRUCT"
        elif query_upper.startswith("ASK"):
            return "ASK"
        elif query_upper.startswith("DESCRIBE"):
            return "DESCRIBE"
        else:
            return "UNKNOWN"
    
    def _save_query_to_log(
        self,
        question: str,
        query: str,
        query_type: str,
        graph_uri: str | None = None,
        validation_passed: bool = True,
        execution_error: str | None = None,
        result_count: int = 0,
    ) -> Path | None:
        """
        Save SPARQL query to a log file for debugging.
        
        Args:
            question: Original natural language question
            query: Generated SPARQL query
            query_type: Type of query (SELECT, ASK, etc.)
            graph_uri: Optional graph URI used
            validation_passed: Whether validation passed
            execution_error: Optional execution error message
            result_count: Number of results returned
            
        Returns:
            Path to saved log file, or None if saving failed
        """
        try:
            # Use centralized logging - route to retrieval log directory
            from logging_config import get_module_log_dir
            log_dir = get_module_log_dir("retrieval")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create log entry
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "question": question,
                "query": query,
                "query_type": query_type,
                "graph_uri": graph_uri,
                "validation_passed": validation_passed,
                "execution_error": execution_error,
                "result_count": result_count,
                "query_length": len(query),
            }
            
            # JSON logging disabled - using Phoenix tracing instead
            self.logger.debug("SPARQL query logging (file disabled, using Phoenix)",
                            query_type=query_type, result_count=result_count)
            return None
            
        except Exception as e:
            self.logger.warning("Failed to log SPARQL query", error=str(e))
            return None

    def _validate_sparql_query(self, query: str) -> tuple[bool, str | None]:
        """
        Validate SPARQL query syntax and structure.
        
        Args:
            query: SPARQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not query or not query.strip():
            return False, "Query is empty"
        
        query_upper = query.upper().strip()
        
        # Check for required SPARQL keywords
        required_keywords = ["SELECT", "ASK", "CONSTRUCT", "DESCRIBE"]
        has_keyword = any(keyword in query_upper for keyword in required_keywords)
        
        if not has_keyword:
            return False, "Query missing required SPARQL keyword (SELECT, ASK, CONSTRUCT, or DESCRIBE)"
        
        # Check for balanced braces
        open_braces = query.count("{")
        close_braces = query.count("}")
        if open_braces != close_braces:
            return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"
        
        # Check for balanced parentheses
        open_parens = query.count("(")
        close_parens = query.count(")")
        if open_parens != close_parens:
            return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"
        
        # Check for WHERE clause in SELECT queries
        if "SELECT" in query_upper and "WHERE" not in query_upper:
            return False, "SELECT query missing WHERE clause"
        
        # Basic syntax checks
        if query.count("<") != query.count(">"):
            return False, "Unbalanced angle brackets in URIs"
        
        return True, None
    
    def _enhance_with_text_query(
        self,
        query: str,
        classification,
        question: str,
    ) -> str:
        """
        Enhance SPARQL query with text:query for fast keyword search.
        
        If the query searches proc:rawText with FILTER(CONTAINS(...)),
        replace with text:query for better performance.
        
        Falls back gracefully if text index is unavailable.
        """
        import re
        
        # Check if query already uses text:query
        if "text:query" in query.lower():
            return query  # Already optimized
        
        # Check if query searches proc:rawText
        if "proc:rawText" not in query and "proc:summary" not in query:
            return query  # Not searching text fields
        
        # Extract search terms from classification (for logging)
        search_terms_list = classification.detected_keywords + classification.detected_numbers
        
        # Try to replace FILTER(CONTAINS(...)) with text:query
        # Pattern: FILTER(CONTAINS(?text, "term"))
        contains_pattern = re.compile(
            r'FILTER\s*\(\s*CONTAINS\s*\(\s*\?(\w+)\s*,\s*"([^"]+)"\s*\)\s*\)',
            re.IGNORECASE,
        )
        
        def replace_with_text_query(match):
            var_name = match.group(1)
            search_term = match.group(2)
            
            # Determine predicate based on variable name or context
            predicate = "proc:rawText"
            if "summary" in var_name.lower():
                predicate = "proc:summary"
            elif "keypoint" in var_name.lower() or "key_point" in var_name.lower():
                predicate = "proc:hasKeyPoint"
            
            # Replace with text:query
            return f'?clause text:query ({predicate} "{search_term}") .'
        
        # Replace FILTER(CONTAINS) with text:query
        enhanced_query = contains_pattern.sub(replace_with_text_query, query)
        
        # Ensure text: prefix is added if we're using text:query
        if "text:query" in enhanced_query and "PREFIX text:" not in enhanced_query.upper():
            # Add prefix at the beginning (after existing prefixes)
            prefix_match = re.search(r'(PREFIX\s+\w+:\s*<[^>]+>)', enhanced_query, re.IGNORECASE)
            if prefix_match:
                insert_pos = prefix_match.end()
                enhanced_query = (
                    enhanced_query[:insert_pos] +
                    '\nPREFIX text: <http://jena.apache.org/text#>\n' +
                    enhanced_query[insert_pos:]
                )
            else:
                # No prefixes, add at start
                enhanced_query = 'PREFIX text: <http://jena.apache.org/text#>\n' + enhanced_query
        
        if enhanced_query != query:
            logger.info("Enhanced SPARQL query with text:query for fast search")
            logger.debug(f"Original: {query[:200]}")
            logger.debug(f"Enhanced: {enhanced_query[:200]}")
        
        return enhanced_query
    
    async def generate_and_execute(
        self, 
        question: str, 
        graph_uri: str | None = None
    ) -> dict[str, Any]:
        """
        Generate SPARQL query and execute it against Fuseki.
        
        Args:
            question: Natural language question
            graph_uri: Optional named graph URI to query
            
        Returns:
            Dict with query, explanation, and results
        """
        if not self.sparql_store:
            raise ValueError("SPARQLStore not configured")
        
        # Generate query (process() already logs start/complete)
        sparql_query = await self.process(question)
        
        # Handle graph URI - if not provided, query all graphs using FROM NAMED
        final_query = sparql_query.query
        original_braces = (final_query.count('{'), final_query.count('}'))
        
        # If no graph_uri, modify query to search all named graphs
        # Fuseki stores data in named graphs, so we wrap WHERE in GRAPH ?g
        # GRAPH ?g automatically searches all named graphs
        if not graph_uri:
            # Check if query already has FROM or GRAPH clause
            query_upper = final_query.upper()
            if "FROM" not in query_upper and "GRAPH" not in query_upper:
                import re
                
                # Handle SELECT queries - wrap WHERE in GRAPH ?g
                if "SELECT" in query_upper:
                    # Find WHERE clause position (may be after PREFIX declarations)
                    where_match = re.search(r'\bWHERE\s*\{', final_query, re.IGNORECASE | re.MULTILINE)
                    if where_match:
                        where_start = where_match.start()
                        where_brace_start = where_match.end() - 1
                        
                        # Find matching closing brace for WHERE
                        brace_count = 1
                        where_brace_end = None
                        for i in range(where_brace_start + 1, len(final_query)):
                            if final_query[i] == '{':
                                brace_count += 1
                            elif final_query[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    where_brace_end = i
                                    break
                        
                        if where_brace_end:
                            # Wrap WHERE body in GRAPH ?g { ... }
                            # This searches all named graphs automatically
                            before_where = final_query[:where_start]
                            where_keyword = final_query[where_start:where_brace_start+1]
                            where_body = final_query[where_brace_start+1:where_brace_end]
                            after_where = final_query[where_brace_end:]
                            
                            # Reconstruct with GRAPH wrapper (no FROM NAMED needed)
                            # GRAPH ?g automatically searches all named graphs
                            final_query = (
                                before_where +
                                where_keyword + "\n    GRAPH ?g {\n      " +
                                where_body + "\n    }\n  " +
                                after_where
                            )
                            
                            self.logger.info(
                                "Wrapped query in GRAPH ?g for multi-graph search",
                                original_length=len(sparql_query.query),
                                modified_length=len(final_query),
                                query_preview=final_query[:300],
                            )
                
                # Handle ASK queries - wrap pattern in GRAPH ?g
                elif "ASK" in query_upper:
                    # Pattern: ASK { ... } -> ASK { GRAPH ?g { ... } }
                    ask_match = re.search(r'\bASK\s*\{', final_query, re.IGNORECASE)
                    if ask_match:
                        ask_brace_start = ask_match.end() - 1
                        # Find matching closing brace
                        brace_count = 1
                        ask_brace_end = None
                        for i in range(ask_brace_start + 1, len(final_query)):
                            if final_query[i] == '{':
                                brace_count += 1
                            elif final_query[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    ask_brace_end = i
                                    break
                        
                        if ask_brace_end:
                            before_ask = final_query[:ask_match.end()]
                            ask_body = final_query[ask_brace_start+1:ask_brace_end]
                            after_ask = final_query[ask_brace_end:]
                            
                            final_query = (
                                before_ask + "\n    GRAPH ?g {\n      " +
                                ask_body + "\n    }\n  " + after_ask
                            )
                            
                            self.logger.info(
                                "Wrapped ASK query in GRAPH ?g for multi-graph search",
                                original_length=len(sparql_query.query),
                                modified_length=len(final_query),
                            )
                
                # Handle CONSTRUCT queries - wrap WHERE in GRAPH ?g
                elif "CONSTRUCT" in query_upper:
                    where_match = re.search(r'\bWHERE\s*\{', final_query, re.IGNORECASE | re.MULTILINE)
                    if where_match:
                        where_start = where_match.start()
                        where_brace_start = where_match.end() - 1
                        
                        # Find matching closing brace for WHERE
                        brace_count = 1
                        where_brace_end = None
                        for i in range(where_brace_start + 1, len(final_query)):
                            if final_query[i] == '{':
                                brace_count += 1
                            elif final_query[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    where_brace_end = i
                                    break
                        
                        if where_brace_end:
                            before_where = final_query[:where_start]
                            where_keyword = final_query[where_start:where_brace_start+1]
                            where_body = final_query[where_brace_start+1:where_brace_end]
                            after_where = final_query[where_brace_end:]
                            
                            final_query = (
                                before_where +
                                where_keyword + "\n    GRAPH ?g {\n      " +
                                where_body + "\n    }\n  " +
                                after_where
                            )
                            
                            self.logger.info(
                                "Wrapped CONSTRUCT query in GRAPH ?g for multi-graph search",
                                original_length=len(sparql_query.query),
                                modified_length=len(final_query),
                            )
                
                # Handle DESCRIBE queries - wrap pattern in GRAPH ?g
                elif "DESCRIBE" in query_upper:
                    # DESCRIBE queries may have WHERE clause or just pattern
                    where_match = re.search(r'\bWHERE\s*\{', final_query, re.IGNORECASE)
                    if where_match:
                        where_start = where_match.start()
                        where_brace_start = where_match.end() - 1
                        
                        brace_count = 1
                        where_brace_end = None
                        for i in range(where_brace_start + 1, len(final_query)):
                            if final_query[i] == '{':
                                brace_count += 1
                            elif final_query[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    where_brace_end = i
                                    break
                        
                        if where_brace_end:
                            before_where = final_query[:where_start]
                            where_keyword = final_query[where_start:where_brace_start+1]
                            where_body = final_query[where_brace_start+1:where_brace_end]
                            after_where = final_query[where_brace_end:]
                            
                            final_query = (
                                before_where +
                                where_keyword + "\n    GRAPH ?g {\n      " +
                                where_body + "\n    }\n  " +
                                after_where
                            )
                            
                            self.logger.info(
                                "Wrapped DESCRIBE query in GRAPH ?g for multi-graph search",
                                original_length=len(sparql_query.query),
                                modified_length=len(final_query),
                            )
        
        # Wrap query in GRAPH clause if specific graph_uri is provided
        if graph_uri:
            # Check if query already has GRAPH clause - if so, remove it first
            # The LLM sometimes generates GRAPH clauses incorrectly (often with missing closing braces)
            query_upper = final_query.upper()
            graph_removed = False
            if "GRAPH" in query_upper:
                self.logger.warning(
                    "Query already contains GRAPH clause, removing it before re-wrapping",
                    query_preview=final_query[:200],
                )
                # Remove existing GRAPH clause - find and remove GRAPH <...> { ... } pattern
                import re
                # Pattern: GRAPH <uri> { ... } - remove the GRAPH wrapper but keep content
                graph_pattern = r'GRAPH\s*<[^>]+>\s*\{'
                graph_match = re.search(graph_pattern, final_query, re.IGNORECASE)
                if graph_match:
                    graph_start = graph_match.start()
                    graph_brace_start = graph_match.end() - 1  # Position of {
                    
                    # Find matching closing brace for GRAPH (or end of query if missing)
                    brace_count = 1
                    graph_brace_end = None
                    for i in range(graph_brace_start + 1, len(final_query)):
                        if final_query[i] == '{':
                            brace_count += 1
                        elif final_query[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                graph_brace_end = i
                                break
                    
                    if graph_brace_end:
                        # Remove GRAPH wrapper, keep content
                        before_graph = final_query[:graph_start]
                        graph_content = final_query[graph_brace_start + 1:graph_brace_end]
                        after_graph = final_query[graph_brace_end + 1:]
                        final_query = before_graph + graph_content + after_graph
                        self.logger.info("Removed existing GRAPH clause from query")
                        graph_removed = True
                    else:
                        # GRAPH clause is missing closing brace - remove GRAPH and add closing brace
                        self.logger.warning("GRAPH clause missing closing brace, fixing")
                        before_graph = final_query[:graph_start]
                        graph_content = final_query[graph_brace_start + 1:]  # Everything after GRAPH {
                        # Add closing brace for WHERE if needed
                        final_query = before_graph + graph_content + "\n}"
                        self.logger.info("Fixed missing closing brace in GRAPH clause")
                        graph_removed = True
            
            # Now wrap in GRAPH clause if still needed (and we removed the old one)
            if graph_removed or ("GRAPH" not in final_query.upper() and "FROM NAMED" not in final_query.upper()):
                self.logger.debug(
                    "Wrapping query in GRAPH clause",
                    original_braces=original_braces,
                    query_preview=final_query[:200],
                )
                import re
                
                # For SELECT queries, wrap WHERE content in GRAPH
                if final_query.upper().strip().startswith("SELECT"):
                    # Find WHERE { and the matching closing brace
                    where_match = re.search(r'\bWHERE\s*\{', final_query, re.IGNORECASE)
                    if where_match:
                        where_brace_pos = where_match.end() - 1  # Position of opening {
                        
                        # Find matching closing brace by counting
                        brace_count = 1
                        where_close_pos = None
                        for i in range(where_brace_pos + 1, len(final_query)):
                            char = final_query[i]
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    where_close_pos = i
                                    break
                        
                        if where_close_pos is not None:
                            # #region agent log
                            import json
                            with open('/Users/manu/Documents/repos/contract-jena/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'A',
                                    'location': 'sparql_generator.py:353',
                                    'message': 'Before splitting query',
                                    'data': {
                                        'where_brace_pos': where_brace_pos,
                                        'where_close_pos': where_close_pos,
                                        'query_length': len(final_query),
                                        'query_end_preview': final_query[max(0, where_close_pos-50):where_close_pos+10]
                                    },
                                    'timestamp': __import__('time').time() * 1000
                                }) + '\n')
                            # #endregion
                            
                            # Split query into parts
                            prefix = final_query[:where_brace_pos + 1]  # Up to and including "WHERE {"
                            where_body = final_query[where_brace_pos + 1:where_close_pos]  # Content inside WHERE
                            suffix = final_query[where_close_pos + 1:]  # Everything after closing }
                            
                            # #region agent log
                            with open('/Users/manu/Documents/repos/contract-jena/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'B',
                                    'location': 'sparql_generator.py:360',
                                    'message': 'After splitting query parts',
                                    'data': {
                                        'prefix_end': repr(prefix[-30:]),
                                        'where_body_preview': repr(where_body[:50]),
                                        'where_body_end': repr(where_body[-30:]),
                                        'suffix': repr(suffix),
                                        'suffix_length': len(suffix)
                                    },
                                    'timestamp': __import__('time').time() * 1000
                                }) + '\n')
                            # #endregion
                            
                            # Clean and wrap
                            body_clean = where_body.strip()
                            
                            # #region agent log
                            with open('/Users/manu/Documents/repos/contract-jena/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'C',
                                    'location': 'sparql_generator.py:375',
                                    'message': 'Before reconstruction',
                                    'data': {
                                        'body_clean_preview': repr(body_clean[:50]),
                                        'body_clean_end': repr(body_clean[-30:]),
                                        'graph_uri': graph_uri
                                    },
                                    'timestamp': __import__('time').time() * 1000
                                }) + '\n')
                            # #endregion
                            
                            # Reconstruct: WHERE { GRAPH <uri> { body } }
                            graph_open = "\n  GRAPH <" + graph_uri + "> {\n    "
                            graph_close = "\n  }\n"
                            where_close = "}"
                            
                            # Debug: Print to stderr so we can see it
                            import sys
                            print(f"DEBUG: prefix ends with: {repr(prefix[-30:])}", file=sys.stderr)
                            print(f"DEBUG: body_clean ends with: {repr(body_clean[-30:])}", file=sys.stderr)
                            print(f"DEBUG: suffix = {repr(suffix)}", file=sys.stderr)
                            print(f"DEBUG: graph_close = {repr(graph_close)}", file=sys.stderr)
                            print(f"DEBUG: where_close = {repr(where_close)}", file=sys.stderr)
                            
                            # Build parts separately to verify
                            part1 = prefix + graph_open + body_clean
                            part2 = graph_close + where_close + suffix
                            final_query = part1 + part2
                            
                            print(f"DEBUG: After reconstruction - Opens: {final_query.count('{')}, Closes: {final_query.count('}')}", file=sys.stderr)
                            print(f"DEBUG: Query ends with: {repr(final_query[-100:])}", file=sys.stderr)
                            
                            # #region agent log
                            with open('/Users/manu/Documents/repos/contract-jena/.cursor/debug.log', 'a') as f:
                                f.write(json.dumps({
                                    'sessionId': 'debug-session',
                                    'runId': 'run1',
                                    'hypothesisId': 'D',
                                    'location': 'sparql_generator.py:395',
                                    'message': 'After reconstruction',
                                    'data': {
                                        'opens': final_query.count('{'),
                                        'closes': final_query.count('}'),
                                        'query_end': repr(final_query[-150:]),
                                        'graph_open': repr(graph_open),
                                        'graph_close': repr(graph_close),
                                        'where_close': repr(where_close)
                                    },
                                    'timestamp': __import__('time').time() * 1000
                                }) + '\n')
                            # #endregion
                            
                            # Verify braces are balanced
                            opens = final_query.count('{')
                            closes = final_query.count('}')
                            if opens != closes:
                                self.logger.error(
                                    "Brace mismatch after GRAPH wrap - attempting fix",
                                    opens=opens,
                                    closes=closes,
                                    query_tail=final_query[-200:],
                                )
                                # Try to fix by adding missing closing braces
                                if opens > closes:
                                    missing = opens - closes
                                    final_query = final_query + "\n" + "}" * missing
                                    self.logger.info(
                                        "Added missing closing braces",
                                        count=missing,
                                    )
                                else:
                                    # Too many closing braces - this is harder to fix
                                    # Log and use original query
                                    self.logger.warning(
                                        "Too many closing braces, using original query",
                                        excess=closes - opens,
                                    )
                                    final_query = sparql_query.query
                        else:
                            self.logger.warning("Could not find WHERE closing brace")
                    else:
                        # No WHERE found, this is unusual for SELECT
                        self.logger.warning("SELECT query without WHERE clause", query_preview=final_query[:200])
                elif final_query.upper().strip().startswith("ASK"):
                    # For ASK queries, wrap pattern in GRAPH
                    # Pattern: ASK { ... } -> ASK { GRAPH <uri> { ... } }
                    pattern = r"(ASK\s*\{)"
                    replacement = rf"\1\n  GRAPH <{graph_uri}> {{"
                    final_query = re.sub(pattern, replacement, final_query, flags=re.IGNORECASE)
                    # Find the last closing brace and add closing GRAPH brace before it
                    last_brace = final_query.rfind('}')
                    if last_brace > 0:
                        final_query = final_query[:last_brace] + "\n  }" + final_query[last_brace:]
                else:
                    # For other query types, wrap WHERE content in GRAPH
                    if "WHERE" in final_query.upper():
                        # Simple approach: WHERE { ... } -> WHERE { GRAPH <uri> { ... } }
                        pattern = r"(WHERE\s*\{)"
                        replacement = rf"\1\n  GRAPH <{graph_uri}> {{"
                        final_query = re.sub(pattern, replacement, final_query, flags=re.IGNORECASE)
                        # Add closing brace before the last brace of WHERE
                        # Find the matching closing brace
                        brace_count = 0
                        found_where = False
                        for i, char in enumerate(final_query):
                            if final_query[i:i+5].upper() == "WHERE":
                                found_where = True
                            elif found_where and char == '{':
                                brace_count += 1
                            elif found_where and char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # This is the closing brace of WHERE
                                    final_query = final_query[:i] + "\n  }" + final_query[i:]
                                    break
        
        # Log the generated query for debugging
        self.logger.info(
            "SPARQL query generated",
            question=question[:100],
            query_type=sparql_query.query_type,
            query_length=len(final_query),
            graph_uri=graph_uri,
            query_preview=final_query[:200] + "..." if len(final_query) > 200 else final_query,
        )
        
        # Validate query before execution
        is_valid, validation_error = self._validate_sparql_query(final_query)
        if not is_valid:
            error_msg = f"SPARQL query validation failed: {validation_error}"
            self.logger.error(
                "SPARQL query validation failed",
                question=question[:100],
                error=validation_error,
                query=final_query[:500],
            )
            return {
                "question": question,
                "query": final_query,
                "explanation": sparql_query.explanation,
                "results": [{"error": error_msg, "validation_failed": True}],
                "validation_error": validation_error,
            }
        
        # Execute query
        results = []
        execution_error = None
        try:
            self.logger.debug("Executing SPARQL query", query_type=sparql_query.query_type)
            
            if sparql_query.query_type == "SELECT" or sparql_query.query_type == "UNKNOWN":
                # Try SELECT for unknown queries (most common)
                results = self.sparql_store.execute_select(final_query)
                self.logger.info(
                    "SPARQL SELECT executed successfully",
                    result_count=len(results),
                    question=question[:100],
                )
            elif sparql_query.query_type == "ASK":
                ask_result = self.sparql_store.execute_ask(final_query)
                results = [{"result": ask_result}]
                self.logger.info(
                    "SPARQL ASK executed successfully",
                    result=ask_result,
                    question=question[:100],
                )
            else:
                results = [{"info": f"Query type {sparql_query.query_type} - manual review needed"}]
                self.logger.warning(
                    "Unsupported query type",
                    query_type=sparql_query.query_type,
                    question=question[:100],
                )
        except Exception as e:
            execution_error = str(e)
            error_details = {
                "error": execution_error,
                "error_type": type(e).__name__,
                "query": final_query[:500],  # Log first 500 chars of query
            }
            
            # Provide more detailed error information
            if "syntax" in execution_error.lower() or "parse" in execution_error.lower():
                error_details["suggestion"] = "Check SPARQL syntax - may need to review query structure"
            elif "timeout" in execution_error.lower():
                error_details["suggestion"] = "Query timed out - may be too complex or dataset too large"
            elif "401" in execution_error or "unauthorized" in execution_error.lower():
                error_details["suggestion"] = "Authentication failed - check Fuseki credentials"
            elif "404" in execution_error or "not found" in execution_error.lower():
                error_details["suggestion"] = "Endpoint not found - check Fuseki URL and dataset name"
            
            self.logger.error(
                "SPARQL query execution failed",
                question=question[:100],
                error=execution_error,
                error_type=type(e).__name__,
                query_preview=final_query[:200],
                **error_details,
            )
            results = [error_details]
        
        result_count = len(results) if results and not any("error" in r for r in results) else 0
        
        self.log_complete(
            "sparql_execution",
            question=question[:100],
            success=execution_error is None,
            result_count=result_count,
        )
        
        # Save query to log file for debugging
        log_file = self._save_query_to_log(
            question=question,
            query=final_query,
            query_type=sparql_query.query_type,
            graph_uri=graph_uri,
            validation_passed=is_valid,
            execution_error=execution_error,
            result_count=result_count,
        )
        
        if log_file:
            self.logger.debug("SPARQL query saved to log", log_file=str(log_file))
        
        return {
            "question": question,
            "query": final_query,  # Return the final query with GRAPH clause if added
            "explanation": sparql_query.explanation,
            "results": results,
            "validation_passed": is_valid,
            "execution_error": execution_error,
            "log_file": str(log_file) if log_file else None,
        }

    # Pre-built query templates for common questions
    QUERY_TEMPLATES = {
        "all_contracts": """
            SELECT ?contract ?value ?effectiveDate ?jurisdiction
            WHERE {
                ?contract rdf:type proc:Contract .
                OPTIONAL { ?contract proc:contractValue ?value }
                OPTIONAL { ?contract proc:effectiveDate ?effectiveDate }
                OPTIONAL { ?contract proc:governedBy ?jurisdiction }
            }
        """,
        "high_risk_contracts": """
            SELECT DISTINCT ?contract ?clause ?risk
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:hasClause ?clause .
                ?clause proc:introducesRisk ?risk .
                FILTER(CONTAINS(STR(?risk), "High"))
            }
        """,
        "contracts_by_jurisdiction": """
            SELECT ?contract ?value
            WHERE {
                ?contract rdf:type proc:Contract .
                ?contract proc:governedBy proc:{jurisdiction} .
                OPTIONAL { ?contract proc:contractValue ?value }
            }
        """,
        "termination_clauses": """
            SELECT ?contract ?clause ?noticePeriod
            WHERE {
                ?contract proc:hasClause ?clause .
                ?clause rdf:type proc:TerminationClause .
                ?clause proc:noticePeriod ?noticePeriod .
            }
            ORDER BY ?noticePeriod
        """,
    }

    def get_template_query(self, template_name: str, **params: Any) -> str:
        """Get a pre-built query template with parameters filled in."""
        template = self.QUERY_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(f"Unknown template: {template_name}")
        return template.format(**params) if params else template
