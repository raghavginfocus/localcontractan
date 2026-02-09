"""
Unified Query Analyzer - Combines complexity detection and query decomposition.

This analyzer performs both complexity classification and query decomposition in a 
SINGLE LLM call for efficiency, then provides a complete execution plan.
"""

import time
from typing import Any
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class QueryComplexity(str, Enum):
    """Query complexity levels."""
    SIMPLE = "simple"
    COMPLEX = "complex"


class SubQuery(BaseModel):
    """A sub-query in the execution plan."""
    
    step_number: int = Field(description="Order in execution sequence")
    question: str = Field(description="The sub-question to answer")
    purpose: str = Field(description="Why this step is needed")
    query_type: str = Field(
        default="hybrid",
        description="Type: kg_only, vector_only, or hybrid"
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="Step numbers this depends on"
    )


class QueryAnalysisResult(BaseModel):
    """Complete analysis result with complexity and execution plan."""
    
    original_question: str = Field(description="Original question")
    complexity: QueryComplexity = Field(description="Detected complexity")
    confidence: float = Field(description="Confidence in classification (0-1)")
    reasoning: str = Field(description="Explanation of classification")
    
    # Execution plan
    sub_queries: list[SubQuery] = Field(
        default_factory=list,
        description="Ordered sub-queries (empty for SIMPLE queries)"
    )
    synthesis_strategy: str = Field(
        default="direct",
        description="How to combine results"
    )
    
    # Timing
    analysis_time_ms: float = Field(default=0.0, description="Time taken for analysis")
    timestamp: datetime = Field(default_factory=datetime.now)


class UnifiedQueryAnalyzer(BaseAgent):
    """
    Unified analyzer that performs complexity detection AND query decomposition
    in a single LLM call for maximum efficiency.
    """
    
    UNIFIED_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are a query analysis expert for a contract knowledge graph system.

Analyze the query and provide:
1. COMPLEXITY: SIMPLE or COMPLEX
2. REASONING: Brief explanation (1-2 sentences)
3. EXECUTION PLAN: How to retrieve information

SIMPLE queries (direct KG retrieval) - use query_type kg_only when the answer is in the knowledge graph:
- Counts: "how many contracts", "count clauses"
- Lists: "list all contracts", "what types of clauses", "find high-risk contracts", "contracts by risk", "high-value contracts"
- Direct lookups: "what is the value of contract X"
- Single entity queries: "show termination clause for contract X"
- Risk/severity/value/jurisdiction: "find high-risk contracts", "contracts by risk" ->
  kg_only (KG has proc:hasRisk, proc:severity, proc:contractValue, proc:governedBy)

COMPLEX queries (need decomposition):
- Analysis: "analyze risk", "compare contracts"
- Multi-aspect: "termination AND liability AND penalties"
- Ranking: "which contracts have highest risk"
- Cross-document: "compare across all contracts"

For SIMPLE queries:
- Return single step with appropriate query_type (kg_only, vector_only, or hybrid)

For COMPLEX queries - CRITICAL DECOMPOSITION RULES:

**INDEPENDENT QUERIES ONLY:**
- Each sub-query MUST retrieve ALL relevant data for its topic
- NO dependencies on previous results
- NO phrases: "specific", "particular", "from step X", "with Y from previous"
- Query format: "Find ALL [entity type] for ALL contracts"

**EXAMPLES OF CORRECT DECOMPOSITION:**
Bad: "Find termination clauses for contracts with high risk"
Good: "Find ALL termination clauses for ALL contracts"

Bad: "Identify jurisdictions for contracts with specific termination clauses"
Good: "Find ALL governing jurisdictions for ALL contracts"

Bad: "Analyze liability clauses for contracts in specific jurisdictions"
Good: "Find ALL liability clauses for ALL contracts"

**EXECUTION:**
- DEPENDS_ON is for ORDER only (e.g., get clauses before analyzing them)
- NOT for filtering or passing data
- Synthesis will combine all results intelligently

**QUERY TYPES:**
- kg_only: Structured data (contracts, clauses, jurisdictions, risks)
- vector_only: Text search (clause content, descriptions)
- hybrid: Both needed

