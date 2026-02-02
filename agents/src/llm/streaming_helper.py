"""
LLM Streaming Helper - Utilities for streaming LLM responses.

Provides streaming support for LLM calls to improve perceived performance
and enable real-time response display.
"""

from typing import AsyncIterator, Any, Optional
from langchain_core.runnables import Runnable
from langchain_core.messages import BaseMessage
from logger import get_module_logger

logger = get_module_logger(__name__)


async def stream_llm_response(
    chain: Runnable,
    input_data: dict[str, Any],
    callback: Optional[callable] = None,
) -> AsyncIterator[str]:
    """
    Stream LLM response chunks as they arrive.
    
    Args:
        chain: LangChain runnable chain (prompt | llm | parser)
        input_data: Input dictionary for the chain
        callback: Optional callback function called for each chunk
        
    Yields:
        String chunks of the LLM response
        
    Example:
        async for chunk in stream_llm_response(chain, {"question": "What is..."}):
            print(chunk, end="", flush=True)
    """
    try:
        # Use astream for streaming support
        async for chunk in chain.astream(input_data):
            # Handle different chunk types
            if isinstance(chunk, str):
                text = chunk
            elif isinstance(chunk, BaseMessage):
                text = chunk.content
            elif hasattr(chunk, 'content'):
                text = chunk.content
            else:
                text = str(chunk)
            
            # Call callback if provided
            if callback:
                try:
                    callback(text)
                except Exception as e:
                    logger.warning("Callback failed", error=str(e))
            
            yield text
            
    except Exception as e:
        logger.error("Streaming failed", error=str(e))
        raise


async def stream_and_collect(
    chain: Runnable,
    input_data: dict[str, Any],
    callback: Optional[callable] = None,
) -> str:
    """
    Stream LLM response and collect full text.
    
    Args:
        chain: LangChain runnable chain
        input_data: Input dictionary
        callback: Optional callback for each chunk
        
    Returns:
        Complete response text
        
    Example:
        full_response = await stream_and_collect(
            chain, 
            {"question": "What is..."},
            callback=lambda chunk: print(chunk, end="")
        )
    """
    chunks = []
    
    async for chunk in stream_llm_response(chain, input_data, callback):
        chunks.append(chunk)
    
    return "".join(chunks)


class StreamingBuffer:
    """
    Buffer for collecting streaming chunks with size limits.
    
    Useful for displaying partial responses while preventing memory issues.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Initialize streaming buffer.
        
        Args:
            max_size: Maximum buffer size in characters
        """
        self.max_size = max_size
        self.chunks: list[str] = []
        self.total_size = 0
        self.overflow = False
    
    def add(self, chunk: str) -> None:
        """Add chunk to buffer."""
        chunk_size = len(chunk)
        
        if self.total_size + chunk_size > self.max_size:
            # Calculate how much we can add
            remaining = self.max_size - self.total_size
            if remaining > 0:
                self.chunks.append(chunk[:remaining])
                self.total_size = self.max_size
            self.overflow = True
            logger.warning(
                "Streaming buffer overflow",
                max_size=self.max_size,
                total_size=self.total_size + chunk_size
            )
        else:
            self.chunks.append(chunk)
            self.total_size += chunk_size
    
    def get_text(self) -> str:
        """Get buffered text."""
        text = "".join(self.chunks)
        if self.overflow:
            text += "\n[... response truncated ...]"
        return text
    
    def clear(self) -> None:
        """Clear buffer."""
        self.chunks.clear()
        self.total_size = 0
        self.overflow = False


async def stream_with_buffer(
    chain: Runnable,
    input_data: dict[str, Any],
    max_size: int = 10000,
    callback: Optional[callable] = None,
) -> tuple[str, bool]:
    """
    Stream response with size-limited buffer.
    
    Args:
        chain: LangChain runnable chain
        input_data: Input dictionary
        max_size: Maximum buffer size
        callback: Optional callback for each chunk
        
    Returns:
        Tuple of (buffered_text, was_truncated)
    """
    buffer = StreamingBuffer(max_size=max_size)
    
    async for chunk in stream_llm_response(chain, input_data, callback):
        buffer.add(chunk)
        if buffer.overflow:
            break
    
    return buffer.get_text(), buffer.overflow


# Convenience function for common use case
async def stream_answer(
    chain: Runnable,
    question: str,
    context: Optional[str] = None,
    callback: Optional[callable] = None,
) -> str:
    """
    Stream answer to a question with optional context.
    
    Args:
        chain: LangChain runnable chain
        question: Question to answer
        context: Optional context for the question
        callback: Optional callback for each chunk
        
    Returns:
        Complete answer text
    """
    input_data = {"question": question}
    if context:
        input_data["context"] = context
    
    return await stream_and_collect(chain, input_data, callback)


