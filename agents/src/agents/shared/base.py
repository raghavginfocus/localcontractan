"""
Base agent class with common functionality.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from langchain_core.language_models import BaseChatModel

from config import Settings, get_settings
from logger import get_module_logger
from logging_config import get_log_dir
from llm.provider_factory import LLMProviderFactory


class BaseAgent(ABC):
    """
    Base class for all Contract KG agents.
    
    Provides:
    - LLM initialization based on configuration
    - Common logging and error handling
    - Retry logic for API calls
    - Automatic process explanation generation
    """

    def __init__(
        self,
        settings: Settings | None = None,
        llm: BaseChatModel | None = None,
        enable_explanations: bool | None = None,
    ):
        """
        Initialize the agent.
        
        Args:
            settings: Application settings
            llm: Optional pre-configured LLM instance
            enable_explanations: Whether to auto-generate explanations (defaults to settings value)
        """
        self.settings = settings or get_settings()
        self.llm = llm or self._create_llm()
        # Use the actual subclass's module name for logging, not BaseAgent's module
        # This ensures retrieval agents log to retrieval.log, not ingestion.log
        import inspect
        subclass_module = inspect.getmodule(self.__class__).__name__ if inspect.getmodule(self.__class__) else __name__
        self.logger = get_module_logger(subclass_module).bind(
            agent=self.__class__.__name__
        )
        
        # Enable explanations (default from settings, or True if not set)
        if enable_explanations is None:
            enable_explanations = getattr(self.settings, 'enable_agent_explanations', True)
        self.enable_explanations = enable_explanations
        self.explanation_builder = None

    def _create_llm(self) -> BaseChatModel:
        """
        Create LLM instance using provider abstraction layer.
        
        This method uses the LLMProviderFactory to create the appropriate
        provider instance, which then creates the LangChain chat model.
        This abstraction allows easy swapping of LLM providers without
        modifying agent code.
        """
        try:
            # Create provider instance using factory
            provider = LLMProviderFactory.create_provider(self.settings.llm_provider)
            
            # Validate configuration
            if not provider.validate_config(self.settings):
                raise ValueError(
                    f"Invalid configuration for provider '{provider.name}'. "
                    f"Please check your settings (e.g., API keys, model names)."
                )
            
            # Create chat model with default temperature
            return provider.create_chat_model(
                settings=self.settings,
                temperature=0.1,  # Low temperature for structured extraction
            )
        except ValueError as e:
            # Re-raise ValueError (e.g., unknown provider, invalid config)
            raise
        except Exception as e:
            # Wrap other exceptions with context
            raise RuntimeError(
                f"Failed to create LLM instance for provider '{self.settings.llm_provider}': {e}"
            ) from e

    def _get_agent_type(self) -> str:
        """
        Determine agent type based on class name or module.
        
        Returns:
            Agent type: "extraction", "generation", "retrieval", "validation", "alignment", etc.
        """
        class_name = self.__class__.__name__.lower()
        
        # Map class names to types
        if "extraction" in class_name or "extract" in class_name:
            return "extraction"
        elif "generation" in class_name or "generate" in class_name or "designer" in class_name:
            return "generation"
        elif "retrieval" in class_name or "rag" in class_name or "sparql" in class_name:
            return "retrieval"
        elif "validation" in class_name or "validate" in class_name:
            return "validation"
        elif "alignment" in class_name or "align" in class_name:
            return "alignment"
        elif "reasoning" in class_name or "reason" in class_name:
            return "reasoning"
        elif "loader" in class_name or "load" in class_name:
            return "loading"
        else:
            return "general"
    
    def _init_explanation(self, context_id: str | None = None) -> None:
        """
        Initialize explanation builder if explanations are enabled.
        
        Args:
            context_id: Optional context identifier (e.g., document_id) to make session_id unique
        """
        if not self.enable_explanations:
            return
        
        try:
            from agent_explanation import AgentExplanationBuilder
            import os
            import threading
            
            # Generate unique session ID with context and process/thread info
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            process_id = os.getpid()
            thread_id = threading.get_ident()
            
            # Include context_id if provided (e.g., document_id)
            if context_id:
                session_id = f"{context_id}_{timestamp}_{process_id}_{thread_id}"
            else:
                session_id = f"{timestamp}_{process_id}_{thread_id}"
            
            self.explanation_builder = AgentExplanationBuilder(
                agent_name=self.__class__.__name__,
                agent_type=self._get_agent_type(),
                session_id=session_id,
            )
        except ImportError:
            # If explanation module not available, silently disable
            self.enable_explanations = False
            self.logger.warning("Explanation module not available, disabling explanations")
    
    def _record_input(self, input_data: Any) -> None:
        """Record input data in explanation."""
        if not self.explanation_builder:
            return
        
        try:
            # Try to get meaningful input summary
            if isinstance(input_data, dict):
                input_summary = {
                    "input_type": "dict",
                    "keys": list(input_data.keys()),
                    "size": len(input_data),
                }
                # Add preview of text if present
                if "text" in input_data:
                    input_summary["text_length"] = len(str(input_data["text"]))
                if "document_id" in input_data:
                    input_summary["document_id"] = input_data["document_id"]
            elif isinstance(input_data, str):
                input_summary = {
                    "input_type": "string",
                    "length": len(input_data),
                    "preview": input_data[:200],
                }
            else:
                input_summary = {
                    "input_type": type(input_data).__name__,
                    "preview": str(input_data)[:200],
                }
            
            size = None
            if hasattr(input_data, "__len__"):
                size = len(input_data)
            elif isinstance(input_data, dict) and "text" in input_data:
                size = len(str(input_data["text"]))
            
            self.explanation_builder.set_input(input_summary, size=size)
        except Exception as e:
            self.logger.debug("Failed to record input in explanation", error=str(e))
    
    def _record_output(self, result: Any) -> None:
        """Record output data in explanation."""
        if not self.explanation_builder:
            return
        
        try:
            # Try to get meaningful output summary
            if hasattr(result, "__dict__"):
                # Pydantic model or dataclass
                result_dict = result.__dict__ if hasattr(result, "__dict__") else {}
                output_summary = {
                    "result_type": type(result).__name__,
                    "success": getattr(result, "success", True),
                }
                
                # Try to extract counts
                count = None
                if hasattr(result, "clauses") and isinstance(result.clauses, list):
                    count = len(result.clauses)
                    output_summary["clauses_count"] = count
                elif hasattr(result, "items") and isinstance(result.items, list):
                    count = len(result.items)
                    output_summary["items_count"] = count
                elif isinstance(result, list):
                    count = len(result)
                    output_summary["items_count"] = count
                
                self.explanation_builder.set_output(output_summary, count=count)
            elif isinstance(result, dict):
                self.explanation_builder.set_output({
                    "result_type": "dict",
                    "keys": list(result.keys()),
                }, count=result.get("count") or result.get("total"))
            elif isinstance(result, list):
                self.explanation_builder.set_output({
                    "result_type": "list",
                }, count=len(result))
            else:
                self.explanation_builder.set_output({
                    "result_type": type(result).__name__,
                })
        except Exception as e:
            self.logger.debug("Failed to record output in explanation", error=str(e))
    
    def _save_explanation(self) -> None:
        """
        Explanation saving disabled - using Phoenix tracing instead.
        Phoenix captures all agent reasoning, decisions, and intermediate steps.
        """
        # Disabled for performance - Phoenix provides better observability
        pass
    
    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        """
        Process input and return results.
        
        This method should be implemented by subclasses. The base class
        automatically handles explanation generation if enabled.
        
        Args:
            input_data: Agent-specific input
            
        Returns:
            Agent-specific output
        """
        pass
    
    async def _process_with_explanation(self, input_data: Any) -> Any:
        """
        Wrapper around process() that automatically generates explanations.
        
        This is called by agents that want automatic explanation generation.
        Subclasses can override process() directly if they want manual control.
        """
        # Initialize explanation - create new one for each process call
        # This ensures each test case gets its own explanation file
        self._init_explanation()
        
        # Record input
        self._record_input(input_data)
        
        start_time = datetime.now()
        error_occurred = False
        
        try:
            # Call the actual process method (implemented by subclass)
            result = await self.process(input_data)
            
            # Record output
            self._record_output(result)
            
            # Add timing
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            if self.explanation_builder:
                self.explanation_builder.add_metadata("duration_ms", duration_ms)
            
            # Save explanation after each process call
            if self.explanation_builder:
                self._save_explanation()
            
            return result
            
        except Exception as e:
            error_occurred = True
            if self.explanation_builder:
                self.explanation_builder.add_error(str(e))
                self.explanation_builder.add_metadata("error_occurred", True)
                # Save explanation even on error
                self._save_explanation()
            
            # Re-raise the exception
            raise
            
        finally:
            # Always save explanation if enabled
            if self.enable_explanations:
                self._save_explanation()

    def log_start(self, operation: str, **kwargs: Any) -> None:
        """Log the start of an operation."""
        # Single log with all details
        self.logger.info(f"Starting {operation}", **kwargs)
        
        # Auto-initialize explanation if this is the main process() call
        if operation in ["process", "clause_extraction", "entity_extraction", "rdf_generation",
                         "rag_processing", "sparql_generation"] and self.enable_explanations:
            if not self.explanation_builder:
                self._init_explanation()
            if self.explanation_builder:
                # Record operation start
                self.explanation_builder.add_metadata("operation", operation)
                self.explanation_builder.add_metadata("operation_kwargs", kwargs)

    def log_complete(self, operation: str, **kwargs: Any) -> None:
        """Log the completion of an operation."""
        # Single log with all details
        self.logger.info(f"Completed {operation}", **kwargs)
        
        # Auto-record completion in explanation
        if self.explanation_builder and operation in ["process", "clause_extraction", "entity_extraction", 
                                                      "rdf_generation", "rag_processing", "sparql_generation"]:
            # Update output with completion info
            if "clause_count" in kwargs:
                self.explanation_builder.set_output({"clauses_extracted": kwargs["clause_count"]}, 
                                                   count=kwargs["clause_count"])
            elif "entity_count" in kwargs:
                self.explanation_builder.set_output({"entities_extracted": kwargs["entity_count"]}, 
                                                   count=kwargs["entity_count"])
            # Save explanation when operation completes
            self._save_explanation()

    def log_error(self, operation: str, error: Exception, **kwargs: Any) -> None:
        """Log an error during an operation."""
        self.logger.error(f"Error in {operation}", error=str(error), **kwargs)
        self.logger.error(f"ERROR in {operation}", error=str(error))
        
        # Auto-record error in explanation
        if self.explanation_builder:
            self.explanation_builder.add_error(str(error))
            self._save_explanation()
    
    def log_progress(self, message: str) -> None:
        """Log progress update (useful for long-running operations)."""
        self.logger.info(message)