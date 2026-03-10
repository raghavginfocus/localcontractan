"""
Answer Critique Agent

This agent evaluates the quality and completeness of generated answers.
It determines if the answer:
1. Actually addresses the question asked
2. Is complete and sufficient
3. Needs more information or refinement
4. Identifies what's missing if incomplete
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate

from agents.shared.base import BaseAgent
from config import Settings


class AnswerCritique(BaseModel):
    """Structured critique of an answer."""
    
    is_complete: bool = Field(
        description="Whether the answer fully addresses the question"
    )
    is_relevant: bool = Field(
        description="Whether the answer is relevant to the question"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence in the answer quality (0-1)"
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="List of missing information needed to complete the answer"
    )
    reasoning: str = Field(
        description="Explanation of the critique"
    )
    needs_refinement: bool = Field(
        description="Whether the answer needs further refinement"
    )
    suggested_follow_up_queries: List[str] = Field(
        default_factory=list,
        description="Suggested queries to gather missing information"
    )


class AnswerCritiqueAgent(BaseAgent):
    """
    Agent that critiques answer quality and completeness.
    
    This agent acts as a quality gate, ensuring answers are:
    - Complete and sufficient
    - Relevant to the question
    - Backed by appropriate evidence
    
    If an answer is incomplete, it identifies what's missing and
    suggests follow-up queries to gather the needed information.
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        llm: Optional[BaseChatModel] = None
    ):
        super().__init__(settings, llm)
        self.name = "AnswerCritiqueAgent"
        self._setup_prompts()
    
    async def process(self, input_data: Any) -> Any:
        """Required abstract method - delegates to critique_answer."""
        return await self.critique_answer(**input_data)
    
    def _setup_prompts(self):
        """Setup the critique prompt template."""
        self.critique_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert answer quality evaluator for a contract knowledge graph system.

Your task is to critically evaluate whether an answer:
1. **Fully addresses the question** - Does it answer what was asked?
2. **Is complete** - Does it provide sufficient detail and coverage?
3. **Is relevant** - Does it stay on topic?
4. **Uses evidence appropriately** - Is it backed by the provided facts?

For incomplete answers, identify:
- What specific information is missing
- What follow-up queries would gather that information

Be strict but fair. Simple questions need simple answers. Complex questions need comprehensive answers.

Output your critique as structured JSON."""),
            ("human", """Question: {question}

Answer: {answer}

Available Facts Used: {facts_summary}

Number of facts: {num_facts}
Sources: {sources}

Evaluate this answer critically. Consider:
- Does it answer the specific question asked?
- Is it complete for the question's complexity?
- What's missing (if anything)?
- Should we gather more information?

