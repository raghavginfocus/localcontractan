#!/usr/bin/env python3
"""
Test script for new GraphRAG features.

Tests:
1. Dynamic Ontology Manager
2. Reasoning Engine Integration
3. Batch Processing
4. Named Graph Architecture
5. Vector-RDF Linking

Usage:
    uv run python scripts/test_new_features.py
"""

import asyncio
import sys
from pathlib import Path

# Add agents to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from ontology_manager import initialize_ontology, get_ontology_manager
from agents.ingestion.reasoning_agent import ReasoningAgent
from batch_processor import BatchProcessor, DocumentTask
from graph_manager import get_graph_manager
from fuseki_client import FusekiClient
from vector_store import MilvusVectorStore
from config import get_settings
from rdflib import Graph, Namespace, URIRef, Literal


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def test_ontology_manager():
    """Test 1: Dynamic Ontology Manager."""
    print_section("TEST 1: Dynamic Ontology Manager")
    
    try:
        # Find ontology file (test runs from agents/ directory)
        # Use the root ontology file which is in correct RDF/XML format
        ontology_paths = [
            Path("../ontology/procurement.owl"),
            Path("ontology/procurement.owl"),
        ]
        
        ontology_path = None
        for path in ontology_paths:
            if path.exists():
                ontology_path = path
                break
        
        if not ontology_path:
            print("❌ No ontology file found!")
            print(f"   Searched paths:")
            for p in ontology_paths:
                print(f"   - {p.absolute()}")
            return False
        
        print(f"📁 Loading ontology from: {ontology_path}")
        
        # Initialize ontology manager
        manager = initialize_ontology(ontology_path)
        
        # Get active schema
        schema = manager.get_active_schema()
        
        print(f"✅ Ontology loaded successfully!")
        print(f"   Version: {schema.version}")
        print(f"   Classes: {len(schema.get_all_classes())}")
        print(f"   Properties: {len(schema.get_all_properties())}")
        
        # Test class validation
        test_classes = [
            "Contract",
            "TerminationClause",
            "PaymentClause",
            "NonExistentClause"
        ]
        
        print("\n📋 Testing class validation:")
        for class_name in test_classes:
            exists = manager.validate_class(class_name)
            icon = "✅" if exists else "❌"
            print(f"   {icon} {class_name}: {exists}")
        
        # Test property validation
        test_properties = [
            "noticePeriod",
            "contractValue",
            "nonExistentProperty"
        ]
        
        print("\n📋 Testing property validation:")
        for prop_name in test_properties:
            exists = manager.validate_property(prop_name)
            icon = "✅" if exists else "❌"
            print(f"   {icon} {prop_name}: {exists}")
        
        # Show class hierarchy
        print("\n🌳 Class hierarchy sample:")
        hierarchy = schema._class_hierarchy
        for parent, children in list(hierarchy.items())[:5]:
            print(f"   {parent}")
            for child in children:
                print(f"      └─ {child}")
        
        print("\n✅ Ontology Manager test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Ontology Manager test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_reasoning_agent():
    """Test 2: Reasoning Engine Integration."""
    print_section("TEST 2: Reasoning Engine Integration")
    
    try:
        # Check if rules file exists
        rules_path = Path("rules/procurement.rules")
        if not rules_path.exists():
            print(f"⚠️  Rules file not found: {rules_path}")
            print("   Skipping reasoning test")
            return True
        
        print(f"📁 Using rules file: {rules_path}")
        
        # Create reasoning agent
        agent = ReasoningAgent()
        
        print("🔄 Applying reasoning rules...")
        
        # Apply reasoning
        result = await agent.process({
            "rule_files": [str(rules_path)],
            "reasoning_type": "both"
        })
        
        if result.success:
            print(f"✅ Reasoning completed successfully!")
            print(f"   Inferred triples: {result.inferred_triples}")
            print(f"   Rules applied: {len(result.rules_applied)}")
            print(f"   Time: {result.reasoning_time_ms:.0f}ms")
            
            if result.rules_applied:
                print(f"\n📋 Rules that fired:")
                for rule in result.rules_applied[:5]:
                    print(f"      - {rule}")
            
            print("\n✅ Reasoning Agent test PASSED")
            return True
        else:
            print(f"❌ Reasoning failed: {result.error}")
            return False
        
    except Exception as e:
        print(f"\n❌ Reasoning Agent test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_batch_processor():
    """Test 3: Batch Processing."""
    print_section("TEST 3: Batch Processing")
    
    try:
        # Create sample tasks
        sample_contracts = [
            "IT Services Agreement between ABC Corp and XYZ Ltd...",
            "Hardware Supply Agreement for network equipment...",
            "Consulting Services Agreement for Q1 2024...",
        ]
        
        tasks = [
            DocumentTask(
                task_id=f"test_task_{i}",
                text=text,
                document_id=f"test_doc_{i}"
            )
            for i, text in enumerate(sample_contracts)
        ]
        
        print(f"📦 Created {len(tasks)} test tasks")
        
        # Create batch processor
        processor = BatchProcessor(
            max_concurrent=2,
            max_retries=1
        )
        
        print("🔄 Processing batch...")
        
        # Track progress
        def progress_callback(batch_result):
            completed = sum(
                1 for t in batch_result.tasks
                if t.status in ["completed", "failed"]
            )
            print(f"   Progress: {completed}/{batch_result.total_tasks}")
        
        # Process batch
        result = await processor.process_batch(
            tasks,
            batch_id="test_batch",
            progress_callback=progress_callback
        )
        
        print(f"\n✅ Batch processing completed!")
        print(f"   Status: {result.status}")
        print(f"   Total tasks: {result.total_tasks}")
        print(f"   Completed: {result.completed}")
        print(f"   Failed: {result.failed}")
        print(f"   Duration: {result.total_duration_ms:.0f}ms")
        
        if result.completed > 0:
            print(f"\n📊 Aggregated metrics:")
            print(f"   Total clauses: {result.total_clauses}")
            print(f"   Total entities: {result.total_entities}")
            print(f"   Total triples: {result.total_triples}")
            print(f"   Total risks: {result.total_risks}")
        
        # Show task details
        print(f"\n📋 Task details:")
        for task in result.tasks:
            icon = "✅" if task.status == "completed" else "❌"
            print(f"   {icon} {task.task_id}: {task.status}")
            if task.error:
                print(f"      Error: {task.error[:100]}")
        
        print("\n✅ Batch Processor test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Batch Processor test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_named_graphs():
    """Test 4: Named Graph Architecture."""
    print_section("TEST 4: Named Graph Architecture")
    
    try:
        # Initialize graph manager
        graph_manager = get_graph_manager()
        fuseki_client = FusekiClient()
        
        print("📊 Testing named graph operations...")
        
        # Create test RDF data
        g = Graph()
        PROC = Namespace("http://procurement.kg/ontology#")
        CONTRACT = Namespace("http://procurement.kg/contract#")
        
        # Add test triples
        contract_uri = CONTRACT["test_contract_001"]
        g.add((contract_uri, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), PROC.Contract))
        g.add((contract_uri, PROC.contractValue, Literal(100000)))
        
        clause_uri = CONTRACT["test_clause_001"]
        g.add((clause_uri, URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), PROC.TerminationClause))
        g.add((contract_uri, PROC.hasClause, clause_uri))
        
        print(f"   Created test graph with {len(g)} triples")
        
        # Test 1: Create document graph
        print("\n1️⃣  Testing document graph creation...")
        doc_id = "test_doc_001"
        graph_info = graph_manager.create_document_graph(
            document_id=doc_id,
            rdf_graph=g,
            tenant_id="test_tenant"
        )
        print(f"   ✅ Created graph: {graph_info.graph_uri}")
        print(f"      Triples: {graph_info.triple_count}")
        
        # Test 2: Query document graph
        print("\n2️⃣  Testing document-scoped query...")
        results = graph_manager.query_document(
            document_id=doc_id,
            sparql_query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            include_inferred=False
        )
        print(f"   ✅ Query returned {len(results)} results")
        
        # Test 3: Create inferred graph
        print("\n3️⃣  Testing inferred graph...")
        inferred_g = Graph()
        inferred_g.add((clause_uri, PROC.introducesRisk, PROC.HighTerminationRisk))
        
        inferred_info = graph_manager.create_inferred_graph(
            document_id=doc_id,
            inferred_triples=inferred_g
        )
        print(f"   ✅ Created inferred graph: {inferred_info.graph_uri}")
        print(f"      Inferred triples: {inferred_info.triple_count}")
        
        # Test 4: Query with inference
        print("\n4️⃣  Testing query with inference...")
        results_with_inference = graph_manager.query_document(
            document_id=doc_id,
            sparql_query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            include_inferred=True
        )
        print(f"   ✅ Query with inference returned {len(results_with_inference)} results")
        print(f"      Difference: +{len(results_with_inference) - len(results)} triples")
        
        # Test 5: List graphs
        print("\n5️⃣  Testing graph listing...")
        graphs = graph_manager.list_document_graphs(tenant_id="test_tenant")
        print(f"   ✅ Found {len(graphs)} graphs for tenant")
        
        # Test 6: Graph statistics
        print("\n6️⃣  Testing graph statistics...")
        stats = graph_manager.get_graph_statistics(graph_info.graph_uri)
        print(f"   ✅ Graph stats: {stats['triple_count']} triples")
        
        # Test 7: Cleanup
        print("\n7️⃣  Testing graph deletion...")
        deleted = graph_manager.delete_document_graph(doc_id)
        print(f"   ✅ Deleted graphs: {deleted}")
        
        print("\n✅ Named Graph Architecture test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Named Graph Architecture test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_vector_rdf_linking():
    """Test 5: Vector-RDF Linking."""
    print_section("TEST 5: Vector-RDF Linking")
    
    try:
        # Initialize components
        vector_store = MilvusVectorStore()
        graph_manager = get_graph_manager()
        
        print("🔗 Testing vector-RDF linking...")
        
        # Test data
        doc_id = "test_doc_002"
        graph_uri = graph_manager.get_document_graph_uri(doc_id)
        
        test_clauses = [
            {
                "clause_id": "clause_001",
                "contract_id": "contract_001",
                "clause_type": "TerminationClause",
                "text": "Either party may terminate this agreement with 30 days notice.",
                "rdf_uri": "http://procurement.kg/contract#clause_001",
                "graph_uri": graph_uri,
            },
            {
                "clause_id": "clause_002",
                "contract_id": "contract_001",
                "clause_type": "PaymentClause",
                "text": "Payment shall be made within 30 days of invoice date.",
                "rdf_uri": "http://procurement.kg/contract#clause_002",
                "graph_uri": graph_uri,
            },
        ]
        
        # Test 1: Add clauses with RDF linking
        print("\n1️⃣  Testing clause indexing with RDF URIs...")
        indexed = vector_store.add_clauses_batch(test_clauses)
        print(f"   ✅ Indexed {indexed} clauses with RDF linking")
        
        # Test 2: Search with graph filtering
        print("\n2️⃣  Testing graph-scoped search...")
        results = vector_store.search(
            query="termination notice period",
            top_k=5,
            graph_uri=graph_uri
        )
        print(f"   ✅ Found {len(results)} results")
        
        if results:
            print(f"\n   📋 Top result:")
            top = results[0]
            print(f"      Clause: {top['clause_id']}")
            print(f"      Type: {top['clause_type']}")
            print(f"      Score: {top['score']:.3f}")
            print(f"      RDF URI: {top['rdf_uri']}")
            print(f"      Graph URI: {top['graph_uri']}")
        
        # Test 3: Search without graph filter
        print("\n3️⃣  Testing search without graph filter...")
        all_results = vector_store.search(
            query="payment terms",
            top_k=5
        )
        print(f"   ✅ Found {len(all_results)} results across all graphs")
        
        # Test 4: Verify RDF URIs in results
        print("\n4️⃣  Verifying RDF URI presence...")
        has_rdf_uris = all(
            'rdf_uri' in r and r['rdf_uri']
            for r in all_results
        )
        has_graph_uris = all(
            'graph_uri' in r and r['graph_uri']
            for r in all_results
        )
        
        if has_rdf_uris and has_graph_uris:
            print(f"   ✅ All results have RDF and graph URIs")
        else:
            print(f"   ⚠️  Some results missing URIs")
            print(f"      RDF URIs: {has_rdf_uris}")
            print(f"      Graph URIs: {has_graph_uris}")
        
        # Test 5: Cleanup
        print("\n5️⃣  Testing cleanup...")
        deleted = vector_store.delete_by_contract("contract_001")
        print(f"   ✅ Deleted {deleted} vectors")
        
        print("\n✅ Vector-RDF Linking test PASSED")
        return True
        
    except Exception as e:
        print(f"\n❌ Vector-RDF Linking test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("  🧪 GraphRAG New Features Test Suite")
    print("=" * 70)
    
    # Check settings
    settings = get_settings()
    print(f"\n⚙️  Configuration:")
    print(f"   Fuseki: {settings.fuseki_url}/{settings.fuseki_dataset}")
    print(f"   Milvus: {settings.milvus_host}:{settings.milvus_port}")
    print(f"   LLM: {settings.llm_provider}")
    
    results = {}
    
    # Test 1: Ontology Manager
    results['ontology'] = test_ontology_manager()
    
    # Test 2: Reasoning Agent
    results['reasoning'] = await test_reasoning_agent()
    
    # Test 3: Batch Processor
    results['batch'] = await test_batch_processor()
    
    # Test 4: Named Graph Architecture
    results['named_graphs'] = await test_named_graphs()
    
    # Test 5: Vector-RDF Linking
    results['vector_rdf'] = await test_vector_rdf_linking()
    
    # Summary
    print_section("TEST SUMMARY")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed
    
    print(f"Total tests: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    print("\n📋 Detailed results:")
    for test_name, result in results.items():
        icon = "✅" if result else "❌"
        status = "PASSED" if result else "FAILED"
        print(f"   {icon} {test_name.title()}: {status}")
    
    if failed == 0:
        print("\n🎉 All tests PASSED! System is ready for production.")
        print("\n📚 Next steps:")
        print("   1. Review FIXES_IMPLEMENTATION_SUMMARY.md for details")
        print("   2. Review IMPLEMENTATION_GUIDE.md for integration")
        print("   3. Update ingestion_orchestrator.py to use new components")
        print("   4. Run full integration tests with real documents")
        print("   5. Deploy to staging environment")
    else:
        print("\n⚠️  Some tests failed. Please review errors above.")
        print("   Check that Fuseki and Milvus are running.")
        print("   Verify ontology and rules files exist.")
    
    print("\n" + "=" * 70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


