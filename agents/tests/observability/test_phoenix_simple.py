#!/usr/bin/env python3
"""
Simple Phoenix observability test with LangGraph V2.
Tests with real data in Milvus (15 entities).
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.retrieval.retrieval_orchestrator_langgraph_v2 import (
    LangGraphRetrievalOrchestrator,
)


async def main():
    """Run simple test queries with Phoenix tracing."""
    
    print("=" * 80)
    print("PHOENIX OBSERVABILITY TEST")
    print("=" * 80)
    print("📊 Phoenix UI: http://localhost:6006")
    print("🐳 Phoenix runs in Docker (see docker-compose.yml)")
    print("🔍 Tracing is automatic via LangGraph instrumentation\n")
    
    # Initialize orchestrator (Phoenix setup happens inside)
    print("Initializing LangGraph orchestrator...")
    orchestrator = LangGraphRetrievalOrchestrator()
    print("✅ Orchestrator ready\n")
    
    # Test queries
    test_queries = [
        "How many contracts are there?",
        "What are the termination clauses in the contracts?",
        "What are the payment terms?",
    ]
    
    print("=" * 80)
    print("RUNNING TEST QUERIES WITH PHOENIX OBSERVABILITY")
    print("=" * 80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"Query {i}/{len(test_queries)}: {query}")
        print(f"{'='*80}\n")
        
        try:
            result = await orchestrator.retrieve(query)
            
            answer = result.get('answer', 'No answer')
            print(f"✅ Answer: {answer[:200]}...")
            print(f"📊 Confidence: {result.get('confidence', 'N/A')}")
            print(f"✓ Success: {result.get('success', False)}")
            
            if result.get('log_file'):
                print(f"📝 Log file: {result['log_file']}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("✅ Test complete! Check Phoenix UI for traces:")
    print("   http://localhost:6006")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(main())