Provide your critique as JSON with these fields:
- is_complete: boolean
- is_relevant: boolean
- confidence_score: float (0-1)
- missing_information: list of strings
- reasoning: string explaining your assessment
- needs_refinement: boolean
- suggested_follow_up_queries: list of strings (if refinement needed)""")
        ])
    
    async def critique_answer(
        self,
        question: str,
        answer: str,
        facts: List[Dict[str, Any]],
        sources: List[str]
    ) -> AnswerCritique:
        """
        Critique an answer for quality and completeness.
        
        Args:
            question: The original question
            answer: The generated answer
            facts: Facts used to generate the answer
            sources: Sources of the facts (KG, vector, etc.)
            
        Returns:
            AnswerCritique with detailed evaluation
        """
        self.logger.info(
            f"Critiquing answer for question: {question[:100]}..."
        )
        
        # Prepare facts summary
        facts_summary = self._summarize_facts(facts)
        
        # Create structured LLM - let LangChain auto-detect best method
        structured_llm = self.llm.with_structured_output(AnswerCritique)
        
        # Generate critique
        critique_chain = self.critique_prompt | structured_llm
        
        try:
            critique = await critique_chain.ainvoke({
                "question": question,
                "answer": answer,
                "facts_summary": facts_summary,
                "num_facts": len(facts),
                "sources": ", ".join(sources)
            })
            
            # Handle None response from LLM (structured output not supported)
            if critique is None:
                self.logger.warning(
                    "LLM returned None - structured output may not be supported. "
                    "Creating permissive critique to allow answer through."
                )
                critique = AnswerCritique(
                    is_complete=True,
                    is_relevant=True,
                    confidence_score=0.7,
                    missing_information=[],
                    reasoning="LLM structured output unavailable, accepting answer",
                    needs_refinement=False,
                    suggested_follow_up_queries=[]
                )
        except Exception as e:
            self.logger.error(f"Critique failed: {e}. Accepting answer.")
            critique = AnswerCritique(
                is_complete=True,
                is_relevant=True,
                confidence_score=0.7,
                missing_information=[],
                reasoning=f"Critique error: {str(e)}",
                needs_refinement=False,
                suggested_follow_up_queries=[]
            )
        
        self.logger.info(
            f"Critique complete - Complete: {critique.is_complete}, "
            f"Relevant: {critique.is_relevant}, "
            f"Confidence: {critique.confidence_score:.2f}, "
            f"Needs refinement: {critique.needs_refinement}"
        )
        
        if critique.missing_information:
            self.logger.info(
                f"Missing information: {critique.missing_information}"
            )
        
        if critique.suggested_follow_up_queries:
            self.logger.info(
                f"Suggested follow-ups: "
                f"{critique.suggested_follow_up_queries}"
            )
        
        return critique
    
    def _summarize_facts(self, facts: List[Dict[str, Any]]) -> str:
        """Create a concise summary of facts for the critique."""
        if not facts:
            return "No facts provided"
        
        # Group facts by type if available
        fact_types = {}
        for fact in facts:
            fact_type = fact.get("type", "unknown")
            if fact_type not in fact_types:
                fact_types[fact_type] = 0
            fact_types[fact_type] += 1
        
        summary_parts = [f"{count} {ftype} facts" for ftype, count in fact_types.items()]
        
        # Add sample facts
        sample_facts = facts[:3]
        samples = []
        for fact in sample_facts:
            if isinstance(fact, dict):
                # Extract key information
                if "subject" in fact and "predicate" in fact:
                    samples.append(f"{fact['subject']} {fact['predicate']} {fact.get('object', '...')}")
                elif "text" in fact:
                    samples.append(fact["text"][:100])
        
        summary = ", ".join(summary_parts)
        if samples:
            summary += f"\nSample: {'; '.join(samples)}"
        
        return summary
    
    def should_refine(
        self,
        critique: AnswerCritique,
        iteration: int,
        max_iterations: int = 3,
        previous_fact_count: int = 0,
        current_fact_count: int = 0
    ) -> bool:
        """
        Determine if answer should be refined based on critique.
        
        Pragmatic stopping criteria:
        - Accept "good enough" answers (relevant + reasonably complete)
        - Stop if no progress (no new facts retrieved)
        - Stop if confidence threshold met
        
        Args:
            critique: The answer critique
            iteration: Current iteration number
            max_iterations: Maximum allowed iterations
            previous_fact_count: Facts from previous iteration
            current_fact_count: Facts in current iteration
            
        Returns:
            True if refinement should continue
        """
        # Don't refine if we've hit max iterations
        if iteration >= max_iterations:
            self.logger.info(
                f"Max iterations ({max_iterations}) reached, "
                "stopping refinement"
            )
            return False
        
        # PRAGMATIC: Accept "good enough" answers
        # If relevant AND confidence >= 0.75, accept it
        if critique.is_relevant and critique.confidence_score >= 0.75:
            self.logger.info(
                f"Answer is relevant with good confidence "
                f"({critique.confidence_score:.2f}), accepting"
            )
            return False
        
        # Don't refine if answer is complete and relevant
        if critique.is_complete and critique.is_relevant:
            self.logger.info(
                "Answer is complete and relevant, no refinement needed"
            )
            return False
        
        # Don't refine if confidence is very high
        if critique.confidence_score >= 0.9:
            self.logger.info(
                f"High confidence ({critique.confidence_score:.2f}), "
                "accepting answer"
            )
            return False
        
        # EARLY STOPPING: No progress made (no new facts)
        if iteration > 1 and current_fact_count <= previous_fact_count:
            self.logger.info(
                f"No new facts retrieved "
                f"(prev: {previous_fact_count}, curr: {current_fact_count}), "
                "stopping refinement"
            )
            return False
        
        # Refine if explicitly marked as needing refinement AND confidence low
        if critique.needs_refinement and critique.confidence_score < 0.65:
            self.logger.info(
                f"Critique indicates refinement needed with low confidence "
                f"({critique.confidence_score:.2f})"
            )
            return True
        
        # Refine if there's missing information and confidence is low
        if critique.missing_information and critique.confidence_score < 0.65:
            self.logger.info(
                f"Missing information detected with low confidence "
                f"({critique.confidence_score:.2f}), refining"
            )
            return True
        
        self.logger.info(
            f"No refinement needed - confidence: {critique.confidence_score:.2f}, "
            f"relevant: {critique.is_relevant}, complete: {critique.is_complete}"
        )
        return False


