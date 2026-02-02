"""
RAG Orchestrator Agent - Combines Knowledge Graph and Vector retrieval.

Features comprehensive logging of all inputs/outputs for:
- Debugging and troubleshooting
- Evaluation and quality assessment
- Audit trails and transparency
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from config import get_settings
from logging_utils import RAGLogger, get_rag_logger
from logging_config import get_log_dir


class RAGResponse(BaseModel):
    """Response from the RAG system."""
    
    success: bool = Field(default=True, description="Whether the query succeeded")
    question: str = Field(description="Original question")
    answer: str = Field(description="Generated answer")
    sparql_query: str | None = Field(default=None, description="SPARQL query used")
    kg_facts: list[dict[str, Any]] = Field(default_factory=list, description="Facts from KG")
    vector_context: list[dict[str, Any]] = Field(default_factory=list, description="Context from vector DB")
    explanation_trace: str = Field(default="", description="Reasoning trace")
    confidence: float = Field(default=0.0, description="Confidence score 0-1")
    log_file: str | None = Field(default=None, description="Path to detailed log file")
    error: str | None = Field(default=None, description="Error message if failed")


class RAGOrchestratorAgent(BaseAgent):
    """
    Hybrid RAG Orchestrator combining Knowledge Graph and Vector retrieval.
    
    This agent:
    1. Analyzes the question to determine retrieval strategy
    2. Queries the Knowledge Graph via SPARQL for structured facts
    3. Queries Milvus for supporting text/context
    4. Combines both sources to generate a comprehensive answer
    5. Provides explanation traces for auditability
    """

    STRATEGY_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are a query routing expert. Analyze the question and determine the best retrieval strategy.

Strategies:
1. KG_ONLY: ONLY for simple factual lookups like "list all contracts" or "count contracts"
2. VECTOR_ONLY: For questions about specific clause wording or searching text
3. HYBRID: DEFAULT - Use for most questions. Combines structured KG facts WITH clause text context.
4. DIRECT: Only for greetings or questions not about contracts

IMPORTANT: Most questions should use HYBRID because:
- KG provides structured data (values, dates, notice periods)
- Vector store provides full clause text for context

Use HYBRID for: contract values, termination periods, risks, compliance, payments, penalties, analysis.
Use KG_ONLY for: simple counts, listing entities.

Respond with ONLY the strategy name (KG_ONLY, VECTOR_ONLY, HYBRID, or DIRECT)."""),
        ("human", "{question}"),
    ])

    ANSWER_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert procurement contract analyst. 
Answer the question concisely using ONLY the provided facts and context.

CRITICAL INSTRUCTIONS:
1. Be CONCISE - provide only relevant information, no unnecessary explanations
2. Structure your answer clearly with bullet points or numbered lists when appropriate
3. Use ONLY information from the provided facts and context - do not add general knowledge
4. If information is incomplete, state what is available and what is missing
5. For risks/compliance: List specific findings, not generic advice
6. Avoid verbose introductions or conclusions - get straight to the point

Knowledge Graph Facts (structured, inferred):
{kg_facts}

Supporting Context (from contract text):
{vector_context}

Question: {question}

