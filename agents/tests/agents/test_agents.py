#!/usr/bin/env python3
"""
Test LLM Agents

Tests individual agents in the Contract KG system.
Requires LLM API key to be configured in .env file.

Usage:
    uv run python test_agents.py                    # Test all agents
    uv run python test_agents.py --sparql           # Test SPARQL generator only
    uv run python test_agents.py --clause           # Test clause extraction
    uv run python test_agents.py --check-config     # Check configuration
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings


def check_config():
    """Check if configuration is valid."""
    settings = get_settings()
    
    print("🔧 Configuration Check")
    print("=" * 50)
    
    # Fuseki
    print(f"\n📊 Fuseki:")
    print(f"   URL: {settings.fuseki_url}")
    print(f"   Dataset: {settings.fuseki_dataset}")
    
    # LLM
    print(f"\n🤖 LLM Provider: {settings.llm_provider}")
    
    if settings.llm_provider == "openai":
        has_key = bool(settings.openai_api_key)
        print(f"   OpenAI API Key: {'✅ Set' if has_key else '❌ Missing'}")
        print(f"   Model: {settings.openai_model}")
        if not has_key:
            print("\n⚠️  Set OPENAI_API_KEY in agents/.env file")
            return False
            
    elif settings.llm_provider == "anthropic":
        has_key = bool(settings.anthropic_api_key)
        print(f"   Anthropic API Key: {'✅ Set' if has_key else '❌ Missing'}")
        print(f"   Model: {settings.anthropic_model}")
        if not has_key:
            print("\n⚠️  Set ANTHROPIC_API_KEY in agents/.env file")
            return False
            
    elif settings.llm_provider == "ollama":
        print(f"   Ollama URL: {settings.ollama_base_url}")
        print(f"   Model: {settings.ollama_model}")
    
    # Milvus
    print(f"\n🔍 Milvus:")
    print(f"   Host: {settings.milvus_host}:{settings.milvus_port}")
    print(f"   Collection: {settings.milvus_collection}")
    
    print("\n" + "=" * 50)
    return True


async def test_fuseki_client():
    """Test basic Fuseki connectivity."""
    print("\n🧪 Testing FusekiClient...")
    
    from contract_kg import FusekiClient
    
    try:
        client = FusekiClient()
        count = client.get_triple_count()
        print(f"   ✅ Connected to Fuseki")
        print(f"   📊 Triple count: {count}")
        
        # Test query
        results = client.execute_select("""
            SELECT ?contract WHERE { ?contract a proc:Contract } LIMIT 3
        """)
        print(f"   📋 Found {len(results)} contracts")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


async def test_milvus():
    """Test Milvus connectivity."""
    print("\n🧪 Testing MilvusVectorStore...")
    
    from contract_kg import MilvusVectorStore
    
    try:
        store = MilvusVectorStore()
        stats = store.get_collection_stats()
        print(f"   ✅ Connected to Milvus")
        print(f"   📊 Collection: {stats['name']}")
        print(f"   📊 Entities: {stats['num_entities']}")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return False


async def test_sparql_generator():
    """Test SPARQL generator agent."""
    print("\n🧪 Testing SPARQLGeneratorAgent...")
    
    from agents import SPARQLGeneratorAgent
    from contract_kg import FusekiClient
    
    try:
        client = FusekiClient()
        agent = SPARQLGeneratorAgent(fuseki_client=client)
        
        questions = [
            "Find all contracts governed by EU",
            "What contracts have termination clauses with less than 30 days notice?",
            "List high value contracts",
        ]
        
        for question in questions:
            print(f"\n   Q: {question}")
            result = await agent.process(question)
            print(f"   Generated SPARQL ({result.query_type}):")
            # Show first 2 lines of query
            lines = result.query.strip().split("\n")[:2]
            for line in lines:
                print(f"      {line}")
            if len(result.query.strip().split("\n")) > 2:
                print("      ...")
        
        print("\n   ✅ SPARQLGeneratorAgent working")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_clause_extraction():
    """Test clause extraction agent."""
    print("\n🧪 Testing ClauseExtractionAgent...")
    
    from agents import ClauseExtractionAgent
    
    sample_text = """
    SECTION 12 - TERMINATION
    
    12.1 Termination for Convenience. Either party may terminate this Agreement 
    at any time by providing thirty (30) days prior written notice to the other party.
    
    12.2 Termination for Cause. Either party may terminate this Agreement immediately 
    upon written notice if the other party materially breaches any provision of this 
    Agreement and fails to cure such breach within fifteen (15) days after receiving 
    written notice thereof.
    
    SECTION 5 - PAYMENT TERMS
    
    5.1 Payment. Buyer shall pay Supplier within forty-five (45) days of receipt 
    of a valid invoice. All payments shall be made in US Dollars.
    """
    
    try:
        agent = ClauseExtractionAgent()
        result = await agent.process({
            "document_id": "test_doc",
            "text": sample_text,
        })
        
        print(f"   📋 Extracted {len(result.clauses)} clauses:")
        for clause in result.clauses:
            print(f"      - {clause.clause_type}: {clause.summary[:50]}...")
        
        print("\n   ✅ ClauseExtractionAgent working")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rag():
    """Test RAG orchestrator."""
    print("\n🧪 Testing RAGOrchestratorAgent...")
    
    from agents import RAGOrchestratorAgent
    
    try:
        agent = RAGOrchestratorAgent()
        
        question = "What contracts have termination risk?"
        print(f"   Q: {question}")
        
        result = await agent.process(question)
        
        print(f"   📊 Strategy: {result.explanation_trace.split()[2] if result.explanation_trace else 'Unknown'}")
        print(f"   📊 KG Facts: {len(result.kg_facts)}")
        print(f"   📊 Vector Contexts: {len(result.vector_context)}")
        print(f"   📊 Confidence: {result.confidence:.2f}")
        print(f"\n   💬 Answer preview:")
        answer_preview = result.answer[:200] + "..." if len(result.answer) > 200 else result.answer
        print(f"      {answer_preview}")
        
        print("\n   ✅ RAGOrchestratorAgent working")
        return True
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test LLM agents")
    parser.add_argument("--check-config", action="store_true", help="Check configuration only")
    parser.add_argument("--fuseki", action="store_true", help="Test Fuseki client only")
    parser.add_argument("--milvus", action="store_true", help="Test Milvus only")
    parser.add_argument("--sparql", action="store_true", help="Test SPARQL generator only")
    parser.add_argument("--clause", action="store_true", help="Test clause extraction only")
    parser.add_argument("--rag", action="store_true", help="Test RAG orchestrator only")
    
    args = parser.parse_args()
    
    # Check config first
    if args.check_config:
        check_config()
        return
    
    # Check config is valid
    if not check_config():
        sys.exit(1)
    
    results = {}
    
    # Run specific tests or all
    if args.fuseki or not any([args.fuseki, args.milvus, args.sparql, args.clause, args.rag]):
        results["FusekiClient"] = await test_fuseki_client()
    
    if args.milvus or not any([args.fuseki, args.milvus, args.sparql, args.clause, args.rag]):
        results["MilvusVectorStore"] = await test_milvus()
    
    if args.sparql or not any([args.fuseki, args.milvus, args.sparql, args.clause, args.rag]):
        results["SPARQLGeneratorAgent"] = await test_sparql_generator()
    
    if args.clause or not any([args.fuseki, args.milvus, args.sparql, args.clause, args.rag]):
        results["ClauseExtractionAgent"] = await test_clause_extraction()
    
    if args.rag or not any([args.fuseki, args.milvus, args.sparql, args.clause, args.rag]):
        results["RAGOrchestratorAgent"] = await test_rag()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {name}: {status}")
    
    all_passed = all(results.values())
    print("=" * 50)
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
