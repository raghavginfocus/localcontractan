"""
Test script for the new improved agentic architecture.
This directly tests the IterativeOrchestrator with answer critique and refinement.
"""

import asyncio
import sys
from pathlib import Path

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from agents.retrieval.iterative_orchestrator import (
    IterativeOrchestrator,
    RetrievalResult
)
from service_factory import get_service_factory


async def mock_retrieval(query: str) -> RetrievalResult:
    """Mock retrieval function for testing."""
    print(f"\n🔍 RETRIEVAL CALLED: {query[:80]}...")
    
    # Simulate retrieving facts
    facts = [
        {"subject": "contract_1", "predicate": "hasClause", "object": "payment_clause"},
        {"subject": "contract_1", "predicate": "hasClause", "object": "termination_clause"},
        {"subject": "contract_2", "predicate": "hasClause", "object": "payment_clause"},
        {"subject": "contract_2", "predicate": "hasClause", "object": "liability_clause"},
    ]
    
    return RetrievalResult(
        facts=facts,
        sources=["KG"],
        query_used=query,
        duration_ms=100.0
    )


async def mock_synthesis(question: str, facts: list) -> str:
    """Mock synthesis function for testing."""
    print(f"\n📝 SYNTHESIS CALLED with {len(facts)} facts")
    
    # Simulate answer generation
    if len(facts) < 10:
        return f"Based on {len(facts)} facts, I found some contracts but need more details about clause types and combinations."
    else:
        return f"Based on {len(facts)} facts, here's a comprehensive analysis of clause patterns across contracts..."


async def test_new_architecture():
    """Test the new iterative architecture."""
    print("=" * 70)
    print("🧪 TESTING NEW IMPROVED AGENTIC ARCHITECTURE")
    print("=" * 70)
    
    settings = get_settings()
    
    # Create orchestrator
    orchestrator = IterativeOrchestrator(
        settings=settings,
        max_iterations=3
    )
    
    # Test question
    question = "Identify patterns across contracts: which clause combinations are common?"
    
    print(f"\n❓ Question: {question}")
    print("\n" + "=" * 70)
    
    # Run with refinement
    session = await orchestrator.answer_with_refinement(
        question=question,
        retrieval_fn=mock_retrieval,
        synthesis_fn=mock_synthesis
    )
    
    # Print results
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"\n✅ Final Answer:\n{session.final_answer}")
    print(f"\n📈 Statistics:")
    print(f"  - Iterations: {len(session.iterations)}")
    print(f"  - Refinements: {session.refinement_count}")
    print(f"  - Total Duration: {session.total_duration_ms:.0f}ms")
    print(f"  - Final Confidence: {session.final_critique.confidence_score:.2f}")
    print(f"  - Is Complete: {session.final_critique.is_complete}")
    print(f"  - Is Relevant: {session.final_critique.is_relevant}")
    
    print("\n📝 Iteration Details:")
    for i, iteration in enumerate(session.iterations, 1):
        print(f"\n  Iteration {i}:")
        print(f"    - Question: {iteration.question[:60]}...")
        print(f"    - Facts Retrieved: {len(iteration.retrieval_results)}")
        print(f"    - Total Facts: {iteration.total_facts}")
        if iteration.critique:
            print(f"    - Confidence: {iteration.critique.confidence_score:.2f}")
            print(f"    - Complete: {iteration.critique.is_complete}")
            print(f"    - Needs Refinement: {iteration.critique.needs_refinement}")
            if iteration.critique.missing_information:
                print(f"    - Missing: {iteration.critique.missing_information[:2]}")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_new_architecture())


