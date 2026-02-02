"""
Comprehensive logging utilities for Contract KG RAG system.

Provides detailed logging of all agent inputs, outputs, and intermediate
steps for transparency, evaluation, and debugging.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict

from logger import get_module_logger

logger = get_module_logger(__name__)


@dataclass
class StepLog:
    """Represents a single processing step."""
    step_name: str
    timestamp: str
    input_data: Any
    output_data: Any = None
    duration_ms: float = 0.0
    status: str = "pending"  # pending, success, error
    error_message: str = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SessionLog:
    """Represents a complete RAG session with all steps."""
    session_id: str
    started_at: str
    question: str
    steps: list[StepLog] = field(default_factory=list)
    final_answer: str = None
    final_confidence: float = 0.0
    total_duration_ms: float = 0.0
    status: str = "in_progress"  # in_progress, completed, failed
    stdout_messages: list[str] = field(default_factory=list)
    
    # Answer quality evaluation metrics
    evaluation_metrics: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "question": self.question,
            "steps": [asdict(s) for s in self.steps],
            "final_answer": self.final_answer,
            "final_confidence": self.final_confidence,
            "total_duration_ms": self.total_duration_ms,
            "status": self.status,
            "stdout_messages": self.stdout_messages,
        }
        
        # Include evaluation metrics if present
        if self.evaluation_metrics:
            result["evaluation_metrics"] = self.evaluation_metrics
        
        return result


class RAGLogger:
    """
    Centralized logger for RAG pipeline operations.
    
    Logs all inputs/outputs to structured files for:
    - Debugging issues
    - Evaluating answer quality
    - Understanding system behavior
    - Audit trails
    """
    
    def __init__(self, log_dir: str | None = None):
        """
        Initialize the RAG logger.
        
        Args:
            log_dir: Directory to store log files (defaults to centralized logs/retrieval)
        """
        if log_dir is None:
            from logging_config import get_module_log_dir
            log_dir = str(get_module_log_dir("retrieval"))
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.log_dir / "sessions").mkdir(exist_ok=True)
        
        self.current_session: SessionLog = None
        self._step_start_time: float = None
        self._original_stdout = None
        
    def log_message(self, message: str) -> None:
        """
        Log a message to the current session (for capturing stdout/print statements).
        
        Args:
            message: Message to log
        """
        if self.current_session:
            self.current_session.stdout_messages.append(f"[{datetime.now().isoformat()}] {message}")
        # Also log to structured logger (message is positional, not keyword)
        logger.info(f"Session message: {message}")
    
    def start_session(self, question: str) -> str:
        """
        Start a new logging session.
        
        Args:
            question: The user's question
            
        Returns:
            Session ID
        """
        import time
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        self.current_session = SessionLog(
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            question=question,
        )
        self._session_start_time = time.time()
        
        logger.info("RAG session started", session_id=session_id, question=str(question)[:100])
        self.log_message(f"RAG session started - Question: {question}")
        return session_id
    
    def log_step_start(self, step_name: str, input_data: Any, metadata: dict = None) -> None:
        """
        Log the start of a processing step.
        
        Args:
            step_name: Name of the step (e.g., "sparql_generation", "vector_search")
            input_data: Input to this step
            metadata: Additional metadata
        """
        import time
        self._step_start_time = time.time()
        
        step = StepLog(
            step_name=step_name,
            timestamp=datetime.now().isoformat(),
            input_data=self._serialize(input_data),
            metadata=metadata or {},
        )
        
        if self.current_session:
            self.current_session.steps.append(step)
        
        logger.debug(f"Step started: {step_name}", input_preview=str(input_data))
    
    def log_step_end(
        self,
        step_name: str,
        output_data: Any,
        status: str = "success",
        error_message: str = None,
    ) -> None:
        """
        Log the end of a processing step.
        
        Args:
            step_name: Name of the step
            output_data: Output from this step
            status: "success" or "error"
            error_message: Error message if status is "error"
        """
        import time
        duration_ms = (time.time() - self._step_start_time) * 1000 if self._step_start_time else 0
        
        if self.current_session and self.current_session.steps:
            # Find the matching step
            for step in reversed(self.current_session.steps):
                if step.step_name == step_name and step.status == "pending":
                    step.output_data = self._serialize(output_data)
                    step.duration_ms = duration_ms
                    step.status = status
                    step.error_message = error_message
                    break
        
        log_method = logger.info if status == "success" else logger.error
        log_method(
            f"Step completed: {step_name}",
            status=status,
            duration_ms=round(duration_ms, 2),
            output_preview=str(output_data) if output_data else None,
        )
    
    def end_session(
        self,
        final_answer: str,
        confidence: float,
        status: str = "completed",
        evaluation_metrics: dict = None,
    ) -> str:
        """
        End the current session and save logs.
        
        Args:
            final_answer: The generated answer
            confidence: Confidence score
            status: "completed" or "failed"
            evaluation_metrics: Answer quality evaluation metrics
            
        Returns:
            Path to the log file
        """
        import time
        
        if not self.current_session:
            return None
        
        total_duration = (time.time() - self._session_start_time) * 1000
        
        self.current_session.final_answer = final_answer
        self.current_session.final_confidence = confidence
        self.current_session.total_duration_ms = total_duration
        self.current_session.status = status
        
        # Store evaluation metrics if provided
        if evaluation_metrics:
            self.current_session.evaluation_metrics = evaluation_metrics
        
        # Log final answer (full answer, not truncated)
        self.log_message(f"Final answer: {final_answer}")
        self.log_message(f"Confidence: {confidence:.1%}, Duration: {total_duration:.0f}ms")
        
        # Session JSON logging disabled - using Phoenix tracing instead
        log_file = None
        
        logger.info(
            "RAG session completed",
            session_id=self.current_session.session_id,
            status=status,
            confidence=confidence,
            duration_ms=round(total_duration, 2),
            log_file=str(log_file),
        )
        
        session_id = self.current_session.session_id
        self.current_session = None
        
        return str(log_file)
    
    def _serialize(self, data: Any) -> Any:
        """Serialize data for JSON storage."""
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, (list, tuple)):
            return [self._serialize(item) for item in data]
        if isinstance(data, dict):
            return {k: self._serialize(v) for k, v in data.items()}
        # For objects, try to get dict representation
        if hasattr(data, '__dict__'):
            return self._serialize(vars(data))
        return str(data)
    
    def get_session_log(self, session_id: str) -> dict | None:
        """
        Load a session log by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session log dict or None
        """
        log_file = self.log_dir / "sessions" / f"{session_id}.json"
        if log_file.exists():
            with open(log_file) as f:
                return json.load(f)
        return None
    
    def list_sessions(self, limit: int = 20) -> list[dict]:
        """
        List recent sessions.
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of session summaries
        """
        sessions_dir = self.log_dir / "sessions"
        files = sorted(sessions_dir.glob("*.json"), reverse=True)[:limit]
        
        summaries = []
        for f in files:
            try:
                with open(f) as fp:
                    data = json.load(fp)
                    summaries.append({
                        "session_id": data.get("session_id"),
                        "question": data.get("question", "")[:80],
                        "status": data.get("status"),
                        "confidence": data.get("final_confidence"),
                        "duration_ms": data.get("total_duration_ms"),
                    })
            except Exception:
                pass
        
        return summaries


# Global logger instance
_rag_logger: RAGLogger = None


def get_rag_logger(log_dir: str | None = None) -> RAGLogger:
    """Get or create the global RAG logger."""
    global _rag_logger
    if _rag_logger is None:
        _rag_logger = RAGLogger(log_dir)
    return _rag_logger
