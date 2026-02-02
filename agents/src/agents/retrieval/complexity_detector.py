"""
Query Complexity Detector - Determines if a query needs multi-step reasoning.

Analyzes queries to detect complexity indicators and route to appropriate
retrieval strategy (simple vs. ReAct multi-step).
"""

from enum import Enum
from typing import Any
import re

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class QueryComplexity(str, Enum):
    """Query complexity levels."""
    SIMPLE = "simple"  # Single-shot retrieval sufficient
    MODERATE = "moderate"  # May benefit from 2-3 steps
    COMPLEX = "complex"  # Requires multi-step reasoning


class ComplexityAnalysis(BaseModel):
    """Result of complexity analysis."""
    
    complexity: QueryComplexity = Field(description="Detected complexity level")
    confidence: float = Field(description="Confidence in classification (0-1)")
    indicators: list[str] = Field(default_factory=list, description="Detected complexity indicators")
    reasoning: str = Field(description="Explanation of classification")
    recommended_strategy: str = Field(description="Recommended retrieval strategy")


class QueryComplexityDetector(BaseAgent):
    """
    Detects query complexity to route to appropriate retrieval strategy.
    
    Uses both rule-based heuristics and LLM-based analysis for robust detection.
    """
    
    # Complexity indicators (rule-based)
    COMPLEXITY_PATTERNS = {
        "multiple_aspects": [
            r"\band\b.*\band\b",  # "X and Y and Z"
            r"consider.*,.*,",  # "consider A, B, C"
            r"including.*,.*,",  # "including X, Y, Z"
        ],
        "comparison": [
            r"\b(compare|contrast|versus|vs|difference between)\b",
            r"\b(highest|lowest|best|worst|most|least)\b",
            r"\b(which|what).*\b(more|less|better|worse)\b",
            r"\b(rank|order|sort|prioritize)\b",
        ],
        "aggregation": [
            r"\b(analyze|summarize|overview|profile|assessment)\b",
            r"\b(all|every|each).*\b(contract|clause|term)\b",
            r"\b(total|sum|count|average|aggregate)\b",
        ],
        "conditional": [
            r"\bif\b.*\bthen\b",
            r"\bwhen\b.*\bthen\b",
            r"\bdepending on\b",
            r"\bin case of\b",
        ],
        "cross_document": [
            r"\bacross\b.*\b(contracts|documents)\b",
            r"\bbetween\b.*\b(contracts|documents)\b",
            r"\ball\b.*\b(contracts|documents)\b",
        ],
        "multi_step": [
            r"\bfirst.*then\b",
            r"\bstep by step\b",
            r"\bprocess\b",
            r"\bprocedure\b",
        ],
    }
    
    # Fast, lightweight prompt for quick classification
    FAST_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """Classify this query as SIMPLE or COMPLEX.

SIMPLE queries (use KG directly, no vector search needed):
- Counts: "how many contracts", "count clauses", "number of..."
- Lists: "list all contracts", "what types of clauses", "show all..."
- Direct lookups: "what is the value of contract X", "termination period for..."

COMPLEX queries (use vector first, then ReAct if needed):
- Analysis: "analyze risk", "compare contracts", "assess compliance"
- Multi-aspect: "termination AND liability AND penalties"
- Ranking: "which contracts have highest risk"
- Synthesis: "provide assessment considering multiple factors"

Respond with ONLY: SIMPLE or COMPLEX"""),
        ("human", "{question}"),
    ])
    
    ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are a query complexity analyzer for a contract knowledge graph system.

Analyze the query and determine its complexity level:

SIMPLE: Single-shot retrieval sufficient
- Direct factual lookup: "What is the contract value?"
- Simple list: "List all contracts"
- Single entity query: "Show termination clause for contract X"

MODERATE: May benefit from 2-3 retrieval steps
- Two aspects: "What are the payment terms and penalties?"
- Simple comparison: "Which contract has higher value?"
- Basic aggregation: "Count contracts by jurisdiction"

COMPLEX: Requires multi-step reasoning and analysis
- Multiple aspects: "Analyze termination, liability, AND unusual clauses"
- Cross-document comparison: "Compare risk profiles across all contracts"
- Ranking/scoring: "Which contracts have highest risk?"
- Conditional logic: "If termination < 30 days, check liability terms"
- Synthesis required: "Provide risk assessment considering multiple factors"

