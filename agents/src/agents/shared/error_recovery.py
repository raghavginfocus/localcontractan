"""
Error Recovery Agent - Self-healing mechanism for ingestion pipeline
failures.

This agent analyzes errors, diagnoses root causes, and attempts automatic
recovery with LLM-powered debugging and fix generation.
"""

from typing import Any, Dict, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass, field
import time
import inspect

try:
    from pydantic import ValidationError
except ImportError:
    ValidationError = Exception  # Fallback if pydantic not available

from .base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class ErrorType(str, Enum):
    """Types of errors that can be recovered."""
    VALIDATION_ERROR = "validation_error"
    EMPTY_INPUT = "empty_input"
    LLM_OUTPUT_ERROR = "llm_output_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN = "unknown"


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""
    attempt_number: int
    error_type: ErrorType
    error_message: str
    diagnosis: Optional[str] = None
    fix_strategy: Optional[str] = None
    success: bool = False
    duration_ms: float = 0.0


@dataclass
class RecoveryResult:
    """Result of error recovery process."""
    success: bool
    result: Any = None
    attempts: List[RecoveryAttempt] = field(default_factory=list)
    final_error: Optional[str] = None


class ErrorRecoveryAgent(BaseAgent):
    """
    Agent that attempts to recover from errors in the ingestion pipeline.

    Features:
    - Automatic error classification
    - LLM-powered diagnosis
    - Retry with exponential backoff
    - Fix strategy generation
    - Learning from failures
    """

    def __init__(
        self, max_retries: int = 3, backoff_factor: float = 2.0
    ):
        """
        Initialize error recovery agent.
        
        Args:
            max_retries: Maximum number of recovery attempts
            backoff_factor: Multiplier for exponential backoff (seconds)
        """
        super().__init__()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
    
    async def process(
        self, input_data: Dict[str, Any]
    ) -> RecoveryResult:
        """
        Attempt to recover from an error.

        Args:
            input_data: Dict containing:
                - operation: Callable to retry
                - args: Arguments for operation
                - kwargs: Keyword arguments for operation
                - error: Original error
                - context: Additional context

        Returns:
            RecoveryResult with success status and result
        """
        operation = input_data.get("operation")
        args = input_data.get("args", ())
        kwargs = input_data.get("kwargs", {})
        original_error: Optional[Exception] = input_data.get("error")
        context = input_data.get("context", {})

        if not operation or not original_error:
            return RecoveryResult(
                success=False,
                final_error="Missing operation or error in input"
            )
        
        attempts = []
        
        for attempt_num in range(1, self.max_retries + 1):
            logger.info(f"Recovery attempt {attempt_num}/{self.max_retries}")
            
            start_time = time.time()
            
            # Classify error
            error_type = self._classify_error(original_error)
            
            # Create recovery attempt record
            attempt = RecoveryAttempt(
                attempt_number=attempt_num,
                error_type=error_type,
                error_message=str(original_error)
            )
            
            try:
                # Diagnose and generate fix strategy
                diagnosis = await self._diagnose_error(
                    original_error, error_type, context
                )
                attempt.diagnosis = diagnosis.get("root_cause")
                attempt.fix_strategy = diagnosis.get("fix_strategy")
                
                logger.info(f"Diagnosis: {attempt.diagnosis}")
                logger.info(f"Fix strategy: {attempt.fix_strategy}")
                
                # Apply fixes to kwargs
                modified_kwargs = self._apply_fixes(
                    kwargs, diagnosis, error_type
                )
                
                # Retry operation with fixes
                result = await self._retry_operation(
                    operation, args, modified_kwargs
                )
                
                # Success!
                attempt.success = True
                attempt.duration_ms = (time.time() - start_time) * 1000
                attempts.append(attempt)

                logger.info(
                    f"✓ Recovery successful on attempt {attempt_num}"
                )
                return RecoveryResult(
                    success=True, result=result, attempts=attempts
                )
                
            except Exception as e:
                # Recovery attempt failed
                attempt.success = False
                attempt.duration_ms = (time.time() - start_time) * 1000
                attempts.append(attempt)

                logger.warning(
                    f"✗ Recovery attempt {attempt_num} failed: {e}"
                )

                # Update error for next attempt
                original_error = e

                # Exponential backoff before next attempt
                if attempt_num < self.max_retries:
                    backoff_time = self.backoff_factor ** attempt_num
                    logger.info(
                        f"Waiting {backoff_time}s before next attempt..."
                    )
                    time.sleep(backoff_time)
        
        # All attempts failed
        logger.error(
            f"✗ All {self.max_retries} recovery attempts failed"
        )
        return RecoveryResult(
            success=False,
            attempts=attempts,
            final_error=str(original_error) if original_error else "Unknown"
        )
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """Classify the type of error."""
        if isinstance(error, ValidationError):
            return ErrorType.VALIDATION_ERROR
        
        error_str = str(error).lower()
        
        if "empty" in error_str or "no clauses" in error_str:
            return ErrorType.EMPTY_INPUT
        elif "invalid json" in error_str or "output parsing" in error_str:
            return ErrorType.LLM_OUTPUT_ERROR
        elif "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        else:
            return ErrorType.UNKNOWN
    
    async def _diagnose_error(
        self,
        error: Exception,
        error_type: ErrorType,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Use LLM to diagnose error and suggest fix.

        Args:
            error: The exception
            error_type: Classified error type
            context: Additional context

        Returns:
            Dict with root_cause and fix_strategy
        """
        # For now, use rule-based diagnosis
        # TODO: Implement LLM-powered diagnosis
        
        if error_type == ErrorType.VALIDATION_ERROR:
            return {
                "root_cause": (
                    "Pydantic validation failed - field type mismatch"
                ),
                "fix_strategy": (
                    "Add default values or make fields optional"
                )
            }
        elif error_type == ErrorType.EMPTY_INPUT:
            return {
                "root_cause": "No input data provided to agent",
                "fix_strategy": "Skip processing or use default values"
            }
        elif error_type == ErrorType.LLM_OUTPUT_ERROR:
            return {
                "root_cause": "LLM returned invalid JSON format",
                "fix_strategy": (
                    "Retry with stricter prompt or fallback parsing"
                )
            }
        else:
            return {
                "root_cause": "Unknown error type",
                "fix_strategy": "Retry with same parameters"
            }
    
    def _apply_fixes(
        self,
        kwargs: Dict[str, Any],
        diagnosis: Dict[str, str],
        error_type: ErrorType
    ) -> Dict[str, Any]:
        """
        Apply fixes to operation kwargs based on diagnosis.

        Args:
            kwargs: Original kwargs
            diagnosis: Diagnosis from LLM
            error_type: Type of error

        Returns:
            Modified kwargs with fixes applied
        """
        modified = kwargs.copy()
        
        # Apply type-specific fixes
        if error_type == ErrorType.EMPTY_INPUT:
            # Add flag to handle empty input gracefully
            modified["allow_empty"] = True
        elif error_type == ErrorType.LLM_OUTPUT_ERROR:
            # Increase temperature for more creative output
            if "temperature" in modified:
                modified["temperature"] = min(
                    modified["temperature"] + 0.1, 1.0
                )

        return modified
    
    async def _retry_operation(
        self,
        operation: Callable,
        args: tuple,
        kwargs: Dict[str, Any]
    ) -> Any:
        """
        Retry the operation with modified parameters.

        Args:
            operation: Function to retry
            args: Positional arguments
            kwargs: Keyword arguments (possibly modified)

        Returns:
            Result of operation
        """
        # Check if operation is async
        if inspect.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)


def with_error_recovery(max_retries: int = 3):
    """
    Decorator to add error recovery to any function.

    Usage:
        @with_error_recovery(max_retries=3)
        async def extract_entities(text: str):
            # ... extraction logic
            pass
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            recovery_agent = ErrorRecoveryAgent(max_retries=max_retries)

            try:
                # Try original operation
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                # Attempt recovery
                logger.warning(
                    f"Error in {func.__name__}: {e}. "
                    f"Attempting recovery..."
                )

                recovery_result = await recovery_agent.process({
                    "operation": func,
                    "args": args,
                    "kwargs": kwargs,
                    "error": e,
                    "context": {"function_name": func.__name__}
                })

                if recovery_result.success:
                    return recovery_result.result
                else:
                    # Re-raise original error if recovery failed
                    raise e

        return wrapper
    return decorator