"""
LLM Batch Helper - Utilities for batch LLM processing.

Provides optimized batch processing for LLM calls using:
- LangChain's abatch() method when available
- Parallel ainvoke() calls as fallback
- Automatic batching and chunking for large requests
"""

from typing import Any, Callable, TypeVar, Sequence
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from logger import get_module_logger

logger = get_module_logger(__name__)

T = TypeVar('T')


async def batch_llm_calls(
    chain: Runnable,
    inputs: Sequence[dict[str, Any]],
    batch_size: int = 10,
    use_native_batch: bool = True,
) -> list[Any]:
    """
    Execute multiple LLM calls efficiently using batch API when available.
    
    Args:
        chain: LangChain runnable chain (prompt | llm | parser)
        inputs: List of input dictionaries for each call
        batch_size: Maximum batch size for native batch API
        use_native_batch: Whether to use native abatch() if available
        
    Returns:
        List of results in the same order as inputs
    """
    if not inputs:
        return []
    
    # Try to use native batch API if available and enabled
    if use_native_batch and hasattr(chain, 'abatch'):
        try:
            # Check if the underlying LLM supports batch processing
            # Most LangChain models support abatch()
            logger.debug(
                "Using native batch API",
                batch_size=len(inputs),
                total_inputs=len(inputs)
            )
            
            # Process in chunks if batch is too large
            if len(inputs) <= batch_size:
                results = await chain.abatch(inputs)
                return list(results)
            else:
                # Process in batches
                all_results = []
                for i in range(0, len(inputs), batch_size):
                    batch = inputs[i:i + batch_size]
                    batch_results = await chain.abatch(batch)
                    all_results.extend(batch_results)
                    logger.debug(
                        "Processed batch chunk",
                        chunk=i // batch_size + 1,
                        total_chunks=(len(inputs) + batch_size - 1) // batch_size,
                        chunk_size=len(batch)
                    )
                return all_results
                
        except Exception as e:
            logger.warning(
                "Native batch API failed, falling back to parallel ainvoke",
                error=str(e)
            )
            # Fall through to parallel ainvoke
    
    # Fallback: Use parallel ainvoke() calls
    import asyncio
    
    logger.debug(
        "Using parallel ainvoke calls",
        total_inputs=len(inputs)
    )
    
    async def invoke_single(input_data: dict[str, Any]) -> Any:
        """Invoke chain for a single input."""
        try:
            return await chain.ainvoke(input_data)
        except Exception as e:
            logger.error(
                "Failed to invoke LLM chain",
                error=str(e),
                input_keys=list(input_data.keys())
            )
            raise
    
    # Execute all calls in parallel
    results = await asyncio.gather(
        *[invoke_single(inp) for inp in inputs],
        return_exceptions=True
    )
    
    # Check for exceptions
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(
                "LLM call failed in batch",
                index=i,
                error=str(result)
            )
            # Re-raise the first exception
            raise result
    
    return list(results)


async def batch_llm_with_retry(
    chain: Runnable,
    inputs: Sequence[dict[str, Any]],
    max_retries: int = 2,
    batch_size: int = 10,
) -> list[Any]:
    """
    Execute batch LLM calls with automatic retry on failures.
    
    Args:
        chain: LangChain runnable chain
        inputs: List of input dictionaries
        max_retries: Maximum retry attempts for failed calls
        batch_size: Maximum batch size
        
    Returns:
        List of results
    """
    from tenacity import retry, stop_after_attempt, wait_exponential
    
    @retry(
        stop=stop_after_attempt(max_retries + 1),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def batch_with_retry():
        return await batch_llm_calls(chain, inputs, batch_size)
    
    return await batch_with_retry()


def get_batch_size_for_provider(llm: BaseChatModel) -> int:
    """
    Get optimal batch size for a specific LLM provider.
    
    Args:
        llm: LangChain chat model instance
        
    Returns:
        Recommended batch size
    """
    llm_type = type(llm).__name__
    
    # Provider-specific batch size recommendations
    batch_sizes = {
        'ChatOpenAI': 50,  # OpenAI supports large batches
        'ChatAnthropic': 20,  # Anthropic has moderate batch limits
        'ChatOllama': 5,  # Local Ollama may have resource constraints
        'ChatWatsonX': 10,  # WatsonX moderate batches
    }
    
    # Check if we have a specific recommendation
    for provider_name, batch_size in batch_sizes.items():
        if provider_name in llm_type:
            return batch_size
    
    # Default batch size
    return 10


async def batch_extract_clauses(
    clause_agent: Any,
    documents: list[dict[str, Any]],
    batch_size: int | None = None,
) -> list[Any]:
    """
    Batch extract clauses from multiple documents.
    
    Args:
        clause_agent: ClauseExtractionAgent instance
        documents: List of dicts with 'document_id' and 'text'
        batch_size: Optional batch size (auto-detected if None)
        
    Returns:
        List of ClauseExtractionResult objects
    """
    if not documents:
        return []
    
    # Auto-detect batch size if not provided
    if batch_size is None:
        batch_size = get_batch_size_for_provider(clause_agent.llm)
    
    # Create chain for clause extraction
    from langchain_core.output_parsers import JsonOutputParser
    parser = JsonOutputParser()
    chain = clause_agent.EXTRACTION_PROMPT | clause_agent.llm | parser
    
    # Prepare inputs
    inputs = [
        {
            "document_id": doc.get("document_id", f"doc_{i}"),
            "contract_text": doc.get("text", "")[:30000],  # Limit text length
        }
        for i, doc in enumerate(documents)
    ]
    
    # Execute batch extraction
    results = await batch_llm_calls(chain, inputs, batch_size=batch_size)
    
    # Parse results into ClauseExtractionResult objects
    from agents.ingestion.clause_extraction import ClauseExtractionResult, ExtractedClause
    
    parsed_results = []
    for i, result in enumerate(results):
        try:
            clauses = [
                ExtractedClause(**clause_data)
                for clause_data in result.get("clauses", [])
            ]
            
            extraction_result = ClauseExtractionResult(
                document_id=documents[i].get("document_id", f"doc_{i}"),
                clauses=clauses,
                unclassified_sections=result.get("unclassified_sections", []),
            )
            parsed_results.append(extraction_result)
        except Exception as e:
            logger.error(
                "Failed to parse clause extraction result",
                index=i,
                error=str(e)
            )
            # Create empty result on parse failure
            parsed_results.append(
                ClauseExtractionResult(
                    document_id=documents[i].get("document_id", f"doc_{i}"),
                    clauses=[],
                    unclassified_sections=[],
                )
            )
    
    return parsed_results
