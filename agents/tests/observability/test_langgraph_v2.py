"""
Test the simplified LangGraph orchestrator that wraps existing agents.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.retrieval.retrieval_orchestrator_langgraph_v2 import (
    LangGraphRetrievalOrchestrator
)
from logger import get_module_logger

logger = get_module_logger(__name__)


async def test_simple_query():
    """Test with a simple query."""
    print("\n" + "=" * 60)
    print("TEST 1: Simple Query")
    print("=" * 60)
    
    orchestrator = LangGraphRetrievalOrchestrator(
        enable_logging=True,
        checkpoint_path="checkpoints/test_v2.db",
    )
    
    question = "How many contracts are there?"
    
    result = await orchestrator.retrieve(
        question=question,
        thread_id="test_simple",
    )
    
    print(f"\n✓ Question: {question}")
    print(f"✓ Strategy: {result['strategy']}")
    print(f"✓ Success: {result['success']}")
    print(f"✓ Answer: {result['answer'][:200] if result['answer'] else 'None'}...")
    print(f"✓ Confidence: {result['confidence']:.2%}")
    print(f"✓ Duration: {result['total_duration_ms']:.0f}ms")
    print(f"✓ Log file: {result['log_file']}")
    
    return result


async def test_complex_query():
    """Test with a complex query."""
    print("\n" + "=" * 60)
    print("TEST 2: Complex Query")
    print("=" * 60)
    
    orchestrator = LangGraphRetrievalOrchestrator(
        enable_logging=True,
        checkpoint_path="checkpoints/test_v2.db",
    )
    
    question = "What are the termination clauses and their notice periods?"
    
    result = await orchestrator.retrieve(
        question=question,
        thread_id="test_complex",
    )
    
    print(f"\n✓ Question: {question}")
    print(f"✓ Strategy: {result['strategy']}")
    print(f"✓ Success: {result['success']}")
    print(f"✓ Answer: {result['answer'][:200] if result['answer'] else 'None'}...")
    print(f"✓ Confidence: {result['confidence']:.2%}")
    print(f"✓ Duration: {result['total_duration_ms']:.0f}ms")
    print(f"✓ Log file: {result['log_file']}")
    
    return result


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Testing LangGraph Orchestrator V2")
    print("(Wraps existing agents + proper logging)")
    print("=" * 60)
    
    try:
        # Test simple query
        result1 = await test_simple_query()
        
        # Test complex query
        result2 = await test_complex_query()
        
        print("\n" + "=" * 60)
        print("✓✓✓ ALL TESTS COMPLETED ✓✓✓")
        print("=" * 60)
        print(f"\nCheck log files:")
        print(f"  - {result1['log_file']}")
        print(f"  - {result2['log_file']}")
        print(f"\nCheck Phoenix UI: http://localhost:6006")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


