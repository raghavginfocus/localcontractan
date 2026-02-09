"""
ReAct Retrieval Agent - Optimized multi-step reasoning for complex queries.

Implements the ReAct (Reasoning + Acting) pattern with optimizations:
- Uses pre-analyzed query plans (no redundant LLM calls)
- Executes decomposed sub-queries (not original complex question)
- Parallel execution of independent sub-queries
- Optimized synthesis (main bottleneck addressed)
- Comprehensive timing logs for optimization

Flow:
1. Receive pre-analyzed query plan from orchestrator
2. Execute sub-queries in optimal order (parallel where possible)
3. Optimized synthesis with smart data filtering
"""

import time
import asyncio
from typing import Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agents.shared.base import BaseAgent
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.synthesis_optimizer import SynthesisOptimizer
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from logger import get_module_logger

logger = get_module_logger(__name__)


class ActionType(str, Enum):
    """Types of actions the agent can take."""
    SPARQL_QUERY = "sparql_query"
    VECTOR_SEARCH = "vector_search"
    HYBRID_RETRIEVAL = "hybrid_retrieval"
    SYNTHESIZE = "synthesize"
    COMPLETE = "complete"


class ReActStep(BaseModel):
    """A single step in the ReAct reasoning loop with timing."""
    
    iteration: int = Field(description="Iteration number")
    thought: str = Field(description="Reasoning about what to do")
    action_type: ActionType = Field(description="Type of action to take")
    action_input: dict[str, Any] = Field(
        default_factory=dict,
        description="Input for the action"
    )
    observation: str = Field(
        default="",
        description="Result of the action"
    )
    reflection: str = Field(
        default="",
        description="Analysis of observation"
    )
    data_collected: dict[str, Any] = Field(
        default_factory=dict,
        description="Data gathered in this step"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_ms: float = Field(default=0.0, description="Step execution time")
    llm_time_ms: float = Field(default=0.0, description="LLM call time")
    retrieval_time_ms: float = Field(
        default=0.0,
        description="Retrieval time"
    )
    kg_retrieval_time_ms: float = Field(
        default=0.0,
        description="Knowledge Graph retrieval time"
    )
    vector_retrieval_time_ms: float = Field(
        default=0.0,
        description="Vector store retrieval time"
    )


class ReActResult(BaseModel):
    """Result from ReAct reasoning process with timing breakdown."""
    
    question: str = Field(description="Original question")
    steps: list[ReActStep] = Field(
        default_factory=list,
        description="All reasoning steps"
    )
    final_answer: str = Field(description="Synthesized answer")
    confidence: float = Field(description="Confidence score 0-1")
    total_iterations: int = Field(description="Number of iterations")
    aggregated_data: dict[str, Any] = Field(
        default_factory=dict,
        description="All data collected"
    )
    
    # Timing breakdown
    analysis_time_ms: float = Field(
        default=0.0,
        description="Query analysis time"
    )
    retrieval_time_ms: float = Field(
        default=0.0,
        description="Total retrieval time"
    )
    kg_retrieval_time_ms: float = Field(
        default=0.0,
        description="Total Knowledge Graph retrieval time"
    )
    vector_retrieval_time_ms: float = Field(
        default=0.0,
        description="Total Vector store retrieval time"
    )
    synthesis_time_ms: float = Field(
        default=0.0,
        description="Answer synthesis time"
    )
    total_time_ms: float = Field(default=0.0, description="Total execution time")
    
    # Answer quality evaluation metrics
    evaluation_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Answer quality evaluation metrics"
    )


class ReActRetrievalAgent(BaseAgent):
    """
    Optimized ReAct-style agent for complex multi-step retrieval.
    
    Key optimizations:
    1. Uses pre-analyzed query plans (no redundant decomposition)
    2. Executes sub-queries directly (not original complex question)
    3. Parallel execution of independent sub-queries
    4. Comprehensive timing logs
    """
    
    MAX_ITERATIONS = 10  # Safety limit
    
    SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are synthesizing a final answer from collected data.

Original Question: {question}

All Collected Data:
{all_data}

Reasoning Steps Taken:
{reasoning_trace}

