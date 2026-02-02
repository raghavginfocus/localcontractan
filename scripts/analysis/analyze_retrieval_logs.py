#!/usr/bin/env python3
"""
Analyze Retrieval Pipeline Logs

Parses retrieval.log and generates a comprehensive summary report of each RAG session.

Usage:
    cd agents
    PYTHONPATH=src uv run python ../scripts/analyze_retrieval_logs.py
    PYTHONPATH=src uv run python ../scripts/analyze_retrieval_logs.py --output report.md
    PYTHONPATH=src uv run python ../scripts/analyze_retrieval_logs.py --last 10  # Last 10 sessions
"""

import argparse
import re
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class StepMetrics:
    """Metrics for a single retrieval step."""
    name: str = ""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalSession:
    """Represents a complete RAG retrieval session."""
    session_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    question: str = ""
    answer: str = ""
    confidence: float = 0.0
    total_duration_ms: float = 0.0
    steps: dict[str, StepMetrics] = field(default_factory=dict)
    kg_facts_count: int = 0
    vector_results_count: int = 0
    sparql_query: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "completed"  # completed, failed, in_progress


class RetrievalLogAnalyzer:
    """Analyzes retrieval pipeline logs."""
    
    # Step patterns for retrieval pipeline
    STEP_PATTERNS = {
        "rag_processing": r"Starting rag_processing|Completed rag_processing|RAG session started|RAG session completed",
        "sparql_generation": r"Starting sparql_generation|Completed sparql_generation|SPARQL query generated",
        "sparql_execution": r"SPARQL SELECT executed|Completed sparql_execution",
        "kg_retrieval": r"Step completed: kg_retrieval|KG retrieval successful|SPARQL query generated for KG retrieval",
        "vector_retrieval": r"Step completed: vector_retrieval|Vector retrieval|search\(query=",
        "answer_generation": r"Step completed: answer_generation|Generated answer",
    }
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.sessions: list[RetrievalSession] = []
    
    def parse(self) -> list[RetrievalSession]:
        """Parse the log file and extract retrieval sessions."""
        if not self.log_file.exists():
            print(f"❌ Log file not found: {self.log_file}")
            return []
        
        # First, load all session JSON files for complete data
        sessions_dir = self.log_file.parent / "sessions"
        session_files = {}
        if sessions_dir.exists():
            for json_file in sessions_dir.glob("*.json"):
                try:
                    with open(json_file, "r") as f:
                        session_data = json.load(f)
                        session_id = session_data.get("session_id", json_file.stem)
                        session_files[session_id] = session_data
                except:
                    pass
        
        # Also check evaluation sessions directory
        eval_sessions_dir = self.log_file.parent.parent / "evaluation" / "sessions"
        if eval_sessions_dir.exists():
            for json_file in eval_sessions_dir.glob("*.json"):
                try:
                    with open(json_file, "r") as f:
                        session_data = json.load(f)
                        session_id = session_data.get("session_id", json_file.stem)
                        session_files[session_id] = session_data
                except:
                    pass
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        current_session: RetrievalSession | None = None
        current_step: StepMetrics | None = None
        
        for line in lines:
            # Parse log line: timestamp | level | module | message
            match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| [^|]+\| (.+)", line)
            if not match:
                continue
            
            timestamp, level, message = match.groups()
            
            # Detect session start
            if "RAG session started" in message:
                if current_session:
                    self._finalize_session(current_session)
                
                # Extract question from message
                question_match = re.search(r"Question: (.+)", message)
                question = question_match.group(1) if question_match else ""
                
                # Extract session ID if available
                session_id_match = re.search(r"session_id=([\w_]+)", message)
                session_id = session_id_match.group(1) if session_id_match else f"session_{len(self.sessions) + 1}"
                
                current_session = RetrievalSession(
                    session_id=session_id,
                    started_at=timestamp,
                    question=question
                )
                current_step = None
            
            if not current_session:
                continue
            
            # Detect session completion
            if "RAG session completed" in message:
                current_session.completed_at = timestamp
                current_session.status = "completed"
                self._finalize_session(current_session)
                current_session = None
                current_step = None
                continue
            
            # Extract final answer (full answer, not truncated)
            if "Final answer:" in message:
                # Get the full answer from the message (it might be split across lines)
                answer_match = re.search(r"Final answer: (.+)", message, re.DOTALL)
                if answer_match:
                    # If answer is truncated in log, we'll get full version from JSON later
                    current_session.answer = answer_match.group(1).strip()
            
            # Extract confidence
            if "Confidence:" in message:
                conf_match = re.search(r"Confidence: ([\d.]+)%", message)
                if conf_match:
                    current_session.confidence = float(conf_match.group(1)) / 100.0
            
            # Extract duration
            if "Duration:" in message:
                dur_match = re.search(r"Duration: ([\d.]+)ms", message)
                if dur_match:
                    current_session.total_duration_ms = float(dur_match.group(1))
            
            # Process steps
            self._process_step_message(current_session, timestamp, level, message)
            
            # Extract metrics
            self._extract_metrics(current_session, message, level)
        
        # Finalize last session if exists
        if current_session:
            self._finalize_session(current_session)
        
        return self.sessions
    
    def _process_step_message(self, session: RetrievalSession, timestamp: str, level: str, message: str):
        """Process step-related messages."""
        step_name = None
        
        # Identify step from message
        for step, pattern in self.STEP_PATTERNS.items():
            if re.search(pattern, message, re.IGNORECASE):
                step_name = step
                break
        
        if not step_name:
            return
        
        if step_name not in session.steps:
            session.steps[step_name] = StepMetrics(name=step_name)
        
        step = session.steps[step_name]
        
        # Step start
        if "Starting" in message:
            step.started_at = timestamp
        
        # Step completion
        if "Completed" in message or "completed:" in message.lower():
            step.completed_at = timestamp
            if step.started_at:
                try:
                    start = datetime.strptime(step.started_at, "%Y-%m-%d %H:%M:%S")
                    end = datetime.strptime(step.completed_at, "%Y-%m-%d %H:%M:%S")
                    step.duration_ms = (end - start).total_seconds() * 1000
                except:
                    pass
        
        # Errors
        if level == "ERROR":
            step.success = False
            if message not in session.errors:
                step.error = message
                session.errors.append(f"{step_name}: {message}")
        
        # Warnings
        if level == "WARNING":
            if message not in step.warnings:
                step.warnings.append(message)
                session.warnings.append(f"{step_name}: {message}")
    
    def _extract_metrics(self, session: RetrievalSession, message: str, level: str):
        """Extract metrics from log messages."""
        # KG facts count
        match = re.search(r"kg_facts_count[=:] (\d+)", message)
        if match:
            session.kg_facts_count = int(match.group(1))
        
        match = re.search(r"KG Facts: (\d+)", message)
        if match:
            session.kg_facts_count = int(match.group(1))
        
        # Vector results count
        match = re.search(r"vector_context_count[=:] (\d+)", message)
        if match:
            session.vector_results_count = int(match.group(1))
        
        match = re.search(r"Vector Results: (\d+)", message)
        if match:
            session.vector_results_count = int(match.group(1))
        
        # SPARQL query (extract from message if available)
        if "SPARQL query generated" in message or "query=" in message:
            # Try to extract query from structured log format
            query_match = re.search(r'query[=:]([^,}\s]+)', message)
            if query_match:
                session.sparql_query = query_match.group(1)
    
    def _finalize_session(self, session: RetrievalSession):
        """Finalize a retrieval session and calculate total duration."""
        if session.started_at and session.completed_at:
            try:
                start = datetime.strptime(session.started_at, "%Y-%m-%d %H:%M:%S")
                end = datetime.strptime(session.completed_at, "%Y-%m-%d %H:%M:%S")
                session.total_duration_ms = (end - start).total_seconds() * 1000
            except:
                pass
        
        # Try to enrich with session JSON data if available
        # Check both retrieval/sessions and evaluation/sessions directories
        sessions_dirs = [
            self.log_file.parent / "sessions",
            self.log_file.parent.parent / "evaluation" / "sessions"
        ]
        
        for sessions_dir in sessions_dirs:
            if not sessions_dir.exists():
                continue
                
            for json_file in sessions_dir.glob("*.json"):
                try:
                    with open(json_file, "r") as f:
                        session_data = json.load(f)
                        json_session_id = session_data.get("session_id", json_file.stem)
                        
                        # Match by session_id or by question similarity
                        question_match = session_data.get("question", "").strip() == session.question.strip()
                        id_match = json_session_id == session.session_id or json_file.stem == session.session_id
                        
                        if id_match or (question_match and session.question):
                            # Enrich with JSON data - always use JSON data as it's more complete
                            if session_data.get("final_answer"):
                                session.answer = session_data["final_answer"]  # Full answer from JSON
                            if session_data.get("final_confidence") is not None:
                                session.confidence = session_data["final_confidence"]
                            if session_data.get("total_duration_ms"):
                                session.total_duration_ms = session_data["total_duration_ms"]
                            if session_data.get("status"):
                                session.status = session_data["status"]
                            
                            # Extract step data from JSON
                            for step_data in session_data.get("steps", []):
                                step_name = step_data.get("step_name", "")
                                if step_name:
                                    if step_name not in session.steps:
                                        session.steps[step_name] = StepMetrics(name=step_name)
                                    step = session.steps[step_name]
                                    if step_data.get("timestamp"):
                                        step.started_at = step_data["timestamp"]
                                    if step_data.get("duration_ms"):
                                        step.duration_ms = step_data["duration_ms"]
                                    if step_data.get("status"):
                                        step.success = step_data["status"] == "success"
                                    if step_data.get("error_message"):
                                        step.error = step_data["error_message"]
                                    
                                    # Extract metrics from output_data
                                    if step_data.get("output_data"):
                                        output = step_data["output_data"]
                                        if isinstance(output, dict):
                                            # KG retrieval step
                                            if "facts_count" in output:
                                                session.kg_facts_count = output["facts_count"]
                                            if "facts" in output and isinstance(output["facts"], list):
                                                session.kg_facts_count = len(output["facts"])
                                            # Vector retrieval step
                                            if "context_count" in output:
                                                session.vector_results_count = output["context_count"]
                                            if "contexts" in output and isinstance(output["contexts"], list):
                                                session.vector_results_count = len(output["contexts"])
                                            # SPARQL query
                                            if "sparql_query" in output and output["sparql_query"]:
                                                session.sparql_query = output["sparql_query"]
                            
                            # Also check for SPARQL query in kg_retrieval step output
                            kg_step = session.steps.get("kg_retrieval")
                            if kg_step and kg_step.metrics.get("sparql_query"):
                                session.sparql_query = kg_step.metrics["sparql_query"]
                            
                            break
                except Exception as e:
                    # Silently continue if JSON parsing fails
                    pass
        
        self.sessions.append(session)
    
    def generate_report(self, output_file: Path | None = None, last_n: int | None = None) -> str:
        """Generate a markdown report."""
        sessions = self.sessions
        if last_n:
            sessions = sessions[-last_n:]
        
        if not sessions:
            return "# Retrieval Pipeline Analysis\n\nNo retrieval sessions found in logs.\n"
        
        report = []
        report.append("# Retrieval Pipeline Analysis Report\n")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"Total Sessions Analyzed: {len(sessions)}\n")
        report.append(f"Log File: {self.log_file}\n\n")
        report.append("---\n\n")
        
        # Summary statistics
        report.append("## Summary Statistics\n\n")
        total_sessions = len(sessions)
        successful_sessions = sum(1 for s in sessions if s.status == "completed" and not s.errors)
        total_duration = sum(s.total_duration_ms for s in sessions) / 1000.0  # Convert to seconds
        avg_confidence = sum(s.confidence for s in sessions) / total_sessions if total_sessions > 0 else 0
        total_kg_facts = sum(s.kg_facts_count for s in sessions)
        total_vector_results = sum(s.vector_results_count for s in sessions)
        total_questions = len(set(s.question for s in sessions))
        
        report.append(f"- **Total Sessions**: {total_sessions}\n")
        report.append(f"- **Successful Sessions**: {successful_sessions} ({successful_sessions/total_sessions*100:.1f}%)\n")
        report.append(f"- **Total Duration**: {total_duration:.1f}s ({total_duration/60:.1f} minutes)\n")
        report.append(f"- **Average Duration per Session**: {total_duration/total_sessions:.1f}s\n")
        report.append(f"- **Average Confidence**: {avg_confidence:.1%}\n")
        report.append(f"- **Total KG Facts Retrieved**: {total_kg_facts}\n")
        report.append(f"- **Total Vector Results Retrieved**: {total_vector_results}\n")
        report.append(f"- **Unique Questions**: {total_questions}\n\n")
        report.append("---\n\n")
        
        # Individual sessions
        for i, session in enumerate(reversed(sessions), 1):
            report.append(f"## Session #{i}: {session.session_id}\n\n")
            
            # Basic info
            report.append(f"**Started**: {session.started_at}\n")
            report.append(f"**Completed**: {session.completed_at or 'Incomplete'}\n")
            report.append(f"**Duration**: {session.total_duration_ms/1000:.1f}s ({session.total_duration_ms/60000:.1f} min)\n")
            report.append(f"**Status**: {'✅ Success' if session.status == 'completed' and not session.errors else '❌ Failed'}\n\n")
            
            # Question
            report.append("### Question\n\n")
            report.append(f"{session.question}\n\n")
            
            # Answer (full answer, not truncated)
            if session.answer:
                report.append("### Answer\n\n")
                report.append(f"{session.answer}\n\n")
            
            # Metrics summary
            report.append("### Metrics Summary\n\n")
            report.append(f"- **Confidence**: {session.confidence:.1%}\n")
            report.append(f"- **KG Facts**: {session.kg_facts_count}\n")
            report.append(f"- **Vector Results**: {session.vector_results_count}\n")
            if session.sparql_query:
                report.append(f"- **SPARQL Query**: `{session.sparql_query[:500]}...`\n" if len(session.sparql_query) > 500 else f"- **SPARQL Query**: `{session.sparql_query}`\n")
            report.append("\n")
            
            # Steps timeline
            report.append("### Processing Steps\n\n")
            step_order = [
                "rag_processing", "sparql_generation", "sparql_execution",
                "kg_retrieval", "vector_retrieval", "answer_generation"
            ]
            
            for step_name in step_order:
                if step_name in session.steps:
                    step = session.steps[step_name]
                    status = "✅" if step.success else "❌"
                    duration = f"{step.duration_ms/1000:.1f}s" if step.duration_ms else "N/A"
                    report.append(f"- {status} **{step_name.replace('_', ' ').title()}**: {duration}\n")
                    if step.warnings:
                        for warning in step.warnings[:3]:
                            report.append(f"  - ⚠️ {warning}\n")
                    if step.error:
                        report.append(f"  - ❌ Error: {step.error}\n")
            
            report.append("\n")
            
            # Errors and warnings
            if session.errors:
                report.append("### Errors\n\n")
                for error in session.errors[:5]:
                    report.append(f"- ❌ {error}\n")
                if len(session.errors) > 5:
                    report.append(f"- ... and {len(session.errors) - 5} more errors\n")
                report.append("\n")
            
            if session.warnings:
                report.append("### Warnings\n\n")
                for warning in session.warnings[:10]:
                    report.append(f"- ⚠️ {warning}\n")
                if len(session.warnings) > 10:
                    report.append(f"- ... and {len(session.warnings) - 10} more warnings\n")
                report.append("\n")
            
            report.append("---\n\n")
        
        report_text = "".join(report)
        
        if output_file:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report_text)
            print(f"✅ Report saved to: {output_file}")
        
        return report_text


def main():
    parser = argparse.ArgumentParser(description="Analyze retrieval pipeline logs")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("agents/logs/retrieval/retrieval.log"),
        help="Path to retrieval log file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path (default: print to stdout)"
    )
    parser.add_argument(
        "--last",
        type=int,
        help="Analyze only the last N sessions"
    )
    
    args = parser.parse_args()
    
    # Resolve log file path
    log_file = args.log_file
    if not log_file.is_absolute():
        log_file = Path(__file__).parent.parent / log_file
    
    analyzer = RetrievalLogAnalyzer(log_file)
    sessions = analyzer.parse()
    
    if not sessions:
        print("❌ No retrieval sessions found in logs.")
        return
    
    print(f"✅ Found {len(sessions)} retrieval session(s)")
    
    report = analyzer.generate_report(output_file=args.output, last_n=args.last)
    
    if not args.output:
        print("\n" + "=" * 70)
        print(report)


if __name__ == "__main__":
    main()
