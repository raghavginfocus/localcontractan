"""
LangGraph-based ReAct Retrieval Agent - Modern implementation with state management.

This replaces the manual ReAct loop with LangGraph's StateGraph for:
- Automatic state persistence
- Built-in checkpointing
- Streaming support
- Better observability
- Cleaner code structure
"""

import time
from typing import Any, Annotated, TypedDict, Literal
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.synthesis_optimizer import SynthesisOptimizer
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from logger import get_module_logger

logger = get_module_logger(__name__)


# State definition for the agent graph
class AgentState(TypedDict):
    """State passed between nodes in the agent graph."""
    
    # Input
    question: str
    sub_queries: list[dict[str, Any]]
    
    # Execution state
    current_batch_idx: int
    completed_queries: list[int]
    aggregated_data: dict[str, Any]
    steps: list[dict[str, Any]]
    
    # Results
    final_answer: str
    confidence: float
    
    # Timing
    retrieval_time_ms: float
    synthesis_time_ms: float
    total_time_ms: float
    
    # Metadata
    iteration: int
    max_iterations: int
    should_continue: bool


class ReActLangGraphAgent(BaseAgent):
    """
    LangGraph-based ReAct agent for complex multi-step retrieval.
    
    Advantages over manual implementation:
    - Automatic state management
    - Built-in checkpointing (resume from failures)
    - Streaming support (real-time updates)
    - Better observability (trace every node)
    - Cleaner separation of concerns
    """
    
    MAX_ITERATIONS = 10
    
    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
        sparql_agent: SPARQLGeneratorAgent | None = None,
        enable_checkpointing: bool = False,  # Disabled by default due to async context manager complexity
        checkpoint_db_path: str = "./checkpoints/react_agent.db",
        **kwargs: Any,
    ):
        """
        Initialize LangGraph ReAct agent.
        
        Args:
            sparql_store: SPARQL store for knowledge graph queries
            vector_store: Vector store for semantic search
            sparql_agent: SPARQL generator agent
            enable_checkpointing: Enable state checkpointing (disabled by default)
            checkpoint_db_path: Path to checkpoint database
        """
        super().__init__(**kwargs)
        
        # Initialize dependencies
        service_factory = get_service_factory(settings=self.settings)
        self.sparql_store = sparql_store or service_factory.get_sparql_store()
        self.vector_store = vector_store or service_factory.get_vector_store()
        self.sparql_agent = sparql_agent or SPARQLGeneratorAgent(
            sparql_store=self.sparql_store,
            settings=self.settings,
        )
        self.synthesis_optimizer = SynthesisOptimizer(llm=self.llm)
        
        # Setup checkpointing - disabled by default due to async context manager complexity
        # For production use, implement proper async context manager lifecycle
        self.enable_checkpointing = enable_checkpointing
        self.checkpoint_db_path = checkpoint_db_path
        self.checkpointer = None
        if enable_checkpointing:
            logger.warning("Checkpointing is disabled - AsyncSqliteSaver requires proper async context manager setup")
            # Note: To enable checkpointing, you need to:
            # 1. Create an async context manager wrapper
            # 2. Initialize AsyncSqliteSaver within that context
            # 3. Pass the initialized saver to the graph
        
        # Build the agent graph
        self.graph = self._build_graph()
        logger.info("LangGraph ReAct agent initialized")
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for ReAct agent."""
        
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes (each represents a step in the ReAct loop)
        workflow.add_node("initialize", self._initialize_node)
        workflow.add_node("execute_batch", self._execute_batch_node)
        workflow.add_node("synthesize", self._synthesize_node)
        
        # Define edges (control flow)
        workflow.set_entry_point("initialize")
        
        # Conditional edge: continue to next batch or synthesize
        workflow.add_conditional_edges(
            "execute_batch",
            self._should_continue,
            {
                "continue": "execute_batch",
                "synthesize": "synthesize",
            }
        )
        
        # After initialization, start executing batches
        workflow.add_edge("initialize", "execute_batch")
        
        # After synthesis, end
        workflow.add_edge("synthesize", END)
        
        # Compile the graph
        return workflow.compile(checkpointer=self.checkpointer)
    
    async def _initialize_node(self, state: AgentState) -> AgentState:
        """Initialize the agent state."""
        logger.info("Initializing ReAct agent state")
        
        state["current_batch_idx"] = 0
        state["completed_queries"] = []
        state["aggregated_data"] = {}
        state["steps"] = []
        state["iteration"] = 0
        state["max_iterations"] = self.MAX_ITERATIONS
        state["should_continue"] = True
        state["retrieval_time_ms"] = 0.0
        state["synthesis_time_ms"] = 0.0
        
        logger.info(f"Processing {len(state['sub_queries'])} sub-queries")
        return state
    
    async def _execute_batch_node(self, state: AgentState) -> AgentState:
        """Execute a batch of sub-queries."""
        batch_start = time.time()
        
        batch_idx = state["current_batch_idx"]
        sub_queries = state["sub_queries"]
        
        # Get queries for this batch (simplified - execute one at a time)
        if batch_idx >= len(sub_queries):
            state["should_continue"] = False
            return state
        
        current_query = sub_queries[batch_idx]
        logger.info(f"Executing query {batch_idx + 1}/{len(sub_queries)}")
        logger.info(f"  Question: {current_query.get('question', '')[:70]}")
        
        # Execute the query based on type
        query_type = current_query.get("query_type", "hybrid")
        question = current_query.get("question", "")
        
        try:
            if query_type == "sparql" or query_type == "kg_only":
                # SPARQL query - convert to expected format
                sparql_result = await self._execute_sparql_query(question)
                # Convert to format expected by synthesis optimizer
                data = {
                    "kg_facts": sparql_result.get("results", []),
                    "sparql_query": sparql_result.get("query", "")
                }
                result_count = len(sparql_result.get("results", []))
            elif query_type == "vector" or query_type == "vector_only":
                # Vector search - convert to expected format
                vector_result = await self._execute_vector_search(question)
                data = {
                    "vector_results": vector_result.get("results", [])
                }
                result_count = len(vector_result.get("results", []))
            else:
                # Hybrid retrieval - convert to expected format
                hybrid_result = await self._execute_hybrid_retrieval(question)
                data = {
                    "kg_facts": hybrid_result.get("sparql_results", []),
                    "vector_results": hybrid_result.get("vector_results", []),
                    "sparql_query": hybrid_result.get("sparql_query", "")
                }
                result_count = len(hybrid_result.get("sparql_results", [])) + len(hybrid_result.get("vector_results", []))
            
            # Store results in format expected by synthesis optimizer
            step_data = {
                "iteration": state["iteration"],
                "query": question,
                "query_type": query_type,
                "result": data,
                "timestamp": datetime.now().isoformat(),
            }
            
            state["steps"].append(step_data)
            state["aggregated_data"][f"step_{state['iteration']}"] = data
            state["completed_queries"].append(batch_idx)
            
            logger.info(f"  Retrieved {result_count} results")
            
        except Exception as e:
            logger.error(f"Error executing query {batch_idx}: {e}", exc_info=True)
            state["aggregated_data"][f"query_{batch_idx}"] = {"error": str(e)}
        
        # Update state
        batch_time = (time.time() - batch_start) * 1000
        state["retrieval_time_ms"] += batch_time
        state["current_batch_idx"] += 1
        state["iteration"] += 1
        
        # Check if we should continue
        if state["current_batch_idx"] >= len(sub_queries):
            state["should_continue"] = False
        elif state["iteration"] >= state["max_iterations"]:
            logger.warning(f"Max iterations ({state['max_iterations']}) reached")
            state["should_continue"] = False
        
        return state
    
    async def _synthesize_node(self, state: AgentState) -> AgentState:
        """Synthesize final answer from collected data with Phoenix tracing."""
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("synthesis") as span:
            synth_start = time.time()
            
            logger.info("Synthesizing final answer from collected data")
            
            # Count facts for tracing
            total_facts = sum(
                len(data.get("results", []))
                for data in state["aggregated_data"].values()
                if isinstance(data, dict)
            )
            span.set_attribute("total_facts", total_facts)
            span.set_attribute("question", state["question"])
            
            # Use synthesis optimizer
            synthesis_result = await self.synthesis_optimizer.synthesize(
                question=state["question"],
                all_data=state["aggregated_data"],
                strategy="optimized",
            )
            
            state["final_answer"] = synthesis_result.answer
            state["confidence"] = synthesis_result.confidence
            state["synthesis_time_ms"] = (time.time() - synth_start) * 1000
            
            span.set_attribute("confidence", synthesis_result.confidence)
            span.set_attribute("facts_used", synthesis_result.facts_used)
            span.set_attribute("synthesis_time_ms", state["synthesis_time_ms"])
            
            logger.info(f"Synthesis complete (confidence: {synthesis_result.confidence:.2f})")
            
            return state
    
    def _should_continue(self, state: AgentState) -> Literal["continue", "synthesize"]:
        """Decide whether to continue executing or synthesize."""
        if state["should_continue"]:
            return "continue"
        return "synthesize"
    
    async def _execute_sparql_query(self, question: str) -> dict[str, Any]:
        """Execute SPARQL query with data normalization."""
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("sparql_execution") as span:
            span.set_attribute("question", question)
            
            try:
                # Use generate_and_execute for atomic operation
                result = await self.sparql_agent.generate_and_execute(question)
                facts = result.get("results", [])
                
                span.set_attribute("results_count", len(facts))
                
                # Normalize clause types (from react_agent_optimized.py)
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
                
                observation = f"Retrieved {len(facts)} facts from knowledge graph"
                logger.info(f"  {observation}")
                
                return {
                    "type": "sparql",
                    "query": result.get("query"),
                    "results": facts,
                    "count": len(facts),
                }
            except Exception as e:
                logger.error(f"SPARQL query failed: {e}")
                span.set_attribute("error", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return {"type": "sparql", "error": str(e), "results": []}
    
    async def _execute_vector_search(self, question: str) -> dict[str, Any]:
        """Execute vector search with Phoenix tracing."""
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span("vector_search") as span:
            span.set_attribute("question", question)
            span.set_attribute("top_k", 10)
            
            try:
                results = self.vector_store.search(question, top_k=10)
                span.set_attribute("results_count", len(results))
                
                observation = f"Retrieved {len(results)} similar clauses"
                logger.info(f"  {observation}")
                
                return {
                    "type": "vector",
                    "results": results,
                    "count": len(results),
                }
            except Exception as e:
                logger.error(f"Vector search failed: {e}")
                span.set_attribute("error", str(e))
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return {"type": "vector", "error": str(e), "results": []}
    
    async def _execute_hybrid_retrieval(self, question: str) -> dict[str, Any]:
        """Execute hybrid retrieval (SPARQL + vector)."""
        try:
            # Execute both in parallel
            import asyncio
            sparql_task = self._execute_sparql_query(question)
            vector_task = self._execute_vector_search(question)
            
            sparql_result, vector_result = await asyncio.gather(
                sparql_task, vector_task, return_exceptions=True
            )
            
            # Extract results safely
            sparql_results = []
            sparql_query = ""
            if not isinstance(sparql_result, Exception):
                sparql_results = sparql_result.get("results", [])
                sparql_query = sparql_result.get("query", "")
            
            vector_results = []
            if not isinstance(vector_result, Exception):
                vector_results = vector_result.get("results", [])
            
            # Return in format expected by synthesis optimizer
            return {
                "type": "hybrid",
                "sparql_results": sparql_results,
                "vector_results": vector_results,
                "sparql_query": sparql_query,
                "total_count": len(sparql_results) + len(vector_results),
            }
        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            return {
                "type": "hybrid",
                "sparql_results": [],
                "vector_results": [],
                "error": str(e)
            }
    
    async def process(self, input_data: str | dict[str, Any]) -> dict[str, Any]:
        """
        Process query using LangGraph ReAct agent.
        
        Args:
            input_data: Query string or dict with 'question' and 'analysis_result'
            
        Returns:
            Dict with answer and metadata
        """
        start_time = time.time()
        
        # Extract question and sub-queries
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
            analysis_result = input_data.get("analysis_result")
        else:
            question = input_data
            analysis_result = None
        
        self.log_start("react_langgraph", question=question[:100])
        logger.info("=" * 60)
        logger.info(f"REACT LANGGRAPH AGENT - Question: {question[:100]}")
        
        # Prepare sub-queries
        if analysis_result and hasattr(analysis_result, 'sub_queries'):
            sub_queries = [
                {
                    "step_number": sq.step_number,
                    "question": sq.question,
                    "purpose": sq.purpose,
                    "query_type": sq.query_type,
                }
                for sq in analysis_result.sub_queries
            ]
        else:
            # Fallback: single query
            sub_queries = [{
                "step_number": 1,
                "question": question,
                "purpose": "Answer question",
                "query_type": "hybrid",
            }]
        
        # Initialize state
        initial_state: AgentState = {
            "question": question,
            "sub_queries": sub_queries,
            "current_batch_idx": 0,
            "completed_queries": [],
            "aggregated_data": {},
            "steps": [],
            "final_answer": "",
            "confidence": 0.0,
            "retrieval_time_ms": 0.0,
            "synthesis_time_ms": 0.0,
            "total_time_ms": 0.0,
            "iteration": 0,
            "max_iterations": self.MAX_ITERATIONS,
            "should_continue": True,
        }
        
        # Execute the graph
        config = {"configurable": {"thread_id": "react_session"}}
        final_state = await self.graph.ainvoke(initial_state, config=config)
        
        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        final_state["total_time_ms"] = total_time
        
        logger.info(f"ReAct LangGraph execution complete in {total_time:.2f}ms")
        logger.info(f"  Retrieval: {final_state['retrieval_time_ms']:.2f}ms")
        logger.info(f"  Synthesis: {final_state['synthesis_time_ms']:.2f}ms")
        
        return final_state
    
    async def stream_process(self, input_data: str | dict[str, Any]):
        """
        Stream the agent execution for real-time updates.
        
        Yields state updates as the agent progresses through nodes.
        """
        # Prepare initial state (same as process)
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
            analysis_result = input_data.get("analysis_result")
        else:
            question = input_data
            analysis_result = None
        
        if analysis_result and hasattr(analysis_result, 'sub_queries'):
            sub_queries = [
                {
                    "step_number": sq.step_number,
                    "question": sq.question,
                    "purpose": sq.purpose,
                    "query_type": sq.query_type,
                }
                for sq in analysis_result.sub_queries
            ]
        else:
            sub_queries = [{
                "step_number": 1,
                "question": question,
                "purpose": "Answer question",
                "query_type": "hybrid",
            }]
        
        initial_state: AgentState = {
            "question": question,
            "sub_queries": sub_queries,
            "current_batch_idx": 0,
            "completed_queries": [],
            "aggregated_data": {},
            "steps": [],
            "final_answer": "",
            "confidence": 0.0,
            "retrieval_time_ms": 0.0,
            "synthesis_time_ms": 0.0,
            "total_time_ms": 0.0,
            "iteration": 0,
            "max_iterations": self.MAX_ITERATIONS,
            "should_continue": True,
        }
        
        # Stream execution
        config = {"configurable": {"thread_id": "react_session"}}
        async for event in self.graph.astream(initial_state, config=config):
            yield event


