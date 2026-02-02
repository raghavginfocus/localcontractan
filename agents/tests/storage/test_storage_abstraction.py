#!/usr/bin/env python3
"""
Test script to verify storage abstraction layer (SPARQL and Vector stores).

This script tests:
1. SPARQL store factory can create stores
2. Vector store factory can create stores
3. Service factory provides dependency injection
4. Components can use abstractions
"""

import sys
from pathlib import Path

# Add agents/src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from storage.sparql.factory import SPARQLStoreFactory
from storage.vector.factory import VectorStoreFactory
from service_factory import ServiceFactory
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.ingestion.vector_index import VectorIndexAgent


def test_sparql_store_factory():
    """Test that SPARQL store factory works."""
    print("=" * 70)
    print("Testing SPARQL Store Factory")
    print("=" * 70)
    
    # List available stores
    stores = SPARQLStoreFactory.list_stores()
    print(f"\n✅ Available SPARQL stores: {stores}")
    
    # Test creating Fuseki store
    try:
        settings = get_settings()
        fuseki_store = SPARQLStoreFactory.create_store("fuseki", settings=settings)
        print(f"✅ Created Fuseki store: {fuseki_store.name}")
        print(f"   Query endpoint: {fuseki_store.query_endpoint}")
        print(f"   Update endpoint: {fuseki_store.update_endpoint}")
        
        # Test validation
        is_valid = fuseki_store.validate_config()
        print(f"   Configuration valid: {is_valid}")
    except Exception as e:
        print(f"❌ Failed to create Fuseki store: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test invalid store
    try:
        SPARQLStoreFactory.create_store("invalid")
        print("❌ Should have raised ValueError for invalid store")
        return False
    except ValueError:
        print("✅ Correctly raised ValueError for invalid store")
    
    return True


def test_vector_store_factory():
    """Test that vector store factory works."""
    print("\n" + "=" * 70)
    print("Testing Vector Store Factory")
    print("=" * 70)
    
    # List available stores
    stores = VectorStoreFactory.list_stores()
    print(f"\n✅ Available vector stores: {stores}")
    
    # Test creating Milvus store
    try:
        settings = get_settings()
        milvus_store = VectorStoreFactory.create_store("milvus", settings=settings)
        print(f"✅ Created Milvus store: {milvus_store.name}")
        
        # Test validation
        is_valid = milvus_store.validate_config()
        print(f"   Configuration valid: {is_valid}")
    except Exception as e:
        print(f"❌ Failed to create Milvus store: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test invalid store
    try:
        VectorStoreFactory.create_store("invalid")
        print("❌ Should have raised ValueError for invalid store")
        return False
    except ValueError:
        print("✅ Correctly raised ValueError for invalid store")
    
    return True


def test_service_factory():
    """Test that service factory provides dependency injection."""
    print("\n" + "=" * 70)
    print("Testing Service Factory (Dependency Injection)")
    print("=" * 70)
    
    try:
        settings = get_settings()
        factory = ServiceFactory(settings=settings)
        
        # Get stores via factory
        sparql_store = factory.get_sparql_store()
        vector_store = factory.get_vector_store()
        
        print(f"\n✅ Service factory created stores:")
        print(f"   SPARQL store: {sparql_store.name}")
        print(f"   Vector store: {vector_store.name}")
        
        # Test singleton behavior (same instance returned)
        sparql_store2 = factory.get_sparql_store()
        if sparql_store is sparql_store2:
            print("✅ SPARQL store is singleton (same instance)")
        else:
            print("⚠️  SPARQL store is not singleton (different instances)")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create service factory: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_integration():
    """Test that agents can use the abstractions."""
    print("\n" + "=" * 70)
    print("Testing Agent Integration")
    print("=" * 70)
    
    try:
        settings = get_settings()
        factory = ServiceFactory(settings=settings)
        
        # Test SPARQLGeneratorAgent with abstraction
        sparql_store = factory.get_sparql_store()
        sparql_agent = SPARQLGeneratorAgent(sparql_store=sparql_store, settings=settings)
        print(f"\n✅ SPARQLGeneratorAgent created with SPARQL store abstraction")
        print(f"   Store type: {type(sparql_agent.sparql_store).__name__}")
        
        # Test VectorIndexAgent with abstraction
        vector_store = factory.get_vector_store()
        vector_agent = VectorIndexAgent(vector_store=vector_store, settings=settings)
        print(f"✅ VectorIndexAgent created with Vector store abstraction")
        print(f"   Store type: {type(vector_agent.vector_store).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create agents: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("Storage Abstraction Layer - Test Suite")
    print("=" * 70)
    
    results = []
    
    # Test 1: SPARQL Store Factory
    results.append(("SPARQL Store Factory", test_sparql_store_factory()))
    
    # Test 2: Vector Store Factory
    results.append(("Vector Store Factory", test_vector_store_factory()))
    
    # Test 3: Service Factory
    results.append(("Service Factory", test_service_factory()))
    
    # Test 4: Agent Integration
    results.append(("Agent Integration", test_agent_integration()))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    if all_passed:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
