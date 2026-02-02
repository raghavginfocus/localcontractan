"""
Agent Process Explanation System

This module provides a standardized way for agents to explain:
- What they processed
- What they extracted/generated
- Why they made certain decisions
- What was covered and what might be missing
- Limitations and gaps

All agents should produce an explanation file alongside their outputs.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class ProcessExplanation:
    """Structured explanation of an agent's process."""
    
    agent_name: str
    agent_type: str  # "extraction", "generation", "alignment", "validation", etc.
    session_id: str
    timestamp: str
    
    # What was processed
    input_summary: dict[str, Any] = field(default_factory=dict)
    input_size: Optional[int] = None  # e.g., number of documents, clauses, etc.
    
    # What was extracted/generated
    output_summary: dict[str, Any] = field(default_factory=dict)
    output_count: Optional[int] = None  # e.g., number of clauses extracted
    
    # Coverage analysis
    coverage_analysis: dict[str, Any] = field(default_factory=dict)
    items_covered: list[str] = field(default_factory=list)
    items_missed: list[str] = field(default_factory=list)
    coverage_percentage: Optional[float] = None
    
    # Decision reasoning
    decisions_made: list[dict[str, Any]] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    
    # Limitations and gaps
    limitations: list[str] = field(default_factory=list)
    gaps_identified: list[str] = field(default_factory=list)
    confidence_level: Optional[str] = None  # "high", "medium", "low"
    
    # Quality metrics
    quality_metrics: dict[str, Any] = field(default_factory=dict)
    validation_results: dict[str, Any] = field(default_factory=dict)
    
    # Files generated
    output_files: list[str] = field(default_factory=list)
    log_files: list[str] = field(default_factory=list)
    
    # Errors and warnings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Process description
    process_description: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)
    
    def save(self, file_path: Path | str) -> Path:
        """Save explanation to JSON file."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, "w") as f:
            f.write(self.to_json())
        
        return file_path


class AgentExplanationBuilder:
    """Builder for creating process explanations."""
    
    def __init__(self, agent_name: str, agent_type: str, session_id: Optional[str] = None):
        """Initialize explanation builder."""
        self.agent_name = agent_name
        self.agent_type = agent_type
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.explanation = ProcessExplanation(
            agent_name=agent_name,
            agent_type=agent_type,
            session_id=self.session_id,
            timestamp=datetime.now().isoformat(),
        )
    
    def set_input(self, summary: dict[str, Any], size: Optional[int] = None) -> "AgentExplanationBuilder":
        """Set input information."""
        self.explanation.input_summary = summary
        self.explanation.input_size = size
        return self
    
    def set_output(self, summary: dict[str, Any], count: Optional[int] = None) -> "AgentExplanationBuilder":
        """Set output information."""
        self.explanation.output_summary = summary
        self.explanation.output_count = count
        return self
    
    def add_coverage(self, item: str, covered: bool, reason: Optional[str] = None) -> "AgentExplanationBuilder":
        """Add coverage information for an item."""
        if covered:
            self.explanation.items_covered.append(item)
        else:
            self.explanation.items_missed.append(item)
            if reason:
                self.explanation.gaps_identified.append(f"{item}: {reason}")
        return self
    
    def set_coverage_analysis(
        self,
        analysis: dict[str, Any],
        percentage: Optional[float] = None
    ) -> "AgentExplanationBuilder":
        """Set coverage analysis."""
        self.explanation.coverage_analysis = analysis
        self.explanation.coverage_percentage = percentage
        return self
    
    def add_decision(
        self,
        decision: str,
        reasoning: str,
        alternatives_considered: Optional[list[str]] = None
    ) -> "AgentExplanationBuilder":
        """Add a decision made during processing."""
        self.explanation.decisions_made.append({
            "decision": decision,
            "reasoning": reasoning,
            "alternatives_considered": alternatives_considered or [],
            "timestamp": datetime.now().isoformat(),
        })
        self.explanation.reasoning.append(f"{decision}: {reasoning}")
        return self
    
    def add_reasoning(self, reasoning: str) -> "AgentExplanationBuilder":
        """Add general reasoning."""
        self.explanation.reasoning.append(reasoning)
        return self
    
    def add_limitation(self, limitation: str) -> "AgentExplanationBuilder":
        """Add a limitation."""
        self.explanation.limitations.append(limitation)
        return self
    
    def add_gap(self, gap: str, reason: Optional[str] = None) -> "AgentExplanationBuilder":
        """Add an identified gap."""
        gap_desc = f"{gap}" + (f": {reason}" if reason else "")
        self.explanation.gaps_identified.append(gap_desc)
        return self
    
    def set_confidence(self, level: str) -> "AgentExplanationBuilder":
        """Set confidence level."""
        self.explanation.confidence_level = level
        return self
    
    def add_quality_metric(self, name: str, value: Any) -> "AgentExplanationBuilder":
        """Add a quality metric."""
        self.explanation.quality_metrics[name] = value
        return self
    
    def add_validation_result(self, name: str, result: Any) -> "AgentExplanationBuilder":
        """Add a validation result."""
        self.explanation.validation_results[name] = result
        return self
    
    def add_output_file(self, file_path: str) -> "AgentExplanationBuilder":
        """Add an output file path."""
        self.explanation.output_files.append(file_path)
        return self
    
    def add_log_file(self, file_path: str) -> "AgentExplanationBuilder":
        """Add a log file path."""
        self.explanation.log_files.append(file_path)
        return self
    
    def add_error(self, error: str) -> "AgentExplanationBuilder":
        """Add an error."""
        self.explanation.errors.append(error)
        return self
    
    def add_warning(self, warning: str) -> "AgentExplanationBuilder":
        """Add a warning."""
        self.explanation.warnings.append(warning)
        return self
    
    def add_metadata(self, key: str, value: Any) -> "AgentExplanationBuilder":
        """Add metadata."""
        self.explanation.metadata[key] = value
        return self
    
    def set_process_description(self, description: str) -> "AgentExplanationBuilder":
        """Set a human-readable description of what the agent did."""
        self.explanation.process_description = description
        return self
    
    def build(self) -> ProcessExplanation:
        """Build the final explanation."""
        return self.explanation
    
    def save(
        self,
        log_dir: Path | str,
        filename_prefix: Optional[str] = None
    ) -> Path:
        """Build and save explanation to file."""
        explanation = self.build()
        
        # Generate filename
        if filename_prefix:
            filename = f"{filename_prefix}_explanation_{self.session_id}.json"
        else:
            filename = f"{self.agent_name}_explanation_{self.session_id}.json"
        
        log_dir = Path(log_dir)
        file_path = log_dir / filename
        
        return explanation.save(file_path)


def create_explanation_for_unanswered_query(
    question: str,
    kg_facts_count: int,
    vector_results_count: int,
    sparql_query: Optional[str] = None,
    errors: Optional[list[str]] = None,
) -> ProcessExplanation:
    """Create explanation for why a query couldn't be answered."""
    
    builder = AgentExplanationBuilder(
        agent_name="RAGOrchestratorAgent",
        agent_type="retrieval",
    )
    
    builder.set_input({
        "question": question,
        "query_type": "unanswered",
    })
    
    builder.set_output({
        "kg_facts_retrieved": kg_facts_count,
        "vector_results_retrieved": vector_results_count,
        "answer_generated": False,
    })
    
    # Analyze why no answer
    reasons = []
    
    if kg_facts_count == 0 and vector_results_count == 0:
        reasons.append("No relevant data found in knowledge graph or vector database")
        builder.add_gap("Data availability", "No matching data for the query")
    elif kg_facts_count == 0:
        reasons.append("No structured data found in knowledge graph (relied on vector search only)")
        builder.add_gap("Structured KG data", "Query requires structured properties that don't exist")
    elif vector_results_count == 0:
        reasons.append("No semantic matches found in vector database (relied on KG only)")
        builder.add_gap("Semantic context", "No semantically similar content found")
    
    if sparql_query:
        builder.add_metadata("sparql_query", sparql_query)
        if "error" in (sparql_query.lower() if sparql_query else ""):
            reasons.append("SPARQL query generation or execution failed")
            builder.add_error("SPARQL query error")
    
    if errors:
        for error in errors:
            reasons.append(f"Error: {error}")
            builder.add_error(error)
    
    # Check if question is relevant to available data
    if kg_facts_count == 0 and vector_results_count == 0:
        builder.add_decision(
            "Cannot answer query",
            "No relevant data exists in the system for this question. The question may be: "
            "1) Outside the scope of ingested documents, 2) Asking about concepts not present in contracts, "
            "3) Using terminology that doesn't match the knowledge graph schema",
            alternatives_considered=["Vector search", "KG query", "Hybrid retrieval"]
        )
        builder.set_confidence("low")
    else:
        builder.add_decision(
            "Partial data available but insufficient for complete answer",
            f"Found {kg_facts_count} KG facts and {vector_results_count} vector results, but they don't contain "
            "enough information to answer the question completely",
        )
        builder.set_confidence("medium")
    
    builder.add_reasoning("; ".join(reasons))
    
    return builder.build()
