"""
Retrieval Orchestrator - Complete orchestration for the retrieval pipeline.

This orchestrator manages the complete flow for answering questions:
1. Unified query analysis (complexity + decomposition in single call)
2. Route to appropriate retrieval strategy:
   - Simple: Direct KG retrieval
   - Complex: Optimized multi-step with decomposed queries
3. Result combination and answer generation
4. Response formatting and comprehensive timing logs
"""

import re
import time
from datetime import datetime
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.rag_orchestrator import RAGOrchestratorAgent, RAGResponse
from agents.retrieval.unified_query_analyzer import (
    UnifiedQueryAnalyzer,
    QueryAnalysisResult,
    QueryComplexity,
)
from agents.retrieval.query_classifier import QueryClassifier, RetrievalRoute
from agents.retrieval.react_agent_optimized import ReActRetrievalAgent
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from fuseki_client import FusekiClient
from service_factory import get_service_factory
from config import Settings, get_settings
from logger import get_module_logger
from logging_config import get_log_dir
from logging_utils import RAGLogger, get_rag_logger

logger = get_module_logger(__name__)


class RetrievalStrategy(str, Enum):
    """Retrieval strategy types."""
    KG_ONLY = "kg_only"  # Only use Knowledge Graph
    VECTOR_ONLY = "vector_only"  # Only use Vector Store
    HYBRID = "hybrid"  # Use both KG and Vector
    REACT_MULTI_STEP = "react_multi_step"  # ReAct reasoning for complex queries
    DIRECT = "direct"  # Direct answer without retrieval


class RetrievalStep(BaseModel):
    """Represents a step in the retrieval pipeline with timing."""
    
    step_name: str
    started_at: datetime
    completed_at: datetime | None = None
    success: bool = False
    duration_ms: float = 0.0
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    
    # Detailed timing breakdown
    llm_time_ms: float = Field(default=0.0, description="LLM call time")
    retrieval_time_ms: float = Field(default=0.0, description="Retrieval time")
    processing_time_ms: float = Field(default=0.0, description="Processing time")


class RetrievalResult(BaseModel):
    """Result of the complete retrieval pipeline."""
    
    question: str = Field(description="Original question")
    success: bool = Field(description="Whether retrieval completed successfully")
    steps: list[RetrievalStep] = Field(default_factory=list, description="Details of each step")
    
    # Strategy and sources
    strategy: RetrievalStrategy = Field(description="Retrieval strategy used")
    kg_facts_count: int = Field(default=0, description="Number of KG facts retrieved")
    vector_context_count: int = Field(default=0, description="Number of vector contexts retrieved")
    text_search_count: int = Field(default=0, description="Number of text search results retrieved")
    
    # Answer
    answer: str = Field(default="", description="Generated answer")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")
    sparql_query: str | None = Field(default=None, description="SPARQL query used")
    
    # Metadata and timing
    total_duration_ms: float = Field(default=0.0)
    analysis_time_ms: float = Field(default=0.0, description="Query analysis time")
    retrieval_time_ms: float = Field(default=0.0, description="Total retrieval time")
    synthesis_time_ms: float = Field(default=0.0, description="Answer synthesis time")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    log_file: str | None = Field(default=None, description="Path to detailed log file")
    error: str | None = None


