"""
Smart Query Decomposer Agent

This agent intelligently decomposes complex queries into sub-queries.
Key improvements:
1. Detects if decomposition is actually needed (avoids over-decomposing)
2. Creates meaningful, focused sub-queries
3. Identifies dependencies between sub-queries
4. Handles multi-hop reasoning requirements
"""

from typing import List, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from agents.shared.base import BaseAgent
from config import Settings


class QueryComplexity(str, Enum):
    """Query complexity levels."""
    SIMPLE = "simple"  # Single entity, single property
    MODERATE = "moderate"  # Multiple entities or properties
    COMPLEX = "complex"  # Multi-hop, patterns, aggregations
    ANALYTICAL = "analytical"  # Requires analysis across multiple contracts


class SubQuery(BaseModel):
    """A sub-query with metadata."""
    query: str = Field(description="The sub-query text")
    purpose: str = Field(description="What this sub-query aims to find")
    depends_on: List[int] = Field(
        default_factory=list,
        description="Indices of sub-queries this depends on"
    )
    entity_focus: Optional[str] = Field(
        None,
        description="Primary entity type this query focuses on"
    )
    expected_info: str = Field(
        description="What information we expect to get"
    )


class DecompositionPlan(BaseModel):
    """Plan for query decomposition."""
    should_decompose: bool = Field(
        description="Whether decomposition is beneficial"
    )
    complexity: QueryComplexity = Field(
        description="Assessed complexity level"
    )
    reasoning: str = Field(
        description="Why decomposition is/isn't needed"
    )
    sub_queries: List[SubQuery] = Field(
        default_factory=list,
        description="List of sub-queries if decomposition is needed"
    )
    execution_order: List[List[int]] = Field(
        default_factory=list,
        description="Batches of sub-query indices to execute in order"
    )


