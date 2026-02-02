"""
Synthesis Optimizer - Optimized answer generation from collected data.

This module provides multiple synthesis strategies to reduce the main bottleneck
in retrieval (synthesis takes 40-60% of total time):

1. Smart Data Filtering: Pre-filter and rank data before synthesis
2. Concise Prompts: Reduce prompt size for faster LLM processing
3. Streaming: Stream answers for better perceived performance
4. Caching: Cache common synthesis patterns
"""

import time
from typing import Any

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from logger import get_module_logger

logger = get_module_logger(__name__)


class SynthesisResult(BaseModel):
    """Result from synthesis with timing breakdown."""
    
    answer: str = Field(description="Generated answer")
    confidence: float = Field(description="Confidence score 0-1")
    data_filtering_ms: float = Field(default=0.0, description="Data filtering time")
    llm_call_ms: float = Field(default=0.0, description="LLM synthesis time")
    total_ms: float = Field(default=0.0, description="Total synthesis time")
    facts_used: int = Field(default=0, description="Number of facts used")
    strategy: str = Field(default="standard", description="Synthesis strategy used")
    
    # Detailed quality evaluation metrics
    relevance_score: float = Field(default=0.0, description="Answer-question relevance")
    data_utilization_score: float = Field(default=0.0, description="Data usage score")
    is_evasive: bool = Field(default=False, description="Evasive answer detected")


