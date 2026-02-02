"""
LangGraph-based Retrieval Orchestrator - Wraps existing agents with state management.

This orchestrator uses LangGraph for:
1. State management and checkpointing
2. Phoenix observability integration
3. Workflow visualization

But delegates actual retrieval to existing, proven agents:
- ReActRetrievalAgent (for complex queries)
- RAGOrchestratorAgent (for simple queries)
- Existing logging via RAGLogger
"""

from datetime import datetime
from typing import Any, TypedDict
from enum import Enum

from langgraph.graph import StateGraph, END

from agents.retrieval.react_agent_optimized import ReActRetrievalAgent
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from config import Settings, get_settings
from logger import get_module_logger
from logging_config import get_log_dir
from logging_utils import get_rag_logger
from observability.phoenix_tracer import setup_phoenix_tracing

logger = get_module_logger(__name__)




class RetrievalState(TypedDict, total=False):
    """State for the retrieval workflow."""
    # Input
    question: str
    graph_uri: str | None
    
    # Analysis
    complexity: str | None
    strategy: str | None
    analysis_result: Any | None
    analysis_time_ms: float
    
    # Results
    answer: str | None
    confidence: float
    success: bool
    error: str | None
    
    # Additional result metadata (for evaluation)
    kg_facts_count: int
    vector_results_count: int
    sparql_query: str | None
    
    # Timing
    started_at: str
    completed_at: str | None
    total_duration_ms: float
    
    # Logging
    log_file: str | None