class RetrievalOrchestrator:
    """
    Complete orchestration for the retrieval pipeline.
    
    Pipeline Flow:
    1. Query understanding and strategy determination
    2. Knowledge Graph retrieval (if needed)
    3. Vector store retrieval (if needed)
    4. Result combination and answer generation
    5. Response formatting
    """

    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
        settings: Settings | None = None,
        enable_logging: bool = True,
        enable_react: bool = True,
    ):
        """
        Initialize the retrieval orchestrator with dependency injection.
        
        Args:
            sparql_store: SPARQL store for KG queries
            vector_store: Vector store for semantic search
            settings: Application settings
            enable_logging: Whether to enable detailed logging
            enable_react: Whether to enable ReAct for complex queries
        """
        self.settings = settings or get_settings()
        self.enable_logging = enable_logging
        self.enable_react = enable_react
        self.logger = logger.bind(orchestrator="RetrievalOrchestrator")
        
        # Use dependency injection - get from service factory if not provided
        service_factory = get_service_factory(settings=self.settings)
        sparql_store = sparql_store or service_factory.get_sparql_store()
        vector_store = vector_store or service_factory.get_vector_store()
        
        # Initialize unified query analyzer (replaces separate complexity detector)
        self.query_analyzer = UnifiedQueryAnalyzer(
            settings=self.settings
        )
        
        # Initialize query classifier for routing (text index vs vector vs SPARQL)
        self.query_classifier = QueryClassifier(settings=self.settings)
        
        # Initialize Fuseki client for text search
        self.fuseki_client = FusekiClient(settings=self.settings)
        
        # Initialize RAG logger for session files and answer logging
        log_dir = str(get_log_dir("retrieval"))
        self.rag_logger = get_rag_logger(log_dir) if enable_logging else None
        
        # Initialize standard RAG orchestrator
        self.rag_orchestrator = RAGOrchestratorAgent(
            sparql_store=sparql_store,
            vector_store=vector_store,
            settings=self.settings,
            log_dir=log_dir,
        )
        
        # Initialize optimized ReAct agent for complex queries
        if self.enable_react:
            self.react_agent = ReActRetrievalAgent(
                sparql_store=sparql_store,
                vector_store=vector_store,
                settings=self.settings,
            )
            logger.info("Initialized optimized ReAct agent with parallel execution")
        else:
            self.react_agent = None
        
        # Initialize SPARQL generator (for direct SPARQL queries if needed)
        self.sparql_agent = SPARQLGeneratorAgent(
            sparql_store=sparql_store,
            settings=self.settings,
        )

    async def retrieve(
        self,
        question: str,
        graph_uri: str | None = None,
        strategy: RetrievalStrategy | None = None,
        force_react: bool = False,
    ) -> RetrievalResult:
        """
        Process a question through the complete retrieval pipeline.
        
        Args:
            question: Natural language question
            graph_uri: Optional named graph URI to query
            strategy: Optional retrieval strategy (auto-determined if not provided)
            force_react: Force use of ReAct agent regardless of complexity
            
        Returns:
            RetrievalResult with answer and sources
        """
        result = RetrievalResult(
            question=question,
            success=False,
            started_at=datetime.now(),
            strategy=strategy or RetrievalStrategy.HYBRID,
        )
        
        # Start RAG logging session (creates session files)
        if self.enable_logging and self.rag_logger:
            self.rag_logger.start_session(question)
        
        self.logger.info("Starting retrieval pipeline", question=question[:100])
        logger.info("=" * 60)
        logger.info(f"RETRIEVAL PIPELINE - Question: {question[:100]}")
        
        try:
            # Step 1: Unified query analysis (single LLM call)
            analysis_start = time.time()
            
            if strategy is None:
                # Unified analysis: complexity + decomposition in one call
                analysis_result = await self.query_analyzer.process(question)
                analysis_time = (time.time() - analysis_start) * 1000
                result.analysis_time_ms = analysis_time
                
                logger.info(f"Query analysis completed in {analysis_time:.2f}ms")
                logger.info(f"  Complexity: {analysis_result.complexity.value}")
                logger.info(f"  Confidence: {analysis_result.confidence:.2f}")
                logger.info(f"  Reasoning: {analysis_result.reasoning[:100]}")
                logger.info(f"  Sub-queries: {len(analysis_result.sub_queries)}")
                
                # Log decomposed queries for transparency
                if analysis_result.sub_queries:
                    logger.info("  Decomposed Query Plan:")
                    for sq in analysis_result.sub_queries:
                        logger.info(f"    [{sq.step_number}] {sq.question[:70]}")
                        logger.info(f"        Type: {sq.query_type}, Depends: {sq.depends_on}")
                
                # Determine strategy based on analysis (Smart Hybrid - Option B)
                if analysis_result.complexity == QueryComplexity.SIMPLE:
                    # For simple queries, use smart hybrid:
                    # - Pure count/list queries → KG_ONLY (fast)
                    # - Queries with keywords → KG + Text Search (comprehensive)
                    # - Other simple queries → Standard Hybrid (KG + Vector + Text)
                    if self._is_pure_count_or_list_query(question, analysis_result):
                        strategy = RetrievalStrategy.KG_ONLY
                        logger.info("Using KG_ONLY for pure count/list query (fast path)")
                    else:
                        strategy = RetrievalStrategy.HYBRID
                        logger.info("Using SMART HYBRID for simple query (KG + Text + Vector when needed)")
                else:
                    strategy = RetrievalStrategy.REACT_MULTI_STEP
                    logger.info("Using REACT for complex query (optimized)")
            else:
                analysis_result = None
                analysis_time = 0.0
            
            result.strategy = strategy
            logger.info(f"Strategy: {strategy.value}")
            
            # Step 1.5: Classify query for optimal routing (text vs vector vs SPARQL)
            classification = self.query_classifier.classify(question)
            logger.info(f"Query classification: {classification.primary_route.value}")
            logger.info(f"  Reasoning: {classification.reasoning}")
            logger.info(f"  Confidence: {classification.confidence:.2f}")
            if classification.detected_keywords:
                logger.info(f"  Keywords: {classification.detected_keywords}")
            if classification.detected_numbers:
                logger.info(f"  Numbers: {classification.detected_numbers}")
            
            # Step 2: Execute appropriate retrieval strategy
            if strategy == RetrievalStrategy.KG_ONLY:
                # Fast path: Direct KG retrieval for pure count/list queries
                # (No text search for these as they're just aggregations)
                return await self._execute_kg_only_retrieval(
                    result, question, graph_uri, classification, use_text_search=False
                )
            elif strategy == RetrievalStrategy.REACT_MULTI_STEP and self.react_agent:
                # Use ReAct agent with pre-analyzed query plan
                return await self._execute_react_retrieval(
                    result, question, graph_uri, analysis_result
                )
            else:
                # Use smart hybrid retrieval (KG + Text + Vector when appropriate)
                return await self._execute_standard_retrieval(
                    result, question, graph_uri, classification
                )
            
            
        except Exception as e:
            self.logger.error("Retrieval failed", error=str(e))
            result.error = str(e)
            result.success = False
            logger.error(f"  ✗ FAILED: {e}")
            
            # End session even on failure
            if self.enable_logging and self.rag_logger:
                log_file = self.rag_logger.end_session(
                    final_answer=result.answer or "",
                    confidence=result.confidence,
                    status="failed",
                )
                result.log_file = log_file
        
        return result
    
    async def _execute_standard_retrieval(
        self,
        result: RetrievalResult,
        question: str,
        graph_uri: str | None,
        classification,
    ) -> RetrievalResult:
        """Execute standard hybrid retrieval with text search integration."""
        try:
            logger.info("Using STANDARD HYBRID retrieval with text search")
            
            # Collect all contexts
            kg_facts = []
            vector_context = []
            text_search_results = []
            
            # Step 1: Text Index Search (if applicable)
            if classification.primary_route in [RetrievalRoute.TEXT_INDEX, RetrievalRoute.HYBRID]:
                if classification.has_exact_terms:
                    logger.info("Using text index for exact term search")
                    if self.enable_logging and self.rag_logger:
                        self.rag_logger.log_step_start("text_search", {
                            "keywords": classification.detected_keywords,
                            "numbers": classification.detected_numbers,
                        })
                    
                    try:
                        # Use text search for detected keywords/numbers
                        search_terms = " ".join(classification.detected_keywords + classification.detected_numbers)
                        if not search_terms:
                            search_terms = question  # Fallback to full query
                        
                        text_search_results = self.fuseki_client.text_search(
                            search_term=search_terms,
                            field="text",
                            limit=10,
                        )
                        result.text_search_count = len(text_search_results)
                        logger.info(f"Text search returned {len(text_search_results)} results")
                        
                        if self.enable_logging and self.rag_logger:
                            self.rag_logger.log_step_end("text_search", {
                                "results_count": len(text_search_results),
                                "results": text_search_results[:5],
                            })
                    except Exception as e:
                        logger.warning(f"Text search failed, falling back: {e}")
                        # Fallback: continue without text search
            
            # Step 2: Knowledge Graph Retrieval (SPARQL)
            if classification.primary_route in [RetrievalRoute.SPARQL, RetrievalRoute.HYBRID]:
                if self.enable_logging and self.rag_logger:
                    self.rag_logger.log_step_start("kg_retrieval", {"question": question, "graph_uri": graph_uri})
                
                kg_facts, sparql_query = await self._step_kg_retrieval(
                    result, question, graph_uri
                )
                result.kg_facts_count = len(kg_facts)
                result.sparql_query = sparql_query
                
                if self.enable_logging and self.rag_logger:
                    self.rag_logger.log_step_end("kg_retrieval", {
                        "sparql_query": sparql_query,
                        "facts_count": len(kg_facts),
                        "facts": kg_facts[:10],
                    })
            
            # Step 3: Vector Store Retrieval (semantic search)
            if classification.primary_route in [RetrievalRoute.VECTOR, RetrievalRoute.HYBRID]:
                if self.enable_logging and self.rag_logger:
                    self.rag_logger.log_step_start("vector_retrieval", {"question": question[:50]})
                
                vector_context = await self._step_vector_retrieval(result, question)
                result.vector_context_count = len(vector_context)
                
                if self.enable_logging and self.rag_logger:
                    self.rag_logger.log_step_end("vector_retrieval", {
                        "context_count": len(vector_context),
                        "contexts": [
                            {"score": c.get("score"), "clause_type": c.get("clause_type"), "text_preview": c.get("text", "")[:100]}
                            for c in vector_context
                        ],
                    })
            
            # Step 4: Merge and deduplicate results
            all_contexts = self._merge_retrieval_results(
                kg_facts, vector_context, text_search_results
            )
            
            # Step 5: Answer Generation
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_start("answer_generation", {
                    "kg_facts_count": len(kg_facts),
                    "vector_context_count": len(vector_context),
                    "text_search_count": len(text_search_results),
                    "total_contexts": len(all_contexts),
                })
            
            answer, confidence = await self._step_answer_generation(
                result, question, kg_facts, all_contexts
            )
            result.answer = answer
            result.confidence = confidence
            
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_end("answer_generation", {
                    "answer_length": len(answer),
                    "answer_preview": answer[:500],
                })
            
            # Mark success
            result.success = True
            
        except Exception as e:
            self.logger.error("Standard retrieval failed", error=str(e))
            result.error = str(e)
            result.success = False
        
        # Finalize timing
        result.completed_at = datetime.now()
        if result.started_at:
            result.total_duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
        
        # End RAG logging session and save log file
        if self.enable_logging and self.rag_logger:
            log_file = self.rag_logger.end_session(
                final_answer=result.answer,
                confidence=result.confidence,
                status="completed" if result.success else "failed",
            )
            result.log_file = log_file
        
        self.logger.info(
            "Standard retrieval completed",
            success=result.success,
            duration_ms=result.total_duration_ms,
        )
        
        return result
    
    def _merge_retrieval_results(
        self,
        kg_facts: list[dict[str, Any]],
        vector_context: list[dict[str, Any]],
        text_search_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Merge and deduplicate results from multiple retrieval sources.
        
        Args:
            kg_facts: SPARQL query results
            vector_context: Vector search results
            text_search_results: Text index search results
            
        Returns:
            Merged and deduplicated list of contexts
        """
        # Use clause_id or rdf_uri as deduplication key
        seen = set()
        merged = []
        
        # Add text search results first (highest precision for exact matches)
        for result in text_search_results:
            clause_id = result.get("clause") or result.get("clause_id")
            if clause_id and clause_id not in seen:
                seen.add(clause_id)
                merged.append({
                    **result,
                    "source": "text_index",
                })
        
        # Add vector results (semantic matches)
        for result in vector_context:
            clause_id = result.get("clause_id")
            rdf_uri = result.get("rdf_uri")
            key = clause_id or rdf_uri
            if key and key not in seen:
                seen.add(key)
                merged.append({
                    **result,
                    "source": "vector",
                })
        
        # Add KG facts (structured data)
        for fact in kg_facts:
            # KG facts may not have clause_id, so use a different key
            fact_key = str(fact.get("clause", "") or fact.get("subject", ""))
            if fact_key and fact_key not in seen:
                seen.add(fact_key)
                merged.append({
                    **fact,
                    "source": "sparql",
                })
        
        logger.info(f"Merged {len(merged)} unique results from {len(text_search_results)} text + {len(vector_context)} vector + {len(kg_facts)} SPARQL")
        return merged
    
    def _is_pure_count_or_list_query(
        self,
        question: str,
        analysis_result: QueryAnalysisResult | None = None,
    ) -> bool:
        """
        Detect if query is a pure count or list query (no text search needed).
        
        These queries are just aggregations/lists and don't benefit from text search.
        Examples:
        - "how many contracts"
        - "list all contracts"
        - "count clauses"
        - "show all parties"
        """
        question_lower = question.lower()
        
        # Check for pure count patterns
        count_patterns = [
            r'\b(count|how many|number of|total number)\b',
            r'\b(how many|how much)\s+\w+\s+(are|do|does)',
        ]
        
        # Check for pure list patterns (without semantic intent)
        list_patterns = [
            r'\blist\s+(all|every)\s+\w+',
            r'\bshow\s+(all|every)\s+\w+',
            r'\bwhat\s+(are|is)\s+(all|every)\s+\w+',
        ]
        
        # Check if it's a pure structured query (from classification)
        if analysis_result:
            # Check sub-queries - if all are kg_only and simple lists/counts
            if analysis_result.sub_queries:
                all_simple = all(
                    sq.query_type == "kg_only" and 
                    any(pattern in sq.question.lower() for pattern in ["list", "count", "how many", "show all"])
                    for sq in analysis_result.sub_queries
                )
                if all_simple:
                    return True
        
        # Check question directly
        for pattern in count_patterns + list_patterns:
            if re.search(pattern, question_lower):
                # Make sure it's not asking for details (which would need text search)
                if not any(word in question_lower for word in ["what", "details", "explain", "describe", "about"]):
                    return True
        
        return False
    
    async def _execute_kg_only_retrieval(
        self,
        result: RetrievalResult,
        question: str,
        graph_uri: str | None,
        classification,
        use_text_search: bool = True,
    ) -> RetrievalResult:
        """
        Execute KG-only retrieval for simple queries (fast path).
        
        Args:
            use_text_search: If True, include text search when keywords detected (smart hybrid)
                           If False, skip text search (for pure count/list queries)
        """
        try:
            logger.info(f"Using KG_ONLY retrieval (fast path, text_search={'enabled' if use_text_search else 'disabled'})")
            
            # Log step: KG Retrieval
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_start("kg_retrieval", {"question": question, "graph_uri": graph_uri})
            
            # Step 1: Knowledge Graph Retrieval
            kg_facts, sparql_query = await self._step_kg_retrieval(
                result, question, graph_uri
            )
            result.kg_facts_count = len(kg_facts)
            result.sparql_query = sparql_query
            
            # Step 1.5: Text Index Search (if enabled and keywords detected)
            text_search_results = []
            if use_text_search and classification.has_exact_terms:
                logger.info("Adding text search for additional context (smart hybrid)")
                if self.enable_logging and self.rag_logger:
                    self.rag_logger.log_step_start("text_search", {
                        "keywords": classification.detected_keywords,
                        "numbers": classification.detected_numbers,
                    })
                
                try:
                    # Use text search for detected keywords/numbers
                    search_terms = " ".join(classification.detected_keywords + classification.detected_numbers)
                    if not search_terms:
                        search_terms = question  # Fallback to full query
                    
                    text_search_results = self.fuseki_client.text_search(
                        search_term=search_terms,
                        field="text",
                        limit=10,
                    )
                    result.text_search_count = len(text_search_results)
                    logger.info(f"  ✓ Retrieved {len(text_search_results)} results from text index")
                    
                    if self.enable_logging and self.rag_logger:
                        self.rag_logger.log_step_end("text_search", {
                            "results_count": len(text_search_results),
                            "search_terms": search_terms,
                        })
                except Exception as e:
                    logger.warning(f"Text search failed (continuing without it): {e}")
                    if self.enable_logging and self.rag_logger:
                        self.rag_logger.log_step_end("text_search", {"error": str(e)})
            
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_end("kg_retrieval", {
                    "sparql_query": sparql_query,
                    "facts_count": len(kg_facts),
                    "text_search_count": len(text_search_results),
                    "facts": kg_facts[:10],
                })
            
            # Merge KG facts with text search results
            all_contexts = self._merge_retrieval_results(kg_facts, [], text_search_results)
            
            # Log step: Answer Generation
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_start("answer_generation", {
                    "kg_facts_count": len(kg_facts),
                    "text_search_count": len(text_search_results),
                    "total_contexts": len(all_contexts),
                })
            
            # Step 2: Answer Generation (with text search context if available)
            answer, confidence = await self._step_answer_generation(
                result, question, kg_facts, all_contexts
            )
            result.answer = answer
            result.confidence = confidence
            
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_end("answer_generation", {
                    "answer_length": len(answer),
                    "answer_preview": answer[:500],
                })
            
            result.success = True
            
        except Exception as e:
            self.logger.error("KG-only retrieval failed", error=str(e))
            result.error = str(e)
            result.success = False
        
        # Finalize timing
        result.completed_at = datetime.now()
        if result.started_at:
            result.total_duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
        
        # End RAG logging session
        if self.enable_logging and self.rag_logger:
            log_file = self.rag_logger.end_session(
                final_answer=result.answer,
                confidence=result.confidence,
                status="completed" if result.success else "failed",
            )
            result.log_file = log_file
        
        self.logger.info(
            "KG-only retrieval completed",
            success=result.success,
            duration_ms=result.total_duration_ms,
        )
        
        return result
    
    async def _execute_react_retrieval(
        self,
        result: RetrievalResult,
        question: str,
        graph_uri: str | None = None,
        analysis_result: QueryAnalysisResult | None = None,
    ) -> RetrievalResult:
        """Execute optimized ReAct retrieval with pre-analyzed query plan."""
        try:
            logger.info("Using REACT MULTI-STEP retrieval")
            
            # Log ReAct step start
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_start("react_retrieval", {
                    "question": question,
                    "strategy": "REACT_MULTI_STEP",
                })
            
            # Execute ReAct with pre-analyzed plan (if available)
            retrieval_start = time.time()
            
            if analysis_result:
                # Pass the pre-analyzed plan to avoid re-analysis
                react_result = await self.react_agent.process({
                    "question": question,
                    "analysis_result": analysis_result,
                })
            else:
                # Fallback to original behavior
                react_result = await self.react_agent.process(question)
            
            retrieval_time = (time.time() - retrieval_start) * 1000
            result.retrieval_time_ms = retrieval_time
            
            logger.info(f"ReAct retrieval completed in {retrieval_time:.2f}ms")
            
            # Log ReAct iterations as steps (after execution completes)
            if self.enable_logging and self.rag_logger:
                for react_step in react_result.steps:
                    # Log each iteration as a step
                    self.rag_logger.log_step_start(
                        f"react_iteration_{react_step.iteration}",
                        {
                            "thought": react_step.thought[:200],
                            "action": react_step.action_type.value,
                        }
                    )
                    self.rag_logger.log_step_end(
                        f"react_iteration_{react_step.iteration}",
                        {
                            "observation": react_step.observation[:200] if react_step.observation else "",
                            "reflection": react_step.reflection[:200] if react_step.reflection else "",
                            "data_collected": {
                                "kg_facts_count": len(react_step.data_collected.get("kg_facts", [])),
                                "vector_results_count": len(react_step.data_collected.get("vector_results", [])),
                            },
                        },
                        status="success"
                    )
            
            # Convert ReAct result to RetrievalResult format
            result.answer = react_result.final_answer
            result.confidence = react_result.confidence
            result.success = True
            
            # Aggregate data counts from all steps
            total_kg_facts = 0
            total_vector_results = 0
            
            for step_data in react_result.aggregated_data.values():
                if isinstance(step_data, dict):
                    total_kg_facts += len(step_data.get("kg_facts", []))
                    total_vector_results += len(
                        step_data.get("vector_results", [])
                    )
            
            result.kg_facts_count = total_kg_facts
            result.vector_context_count = total_vector_results
            
            # Add ReAct steps to result
            for react_step in react_result.steps:
                result.steps.append(RetrievalStep(
                    step_name=f"react_iteration_{react_step.iteration}",
                    started_at=react_step.timestamp,
                    completed_at=react_step.timestamp,
                    success=True,
                    duration_ms=0.0,
                    result={
                        "thought": react_step.thought,
                        "action": react_step.action_type.value,
                        "observation": react_step.observation,
                        "reflection": react_step.reflection,
                    },
                ))
            
            # Log ReAct step end with evaluation metrics
            if self.enable_logging and self.rag_logger:
                self.rag_logger.log_step_end("react_retrieval", {
                    "total_iterations": react_result.total_iterations,
                    "final_answer_length": len(react_result.final_answer),
                    "confidence": react_result.confidence,
                })
            
            # Extract evaluation metrics from react_result if available
            evaluation_metrics = {}
            if hasattr(react_result, 'evaluation_metrics'):
                evaluation_metrics = react_result.evaluation_metrics
            
        except Exception as e:
            self.logger.error("ReAct retrieval failed", error=str(e))
            result.error = str(e)
            result.success = False
        
        # Finalize timing
        result.completed_at = datetime.now()
        if result.started_at:
            result.total_duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
        
        # End RAG logging session and save log file with evaluation metrics
        if self.enable_logging and self.rag_logger:
            log_file = self.rag_logger.end_session(
                final_answer=result.answer,
                confidence=result.confidence,
                status="completed" if result.success else "failed",
                evaluation_metrics=evaluation_metrics if 'evaluation_metrics' in locals() else None,
            )
            result.log_file = log_file
        
        self.logger.info(
            "ReAct retrieval completed",
            success=result.success,
            duration_ms=result.total_duration_ms,
            iterations=len(result.steps),
        )
        
        return result

    async def _step_kg_retrieval(
        self,
        result: RetrievalResult,
        question: str,
        graph_uri: str | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Step 2: Retrieve from Knowledge Graph."""
        step = RetrievalStep(
            step_name="kg_retrieval",
            started_at=datetime.now(),
        )
        logger.info("=" * 60)
        logger.info("STEP 1: KNOWLEDGE GRAPH RETRIEVAL")
        logger.info("  Generating SPARQL query and executing...")
        
        try:
            kg_facts, sparql_query = await self.rag_orchestrator._retrieve_from_kg(
                question, graph_uri=graph_uri
            )
            
            step.success = True
            step.result = {
                "facts_count": len(kg_facts),
                "query_length": len(sparql_query) if sparql_query else 0,
            }
            logger.info(f"  ✓ Retrieved {len(kg_facts)} facts from KG")
            
            return kg_facts, sparql_query
            
        except Exception as e:
            step.error = str(e)
            logger.error(f"  ✗ FAILED: {e}")
            return [], None
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def _step_vector_retrieval(
        self,
        result: RetrievalResult,
        question: str,
    ) -> list[dict[str, Any]]:
        """Step 3: Retrieve from Vector Store."""
        step = RetrievalStep(
            step_name="vector_retrieval",
            started_at=datetime.now(),
        )
        logger.info("=" * 60)
        logger.info("STEP 2: VECTOR STORE RETRIEVAL")
        logger.info("  Performing semantic search...")
        
        try:
            vector_context = await self.rag_orchestrator._retrieve_from_vector(question)
            
            step.success = True
            step.result = {"context_count": len(vector_context)}
            logger.info(f"  ✓ Retrieved {len(vector_context)} contexts from vector store")
            
            return vector_context
            
        except Exception as e:
            step.error = str(e)
            logger.error(f"  ✗ FAILED: {e}")
            return []
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def _step_answer_generation(
        self,
        result: RetrievalResult,
        question: str,
        kg_facts: list[dict[str, Any]],
        vector_context: list[dict[str, Any]],
    ) -> tuple[str, float]:
        """Step 4: Generate answer from retrieved information."""
        step = RetrievalStep(
            step_name="answer_generation",
            started_at=datetime.now(),
        )
        logger.info("=" * 60)
        logger.info("STEP 3: ANSWER GENERATION")
        logger.info("  Combining sources and generating answer...")
        
        try:
            answer, _ = await self.rag_orchestrator._generate_answer(
                question, kg_facts, vector_context
            )
            
            # Calculate confidence
            confidence = self.rag_orchestrator._calculate_confidence(
                kg_facts, vector_context
            )
            
            step.success = True
            step.result = {
                "answer_length": len(answer),
                "confidence": confidence,
            }
            logger.info(f"  ✓ Generated answer ({len(answer)} chars, confidence: {confidence:.2f})")
            
            return answer, confidence
            
        except Exception as e:
            step.error = str(e)
            logger.error(f"  ✗ FAILED: {e}")
            return "", 0.0
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def retrieve_batch(
        self,
        questions: list[str],
        graph_uri: str | None = None,
    ) -> list[RetrievalResult]:
        """
        Process multiple questions.
        
        Args:
            questions: List of questions
            graph_uri: Optional named graph URI
            
        Returns:
            List of RetrievalResult objects
        """
        results = []
        
        for question in questions:
            result = await self.retrieve(question, graph_uri=graph_uri)
            results.append(result)
        
        return results

    def get_pipeline_summary(self, result: RetrievalResult) -> dict[str, Any]:
        """Get a summary of the pipeline execution."""
        step_summary = {}
        for step in result.steps:
            step_summary[step.step_name] = {
                "success": step.success,
                "duration_ms": step.duration_ms,
                "error": step.error,
            }
        
        return {
            "question": result.question,
            "success": result.success,
            "strategy": result.strategy.value,
            "total_duration_ms": result.total_duration_ms,
            "metrics": {
                "kg_facts": result.kg_facts_count,
                "vector_contexts": result.vector_context_count,
                "confidence": result.confidence,
                "answer_length": len(result.answer),
            },
            "steps": step_summary,
        }
