"""
Phoenix Tracing Setup

Properly configures Phoenix observability with OpenTelemetry instrumentation
for LangChain/LangGraph applications.
"""

import os
from typing import Optional
from logger import get_module_logger

logger = get_module_logger(__name__)

# Try to import Phoenix OTEL registration
try:
    from phoenix.otel import register
    PHOENIX_OTEL_AVAILABLE = True
except ImportError:
    try:
        from phoenix.trace.otel import register
        PHOENIX_OTEL_AVAILABLE = True
    except ImportError:
        PHOENIX_OTEL_AVAILABLE = False
        register = None


class PhoenixTracer:
    """Phoenix tracer wrapper."""
    
    def __init__(self, tracer_provider=None):
        """Initialize Phoenix tracer."""
        self._session = None
        self._tracer_provider = tracer_provider
    
    def start(self):
        """Start Phoenix session."""
        pass
    
    def stop(self):
        """Stop Phoenix session."""
        pass


def setup_phoenix_tracing(
    project_name: str = "contract-kg",
    enable_local_server: bool = False,
    phoenix_port: int = 6006,
    auto_start: bool = True,
) -> Optional[PhoenixTracer]:
    """
    Setup Phoenix tracing for LLM observability.
    
    This properly initializes OpenTelemetry instrumentation for LangChain/LangGraph
    to send traces to Phoenix.
    
    Args:
        project_name: Project name for trace grouping
        enable_local_server: Whether to start local Phoenix server (not needed if using Docker)
        phoenix_port: Phoenix server port
        auto_start: Whether to auto-start Phoenix session
        
    Returns:
        PhoenixTracer instance or None
    """
    if not PHOENIX_OTEL_AVAILABLE:
        logger.warning("Phoenix OTEL not available - install arize-phoenix package")
        return None
    
    try:
        # Get Phoenix endpoint from environment or use default
        phoenix_endpoint = os.getenv("PHOENIX_ENDPOINT", f"http://localhost:{phoenix_port}")
        
        # Register Phoenix with OpenTelemetry
        # This automatically instruments LangChain/LangGraph
        tracer_provider = register(
            project_name=project_name,
            auto_instrument=True,  # Auto-instrument based on installed packages
        )
        
        logger.info(f"Phoenix tracing configured (project: {project_name}, endpoint: {phoenix_endpoint})")
        logger.info("Traces will be automatically sent to Phoenix when LangChain/LangGraph is used")
        
        return PhoenixTracer(tracer_provider=tracer_provider)
        
    except Exception as e:
        logger.warning(f"Could not setup Phoenix tracing: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None