class SmartQueryDecomposer(BaseAgent):
    """
    Intelligent query decomposer that avoids unnecessary decomposition.
    
    This agent:
    1. Assesses if a query actually needs decomposition
    2. Creates focused, meaningful sub-queries
    3. Identifies dependencies and execution order
    4. Handles multi-hop reasoning chains
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm: Optional[BaseChatModel] = None
    ):
        super().__init__(settings, llm)
        self.name = "SmartQueryDecomposer"
        self._setup_prompts()
    
    async def process(self, input_data: Any) -> Any:
        """Required abstract method - delegates to decompose_query."""
        if isinstance(input_data, str):
            return await self.decompose_query(input_data)
        return await self.decompose_query(input_data.get("question", ""))
    
    def _setup_prompts(self):
        """Setup decomposition prompt templates."""
        self.decomposition_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert query analyzer for a contract \
knowledge graph system.

Your task is to determine if a query needs decomposition and, if so, \
break it down intelligently.

**When NOT to decompose:**
- Simple lookups (e.g., "What is the value of X?")
- Single entity queries (e.g., "Show me contract ABC")
- Direct property queries (e.g., "What's the payment term?")

**When TO decompose:**
- Multi-hop queries (need info from A to find B)
- Pattern analysis (comparing across multiple entities)
- Aggregations requiring multiple data points
- Questions with multiple distinct parts

**Decomposition principles:**
1. Each sub-query should have a clear, focused purpose
2. Sub-queries should be independently answerable
3. Identify dependencies (some queries need results from others)
4. Keep it minimal - don't over-decompose

Output as structured JSON."""),
            ("human", """Question: {question}

Available context:
- Knowledge Graph: Contract entities, clauses, obligations, risks
- Vector Store: Full text of contract clauses

Analyze this question:
1. Does it need decomposition? (Be conservative - simple is better)
2. What's the complexity level?
3. If decomposing, what are the focused sub-queries?
4. What's the execution order (considering dependencies)?

Provide your analysis as JSON with these fields:
- should_decompose: boolean
- complexity: "simple" | "moderate" | "complex" | "analytical"
- reasoning: string explaining your decision
- sub_queries: list of objects with:
  - query: string
  - purpose: string
  - depends_on: list of integers (indices of dependencies)
  - entity_focus: string (optional)
  - expected_info: string
- execution_order: list of lists (batches of sub-query indices)

Example for "Find contracts with payment terms > 30 days AND \
high risk":
{{
  "should_decompose": true,
  "complexity": "moderate",
  "reasoning": "Requires two independent lookups that can be combined",
  "sub_queries": [
    {{
      "query": "Find contracts with payment terms greater than 30 days",
      "purpose": "Identify contracts by payment term criteria",
      "depends_on": [],
      "entity_focus": "Contract",
      "expected_info": "List of contract IDs with payment terms > 30 days"
    }},
    {{
      "query": "Find contracts with high risk classification",
      "purpose": "Identify high-risk contracts",
      "depends_on": [],
      "entity_focus": "Contract",
      "expected_info": "List of contract IDs with high risk"
    }}
  ],
  "execution_order": [[0, 1]]
}}

Example for "What is the payment term in contract ABC?":
{{
  "should_decompose": false,
  "complexity": "simple",
  "reasoning": "Direct property lookup, no decomposition needed",
  "sub_queries": [],
  "execution_order": []
}}""")
        ])
    
    async def decompose_query(
        self,
        question: str
    ) -> DecompositionPlan:
        """
        Analyze and potentially decompose a query.
        
        DEMO MODE: Always returns SIMPLE plan for fast responses (~40 seconds).
        
        Args:
            question: The user's question
            
        Returns:
            DecompositionPlan with analysis and sub-queries
        """
        self.logger.info(f"Analyzing query: {question[:100]}...")
        
        # ⚡ DEMO MODE: Force all queries to be SIMPLE
        # This bypasses LLM decomposition analysis for fast responses
        plan = DecompositionPlan(
            should_decompose=False,
            complexity=QueryComplexity.SIMPLE,
            reasoning="Demo mode: treating all queries as simple for fast response (~40s)",
            sub_queries=[],
            execution_order=[]
        )
        
        self.logger.info(
            f"Decomposition analysis - Complexity: {plan.complexity}, "
            f"Should decompose: {plan.should_decompose}"
        )
        self.logger.info(f"No decomposition needed: {plan.reasoning}")
        
        return plan
        
        # ========== ORIGINAL CODE (Commented out for demo) ==========
        # Uncomment below to restore full decomposition functionality
        #
        # # Create structured LLM - let LangChain auto-detect best method
        # structured_llm = self.llm.with_structured_output(DecompositionPlan)
        #
        # # Generate decomposition plan
        # chain = self.decomposition_prompt | structured_llm
        #
        # try:
        #     plan = await chain.ainvoke({
        #         "question": question
        #     })
        #
        #     # Handle None response from LLM (structured output not supported)
        #     if plan is None:
        #         self.logger.warning(
        #             "LLM returned None - structured output may not be supported. "
        #             "Treating query as simple (no decomposition)."
        #         )
        #         plan = DecompositionPlan(
        #             should_decompose=False,
        #             complexity=QueryComplexity.SIMPLE,
        #             reasoning="LLM structured output unavailable",
        #             sub_queries=[],
        #             execution_order=[]
        #         )
        # except Exception as e:
        #     self.logger.error(f"Decomposition failed: {e}. Treating as simple.")
        #     plan = DecompositionPlan(
        #         should_decompose=False,
        #         complexity=QueryComplexity.SIMPLE,
        #         reasoning=f"Decomposition error: {str(e)}",
        #         sub_queries=[],
        #         execution_order=[]
        #     )
        #
        # self.logger.info(
        #     f"Decomposition analysis - Complexity: {plan.complexity}, "
        #     f"Should decompose: {plan.should_decompose}"
        # )
        #
        # if plan.should_decompose:
        #     self.logger.info(f"Created {len(plan.sub_queries)} sub-queries")
        #     for i, sq in enumerate(plan.sub_queries):
        #         deps = (f" (depends on: {sq.depends_on})"
        #                 if sq.depends_on else "")
        #         self.logger.info(f"  {i}: {sq.query[:80]}...{deps}")
        # else:
        #     self.logger.info(f"No decomposition needed: {plan.reasoning}")
        #
        # return plan
        # ========== END ORIGINAL CODE ==========
    
    def get_execution_batches(
        self,
        plan: DecompositionPlan
    ) -> List[List[SubQuery]]:
        """
        Get sub-queries organized into execution batches.
        
        Args:
            plan: The decomposition plan
            
        Returns:
            List of batches, where each batch contains sub-queries
            that can be executed in parallel
        """
        if not plan.should_decompose or not plan.sub_queries:
            return []
        
        batches = []
        for batch_indices in plan.execution_order:
            batch = [plan.sub_queries[i] for i in batch_indices]
            batches.append(batch)
        
        return batches
    
    def is_multi_hop(self, plan: DecompositionPlan) -> bool:
        """
        Check if the query requires multi-hop reasoning.
        
        Multi-hop means some sub-queries depend on results from others.
        
        Args:
            plan: The decomposition plan
            
        Returns:
            True if multi-hop reasoning is needed
        """
        if not plan.should_decompose:
            return False
        
        # Check if any sub-query has dependencies
        for sq in plan.sub_queries:
            if sq.depends_on:
                return True
        
        return False