Respond with:
1. Complexity level (SIMPLE, MODERATE, or COMPLEX)
2. Confidence (0-1)
3. Key indicators detected
4. Brief reasoning

Format:
COMPLEXITY: [level]
CONFIDENCE: [0-1]
INDICATORS: [list]
REASONING: [explanation]"""),
        ("human", "Analyze this query:\n\n{question}"),
    ])

    async def fast_classify(self, question: str) -> str:
        """
        Fast classification: SIMPLE or COMPLEX.
        Uses lightweight prompt for quick routing decisions.
        
        Returns:
            "SIMPLE" or "COMPLEX"
        """
        chain = self.FAST_CLASSIFICATION_PROMPT | self.llm | StrOutputParser()
        
        try:
            result = await chain.ainvoke({"question": question})
            classification = result.strip().upper()
            
            # Normalize response
            if "SIMPLE" in classification:
                return "SIMPLE"
            elif "COMPLEX" in classification:
                return "COMPLEX"
            else:
                # Default to COMPLEX if unclear
                return "COMPLEX"
        except Exception as e:
            logger.warning(f"Fast classification failed: {e}, defaulting to COMPLEX")
            return "COMPLEX"
    
    async def process(self, input_data: str | dict[str, Any]) -> ComplexityAnalysis:
        """
        Analyze query complexity.
        
        Args:
            input_data: Query string or dict with 'question' key
            
        Returns:
            ComplexityAnalysis with complexity level and reasoning
        """
        # Extract question
        if isinstance(input_data, dict):
            question = input_data.get("question", "")
        else:
            question = input_data
        
        self.log_start("complexity_detection", question=question[:100])
        
        # Step 1: Rule-based analysis (fast, deterministic)
        rule_based = self._rule_based_analysis(question)
        
        # Step 2: LLM-based analysis (slower, more nuanced)
        llm_based = await self._llm_based_analysis(question)
        
        # Step 3: Combine both analyses
        final_analysis = self._combine_analyses(rule_based, llm_based, question)
        
        self.log_complete(
            "complexity_detection",
            complexity=final_analysis.complexity.value,
            confidence=final_analysis.confidence,
        )
        
        return final_analysis
    
    def _rule_based_analysis(self, question: str) -> dict[str, Any]:
        """Fast rule-based complexity detection using patterns."""
        question_lower = question.lower()
        detected_indicators = []
        indicator_counts = {}
        
        # Check each pattern category
        for category, patterns in self.COMPLEXITY_PATTERNS.items():
            matches = []
            for pattern in patterns:
                if re.search(pattern, question_lower, re.IGNORECASE):
                    matches.append(pattern)
            
            if matches:
                detected_indicators.append(category)
                indicator_counts[category] = len(matches)
        
        # Determine complexity based on indicators
        num_indicators = len(detected_indicators)
        
        if num_indicators == 0:
            complexity = QueryComplexity.SIMPLE
            confidence = 0.8
        elif num_indicators == 1:
            # Single indicator - could be moderate or simple
            if detected_indicators[0] in ["comparison", "aggregation"]:
                complexity = QueryComplexity.MODERATE
                confidence = 0.7
            else:
                complexity = QueryComplexity.SIMPLE
                confidence = 0.6
        elif num_indicators == 2:
            complexity = QueryComplexity.MODERATE
            confidence = 0.75
        else:  # 3+ indicators
            complexity = QueryComplexity.COMPLEX
            confidence = 0.85
        
        # Boost confidence for strong indicators
        if "multiple_aspects" in detected_indicators and num_indicators >= 2:
            complexity = QueryComplexity.COMPLEX
            confidence = min(0.95, confidence + 0.1)
        
        if "cross_document" in detected_indicators:
            complexity = QueryComplexity.COMPLEX
            confidence = min(0.95, confidence + 0.1)
        
        return {
            "complexity": complexity,
            "confidence": confidence,
            "indicators": detected_indicators,
            "indicator_counts": indicator_counts,
        }
    
    async def _llm_based_analysis(self, question: str) -> dict[str, Any]:
        """LLM-based complexity analysis for nuanced understanding."""
        try:
            chain = self.ANALYSIS_PROMPT | self.llm | StrOutputParser()
            response = await chain.ainvoke({"question": question})
            
            # Parse LLM response
            complexity_match = re.search(r"COMPLEXITY:\s*(SIMPLE|MODERATE|COMPLEX)", response, re.IGNORECASE)
            confidence_match = re.search(r"CONFIDENCE:\s*(0?\.\d+|1\.0|1)", response)
            indicators_match = re.search(r"INDICATORS:\s*(.+?)(?=REASONING:|$)", response, re.DOTALL)
            reasoning_match = re.search(r"REASONING:\s*(.+?)$", response, re.DOTALL)
            
            complexity_str = complexity_match.group(1).upper() if complexity_match else "MODERATE"
            complexity = QueryComplexity(complexity_str.lower())
            
            confidence = float(confidence_match.group(1)) if confidence_match else 0.7
            
            indicators_text = indicators_match.group(1).strip() if indicators_match else ""
            indicators = [i.strip() for i in indicators_text.split(",") if i.strip()]
            
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "LLM analysis"
            
            return {
                "complexity": complexity,
                "confidence": confidence,
                "indicators": indicators,
                "reasoning": reasoning,
            }
            
        except Exception as e:
            self.logger.warning("LLM-based analysis failed, using fallback", error=str(e))
            return {
                "complexity": QueryComplexity.MODERATE,
                "confidence": 0.5,
                "indicators": ["llm_analysis_failed"],
                "reasoning": f"LLM analysis failed: {str(e)}",
            }
    
    def _combine_analyses(
        self,
        rule_based: dict[str, Any],
        llm_based: dict[str, Any],
        question: str,
    ) -> ComplexityAnalysis:
        """Combine rule-based and LLM-based analyses."""
        # Weight: 60% rule-based, 40% LLM-based (rules are more reliable)
        rule_weight = 0.6
        llm_weight = 0.4
        
        # Convert complexity to numeric for averaging
        complexity_values = {
            QueryComplexity.SIMPLE: 1,
            QueryComplexity.MODERATE: 2,
            QueryComplexity.COMPLEX: 3,
        }
        
        rule_value = complexity_values[rule_based["complexity"]]
        llm_value = complexity_values[llm_based["complexity"]]
        
        # Weighted average
        avg_value = rule_value * rule_weight + llm_value * llm_weight
        
        # Convert back to complexity
        if avg_value < 1.5:
            final_complexity = QueryComplexity.SIMPLE
        elif avg_value < 2.5:
            final_complexity = QueryComplexity.MODERATE
        else:
            final_complexity = QueryComplexity.COMPLEX
        
        # Combine confidences
        final_confidence = (
            rule_based["confidence"] * rule_weight +
            llm_based["confidence"] * llm_weight
        )
        
        # Combine indicators
        all_indicators = list(set(
            rule_based["indicators"] + llm_based["indicators"]
        ))
        
        # Generate reasoning
        reasoning_parts = [
            f"Rule-based: {rule_based['complexity'].value} ({rule_based['confidence']:.2f})",
            f"LLM-based: {llm_based['complexity'].value} ({llm_based['confidence']:.2f})",
        ]
        
        if rule_based["indicators"]:
            reasoning_parts.append(f"Detected patterns: {', '.join(rule_based['indicators'])}")
        
        if llm_based.get("reasoning"):
            reasoning_parts.append(f"LLM reasoning: {llm_based['reasoning'][:200]}")
        
        reasoning = " | ".join(reasoning_parts)
        
        # Determine recommended strategy
        if final_complexity == QueryComplexity.SIMPLE:
            strategy = "standard_hybrid"  # Standard KG + Vector retrieval
        elif final_complexity == QueryComplexity.MODERATE:
            strategy = "enhanced_hybrid"  # Standard with result refinement
        else:
            strategy = "react_multi_step"  # Full ReAct reasoning loop
        
        return ComplexityAnalysis(
            complexity=final_complexity,
            confidence=final_confidence,
            indicators=all_indicators,
            reasoning=reasoning,
            recommended_strategy=strategy,
        )
    
    def is_complex(self, question: str, threshold: float = 0.6) -> bool:
        """
        Quick synchronous check if query is complex (for routing).
        
        Uses only rule-based analysis for speed.
        
        Args:
            question: Query to analyze
            threshold: Confidence threshold for complex classification
            
        Returns:
            True if query is likely complex
        """
        analysis = self._rule_based_analysis(question)
        return (
            analysis["complexity"] == QueryComplexity.COMPLEX and
            analysis["confidence"] >= threshold
        )