CRITICAL INSTRUCTIONS:
1. Be CONCISE - provide only relevant information
2. Structure clearly with bullet points or numbered lists
3. Use ONLY data from collected findings - no general knowledge
4. For comparisons/rankings: List specific findings with data
5. Avoid verbose introductions - get straight to the point
6. If information is incomplete, state what is available
7. For "clause types": Extract UNIQUE types only, deduplicate

Generate a concise, well-structured answer."""),
        ("human", "Generate the final answer."),
    ])

    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
        sparql_agent: SPARQLGeneratorAgent | None = None,
        **kwargs: Any,
    ):
        """Initialize ReAct agent with dependencies."""
        super().__init__(**kwargs)
        
        # Use dependency injection
        service_factory = get_service_factory(settings=self.settings)
        self.sparql_store = sparql_store or service_factory.get_sparql_store()
        self.vector_store = vector_store or service_factory.get_vector_store()
        
        # Initialize SPARQL agent
        self.sparql_agent = sparql_agent or SPARQLGeneratorAgent(
            sparql_store=self.sparql_store,
            settings=self.settings,
        )
        
        # Initialize synthesis optimizer
        self.synthesis_optimizer = SynthesisOptimizer(llm=self.llm)
        logger.info("Initialized synthesis optimizer for faster answer generation")

    async def process(
        self,
        input_data: str | dict[str, Any]
    ) -> ReActResult:
        """
        Process complex query using optimized ReAct with pre-analyzed plan.
        
        Args:
            input_data: Query string or dict with 'question' and 'analysis_result'
            
        Returns:
            ReActResult with answer and timing breakdown
        """
        start_time = time.time()
        
        # Extract question and pre-analyzed plan
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
            analysis_result = input_data.get("analysis_result")
        else:
            question = input_data
            analysis_result = None
        
        self.log_start("react_retrieval_optimized", question=question[:100])
        logger.info("=" * 60)
        logger.info(f"REACT AGENT (OPTIMIZED) - Question: {question[:100]}")
        
        # Use pre-analyzed plan if available (avoids redundant LLM call)
        analysis_time = 0.0
        if analysis_result and hasattr(analysis_result, 'sub_queries'):
            logger.info("Using pre-analyzed query plan (no re-analysis)")
            sub_queries = analysis_result.sub_queries
            analysis_time = getattr(analysis_result, 'analysis_time_ms', 0.0)
            logger.info(f"  Analysis time saved: {analysis_time:.2f}ms")
        else:
            # Fallback: create simple plan
            logger.info("No pre-analyzed plan, creating simple fallback")
            from agents.retrieval.unified_query_analyzer import SubQuery
            from agents.retrieval.query_classifier import QueryClassifier, RetrievalRoute
            
            # IMPORTANT: Don't default to "hybrid" for every question.
            # Hybrid triggers vector search which computes embeddings (slow on CPU) and
            # can dominate runtime for analytical/structured questions.
            classifier = QueryClassifier(settings=self.settings)
            classification = classifier.classify(question)
            
            # Simplified routing:
            # - Clearly structured/SPARQL/text-index queries -> KG only
            # - Everything else -> hybrid (ReAct can use KG + text index + vector)
            if classification.primary_route in (RetrievalRoute.SPARQL, RetrievalRoute.TEXT_INDEX):
                # Text index is implemented via SPARQL text:query in our stack
                fallback_query_type = "kg_only"
            else:
                # Default to hybrid so ReAct can combine KG and vector evidence
                fallback_query_type = "hybrid"
            
            logger.info(
                "Fallback route classification",
                primary_route=classification.primary_route,
                confidence=classification.confidence,
                query_type=fallback_query_type,
                reasoning=classification.reasoning,
            )
            sub_queries = [
                SubQuery(
                    step_number=1,
                    question=question,
                    purpose="Answer question",
                    query_type=fallback_query_type,
                    depends_on=[],
                )
            ]
        
        logger.info(f"Executing {len(sub_queries)} sub-queries")
        
        # Execute sub-queries with optimal ordering
        retrieval_start = time.time()
        steps = []
        aggregated_data = {}
        
        # Group sub-queries into batches for parallel execution
        batches = self._get_execution_batches(sub_queries)
        logger.info(f"Organized into {len(batches)} execution batches")
        
        iteration = 0
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(f"\nBatch {batch_idx}/{len(batches)}: {len(batch)} queries")
            
            # Log the sub-queries in this batch for transparency
            for sq in batch:
                logger.info(f"  Sub-query {sq.step_number}: {sq.question[:70]}")
                logger.info(f"    Purpose: {sq.purpose[:60]}")
                logger.info(f"    Type: {sq.query_type}")
            
            # Execute batch in parallel if multiple queries
            if len(batch) > 1:
                logger.info(f"  Executing {len(batch)} queries in parallel")
                batch_results = await self._execute_batch_parallel(
                    batch, aggregated_data
                )
            else:
                logger.info(f"  Executing single query")
                batch_results = [await self._execute_single_query(
                    batch[0], aggregated_data
                )]
            
            # Process batch results
            for sub_query, step, data in batch_results:
                iteration += 1
                step.iteration = iteration
                steps.append(step)
                
                step_key = f"step_{iteration}"
                aggregated_data[step_key] = data
                
                logger.info(f"  Step {iteration}: {step.observation[:80]}")
                logger.info(f"    Duration: {step.duration_ms:.2f}ms")
                logger.info(f"    Retrieval: {step.retrieval_time_ms:.2f}ms")
                if step.kg_retrieval_time_ms > 0:
                    logger.info(f"      KG: {step.kg_retrieval_time_ms:.2f}ms")
                if step.vector_retrieval_time_ms > 0:
                    logger.info(f"      Vector: {step.vector_retrieval_time_ms:.2f}ms")
        
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # Calculate total KG and Vector retrieval times
        total_kg_time = sum(s.kg_retrieval_time_ms for s in steps)
        total_vector_time = sum(s.vector_retrieval_time_ms for s in steps)
        
        # Synthesize final answer with optimization
        logger.info(f"\n{'=' * 60}")
        logger.info("Synthesizing final answer (optimized)...")
        
        synthesis_start = time.time()
        synthesis_result = await self.synthesis_optimizer.synthesize(
            question=question,
            all_data=aggregated_data,
            strategy="optimized",  # Use optimized strategy
        )
        final_answer = synthesis_result.answer
        synthesis_time = (time.time() - synthesis_start) * 1000
        
        # Extract detailed evaluation metrics from synthesis result
        evaluation_metrics = {
            "confidence": synthesis_result.confidence,
            "strategy": synthesis_result.strategy,
            "facts_used": synthesis_result.facts_used,
            "data_filtering_ms": synthesis_result.data_filtering_ms,
            "llm_call_ms": synthesis_result.llm_call_ms,
            "synthesis_time_ms": synthesis_time,
            "relevance_score": synthesis_result.relevance_score,
            "data_utilization_score": synthesis_result.data_utilization_score,
            "is_evasive": synthesis_result.is_evasive,
        }
        
        # Log synthesis breakdown with detailed evaluation metrics
        logger.info(f"  Synthesis breakdown:")
        logger.info(f"    Data filtering: {synthesis_result.data_filtering_ms:.2f}ms")
        logger.info(f"    LLM call: {synthesis_result.llm_call_ms:.2f}ms")
        logger.info(f"    Facts used: {synthesis_result.facts_used}")
        logger.info(f"    Total: {synthesis_time:.2f}ms")
        logger.info(f"  Answer Quality Evaluation:")
        logger.info(f"    Confidence: {synthesis_result.confidence:.2f}")
        logger.info(f"    Relevance: {synthesis_result.relevance_score:.2f}")
        logger.info(f"    Data Utilization: {synthesis_result.data_utilization_score:.2f}")
        logger.info(f"    Evasive: {synthesis_result.is_evasive}")
        logger.info(f"    Strategy: {synthesis_result.strategy}")
        
        # Use confidence from synthesis optimizer (includes evaluation)
        confidence = synthesis_result.confidence
        
        total_time = (time.time() - start_time) * 1000
        
        result = ReActResult(
            question=question,
            steps=steps,
            final_answer=final_answer,
            confidence=confidence,
            total_iterations=iteration,
            aggregated_data=aggregated_data,
            analysis_time_ms=analysis_time,
            retrieval_time_ms=retrieval_time,
            kg_retrieval_time_ms=total_kg_time,
            vector_retrieval_time_ms=total_vector_time,
            synthesis_time_ms=synthesis_time,
            total_time_ms=total_time,
            evaluation_metrics=evaluation_metrics,
        )
        
        logger.info(f"  Confidence: {confidence:.2f}")
        logger.info(f"  Answer length: {len(final_answer)} chars")
        logger.info("  Timing breakdown:")
        logger.info(f"    Analysis: {analysis_time:.2f}ms (reused)")
        logger.info(f"    Retrieval: {retrieval_time:.2f}ms")
        if total_kg_time > 0:
            kg_pct = total_kg_time / retrieval_time * 100
            logger.info(f"      - KG: {total_kg_time:.2f}ms ({kg_pct:.1f}%)")
        if total_vector_time > 0:
            vec_pct = total_vector_time / retrieval_time * 100
            logger.info(
                f"      - Vector: {total_vector_time:.2f}ms ({vec_pct:.1f}%)"
            )
        logger.info(f"    Synthesis: {synthesis_time:.2f}ms")
        logger.info(f"    Total: {total_time:.2f}ms")
        
        # Log source contribution metrics
        total_kg_facts = sum(
            len(step_data.get("kg_facts", []))
            for step_data in aggregated_data.values()
            if isinstance(step_data, dict)
        )
        total_vector_results = sum(
            len(step_data.get("vector_results", []))
            for step_data in aggregated_data.values()
            if isinstance(step_data, dict)
        )
        
        logger.info("  Source contribution:")
        logger.info(f"    KG facts: {total_kg_facts}")
        logger.info(f"    Vector results: {total_vector_results}")
        if total_kg_facts > 0 and total_vector_results > 0:
            total_items = total_kg_facts + total_vector_results
            kg_contrib = total_kg_facts / total_items * 100
            vec_contrib = total_vector_results / total_items * 100
            logger.info(f"    KG contribution: {kg_contrib:.1f}%")
            logger.info(f"    Vector contribution: {vec_contrib:.1f}%")
        
        self.log_complete(
            "react_retrieval_optimized",
            iterations=iteration,
            confidence=confidence,
            total_time_ms=total_time,
        )
        
        return result
    
    def _get_execution_batches(self, sub_queries: list) -> list[list]:
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
    
    async def _execute_batch_parallel(
        self,
        batch: list,
        aggregated_data: dict[str, Any],
    ) -> list[tuple]:
        """Execute multiple sub-queries in parallel."""
        tasks = [
            self._execute_single_query(sub_query, aggregated_data)
            for sub_query in batch
        ]
        return await asyncio.gather(*tasks)
    
    async def _execute_single_query(
        self,
        sub_query,
        aggregated_data: dict[str, Any],
    ) -> tuple:
        """Execute a single sub-query and return results."""
        step_start = time.time()
        
        # Determine action type
        action_type, action_input = self._determine_action(
            sub_query.query_type
        )
        
        # Execute retrieval
        retrieval_start = time.time()
        observation, data = await self._execute_action(
            action_type,
            action_input,
            sub_query.question,
        )
        retrieval_time = (time.time() - retrieval_start) * 1000
        
        # Extract timing breakdown from data
        kg_time = data.get("kg_retrieval_time_ms", 0.0)
        vector_time = data.get("vector_retrieval_time_ms", 0.0)
        
        # Create step
        step = ReActStep(
            iteration=0,  # Will be set by caller
            thought=sub_query.purpose,
            action_type=action_type,
            action_input=action_input,
            observation=observation,
            reflection="Completed",
            data_collected=data,
            duration_ms=(time.time() - step_start) * 1000,
            retrieval_time_ms=retrieval_time,
            kg_retrieval_time_ms=kg_time,
            vector_retrieval_time_ms=vector_time,
        )
        
        return (sub_query, step, data)
    
    def _determine_action(
        self,
        query_type: str
    ) -> tuple[ActionType, dict[str, Any]]:
        """Determine action type based on query type."""
        if query_type == "kg_only":
            return ActionType.SPARQL_QUERY, {}
        elif query_type == "vector_only":
            return ActionType.VECTOR_SEARCH, {}
        elif query_type == "synthesis":
            return ActionType.SYNTHESIZE, {}
        else:  # hybrid or default
            return ActionType.HYBRID_RETRIEVAL, {}
    
    async def _execute_action(
        self,
        action_type: ActionType,
        action_input: dict[str, Any],
        question: str,
    ) -> tuple[str, dict[str, Any]]:
        """Execute the determined action."""
        try:
            if action_type == ActionType.SPARQL_QUERY:
                return await self._execute_sparql(question)
            
            elif action_type == ActionType.VECTOR_SEARCH:
                return await self._execute_vector_search(question)
            
            elif action_type == ActionType.HYBRID_RETRIEVAL:
                return await self._execute_hybrid(question)
            
            elif action_type == ActionType.SYNTHESIZE:
                return "Ready to synthesize", {}
            
            else:
                return "Unknown action type", {}
                
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return f"Error: {str(e)}", {}
    
    async def _execute_sparql(
        self,
        question: str
    ) -> tuple[str, dict[str, Any]]:
        """Execute SPARQL query."""
        kg_start = time.time()
        result = await self.sparql_agent.generate_and_execute(question)
        kg_time = (time.time() - kg_start) * 1000
        
        facts = result.get("results", [])
        
        # Log the actual facts retrieved for debugging
        logger.info(f"SPARQL returned {len(facts)} facts")
        if facts and len(facts) > 0:
            logger.info(f"Sample fact keys: {list(facts[0].keys())}")
            logger.info(f"Sample fact: {facts[0]}")
        
        # Normalize clause types
        if facts and isinstance(facts, list) and len(facts) > 0:
            if isinstance(facts[0], dict) and "clauseType" in facts[0]:
                normalized_facts = []
                seen_types = set()
                
                for fact in facts:
                    clause_type_uri = fact.get("clauseType", "")
                    if clause_type_uri:
                        # Extract local name
                        if "#" in clause_type_uri:
                            local_name = clause_type_uri.split("#")[-1]
                        elif "/" in clause_type_uri:
                            local_name = clause_type_uri.split("/")[-1]
                        else:
                            local_name = clause_type_uri
                        
                        # Skip base "Clause" class unless only one
                        if local_name.lower() == "clause" and len(facts) > 1:
                            continue
                        
                        # Deduplicate
                        if local_name not in seen_types:
                            seen_types.add(local_name)
                            normalized_fact = fact.copy()
                            normalized_fact["clauseType"] = local_name
                            normalized_facts.append(normalized_fact)
                
                facts = normalized_facts if normalized_facts else facts
        
        observation = f"Retrieved {len(facts)} facts from Knowledge Graph"
        
        return observation, {
            "kg_facts": facts,
            "sparql_query": result.get("query"),
            "kg_retrieval_time_ms": kg_time,
        }
    
    async def _execute_vector_search(
        self,
        question: str
    ) -> tuple[str, dict[str, Any]]:
        """Execute vector search."""
        vector_start = time.time()
        results = self.vector_store.search(query=question, top_k=5)
        vector_time = (time.time() - vector_start) * 1000
        
        observation = (
            f"Found {len(results)} relevant clauses "
            f"from Milvus vector store"
        )
        
        return observation, {
            "vector_results": results,
            "vector_retrieval_time_ms": vector_time,
        }
    
    async def _execute_hybrid(
        self,
        question: str
    ) -> tuple[str, dict[str, Any]]:
        """Execute both SPARQL and vector search in parallel."""
        # Execute both in parallel for efficiency
        sparql_task = self._execute_sparql(question)
        vector_task = self._execute_vector_search(question)
        
        results = await asyncio.gather(
            sparql_task, vector_task
        )
        (sparql_obs, sparql_data), (vector_obs, vector_data) = results
        
        observation = f"{sparql_obs}. {vector_obs}"
        
        # Merge data with timing information
        data = {**sparql_data, **vector_data}
        
        # Combine timing metrics
        kg_time = sparql_data.get("kg_retrieval_time_ms", 0.0)
        vector_time = vector_data.get("vector_retrieval_time_ms", 0.0)
        data["kg_retrieval_time_ms"] = kg_time
        data["vector_retrieval_time_ms"] = vector_time
        
        return observation, data
    
    async def _synthesize_answer(
        self,
        question: str,
        all_data: dict[str, Any],
        steps: list[ReActStep],
    ) -> str:
        """Synthesize final answer from all collected data."""
        # Format all data
        data_text = self._format_all_data(all_data)
        
        # Format reasoning trace
        trace = "\n".join([
            f"Step {s.iteration}: {s.thought}\n  → {s.observation}"
            for s in steps
        ])
        
        chain = self.SYNTHESIS_PROMPT | self.llm | StrOutputParser()
        
        try:
            answer = await chain.ainvoke({
                "question": question,
                "all_data": data_text,
                "reasoning_trace": trace,
            })
            return answer.strip()
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return f"Unable to synthesize answer: {str(e)}"
    
    def _format_all_data(self, data: dict[str, Any]) -> str:
        """Format all collected data for synthesis."""
        lines = []
        
        # DEBUG: Log what we're receiving
        logger.info(f"_format_all_data received data with keys: {list(data.keys())}")
        for key, value in data.items():
            if isinstance(value, dict):
                logger.info(f"  {key}: dict with keys {list(value.keys())}")
                if "kg_facts" in value:
                    logger.info(f"    kg_facts: {len(value['kg_facts'])} facts")
                    if value['kg_facts']:
                        logger.info(f"    Sample fact: {str(value['kg_facts'][0])[:300]}")
            else:
                logger.info(f"  {key}: {type(value)}")
        
        for step_key, step_data in data.items():
            lines.append(f"\n{step_key.upper()}:")
            
            if isinstance(step_data, dict):
                # KG facts
                kg_facts = step_data.get("kg_facts", [])
                if kg_facts:
                    lines.append(f"  Knowledge Graph Facts ({len(kg_facts)}):")
                    # Show ALL facts, not just first 10
                    for i, fact in enumerate(kg_facts, 1):
                        fact_str = ", ".join(
                            f"{k}: {v}" for k, v in fact.items()
                        )
                        lines.append(f"    {i}. {fact_str}")
                
                # Vector results
                vector_results = step_data.get("vector_results", [])
                if vector_results:
                    lines.append(
                        f"  Vector Search Results ({len(vector_results)}):"
                    )
                    for i, result in enumerate(vector_results[:5], 1):
                        text = result.get("text", "")[:200]
                        clause_type = result.get("clause_type", "Unknown")
                        lines.append(
                            f"    {i}. [{clause_type}] {text}..."
                        )
        
        formatted = "\n".join(lines)
        logger.info(f"Formatted data length: {len(formatted)} chars")
        logger.info(f"Formatted data preview: {formatted[:500]}")
        return formatted
    
    def _calculate_confidence(
        self,
        data: dict[str, Any],
        steps: list[ReActStep],
    ) -> float:
        """Calculate confidence based on data quality and completeness."""
        score = 0.0
        
        # Base score from number of successful steps
        successful_steps = sum(
            1 for s in steps
            if s.data_collected and len(s.data_collected) > 0
        )
        score += min(0.4, successful_steps * 0.1)
        
        # Score from data quantity
        total_kg_facts = 0
        total_vector_results = 0
        
        for step_data in data.values():
            if isinstance(step_data, dict):
                total_kg_facts += len(step_data.get("kg_facts", []))
                vec_results = step_data.get("vector_results", [])
                total_vector_results += len(vec_results)
        
        score += min(0.3, total_kg_facts * 0.05)
        score += min(0.2, total_vector_results * 0.04)
        
        # Bonus for having both KG and vector data
        if total_kg_facts > 0 and total_vector_results > 0:
            score += 0.1
        
        return min(1.0, score)