class LangGraphRetrievalOrchestrator:
    """
    LangGraph-based orchestrator that wraps existing retrieval agents.
    
    Benefits:
    - State management and checkpointing via LangGraph
    - Phoenix observability for all LLM calls
    - Workflow visualization
    - Preserves existing agent logic and logging
    """
    
    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
        settings: Settings | None = None,
        enable_logging: bool = True,
        checkpoint_path: str = "checkpoints/retrieval.db",
    ):
        """Initialize the LangGraph orchestrator."""
        self.settings = settings or get_settings()
        self.enable_logging = enable_logging
        
        # Get stores from service factory
        service_factory = get_service_factory(settings=self.settings)
        self.sparql_store = sparql_store or service_factory.get_sparql_store()
        self.vector_store = vector_store or service_factory.get_vector_store()
        
        # Setup Phoenix tracing for observability
        setup_phoenix_tracing()
        
        # Initialize RAG logger
        log_dir = str(get_log_dir("retrieval"))
        self.rag_logger = get_rag_logger(log_dir) if enable_logging else None
        
        # Initialize ReAct agent only (simplified architecture)
        # Removed: UnifiedQueryAnalyzer (saves 60-80s per query)
        # Removed: RAGOrchestratorAgent (ReAct handles all queries)
        self.react_agent = ReActRetrievalAgent(
            sparql_store=self.sparql_store,
            vector_store=self.vector_store,
            settings=self.settings,
        )
        
        # Build LangGraph workflow
        self.workflow = self._build_workflow()
        
        # Setup checkpointing - compile without checkpointer for now
        # Checkpointing will be added when needed
        self.checkpoint_path = checkpoint_path
        self.app = self.workflow.compile()  # Compile without checkpointer
        self._checkpointer = None
        
        logger.info("LangGraph retrieval orchestrator initialized")
    
    def _build_workflow(self) -> StateGraph:
        """Build simplified LangGraph workflow - direct to ReAct agent."""
        workflow = StateGraph(RetrievalState)
        
        # Simplified: Only 2 nodes (execute + finalize)
        # Removed: analyze, route nodes (saves 60-80s)
        workflow.add_node("execute", self._execute_retrieval)
        workflow.add_node("finalize", self._finalize_result)
        
        # Direct path: entry -> execute -> finalize -> end
        workflow.set_entry_point("execute")
        workflow.add_edge("execute", "finalize")
        workflow.add_edge("finalize", END)
        
        return workflow
    
    async def _execute_retrieval(self, state: RetrievalState) -> RetrievalState:
        """Execute retrieval using ReAct agent (handles all query types)."""
        logger.info("Executing retrieval with ReAct agent", question=state["question"][:100])
        
        try:
            # Use ReAct agent for all queries (no pre-analysis)
            result = await self.react_agent.process({
                "question": state["question"],
            })
            
            # Extract metadata from ReAct result
            kg_facts_count = 0
            vector_results_count = 0
            sparql_query = None
            
            # Extract from aggregated_data
            if hasattr(result, 'aggregated_data') and result.aggregated_data:
                aggregated = result.aggregated_data
                kg_facts = aggregated.get('kg_facts', [])
                vector_results = aggregated.get('vector_results', [])
                kg_facts_count = len(kg_facts) if isinstance(kg_facts, list) else 0
                vector_results_count = len(vector_results) if isinstance(vector_results, list) else 0
            
            # Aggregate from steps
            if hasattr(result, 'steps') and result.steps:
                for step in result.steps:
                    if hasattr(step, 'data') and step.data:
                        step_kg_facts = step.data.get('kg_facts', [])
                        step_vector_results = step.data.get('vector_results', [])
                        if isinstance(step_kg_facts, list):
                            kg_facts_count += len(step_kg_facts)
                        if isinstance(step_vector_results, list):
                            vector_results_count += len(step_vector_results)
                        
                        if not sparql_query:
                            sparql_query = step.data.get('sparql_query') or getattr(step, 'sparql_query', None)
            
            # Fallback to result attributes
            if kg_facts_count == 0:
                kg_facts_count = getattr(result, "kg_facts_count", 0)
            if vector_results_count == 0:
                vector_results_count = getattr(result, "vector_results_count", 0)
            if not sparql_query:
                sparql_query = getattr(result, "sparql_query", None)
            
            return {
                **state,
                "answer": result.final_answer,
                "confidence": result.confidence,
                "success": True,
                "kg_facts_count": kg_facts_count,
                "vector_results_count": vector_results_count,
                "sparql_query": sparql_query,
            }
            
        except Exception as e:
            logger.error("Retrieval failed", error=str(e))
            return {
                **state,
                "answer": "",
                "confidence": 0.0,
                "success": False,
                "error": str(e),
            }
    
    async def _finalize_result(self, state: RetrievalState) -> RetrievalState:
        """Finalize result and log answer."""
        state["completed_at"] = datetime.now().isoformat()
        
        # Calculate total duration
        if state.get("started_at"):
            started = datetime.fromisoformat(state["started_at"])
            completed = datetime.fromisoformat(state["completed_at"])
            state["total_duration_ms"] = (completed - started).total_seconds() * 1000
        
        # Log final answer using existing RAG logger
        if self.enable_logging and self.rag_logger:
            log_file = self.rag_logger.end_session(
                final_answer=state.get("answer", ""),
                confidence=state.get("confidence", 0.0),
                status="completed" if state.get("success") else "failed",
            )
            state["log_file"] = log_file
            
            logger.info(
                "Answer logged",
                log_file=log_file,
                answer_length=len(state.get("answer", "")),
            )
        
        return state
    
    async def process_query(
        self,
        query: str,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """
        Backwards-compatible wrapper used by the FastAPI layer.
        
        The previous retrieval orchestrator exposed `process_query`. This method
        adapts the new LangGraph-based `retrieve` API to the expected response
        shape used in `api.main`.
        """
        result_state = await self.retrieve(question=query)
        
        # Basic fields
        answer = result_state.get("answer", "") or ""
        confidence = float(result_state.get("confidence", 0.0) or 0.0)
        processing_time = float(result_state.get("total_duration_ms", 0.0) or 0.0)
        
        # For now, we don't expose rich sources / reasoning from LangGraph here.
        # Keep the keys for compatibility with the API schema.
        response: dict[str, Any] = {
            "answer": answer,
            "sources": [],  # TODO: map LangGraph step data into sources
            "reasoning_steps": [],  # TODO: expose LangGraph trace if desired
            "confidence": confidence,
            "processing_time": processing_time,
        }
        return response
    
    async def retrieve(
        self,
        question: str,
        graph_uri: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a question through the LangGraph retrieval pipeline.
        
        Args:
            question: Natural language question
            graph_uri: Optional named graph URI
            thread_id: Optional thread ID for checkpointing
            
        Returns:
            Result dictionary with answer and metadata
        """
        # Start RAG logging session
        if self.enable_logging and self.rag_logger:
            self.rag_logger.start_session(question)
        
        logger.info("Starting LangGraph retrieval", question=question[:100])
        
        # Initialize state
        initial_state: RetrievalState = {
            "question": question,
            "graph_uri": graph_uri,
            "complexity": None,
            "strategy": None,
            "analysis_result": None,
            "analysis_time_ms": 0.0,
            "answer": None,
            "confidence": 0.0,
            "success": False,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "total_duration_ms": 0.0,
            "log_file": None,
        }
        
        # Execute workflow (without checkpointing for now - simpler and works)
        # TODO: Add proper checkpointing support when needed
        config = {}
        
        try:
            final_state = await self.app.ainvoke(initial_state, config)
            
            logger.info(
                "LangGraph retrieval complete",
                success=final_state["success"],
                duration_ms=final_state["total_duration_ms"],
            )
            
            return final_state
            
        except Exception as e:
            logger.error("LangGraph retrieval failed", error=str(e))
            
            # End session on failure
            if self.enable_logging and self.rag_logger:
                log_file = self.rag_logger.end_session(
                    final_answer="",
                    confidence=0.0,
                    status="failed",
                )
            
            return {
                **initial_state,
                "success": False,
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            }


