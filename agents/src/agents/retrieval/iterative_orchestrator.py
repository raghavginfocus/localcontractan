"""
Iterative Orchestrator Agent

This orchestrator manages the iterative refinement process:
1. Uses SmartQueryDecomposer to analyze the query
2. Executes retrieval (potentially in multiple steps for multi-hop)
3. Generates initial answer
4. Uses AnswerCritiqueAgent to evaluate quality
5. Refines if needed by gathering more information
6. Repeats until answer is complete or max iterations reached
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.language_models import BaseChatModel

from agents.shared.base import BaseAgent
from config import Settings
from agents.retrieval.smart_query_decomposer import (
    SmartQueryDecomposer,
    DecompositionPlan
)
from agents.retrieval.answer_critique import (
    AnswerCritiqueAgent,
    AnswerCritique
)


@dataclass
class RetrievalResult:
    """Results from a retrieval step."""
    facts: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    query_used: str = ""
    duration_ms: float = 0.0


@dataclass
class IterationState:
    """State for a single iteration."""
    iteration: int
    question: str
    decomposition_plan: Optional[DecompositionPlan] = None
    retrieval_results: List[RetrievalResult] = field(default_factory=list)
    answer: str = ""
    critique: Optional[AnswerCritique] = None
    timestamp: datetime = field(default_factory=datetime.now)
    total_facts: int = 0


@dataclass
class RefinementSession:
    """Complete refinement session tracking."""
    original_question: str
    iterations: List[IterationState] = field(default_factory=list)
    final_answer: str = ""
    final_critique: Optional[AnswerCritique] = None
    total_duration_ms: float = 0.0
    refinement_count: int = 0
    
    def add_iteration(self, state: IterationState):
        """Add an iteration to the session."""
        self.iterations.append(state)
        self.refinement_count = len(self.iterations) - 1


class IterativeOrchestrator(BaseAgent):
    """
    Orchestrates iterative query answering with refinement.
    
    This agent coordinates:
    1. Query analysis and decomposition
    2. Multi-step retrieval execution
    3. Answer generation
    4. Quality critique
    5. Iterative refinement
    
    It ensures answers are complete before returning them.
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm: Optional[BaseChatModel] = None,
        max_iterations: int = 1  # DEMO MODE: Changed from 3 to 1 for fast responses
    ):
        super().__init__(settings, llm)
        self.name = "IterativeOrchestrator"
        self.max_iterations = max_iterations
        
        # Initialize sub-agents
        self.query_decomposer = SmartQueryDecomposer(settings, llm)
        self.answer_critic = AnswerCritiqueAgent(settings, llm)
        
        # DEMO MODE: Log the configuration
        self.logger.info(
            f"IterativeOrchestrator initialized in DEMO MODE: "
            f"max_iterations={self.max_iterations} (no refinement)"
        )
    
    async def process(self, input_data: Any) -> Any:
        """Required abstract method."""
        return await self.answer_with_refinement(**input_data)
    
    async def answer_with_refinement(
        self,
        question: str,
        retrieval_fn,
        synthesis_fn
    ) -> RefinementSession:
        """
        Answer a question with iterative refinement.
        
        Args:
            question: The user's question
            retrieval_fn: Async function to retrieve facts
                         Signature: async (query: str) -> RetrievalResult
            synthesis_fn: Async function to synthesize answer
                         Signature: async (question, facts) -> str
            
        Returns:
            RefinementSession with complete history
        """
        session = RefinementSession(original_question=question)
        start_time = datetime.now()
        
        self.logger.info("=" * 60)
        self.logger.info(f"Starting iterative refinement for: {question}")
        self.logger.info("=" * 60)
        
        current_question = question
        accumulated_facts = []
        seen_questions = set([question.lower()])  # Track questions to avoid loops
        
        for iteration in range(self.max_iterations):
            self.logger.info(f"\n--- Iteration {iteration + 1}/{self.max_iterations} ---")
            
            state = IterationState(
                iteration=iteration + 1,
                question=current_question
            )
            
            # Step 1: Analyze and potentially decompose query
            self.logger.info("Step 1: Query analysis")
            try:
                decomposition_plan = await self.query_decomposer.decompose_query(
                    current_question
                )
                if decomposition_plan is None:
                    self.logger.warning("Query decomposer returned None, creating fallback plan")
                    # Create a simple fallback plan
                    from agents.retrieval.smart_query_decomposer import DecompositionPlan, QueryComplexity
                    decomposition_plan = DecompositionPlan(
                        should_decompose=False,
                        complexity=QueryComplexity.MODERATE,
                        reasoning="Fallback plan due to decomposer error",
                        sub_queries=[],
                        execution_order=[]
                    )
            except Exception as e:
                self.logger.error(f"Query decomposition failed: {e}", exc_info=True)
                # Create a simple fallback plan
                from agents.retrieval.smart_query_decomposer import DecompositionPlan, QueryComplexity
                decomposition_plan = DecompositionPlan(
                    should_decompose=False,
                    complexity=QueryComplexity.MODERATE,
                    reasoning=f"Fallback plan due to error: {str(e)}",
                    sub_queries=[],
                    execution_order=[]
                )
            
            state.decomposition_plan = decomposition_plan
            
            # Step 2: Execute retrieval
            self.logger.info("Step 2: Retrieval execution")
            new_facts = await self._execute_retrieval(
                decomposition_plan,
                current_question,
                retrieval_fn,
                state
            )
            
            # Accumulate facts across iterations
            accumulated_facts.extend(new_facts)
            state.total_facts = len(accumulated_facts)
            
            self.logger.info(
                f"Retrieved {len(new_facts)} new facts "
                f"(total: {len(accumulated_facts)})"
            )
            
            # Step 3: Generate answer
            self.logger.info("Step 3: Answer synthesis")
            answer = await synthesis_fn(question, accumulated_facts)
            state.answer = answer
            
            self.logger.info(f"Generated answer ({len(answer)} chars)")
            
            # Step 4: Critique answer
            self.logger.info("Step 4: Answer critique")
            critique = await self.answer_critic.critique_answer(
                question=question,
                answer=answer,
                facts=accumulated_facts,
                sources=self._get_all_sources(state)
            )
            state.critique = critique
            
            # Add iteration to session
            session.add_iteration(state)
            
            # Step 5: Decide if refinement is needed
            previous_fact_count = state.total_facts - len(new_facts)
            should_refine = self.answer_critic.should_refine(
                critique,
                iteration + 1,
                self.max_iterations,
                previous_fact_count=previous_fact_count,
                current_fact_count=state.total_facts
            )
            
            if not should_refine:
                self.logger.info("Answer is satisfactory, stopping refinement")
                session.final_answer = answer
                session.final_critique = critique
                break
            
            # Prepare for next iteration
            self.logger.info("Answer needs refinement, preparing next iteration")
            
            if critique.suggested_follow_up_queries:
                # Use suggested follow-up as next question
                next_question = critique.suggested_follow_up_queries[0]
                
                # Check if we've seen this question before
                if next_question.lower() in seen_questions:
                    # Allow repeat if confidence is very low AND making progress
                    if (critique.confidence_score < 0.5 and
                        state.total_facts > previous_fact_count):
                        self.logger.info(
                            f"Allowing repeated question due to very low "
                            f"confidence ({critique.confidence_score:.2f}) "
                            f"and progress being made"
                        )
                    else:
                        self.logger.warning(
                            "Repeated follow-up question detected with no "
                            "progress, stopping to avoid infinite loop"
                        )
                        break
                
                current_question = next_question
                seen_questions.add(current_question.lower())
                self.logger.info(f"Next query: {current_question}")
            else:
                # Generate refinement query based on missing info
                next_question = self._generate_refinement_query(
                    question,
                    critique
                )
                
                # Check for repeated question
                if next_question.lower() in seen_questions:
                    # Allow repeat if confidence is very low AND making progress
                    if (critique.confidence_score < 0.5 and
                        state.total_facts > previous_fact_count):
                        self.logger.info(
                            f"Allowing repeated refinement due to very low "
                            f"confidence ({critique.confidence_score:.2f}) "
                            f"and progress being made"
                        )
                    else:
                        self.logger.warning(
                            "Repeated refinement question detected with no "
                            "progress, stopping to avoid infinite loop"
                        )
                        break
                
                current_question = next_question
                seen_questions.add(current_question.lower())
                self.logger.info(f"Generated refinement query: {current_question}")
        
        # Finalize session
        if not session.final_answer:
            # Use last iteration's answer
            session.final_answer = session.iterations[-1].answer
            session.final_critique = session.iterations[-1].critique
        
        end_time = datetime.now()
        session.total_duration_ms = (
            (end_time - start_time).total_seconds() * 1000
        )
        
        self.logger.info("=" * 60)
        self.logger.info(
            f"Refinement complete: {session.refinement_count} refinements, "
            f"{session.total_duration_ms:.0f}ms"
        )
        self.logger.info("=" * 60)
        
        return session
    
    async def _execute_retrieval(
        self,
        plan: DecompositionPlan,
        question: str,
        retrieval_fn,
        state: IterationState
    ) -> List[Dict[str, Any]]:
        """Execute retrieval based on decomposition plan."""
        all_facts = []
        
        if not plan.should_decompose:
            # Simple query - single retrieval
            self.logger.info("Executing single retrieval")
            result = await retrieval_fn(question)
            state.retrieval_results.append(result)
            all_facts.extend(result.facts)
        else:
            # Complex query - execute sub-queries
            self.logger.info(
                f"Executing {len(plan.sub_queries)} sub-queries "
                f"in {len(plan.execution_order)} batches"
            )
            
            batches = self.query_decomposer.get_execution_batches(plan)
            
            for batch_idx, batch in enumerate(batches):
                self.logger.info(
                    f"Batch {batch_idx + 1}/{len(batches)}: "
                    f"{len(batch)} queries"
                )
                
                # Execute batch in parallel (could be optimized)
                for sub_query in batch:
                    self.logger.info(f"  Executing: {sub_query.query[:80]}...")
                    try:
                        result = await retrieval_fn(sub_query.query)
                        state.retrieval_results.append(result)
                        all_facts.extend(result.facts)
                        self.logger.info(f"    Retrieved {len(result.facts)} facts")
                    except Exception as e:
                        self.logger.error(
                            f"Sub-query failed: {sub_query.query[:80]}",
                            error=str(e)
                        )
                        # Continue with other sub-queries
                        continue
        
        return all_facts
    
    def _get_all_sources(self, state: IterationState) -> List[str]:
        """Get all sources from retrieval results."""
        sources = []
        for result in state.retrieval_results:
            sources.extend(result.sources)
        return list(set(sources))  # Deduplicate
    
    def _generate_refinement_query(
        self,
        original_question: str,
        critique: AnswerCritique
    ) -> str:
        """Generate a refinement query based on critique."""
        if not critique.missing_information:
            return original_question
        
        # Create a focused query for the first missing piece
        missing = critique.missing_information[0]
        return f"Find information about: {missing}"


