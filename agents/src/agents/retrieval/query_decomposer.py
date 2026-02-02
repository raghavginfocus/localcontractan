"""
Query Decomposer Agent - Breaks complex queries into executable sub-questions.

Decomposes multi-faceted queries into a sequence of simpler sub-queries that
can be executed step-by-step to build up the final answer.
"""

from typing import Any
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agents.shared.base import BaseAgent


class SubQuery(BaseModel):
    """A sub-query in the decomposition plan."""
    
    step_number: int = Field(description="Order in execution sequence")
    question: str = Field(description="The sub-question to answer")
    purpose: str = Field(description="Why this step is needed")
    depends_on: list[int] = Field(
        default_factory=list,
        description="Step numbers this depends on"
    )
    query_type: str = Field(
        default="hybrid",
        description="Type: kg_only, vector_only, or hybrid"
    )


class QueryPlan(BaseModel):
    """Complete decomposition plan for a complex query."""
    
    original_question: str = Field(description="Original complex question")
    sub_queries: list[SubQuery] = Field(
        default_factory=list,
        description="Ordered list of sub-queries"
    )
    synthesis_strategy: str = Field(
        description="How to combine sub-query results"
    )
    expected_answer_type: str = Field(
        description="Type of final answer expected"
    )


class QueryDecomposer(BaseAgent):
    """
    Decomposes complex queries into executable sub-questions.
    
    Uses LLM to understand query intent and break it down into
    logical steps that can be executed sequentially.
    """
    
    DECOMPOSITION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """Break down this query into executable steps. Be concise.

For SIMPLE queries: return ONE step.
For COMPLEX queries: break into 2-4 steps max.

Each step needs:
- QUESTION: The sub-question to answer
- PURPOSE: Why this step is needed
- TYPE: vector_only (start here for complex), kg_only, or hybrid
- DEPENDS_ON: Step numbers this depends on (empty for first step)

IMPORTANT: For complex queries, START with vector_only to get context quickly.

Example - Complex query:
STEP 1: Search for relevant clauses about [topic]
  PURPOSE: Get initial context from text
  TYPE: vector_only
  DEPENDS_ON: []

STEP 2: Query knowledge graph for structured data
  PURPOSE: Get facts and relationships
  TYPE: kg_only
  DEPENDS_ON: [1]

Now decompose:"""),
        ("human", "{question}"),
    ])
    
    PARSING_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """Parse the decomposition into structured format.

Extract:
- Step number
- Question/task
- Purpose
- Dependencies (step numbers)
- Query type

Return as JSON array."""),
        ("human", "Parse this decomposition:\n\n{decomposition}"),
    ])

    async def process(
        self,
        input_data: str | dict[str, Any]
    ) -> QueryPlan:
        """
        Decompose complex query into sub-queries.
        
        Args:
            input_data: Query string or dict with 'question' key
            
        Returns:
            QueryPlan with ordered sub-queries
        """
        # Extract question
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
        else:
            question = input_data
        
        self.log_start("query_decomposition", question=question[:100])
        
        # Generate decomposition
        decomposition_chain = (
            self.DECOMPOSITION_PROMPT | self.llm | StrOutputParser()
        )
        
        try:
            decomposition_text = await decomposition_chain.ainvoke(
                {"question": question}
            )
            
            # Parse decomposition into structured format
            sub_queries = self._parse_decomposition(decomposition_text)
            
            # Extract synthesis strategy and answer type
            synthesis = self._extract_synthesis_strategy(decomposition_text)
            answer_type = self._extract_answer_type(decomposition_text)
            
            plan = QueryPlan(
                original_question=question,
                sub_queries=sub_queries,
                synthesis_strategy=synthesis,
                expected_answer_type=answer_type,
            )
            
            self.log_complete(
                "query_decomposition",
                num_steps=len(sub_queries),
                answer_type=answer_type,
            )
            
            return plan
            
        except Exception as e:
            self.log_error("query_decomposition", e, question=question[:100])
            # Return simple fallback plan
            return self._create_fallback_plan(question)
    
    def _parse_decomposition(self, text: str) -> list[SubQuery]:
        """Parse decomposition text into SubQuery objects."""
        import re
        
        sub_queries = []
        
        # Find all STEP blocks
        step_pattern = r'STEP\s+(\d+):\s*(.+?)(?=STEP\s+\d+:|SYNTHESIS:|$)'
        steps = re.findall(step_pattern, text, re.DOTALL | re.IGNORECASE)
        
        for step_num_str, step_content in steps:
            step_num = int(step_num_str)
            
            # Extract question (first line usually)
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
                depends_on=depends_on,
                query_type=query_type,
            ))
        
        return sub_queries
    
    def _extract_synthesis_strategy(self, text: str) -> str:
        """Extract synthesis strategy from decomposition."""
        import re
        
        synthesis_match = re.search(
            r'SYNTHESIS:\s*(.+?)(?=ANSWER_TYPE:|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        if synthesis_match:
            return synthesis_match.group(1).strip()
        
        return "Combine results from all sub-queries into coherent answer"
    
    def _extract_answer_type(self, text: str) -> str:
        """Extract expected answer type from decomposition."""
        import re
        
        answer_match = re.search(
            r'ANSWER_TYPE:\s*(\w+(?:_\w+)*)',
            text,
            re.IGNORECASE
        )
        
        if answer_match:
            return answer_match.group(1).lower()
        
        return "comprehensive_analysis"
    
    def _create_fallback_plan(self, question: str) -> QueryPlan:
        """Create simple fallback plan if decomposition fails."""
        return QueryPlan(
            original_question=question,
            sub_queries=[
                SubQuery(
                    step_number=1,
                    question=question,
                    purpose="Answer the question directly",
                    depends_on=[],
                    query_type="hybrid",
                )
            ],
            synthesis_strategy="Use direct answer",
            expected_answer_type="direct_answer",
        )
    
    def validate_plan(self, plan: QueryPlan) -> tuple[bool, list[str]]:
        """
        Validate query plan for correctness.
        
        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []
        
        # Check for empty plan
        if not plan.sub_queries:
            issues.append("Plan has no sub-queries")
            return False, issues
        
        # Check step numbering
        step_numbers = [sq.step_number for sq in plan.sub_queries]
        if step_numbers != list(range(1, len(step_numbers) + 1)):
            issues.append("Step numbers are not sequential")
        
        # Check dependencies
        for sq in plan.sub_queries:
            for dep in sq.depends_on:
                if dep >= sq.step_number:
                    issues.append(
                        f"Step {sq.step_number} depends on "
                        f"later step {dep}"
                    )
                if dep not in step_numbers:
                    issues.append(
                        f"Step {sq.step_number} depends on "
                        f"non-existent step {dep}"
                    )
        
        # Check for circular dependencies
        if self._has_circular_dependencies(plan.sub_queries):
            issues.append("Plan has circular dependencies")
        
        return len(issues) == 0, issues
    
    def _has_circular_dependencies(
        self,
        sub_queries: list[SubQuery]
    ) -> bool:
        """Check for circular dependencies in plan."""
        # Build dependency graph
        graph = {sq.step_number: sq.depends_on for sq in sub_queries}
        
        # DFS to detect cycles
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    return True
        
        return False
    
    def get_execution_order(self, plan: QueryPlan) -> list[list[int]]:
        """
        Get execution order respecting dependencies.
        
        Returns list of batches where each batch can be executed in parallel.
        
        Example:
            [[1], [2, 3], [4]] means:
            - Execute step 1 first
            - Then execute steps 2 and 3 in parallel
            - Finally execute step 4
        """
        # Build dependency graph
        graph = {
            sq.step_number: sq.depends_on
            for sq in plan.sub_queries
        }
        
        # Topological sort with levels
        in_degree = {step: 0 for step in graph}
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0)
        
        for step, deps in graph.items():
            in_degree[step] = len(deps)
        
        batches = []
        remaining = set(graph.keys())
        
        while remaining:
            # Find all steps with no remaining dependencies
            batch = [
                step for step in remaining
                if in_degree[step] == 0
            ]
            
            if not batch:
                # Circular dependency or error
                break
            
            batches.append(sorted(batch))
            
            # Remove batch from remaining and update in_degrees
            for step in batch:
                remaining.remove(step)
                # Decrease in_degree for steps that depend on this one
                for other_step in remaining:
                    if step in graph[other_step]:
                        in_degree[other_step] -= 1
        
        return batches