Provide a concise, well-structured answer with only relevant information."""),
        ("human", "Generate the answer."),
    ])

    def __init__(
        self,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
        sparql_agent: SPARQLGeneratorAgent | None = None,
        rag_logger: RAGLogger | None = None,
        log_dir: str | None = None,
        **kwargs: Any,
    ):
        """
        Initialize the RAG orchestrator.
        
        Args:
            sparql_store: SPARQL store instance (injected via dependency injection)
            vector_store: Vector store instance (injected via dependency injection)
            sparql_agent: Optional SPARQL generator agent
            rag_logger: Optional RAG logger
            log_dir: Optional log directory
            **kwargs: Additional arguments passed to BaseAgent
        """
        super().__init__(**kwargs)
        
        # Use dependency injection - get from service factory if not provided
        service_factory = get_service_factory(settings=self.settings)
        self.sparql_store = sparql_store or service_factory.get_sparql_store()
        self.vector_store = vector_store or service_factory.get_vector_store()
        
        # Initialize SPARQL agent with the store
        self.sparql_agent = sparql_agent or SPARQLGeneratorAgent(
            sparql_store=self.sparql_store,
            settings=self.settings,
        )
        
        # Initialize RAG logger for comprehensive I/O tracking
        if log_dir is None:
            log_dir = str(get_log_dir("retrieval"))
        self.rag_logger = rag_logger or get_rag_logger(log_dir)
        
        # Keep fuseki_client for backward compatibility (deprecated)
        # TODO: Remove after all components are updated
        self.fuseki_client = self.sparql_store

    def _ensure_vector_store(self):
        """Ensure vector store is available."""
        if self.vector_store is None:
            service_factory = get_service_factory(settings=self.settings)
            self.vector_store = service_factory.get_vector_store()
        return self.vector_store

    async def process(self, input_data: dict[str, Any] | str, enable_logging: bool = True) -> RAGResponse:
        """
        Process a question using hybrid RAG.
        
        Args:
            input_data: Either a question string or dict with 'question' and optional 'graph_uri'
            enable_logging: Whether to log all I/O to files
            
        Returns:
            RAGResponse with answer and sources
        """
        # Extract question and graph_uri from input
        if isinstance(input_data, dict):
            question = input_data.get('question', '')
            graph_uri = input_data.get('graph_uri')
            enable_logging = input_data.get('enable_logging', enable_logging)
        else:
            question = input_data
            graph_uri = None
        
        log_file = None
        
        # Initialize explanation builder for each new process call
        # This ensures each test case gets its own explanation file
        if self.enable_explanations:
            self._init_explanation()
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input({"question": question, "graph_uri": graph_uri})
        
        # Start logging session
        if enable_logging:
            self.rag_logger.start_session(question)
        
        self.log_start("rag_processing", question=str(question)[:100])
        
        # Always use HYBRID strategy for richer context
        strategy = "HYBRID"
        
        # Step 1: Knowledge Graph Retrieval (always retrieve from KG)
        if enable_logging:
            self.rag_logger.log_step_start("kg_retrieval", {"question": question, "strategy": strategy})
        
        kg_facts, sparql_query = await self._retrieve_from_kg(question, graph_uri=graph_uri)
        
        if enable_logging:
            self.rag_logger.log_step_end("kg_retrieval", {
                "sparql_query": sparql_query,
                "facts_count": len(kg_facts),
                "facts": kg_facts[:10],  # Limit for logging
            })
        
        # Step 2: Vector Store Retrieval (always retrieve from Vector)
        if enable_logging:
            self.rag_logger.log_step_start("vector_retrieval", {"question": question[:50]})
        
        vector_context = await self._retrieve_from_vector(question)
        
        if enable_logging:
            self.rag_logger.log_step_end("vector_retrieval", {
                "context_count": len(vector_context),
                "contexts": [
                    {"score": c.get("score"), "clause_type": c.get("clause_type"), "text_preview": c.get("text", "")[:100]}
                    for c in vector_context
                ],
            })
        
        # Step 3: Answer Generation
        if enable_logging:
            self.rag_logger.log_step_start("answer_generation", {
                "kg_facts_count": len(kg_facts),
                "vector_context_count": len(vector_context),
            })
        
        answer, trace = await self._generate_answer(question, kg_facts, vector_context)
        
        if enable_logging:
            self.rag_logger.log_step_end("answer_generation", {
                "answer_length": len(answer),
                "answer_preview": answer[:500],
            })
        
        # Calculate confidence based on source availability
        confidence = self._calculate_confidence(kg_facts, vector_context)
        
        result = RAGResponse(
            question=question,
            answer=answer,
            sparql_query=sparql_query,
            kg_facts=kg_facts,
            vector_context=vector_context,
            explanation_trace=trace,
            confidence=confidence,
        )
        
        # Generate explanation for unanswered or low-confidence queries
        if self.enable_explanations and (len(kg_facts) == 0 and len(vector_context) == 0 or confidence < 0.3):
            try:
                from agent_explanation import create_explanation_for_unanswered_query
                from logging_config import get_log_dir
                
                errors = []
                if sparql_query and "error" in str(sparql_query).lower():
                    errors.append("SPARQL query error")
                if len(kg_facts) == 0 and len(vector_context) == 0:
                    errors.append("No relevant data found")
                
                explanation = create_explanation_for_unanswered_query(
                    question=question,
                    kg_facts_count=len(kg_facts),
                    vector_results_count=len(vector_context),
                    sparql_query=sparql_query,
                    errors=errors if errors else None,
                )
                
                # Unanswered query explanation saving disabled - using Phoenix tracing
                self.logger.debug("Unanswered query logged (Phoenix tracing)",
                                question=question[:100], confidence=confidence)
            except Exception as e:
                self.logger.warning("Failed to log unanswered query", error=str(e))
        
        # End logging session
        if enable_logging:
            log_file = self.rag_logger.end_session(answer, confidence)
            result.log_file = log_file
        
        # Record output for explanation
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("kg_facts_count", len(kg_facts))
            self.explanation_builder.add_metadata("vector_context_count", len(vector_context))
            self.explanation_builder.add_metadata("confidence", confidence)
            # Add the actual answer to explanation
            self.explanation_builder.add_metadata("answer", answer)
            self.explanation_builder.add_metadata("sparql_query", sparql_query)
            # Map confidence to level
            if confidence < 0.3:
                self.explanation_builder.set_confidence("low")
            elif confidence < 0.6:
                self.explanation_builder.set_confidence("medium")
            else:
                self.explanation_builder.set_confidence("high")
            # Save explanation
            self._save_explanation()
        
        self.log_complete(
            "rag_processing",
            strategy=strategy,
            kg_fact_count=len(kg_facts),
            vector_context_count=len(vector_context),
        )
        
        return result

    async def _determine_strategy(self, question: str) -> str:
        """Determine the best retrieval strategy for the question."""
        chain = self.STRATEGY_PROMPT | self.llm | StrOutputParser()
        
        try:
            response = await chain.ainvoke({"question": question})
            
            # Parse strategy from response
            response_upper = response.upper()
            if "KG_ONLY" in response_upper:
                return "KG_ONLY"
            elif "VECTOR_ONLY" in response_upper:
                return "VECTOR_ONLY"
            elif "DIRECT" in response_upper:
                return "DIRECT"
            else:
                return "HYBRID"
        except Exception:
            return "HYBRID"  # Default to hybrid

    async def _retrieve_from_kg(
        self,
        question: str,
        graph_uri: str | None = None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Retrieve facts from Knowledge Graph using SPARQL."""
        try:
            self.logger.debug(
                "Starting KG retrieval",
                question=question[:100],
                graph_uri=graph_uri,
            )
            
            result = await self.sparql_agent.generate_and_execute(
                question,
                graph_uri=graph_uri,
            )
            
            # Log the generated SPARQL query
            sparql_query = result.get("query")
            if sparql_query:
                self.logger.info(
                    "SPARQL query generated for KG retrieval",
                    question=question[:100],
                    query_length=len(sparql_query),
                    query_preview=sparql_query[:300] + "..." if len(sparql_query) > 300 else sparql_query,
                )
            
            # Check for validation errors
            if not result.get("validation_passed", True):
                validation_error = result.get("validation_error", "Unknown validation error")
                self.logger.warning(
                    "SPARQL query validation failed",
                    question=question[:100],
                    error=validation_error,
                    query=sparql_query[:500] if sparql_query else None,
                )
                return [], sparql_query
            
            # Check for execution errors
            execution_error = result.get("execution_error")
            if execution_error:
                self.logger.warning(
                    "SPARQL query execution failed",
                    question=question[:100],
                    error=execution_error,
                    query=sparql_query[:500] if sparql_query else None,
                )
                return [], sparql_query
            
            facts = result.get("results", [])
            
            # Check if results contain errors
            if facts and any("error" in fact for fact in facts):
                error_facts = [f for f in facts if "error" in f]
                self.logger.warning(
                    "SPARQL query returned errors",
                    question=question[:100],
                    errors=[e.get("error") for e in error_facts],
                    query=sparql_query[:500] if sparql_query else None,
                )
                # Return empty facts but keep the query for debugging
                return [], sparql_query
            
            # Handle boolean results (ASK queries)
            if isinstance(facts, bool):
                facts = [{"result": facts}]
            
            # Log successful retrieval
            if facts:
                self.logger.info(
                    "KG retrieval successful",
                    question=question[:100],
                    facts_retrieved=len(facts),
                    query=sparql_query[:200] if sparql_query else None,
                )
            else:
                self.logger.debug(
                    "KG retrieval returned no facts",
                    question=question[:100],
                    query=sparql_query[:200] if sparql_query else None,
                )
            
            return facts, sparql_query
            
        except Exception as e:
            error_message = str(e)
            error_type = type(e).__name__
            
            # Provide more context for common errors
            suggestion = None
            if "FusekiClient not configured" in error_message:
                suggestion = "Ensure FusekiClient is properly initialized in SPARQLGeneratorAgent"
            elif "timeout" in error_message.lower():
                suggestion = "Query may be too complex or Fuseki may be slow - consider simplifying query"
            elif "connection" in error_message.lower():
                suggestion = "Check if Fuseki server is running and accessible"
            
            self.logger.error(
                "KG retrieval failed with exception",
                error_message=error_message,
                error_type=error_type,
                question=question[:100],
                graph_uri=graph_uri,
                suggestion=suggestion,
            )
            return [], None

    async def _retrieve_from_vector(self, question: str) -> list[dict[str, Any]]:
        """Retrieve relevant context from Milvus vector database."""
        try:
            vector_store = self._ensure_vector_store()
            # MilvusStore v2 will do summary-first + optional full-text fallback internally.
            results = vector_store.search(query=question, top_k=8)
            return results
        except Exception as e:
            self.logger.warning("Vector retrieval failed", error=str(e))
            return []

    async def _generate_answer(
        self,
        question: str,
        kg_facts: list[dict[str, Any]],
        vector_context: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Generate answer from retrieved information."""
        # Format facts and context
        facts_text = self._format_facts(kg_facts) if kg_facts else "No structured facts found."
        context_text = self._format_vector_context(vector_context) if vector_context else "No supporting text found."
        
        chain = self.ANSWER_PROMPT | self.llm | StrOutputParser()
        
        # Add retry logic for broken pipe errors
        try:
            from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
            
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type((BrokenPipeError, ConnectionError, OSError)),
                reraise=True,
            )
            async def _invoke_with_retry():
                return await chain.ainvoke({
                    "question": question,
                    "kg_facts": facts_text,
                    "vector_context": context_text,
                })
            
            answer = await _invoke_with_retry()
        except (BrokenPipeError, ConnectionError, OSError) as e:
            self.logger.warning(
                "LLM connection error during answer generation",
                error=str(e),
                question=question[:100],
            )
            # Return a fallback answer
            answer = f"Unable to generate complete answer due to connection issue. Based on available information:\n\nKG Facts: {len(kg_facts)} facts found\nVector Context: {len(vector_context)} contexts found\n\nPlease retry the query."
        except Exception as e:
            # For other errors, try once more without retry
            try:
                answer = await chain.ainvoke({
                    "question": question,
                    "kg_facts": facts_text,
                    "vector_context": context_text,
                })
            except Exception as e2:
                self.logger.error(
                    "Answer generation failed after retry",
                    error=str(e2),
                    question=question[:100],
                )
                answer = f"Error generating answer: {str(e2)}"
        
        # Create explanation trace
        trace = f"""
Retrieval Strategy: {"KG + Vector" if kg_facts and vector_context else "KG only" if kg_facts else "Vector only" if vector_context else "Direct"}
KG Facts Retrieved: {len(kg_facts)}
Vector Contexts Retrieved: {len(vector_context)}
"""
        
        return answer, trace

    def _format_facts(self, facts: list[dict[str, Any] | str]) -> str:
        """Format KG facts for the LLM prompt."""
        if not facts:
            return "No facts found."
        
        lines = []
        for i, fact in enumerate(facts, 1):
            if isinstance(fact, dict):
                fact_str = ", ".join(f"{k}: {v}" for k, v in fact.items())
            else:
                fact_str = str(fact)
            lines.append(f"{i}. {fact_str}")
        
        return "\n".join(lines)

    def _format_vector_context(self, contexts: list[dict[str, Any]]) -> str:
        """Format vector search results for the LLM prompt."""
        if not contexts:
            return "No context found."
        
        lines = []
        for i, ctx in enumerate(contexts, 1):
            clause_type = ctx.get("clause_type", "Unknown")
            text = ctx.get("text", "")[:500]  # Truncate long text
            score = ctx.get("score", 0)
            lines.append(f"{i}. [{clause_type}] (relevance: {score:.2f})\n   {text}")
        
        return "\n\n".join(lines)

    def _calculate_confidence(
        self,
        kg_facts: list[dict[str, Any]],
        vector_context: list[dict[str, Any]],
    ) -> float:
        """Calculate confidence score based on evidence."""
        score = 0.0
        
        # KG facts are high confidence (inferred, structured)
        if kg_facts:
            score += min(0.5, len(kg_facts) * 0.1)
        
        # Vector context adds supporting evidence
        if vector_context:
            # Also consider relevance scores
            avg_score = sum(c.get("score", 0) for c in vector_context) / len(vector_context)
            score += min(0.3, len(vector_context) * 0.04 + avg_score * 0.1)
        
        # Bonus for having both sources
        if kg_facts and vector_context:
            score += 0.2
        
        return min(1.0, score)

    def add_clause_to_vector_store(
        self,
        clause_id: str,
        text: str,
        contract_id: str = "",
        clause_type: str = "",
    ) -> None:
        """Add a clause to the vector store for retrieval."""
        vector_store = self._ensure_vector_store()
        vector_store.add_clause(
            clause_id=clause_id,
            text=text,
            contract_id=contract_id,
            clause_type=clause_type,
        )

    def add_clauses_batch(
        self,
        clauses: list[dict[str, Any]],
    ) -> int:
        """Add multiple clauses to the vector store."""
        vector_store = self._ensure_vector_store()
        return vector_store.add_clauses_batch(clauses)

    def search_clauses(
        self,
        query: str,
        top_k: int = 5,
        clause_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Direct search in vector store."""
        vector_store = self._ensure_vector_store()
        return vector_store.search(
            query=query,
            top_k=top_k,
            clause_type=clause_type,
        )
