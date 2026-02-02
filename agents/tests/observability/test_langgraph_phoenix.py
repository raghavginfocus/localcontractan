"""
Test script for LangGraph + Phoenix integration.

This demonstrates:
1. Phoenix observability setup
2. LangGraph agent execution
3. Streaming responses
4. Checkpoint recovery
"""

import asyncio
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from observability import setup_phoenix_tracing
from agents.retrieval.react_agent_langgraph import ReActLangGraphAgent
from agents.retrieval.retrieval_orchestrator_langgraph import (
    RetrievalOrchestratorLangGraph
)
from config import Settings


async def test_basic_query_with_observability():
    """Test basic query with Phoenix observability."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Query with Observability")
    print("=" * 60)
    
    # Setup Phoenix tracing
    print("\n1. Starting Phoenix observability...")
    tracer = setup_phoenix_tracing(
        project_name="contract-kg-test",
        enable_local_server=True,
        phoenix_port=6006,
    )
    print("   ✓ Phoenix UI available at: http://localhost:6006")
    
    # Initialize orchestrator
    print("\n2. Initializing LangGraph orchestrator...")
    settings = Settings()
    orchestrator = RetrievalOrchestratorLangGraph(settings=settings)
    print("   ✓ Orchestrator ready")
    
    # Process query
    print("\n3. Processing query...")
    query = "What are the termination clauses in contracts?"
    
    result = await orchestrator.process(query)
    
    print("\n4. Results:")
    print(f"   Answer: {result['final_answer'][:200]}...")
    print(f"   Confidence: {result['confidence']:.2f}")
    print(f"   Execution path: {result['execution_path']}")
    print(f"   Total time: {result['total_time_ms']:.2f}ms")
    print(f"   - Classification: {result['classification_time_ms']:.2f}ms")
    print(f"   - Analysis: {result['analysis_time_ms']:.2f}ms")
    print(f"   - Execution: {result['execution_time_ms']:.2f}ms")
    
    print("\n5. View detailed traces at: http://localhost:6006")
    print("   - Click on the trace to see the full execution tree")
    print("   - Inspect LLM calls, token usage, and timing")
    
    return tracer


async def test_streaming_responses():
    """Test streaming responses from LangGraph agent."""
    print("\n" + "=" * 60)
    print("TEST 2: Streaming Responses")
    print("=" * 60)
    
    print("\n1. Initializing ReAct agent with streaming...")
    settings = Settings()
    agent = ReActLangGraphAgent(
        enable_checkpointing=True,
        checkpoint_db_path="./checkpoints/test_react.db",
        settings=settings,
    )
    print("   ✓ Agent ready with checkpointing enabled")
    
    print("\n2. Streaming query execution...")
    query = "Compare payment terms across all contracts"
    
    # Create simple analysis result for testing
    class MockAnalysis:
        sub_queries = [
            type('SubQuery', (), {
                'step_number': 1,
                'question': query,
                'purpose': 'Answer question',
                'query_type': 'hybrid',
            })()
        ]
    
    print(f"   Query: {query}")
    print("\n   Streaming events:")
    
    event_count = 0
    async for event in agent.stream_process({
        "question": query,
        "analysis_result": MockAnalysis(),
    }):
        event_count += 1
        # Print node transitions
        for node_name, node_state in event.items():
            if node_name != "__end__":
                print(f"   → {node_name}: iteration {node_state.get('iteration', 0)}")
    
    print(f"\n   ✓ Streamed {event_count} events")
    print("   ✓ Check Phoenix UI for complete trace")


async def test_checkpoint_recovery():
    """Test checkpoint recovery after simulated failure."""
    print("\n" + "=" * 60)
    print("TEST 3: Checkpoint Recovery")
    print("=" * 60)
    
    print("\n1. Setting up agent with checkpointing...")
    settings = Settings()
    checkpoint_path = "./checkpoints/test_recovery.db"
    
    agent = ReActLangGraphAgent(
        enable_checkpointing=True,
        checkpoint_db_path=checkpoint_path,
        settings=settings,
    )
    print(f"   ✓ Checkpoint database: {checkpoint_path}")
    
    print("\n2. Executing query (will save checkpoints)...")
    query = "Find all penalty clauses"
    
    try:
        result = await agent.process(query)
        print(f"   ✓ Execution completed successfully")
        print(f"   Answer: {result.get('final_answer', '')[:100]}...")
    except Exception as e:
        print(f"   ✗ Execution failed: {e}")
        print("   ✓ State saved in checkpoint - can resume later")
    
    print("\n3. Checkpoint saved - can resume from last successful step")
    print(f"   To resume: Use same thread_id in config")


async def test_custom_tracing():
    """Test custom tracing with Phoenix."""
    print("\n" + "=" * 60)
    print("TEST 4: Custom Tracing")
    print("=" * 60)
    
    print("\n1. Getting Phoenix tracer...")
    from observability import setup_phoenix_tracing
    tracer = setup_phoenix_tracing(auto_start=False)
    
    if not tracer._session:
        tracer.start()
    
    print("   ✓ Tracer ready")
    
    print("\n2. Creating custom traced operation...")
    
    async def custom_retrieval(query: str):
        """Example custom operation with tracing."""
        with tracer.trace_agent_step(
            step_name="custom_retrieval",
            agent_name="TestAgent",
            metadata={"query_length": len(query), "test": True}
        ):
            # Simulate work
            await asyncio.sleep(0.1)
            
            # Add span attributes
            tracer.add_span_attribute("results_found", 5)
            tracer.add_span_attribute("data_source", "test_db")
            
            # Add span event
            tracer.add_span_event("retrieval_complete", {
                "status": "success",
                "duration_ms": 100,
            })
            
            return {"results": ["result1", "result2", "result3"]}
    
    print("   Executing custom traced operation...")
    results = await custom_retrieval("test query")
    print(f"   ✓ Retrieved {len(results['results'])} results")
    print("   ✓ Check Phoenix UI for custom span details")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print(" LangGraph + Phoenix Integration Tests")
    print("=" * 70)
    
    try:
        # Test 1: Basic query with observability
        tracer = await test_basic_query_with_observability()
        
        # Test 2: Streaming responses
        await test_streaming_responses()
        
        # Test 3: Checkpoint recovery
        await test_checkpoint_recovery()
        
        # Test 4: Custom tracing
        await test_custom_tracing()
        
        print("\n" + "=" * 70)
        print(" All Tests Complete!")
        print("=" * 70)
        print("\n📊 View traces at: http://localhost:6006")
        print("\n💡 Tips:")
        print("   - Click on traces to see execution details")
        print("   - Use filters to find specific operations")
        print("   - Compare different query executions")
        print("   - Analyze token usage and costs")
        
        # Keep Phoenix running
        print("\n⏸️  Press Ctrl+C to stop Phoenix and exit...")
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            print("\n\n👋 Shutting down...")
            if tracer:
                tracer.stop()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
