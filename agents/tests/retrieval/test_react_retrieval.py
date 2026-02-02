"""
Test script for ReAct-style multi-step retrieval.

Tests the new ReAct agent with complex queries that previously failed
with single-shot retrieval.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.retrieval.retrieval_orchestrator import RetrievalOrchestrator
from agents.retrieval.complexity_detector import QueryComplexityDetector
from config import get_settings


# Test queries - from simple to complex
TEST_QUERIES = {
    "simple": [
        "List all contracts",
        "What is the contract value?",
        "Count the number of contracts",
    ],
    "moderate": [
        "What are the payment terms and penalties?",
        "Which contract has the highest value?",
        "Show termination clauses with notice periods",
    ],
    "complex": [
        # This is the query that failed in the evaluation log
        "Analyze the risk profile of our contracts. Consider termination "
        "conditions, liability terms, and any unusual clauses. Which "
        "contracts have the highest risk?",
        
        "Compare all contracts and identify which ones have both short "
        "termination periods and unlimited liability",
        
        "Evaluate compliance across all contracts considering confidentiality "
        "requirements, data protection clauses, and jurisdiction",
    ],
}


async def test_complexity_detection():
    """Test the complexity detector."""
    print("=" * 80)
    print("TESTING COMPLEXITY DETECTION")
    print("=" * 80)
    
    settings = get_settings()
    detector = QueryComplexityDetector(settings=settings)
    
    for category, queries in TEST_QUERIES.items():
        print(f"\n{category.upper()} QUERIES:")
        print("-" * 80)
        
        for query in queries:
            print(f"\nQuery: {query[:80]}...")
            
            analysis = await detector.process(query)
            
            print(f"  Complexity: {analysis.complexity.value}")
            print(f"  Confidence: {analysis.confidence:.2f}")
            print(f"  Indicators: {', '.join(analysis.indicators[:3])}")
            print(f"  Strategy: {analysis.recommended_strategy}")


async def test_react_retrieval(query: str, force_react: bool = False):
    """Test ReAct retrieval with a specific query."""
    print("\n" + "=" * 80)
    print(f"TESTING REACT RETRIEVAL")
    print("=" * 80)
    print(f"Query: {query}")
    print(f"Force ReAct: {force_react}")
    print("=" * 80)
    
    settings = get_settings()
    orchestrator = RetrievalOrchestrator(
        settings=settings,
        enable_react=True,
    )
    
    try:
        result = await orchestrator.retrieve(
            question=query,
            force_react=force_react,
        )
        
        print(f"\n{'=' * 80}")
        print("RESULTS")
        print("=" * 80)
        print(f"Success: {result.success}")
        print(f"Strategy: {result.strategy.value}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Duration: {result.total_duration_ms:.0f}ms")
        print(f"KG Facts: {result.kg_facts_count}")
        print(f"Vector Contexts: {result.vector_context_count}")
        print(f"Steps: {len(result.steps)}")
        
        if result.steps:
            print(f"\nReasoning Steps:")
            for i, step in enumerate(result.steps, 1):
                print(f"  {i}. {step.step_name}")
                if hasattr(step, 'result') and step.result:
                    thought = step.result.get('thought', '')
                    if thought:
                        print(f"     Thought: {thought[:100]}...")
        
        print(f"\nAnswer ({len(result.answer)} chars):")
        print("-" * 80)
        # Print first 500 chars of answer
        print(result.answer[:500])
        if len(result.answer) > 500:
            print(f"\n... ({len(result.answer) - 500} more characters)")
        
        if result.error:
            print(f"\nError: {result.error}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def compare_standard_vs_react(query: str):
    """Compare standard retrieval vs ReAct for the same query."""
    print("\n" + "=" * 80)
    print("COMPARING STANDARD vs REACT RETRIEVAL")
    print("=" * 80)
    print(f"Query: {query}")
    print("=" * 80)
    
    settings = get_settings()
    orchestrator = RetrievalOrchestrator(
        settings=settings,
        enable_react=True,
    )
    
    # Test with standard retrieval
    print("\n[1/2] Testing STANDARD retrieval...")
    standard_result = await orchestrator.retrieve(
        question=query,
        force_react=False,
    )
    
    # Test with ReAct
    print("\n[2/2] Testing REACT retrieval...")
    react_result = await orchestrator.retrieve(
        question=query,
        force_react=True,
    )
    
    # Compare results
    print(f"\n{'=' * 80}")
    print("COMPARISON")
    print("=" * 80)
    
    print(f"\n{'Metric':<25} {'Standard':<20} {'ReAct':<20}")
    print("-" * 65)
    print(f"{'Success':<25} {str(standard_result.success):<20} "
          f"{str(react_result.success):<20}")
    print(f"{'Confidence':<25} {standard_result.confidence:<20.2f} "
          f"{react_result.confidence:<20.2f}")
    print(f"{'Duration (ms)':<25} {standard_result.total_duration_ms:<20.0f} "
          f"{react_result.total_duration_ms:<20.0f}")
    print(f"{'KG Facts':<25} {standard_result.kg_facts_count:<20} "
          f"{react_result.kg_facts_count:<20}")
    print(f"{'Vector Contexts':<25} {standard_result.vector_context_count:<20} "
          f"{react_result.vector_context_count:<20}")
    print(f"{'Steps':<25} {len(standard_result.steps):<20} "
          f"{len(react_result.steps):<20}")
    print(f"{'Answer Length':<25} {len(standard_result.answer):<20} "
          f"{len(react_result.answer):<20}")
    
    print(f"\n{'=' * 80}")
    print("STANDARD ANSWER (first 300 chars):")
    print("-" * 80)
    print(standard_result.answer[:300])
    
    print(f"\n{'=' * 80}")
    print("REACT ANSWER (first 300 chars):")
    print("-" * 80)
    print(react_result.answer[:300])


async def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test ReAct-style multi-step retrieval"
    )
    parser.add_argument(
        "--test",
        choices=["complexity", "react", "compare", "all"],
        default="all",
        help="Which test to run"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Custom query to test (for react/compare tests)"
    )
    parser.add_argument(
        "--force-react",
        action="store_true",
        help="Force use of ReAct agent"
    )
    
    args = parser.parse_args()
    
    # Default to the failed complex query
    test_query = args.query or TEST_QUERIES["complex"][0]
    
    try:
        if args.test in ["complexity", "all"]:
            await test_complexity_detection()
        
        if args.test in ["react", "all"]:
            print("\n")
            await test_react_retrieval(test_query, args.force_react)
        
        if args.test in ["compare", "all"]:
            print("\n")
            await compare_standard_vs_react(test_query)
        
        print(f"\n{'=' * 80}")
        print("✓ All tests completed")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