Format your response as:

COMPLEXITY: [SIMPLE or COMPLEX]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]

EXECUTION PLAN:
STEP 1: [question]
  PURPOSE: [why needed]
  TYPE: [kg_only/vector_only/hybrid]
  DEPENDS_ON: []

[Additional steps if COMPLEX]

SYNTHESIS: [how to combine results]"""),
        ("human", "{question}"),
    ])

    async def process(
        self,
        input_data: str | dict[str, Any]
    ) -> QueryAnalysisResult:
        """
        Analyze query complexity and create execution plan in a single call.
        
        Args:
            input_data: Query string or dict with 'question' key
            
        Returns:
            QueryAnalysisResult with complexity and execution plan
        """
        # Extract question
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
        else:
            question = input_data
        
        start_time = time.time()
        
        self.log_start("unified_query_analysis", question=question[:100])
        logger.info("=" * 60)
        logger.info(f"UNIFIED QUERY ANALYSIS - Question: {question[:100]}")
        
        try:
            # Single LLM call for both complexity and decomposition
            chain = self.UNIFIED_ANALYSIS_PROMPT | self.llm | StrOutputParser()
            
            llm_start = time.time()
            response = await chain.ainvoke({"question": question})
            llm_time = (time.time() - llm_start) * 1000
            
            logger.info(f"  LLM analysis completed in {llm_time:.2f}ms")
            
            # Parse the unified response
            result = self._parse_unified_response(response, question)
            
            # Calculate total time
            analysis_time = (time.time() - start_time) * 1000
            result.analysis_time_ms = analysis_time
            
            logger.info(f"  Complexity: {result.complexity.value}")
            logger.info(f"  Confidence: {result.confidence:.2f}")
            logger.info(f"  Reasoning: {result.reasoning[:100]}")
            logger.info(f"  Sub-queries: {len(result.sub_queries)}")
            
            # Log each decomposed sub-query for transparency
            if result.sub_queries:
                logger.info("  Decomposed Query Plan:")
                for sq in result.sub_queries:
                    logger.info(f"    Step {sq.step_number}: {sq.question[:80]}")
                    logger.info(f"      Purpose: {sq.purpose[:60]}")
                    logger.info(f"      Type: {sq.query_type}")
                    logger.info(f"      Depends on: {sq.depends_on}")
            
            logger.info(f"  Total analysis time: {analysis_time:.2f}ms")
            
            self.log_complete(
                "unified_query_analysis",
                complexity=result.complexity.value,
                sub_queries=len(result.sub_queries),
                analysis_time_ms=analysis_time,
            )
            
            return result
            
        except Exception as e:
            self.log_error("unified_query_analysis", e, question=question[:100])
            logger.error(f"  Analysis failed: {e}")
            
            # Return fallback simple plan
            analysis_time = (time.time() - start_time) * 1000
            return self._create_fallback_plan(question, analysis_time)
    
    def _parse_unified_response(
        self,
        response: str,
        question: str
    ) -> QueryAnalysisResult:
        """Parse the unified LLM response into structured result."""
        import re
        
        # Extract complexity
        complexity_match = re.search(
            r"COMPLEXITY:\s*(SIMPLE|COMPLEX)",
            response,
            re.IGNORECASE
        )
        complexity_str = complexity_match.group(1).upper() if complexity_match else "SIMPLE"
        complexity = QueryComplexity(complexity_str.lower())
        
        # Extract confidence
        confidence_match = re.search(r"CONFIDENCE:\s*(0?\.\d+|1\.0|1)", response)
        confidence = float(confidence_match.group(1)) if confidence_match else 0.8
        
        # Extract reasoning
        reasoning_match = re.search(
            r"REASONING:\s*(.+?)(?=EXECUTION PLAN:|$)",
            response,
            re.DOTALL | re.IGNORECASE
        )
        reasoning = reasoning_match.group(1).strip() if reasoning_match else "Analysis completed"
        
        # Extract execution plan
        sub_queries = self._parse_execution_plan(response)
        
        # Extract synthesis strategy
        synthesis_match = re.search(
            r"SYNTHESIS:\s*(.+?)$",
            response,
            re.DOTALL | re.IGNORECASE
        )
        synthesis = synthesis_match.group(1).strip() if synthesis_match else "Direct answer"
        
        return QueryAnalysisResult(
            original_question=question,
            complexity=complexity,
            confidence=confidence,
            reasoning=reasoning,
            sub_queries=sub_queries,
            synthesis_strategy=synthesis,
        )
    
    def _parse_execution_plan(self, text: str) -> list[SubQuery]:
        """Parse execution plan into SubQuery objects."""
        import re
        
        sub_queries = []
        
        # Find all STEP blocks
        step_pattern = r'STEP\s+(\d+):\s*(.+?)(?=STEP\s+\d+:|SYNTHESIS:|$)'
        steps = re.findall(step_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for step_num_str, step_content in steps:
            step_num = int(step_num_str)
            
            # Extract question (first line)
            lines = [l.strip() for l in step_content.split('\n') if l.strip()]
            question = lines[0] if lines else step_content[:100]
            
            # Extract PURPOSE
            purpose_match = re.search(
                r'PURPOSE:\s*(.+?)(?=TYPE:|DEPENDS_ON:|$)',
                step_content,
                re.IGNORECASE | re.DOTALL
            )
            purpose = (
                purpose_match.group(1).strip() if purpose_match
                else "Execute step"
            )
            
            # Extract TYPE
            type_match = re.search(
                r'TYPE:\s*(\w+)',
                step_content,
                re.IGNORECASE
            )
            query_type = (
                type_match.group(1).lower() if type_match
                else "hybrid"
            )
            
            # Extract DEPENDS_ON
            depends_match = re.search(
                r'DEPENDS_ON:\s*\[([^\]]*)\]',
                step_content,
                re.IGNORECASE
            )
            depends_on = []
            if depends_match:
                deps_str = depends_match.group(1)
                depends_on = [
                    int(d.strip())
                    for d in deps_str.split(',')
                    if d.strip().isdigit()
                ]
            
            sub_queries.append(SubQuery(
                step_number=step_num,
                question=question,
                purpose=purpose,
                query_type=query_type,
                depends_on=depends_on,
            ))
        
        return sub_queries
    
    def _create_fallback_plan(
        self,
        question: str,
        analysis_time: float
    ) -> QueryAnalysisResult:
        """Create simple fallback plan if analysis fails."""
        return QueryAnalysisResult(
            original_question=question,
            complexity=QueryComplexity.SIMPLE,
            confidence=0.5,
            reasoning="Fallback plan due to analysis error",
            sub_queries=[
                SubQuery(
                    step_number=1,
                    question=question,
                    purpose="Answer the question directly",
                    query_type="hybrid",
                    depends_on=[],
                )
            ],
            synthesis_strategy="Direct answer",
            analysis_time_ms=analysis_time,
        )
    
    def get_execution_batches(
        self,
        sub_queries: list[SubQuery]
    ) -> list[list[SubQuery]]:
        """
        Group sub-queries into batches that can be executed in parallel.
        
        Returns list of batches where each batch can run concurrently.
        """
        if not sub_queries:
            return []
        
        # Build dependency graph
        graph = {sq.step_number: sq.depends_on for sq in sub_queries}
        query_map = {sq.step_number: sq for sq in sub_queries}
        
        # Calculate in-degree for each query
        in_degree = {step: len(deps) for step, deps in graph.items()}
        
        batches = []
        remaining = set(graph.keys())
        
        while remaining:
            # Find all queries with no remaining dependencies
            batch_steps = [
                step for step in remaining
                if in_degree[step] == 0
            ]
            
            if not batch_steps:
                # Circular dependency - break it
                logger.warning("Circular dependency detected, breaking")
                batch_steps = [min(remaining)]
            
            batch = [query_map[step] for step in sorted(batch_steps)]
            batches.append(batch)
            
            # Remove batch from remaining and update in_degrees
            for step in batch_steps:
                remaining.remove(step)
                # Decrease in_degree for queries that depend on this one
                for other_step in remaining:
                    if step in graph[other_step]:
                        in_degree[other_step] -= 1
        
        return batches