class SynthesisOptimizer:
    """
    Optimized synthesis engine with multiple strategies.
    
    Key optimizations:
    1. Smart data filtering (keep only most relevant)
    2. Concise prompts (reduce token count)
    3. Relevance scoring (rank facts by relevance)
    4. Deduplication (remove redundant information)
    """
    
    # Enhanced prompt emphasizing specificity and data usage
    SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """Answer using SPECIFIC details from the provided facts.

Question: {question}

Available Facts:
{filtered_facts}

CRITICAL INSTRUCTIONS:
1. Use SPECIFIC data from facts (contract names, clause types, frequencies)
2. If facts show inconsistencies, LIST them with examples
3. If facts show patterns, DESCRIBE them with data
4. DO NOT say "no information" if facts exist - analyze what's there
5. Be concrete: use actual values, not generic statements
6. DO NOT include any code (no Python, no pseudo-code, no scripts)
7. DO NOT include markdown code fences (no ``` blocks)
8. Provide a business-style answer (bullets/tables ok), not developer guidance

Generate a detailed, data-driven answer:"""),
        ("human", "Generate answer."),
    ])
    
    def __init__(self, llm: Any):
        """Initialize synthesis optimizer with LLM."""
        self.llm = llm
        self.logger = logger.bind(component="SynthesisOptimizer")
    
    async def synthesize(
        self,
        question: str,
        all_data: dict[str, Any],
        strategy: str = "optimized",
    ) -> SynthesisResult:
        """
        Synthesize answer using specified strategy.
        
        Args:
            question: Original question
            all_data: All collected data from retrieval steps
            strategy: "optimized" (default), "standard", or "streaming"
            
        Returns:
            SynthesisResult with answer and timing breakdown
        """
        start_time = time.time()
        
        self.logger.info(f"Starting synthesis with strategy: {strategy}")
        
        # Step 1: Filter and rank data (smart pre-processing)
        filter_start = time.time()
        filtered_data = self._filter_and_rank_data(question, all_data)
        filter_time = (time.time() - filter_start) * 1000
        
        self.logger.info(f"Data filtering completed in {filter_time:.2f}ms")
        self.logger.info(f"  Facts before: {self._count_total_facts(all_data)}")
        self.logger.info(f"  Facts after: {len(filtered_data['facts'])}")
        
        # Step 2: Format for synthesis (concise)
        formatted_facts = self._format_filtered_data(filtered_data)
        
        # Step 3: Synthesize answer
        llm_start = time.time()
        
        if strategy == "streaming":
            answer = await self._synthesize_streaming(question, formatted_facts)
        else:
            answer = await self._synthesize_standard(question, formatted_facts)
        
        llm_time = (time.time() - llm_start) * 1000
        
        self.logger.info(f"LLM synthesis completed in {llm_time:.2f}ms")
        
        # Step 4: Evaluate answer quality and calculate confidence
        evaluation = self._evaluate_answer_quality(
            question, answer, filtered_data
        )
        
        total_time = (time.time() - start_time) * 1000
        
        # Log warning if answer quality is poor
        if evaluation['confidence'] < 0.4:
            self.logger.warning(
                f"Low confidence answer ({evaluation['confidence']:.2f}). "
                f"Answer may not use retrieved data properly."
            )
            if evaluation['is_evasive']:
                self.logger.warning("Evasive answer detected!")
        
        return SynthesisResult(
            answer=answer,
            confidence=evaluation['confidence'],
            data_filtering_ms=filter_time,
            llm_call_ms=llm_time,
            total_ms=total_time,
            facts_used=len(filtered_data['facts']),
            strategy=strategy,
            relevance_score=evaluation['relevance_score'],
            data_utilization_score=evaluation['utilization_score'],
            is_evasive=evaluation['is_evasive'],
        )
    
    def _filter_and_rank_data(
        self,
        question: str,
        all_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Filter and rank data with adaptive thresholds.
        
        Keeps MORE data for analytical questions to avoid data loss.
        """
        # Detect analytical questions
        analytical_keywords = [
            "inconsistencies", "compare", "analyze", "which",
            "differences", "variations", "standardize", "what types",
            "list all", "show all", "what are", "how many"
        ]
        is_analytical = any(
            kw in question.lower() for kw in analytical_keywords
        )
        
        # Collect all facts
        all_kg_facts = []
        all_vector_results = []
        
        for step_data in all_data.values():
            if isinstance(step_data, dict):
                all_kg_facts.extend(step_data.get("kg_facts", []))
                all_vector_results.extend(step_data.get("vector_results", []))
        
        # Deduplicate facts
        unique_kg_facts = self._deduplicate_facts(all_kg_facts)
        unique_vector_results = self._deduplicate_vector_results(
            all_vector_results
        )
        
        # Rank by relevance
        ranked_kg_facts = self._rank_kg_facts(question, unique_kg_facts)
        ranked_vector_results = self._rank_vector_results(
            question,
            unique_vector_results
        )
        
        # Adaptive thresholds
        if is_analytical:
            # Looser filtering for analytical questions: keep more facts/contexts
            TOP_KG_FACTS = 30
            TOP_VECTOR_RESULTS = 15
            self.logger.info(
                "Analytical question - keeping more facts for analysis"
            )
        else:
            TOP_KG_FACTS = 10
            TOP_VECTOR_RESULTS = 5
        
        # Safety: never drop all facts if we had any to begin with.
        # If ranking returns nothing but we do have KG facts/contexts,
        # fall back to the unranked unique sets (capped by TOP_*).
        if not ranked_kg_facts and unique_kg_facts:
            self.logger.info(
                "Ranking returned 0 KG facts; falling back to all unique KG facts"
            )
            ranked_kg_facts = unique_kg_facts
        if not ranked_vector_results and unique_vector_results:
            self.logger.info(
                "Ranking returned 0 vector results; falling back to all unique contexts"
            )
            ranked_vector_results = unique_vector_results
        
        return {
            "facts": ranked_kg_facts[:TOP_KG_FACTS],
            "contexts": ranked_vector_results[:TOP_VECTOR_RESULTS],
        }
    
    def _deduplicate_facts(self, facts: list[dict]) -> list[dict]:
        """Remove duplicate facts based on content."""
        seen = set()
        unique = []
        
        for fact in facts:
            # Create a signature for the fact
            signature = tuple(sorted(fact.items()))
            if signature not in seen:
                seen.add(signature)
                unique.append(fact)
        
        return unique
    
    def _deduplicate_vector_results(self, results: list[dict]) -> list[dict]:
        """Remove duplicate vector results based on text similarity."""
        if not results:
            return []
        
        unique = []
        seen_texts = set()
        
        for result in results:
            text = result.get("text", "")
            # Use first 100 chars as signature
            signature = text[:100].lower().strip()
            
            if signature and signature not in seen_texts:
                seen_texts.add(signature)
                unique.append(result)
        
        return unique
    
    def _rank_kg_facts(
        self,
        question: str,
        facts: list[dict]
    ) -> list[dict]:
        """Rank KG facts by relevance to question."""
        if not facts:
            return []
        
        # Simple keyword-based ranking
        question_lower = question.lower()
        question_words = set(question_lower.split())
        
        scored_facts = []
        for fact in facts:
            # Calculate relevance score
            fact_text = " ".join(str(v).lower() for v in fact.values())
            fact_words = set(fact_text.split())
            
            # Jaccard similarity
            intersection = len(question_words & fact_words)
            union = len(question_words | fact_words)
            score = intersection / union if union > 0 else 0
            
            scored_facts.append((score, fact))
        
        # Sort by score descending
        scored_facts.sort(key=lambda x: x[0], reverse=True)
        
        return [fact for score, fact in scored_facts]
    
    def _rank_vector_results(
        self,
        question: str,
        results: list[dict]
    ) -> list[dict]:
        """Rank vector results by relevance score."""
        if not results:
            return []
        
        # Sort by existing relevance score if available
        scored_results = []
        for result in results:
            score = result.get("score", 0.0)
            scored_results.append((score, result))
        
        # Sort by score descending
        scored_results.sort(key=lambda x: x[0], reverse=True)
        
        return [result for score, result in scored_results]
    
    def _format_filtered_data(self, filtered_data: dict) -> str:
        """Format filtered data with detail for better synthesis."""
        lines = []
        
        # KG Facts (detailed format with all fields)
        facts = filtered_data.get("facts", [])
        if facts:
            lines.append("Knowledge Graph Facts:")
            for i, fact in enumerate(facts, 1):
                # Show all fields clearly
                fact_details = []
                for k, v in fact.items():
                    fact_details.append(f"{k}={v}")
                lines.append(f"{i}. {' | '.join(fact_details)}")
        
        # Vector Contexts (detailed format with more text)
        contexts = filtered_data.get("contexts", [])
        if contexts:
            lines.append("\nRelevant Clause Text:")
            for i, ctx in enumerate(contexts, 1):
                text = ctx.get("text", "")[:250]  # More text
                clause_type = ctx.get("clause_type", "Unknown")
                contract_id = ctx.get("contract_id", "Unknown")
                score = ctx.get("score", 0.0)
                
                lines.append(
                    f"{i}. Contract: {contract_id} | "
                    f"Type: {clause_type} | Score: {score:.2f}"
                )
                lines.append(f"   Text: {text}...")
        
        return "\n".join(lines)
    
    async def _synthesize_standard(
        self,
        question: str,
        formatted_facts: str
    ) -> str:
        """Standard synthesis with enhanced prompt."""
        chain = self.SYNTHESIS_PROMPT | self.llm | StrOutputParser()
        
        try:
            answer = await chain.ainvoke({
                "question": question,
                "filtered_facts": formatted_facts,
            })
            return self._strip_code_blocks(answer).strip()
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            return f"Unable to synthesize answer: {str(e)}"
    
    async def _synthesize_streaming(
        self,
        question: str,
        formatted_facts: str
    ) -> str:
        """Streaming synthesis for better perceived performance."""
        chain = self.SYNTHESIS_PROMPT | self.llm
        
        try:
            answer_chunks = []
            async for chunk in chain.astream({
                "question": question,
                "filtered_facts": formatted_facts,
            }):
                if hasattr(chunk, 'content'):
                    answer_chunks.append(chunk.content)
                else:
                    answer_chunks.append(str(chunk))
            
            return self._strip_code_blocks("".join(answer_chunks)).strip()
        except Exception as e:
            self.logger.error(f"Streaming synthesis failed: {e}")
            return f"Unable to synthesize answer: {str(e)}"
    
    def _strip_code_blocks(self, text: str) -> str:
        """Remove markdown fenced code blocks if the model outputs them anyway."""
        if not text:
            return text
        import re
        # Remove ```...``` blocks (including optional language)
        return re.sub(r"```[\s\S]*?```", "", text)
    
    def _evaluate_answer_quality(
        self,
        question: str,
        answer: str,
        filtered_data: dict
    ) -> dict:
        """
        Evaluate answer quality with multiple checks.
        
        Returns dict with:
        - confidence: Overall score 0-1
        - relevance_score: Answer-question relevance 0-1
        - utilization_score: Data usage score 0-1
        - is_evasive: Boolean flag for evasive answers
        """
        score = 0.0
        
        facts_count = len(filtered_data.get("facts", []))
        contexts_count = len(filtered_data.get("contexts", []))
        
        # 1. Data availability (max 0.3)
        if facts_count > 0:
            score += min(0.15, facts_count * 0.02)
        if contexts_count > 0:
            score += min(0.15, contexts_count * 0.03)
        
        # 2. Answer-question relevance (max 0.3)
        relevance_score = self._check_answer_relevance(question, answer)
        score += relevance_score * 0.3
        
        # 3. Data utilization check (max 0.25)
        utilization_score = self._check_data_utilization(
            answer, filtered_data
        )
        score += utilization_score * 0.25
        
        # 4. Evasiveness check
        is_evasive = self._is_evasive_answer(answer, facts_count, contexts_count)
        if is_evasive:
            score *= 0.3  # Severe penalty for evasive answers
            self.logger.warning(
                "Evasive answer detected - claims no data when data exists"
            )
        
        # 5. Structure bonus (max +0.15)
        if any(m in answer for m in ["-", "•", "1.", "2.", ":"]):
            score += 0.1
        if len(answer) > 100:
            score += 0.05
        
        final_confidence = min(1.0, max(0.0, score))
        
        return {
            'confidence': final_confidence,
            'relevance_score': relevance_score,
            'utilization_score': utilization_score,
            'is_evasive': is_evasive,
        }
    
    def _check_answer_relevance(self, question: str, answer: str) -> float:
        """Check if answer is relevant to question (keyword overlap)."""
        q_words = set(question.lower().split())
        a_words = set(answer.lower().split())
        
        # Remove common words
        stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for",
            "of", "and", "or", "but", "is", "are", "was", "were"
        }
        q_words -= stop_words
        a_words -= stop_words
        
        if not q_words:
            return 0.5
        
        # Jaccard similarity
        intersection = len(q_words & a_words)
        union = len(q_words | a_words)
        
        return intersection / union if union > 0 else 0.0
    
    def _check_data_utilization(
        self, answer: str, filtered_data: dict
    ) -> float:
        """Check if answer actually uses the retrieved data."""
        answer_lower = answer.lower()
        
        # Check if answer references any fact values
        facts = filtered_data.get("facts", [])
        contexts = filtered_data.get("contexts", [])
        
        references = 0
        total_items = len(facts) + len(contexts)
        
        if total_items == 0:
            return 0.0
        
        # Check KG fact references
        for fact in facts:
            for value in fact.values():
                value_str = str(value).lower()
                if len(value_str) > 3 and value_str in answer_lower:
                    references += 1
                    break
        
        # Check vector context references
        for ctx in contexts:
            text = ctx.get("text", "")[:50].lower()
            if text and text in answer_lower:
                references += 1
        
        return min(1.0, references / max(1, total_items * 0.3))
    
    def _is_evasive_answer(
        self, answer: str, facts_count: int, contexts_count: int
    ) -> bool:
        """Detect evasive answers that claim no data when data exists."""
        if facts_count == 0 and contexts_count == 0:
            return False
        
        answer_lower = answer.lower()
        
        # Red flag phrases
        evasive_phrases = [
            "no information",
            "not possible to",
            "cannot identify",
            "insufficient",
            "no details",
            "no data",
            "not available",
            "cannot determine",
        ]
        
        return any(phrase in answer_lower for phrase in evasive_phrases)
    
    def _count_total_facts(self, all_data: dict) -> int:
        """Count total facts in all data."""
        total = 0
        for step_data in all_data.values():
            if isinstance(step_data, dict):
                total += len(step_data.get("kg_facts", []))
                total += len(step_data.get("vector_results", []))
        return total
    

