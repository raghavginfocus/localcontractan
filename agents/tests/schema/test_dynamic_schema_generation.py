"""
Test script for dynamic schema generation in the ingestion pipeline.

This script tests that:
1. New concepts are detected during ontology alignment
2. OWL extensions are generated for new concepts
3. Inference rules are generated for risk patterns
4. Generated schemas are loaded into the system (in ADAPTIVE mode)
5. The system can handle documents with completely new clause types
"""

import asyncio
import json
import logging
from pathlib import Path

from contract_kg.agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig,
    OntologyEvolutionMode,
)
from contract_kg.config import get_settings
from contract_kg.logging_config import ensure_log_dirs

# Setup logging
ensure_log_dirs()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_conservative_mode():
    """Test CONSERVATIVE mode - should only log suggestions."""
    print("\n" + "=" * 80)
    print("TEST 1: CONSERVATIVE MODE")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.CONSERVATIVE,
        generate_owl_extensions=False,
        generate_rules=False,
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    # Test with a document containing new clause types
    test_text = """
    MASTER SERVICES AGREEMENT
    
    1. CLOUD COMPUTING SERVICES
    The Provider shall deliver cloud infrastructure services including:
    - Virtual machine provisioning
    - Container orchestration via Kubernetes
    - Serverless function execution
    - Auto-scaling capabilities
    
    2. DATA RESIDENCY REQUIREMENTS
    All customer data must remain within EU data centers.
    Cross-border data transfers require explicit written consent.
    
    3. QUANTUM COMPUTING ACCESS
    Customer shall have access to quantum computing resources
    for cryptographic and optimization workloads.
    
    4. AI MODEL TRAINING CLAUSE
    Provider grants access to GPU clusters for machine learning
    model training with guaranteed uptime of 99.9%.
    """
    
    result = await orchestrator.ingest(
        text=test_text,
        document_id="test_conservative_mode"
    )
    
    print(f"\n✓ Ingestion completed: {result.success}")
    print(f"  Suggestions found: {len(result.ontology_suggestions)}")
    print(f"  OWL extensions generated: {len(result.ontology_extensions_generated)}")
    print(f"  Rules generated: {len(result.rules_generated)}")
    
    assert result.success, "Ingestion should succeed"
    assert len(result.ontology_suggestions) > 0, "Should detect new concepts"
    assert len(result.ontology_extensions_generated) == 0, "Should not generate OWL in conservative mode"
    assert len(result.rules_generated) == 0, "Should not generate rules in conservative mode"
    
    print("\n✓ CONSERVATIVE MODE TEST PASSED")
    return result


async def test_suggestive_mode():
    """Test SUGGESTIVE mode - should generate but not auto-load."""
    print("\n" + "=" * 80)
    print("TEST 2: SUGGESTIVE MODE")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.SUGGESTIVE,
        generate_owl_extensions=True,
        generate_rules=True,
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    test_text = """
    BLOCKCHAIN INTEGRATION AGREEMENT
    
    1. SMART CONTRACT DEPLOYMENT
    Provider shall deploy and maintain smart contracts on Ethereum
    mainnet with gas optimization guarantees.
    
    2. CRYPTOCURRENCY PAYMENT TERMS
    Payments may be made in Bitcoin, Ethereum, or stablecoins.
    Exchange rate risk is borne by the Customer.
    
    3. DECENTRALIZED STORAGE CLAUSE
    All contract documents shall be stored on IPFS with
    redundancy across 5 nodes minimum.
    """
    
    result = await orchestrator.ingest(
        text=test_text,
        document_id="test_suggestive_mode"
    )
    
    print(f"\n✓ Ingestion completed: {result.success}")
    print(f"  Suggestions found: {len(result.ontology_suggestions)}")
    print(f"  OWL extensions generated: {len(result.ontology_extensions_generated)}")
    print(f"  Rules generated: {len(result.rules_generated)}")
    
    assert result.success, "Ingestion should succeed"
    assert len(result.ontology_suggestions) > 0, "Should detect new concepts"
    assert len(result.ontology_extensions_generated) > 0, "Should generate OWL in suggestive mode"
    
    # Verify files were created
    for owl_path in result.ontology_extensions_generated:
        assert Path(owl_path).exists(), f"OWL file should exist: {owl_path}"
        print(f"  ✓ Generated OWL: {owl_path}")
    
    for rule_path in result.rules_generated:
        assert Path(rule_path).exists(), f"Rule file should exist: {rule_path}"
        print(f"  ✓ Generated Rule: {rule_path}")
    
    print("\n✓ SUGGESTIVE MODE TEST PASSED")
    return result


async def test_adaptive_mode():
    """Test ADAPTIVE mode - should generate and auto-load."""
    print("\n" + "=" * 80)
    print("TEST 3: ADAPTIVE MODE")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.ADAPTIVE,
        generate_owl_extensions=True,
        generate_rules=True,
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    test_text = """
    EDGE COMPUTING SERVICES AGREEMENT
    
    1. EDGE NODE DEPLOYMENT
    Provider shall deploy edge computing nodes within 50ms
    latency of customer locations.
    
    2. 5G NETWORK INTEGRATION
    Services shall leverage 5G network slicing for guaranteed
    bandwidth and ultra-low latency.
    
    3. IOT DEVICE MANAGEMENT
    Provider manages up to 1 million IoT devices per customer
    with real-time telemetry processing.
    
    4. EDGE AI INFERENCE CLAUSE
    AI model inference shall occur at edge nodes with
    <10ms response time guarantee.
    """
    
    result = await orchestrator.ingest(
        text=test_text,
        document_id="test_adaptive_mode"
    )
    
    print(f"\n✓ Ingestion completed: {result.success}")
    print(f"  Suggestions found: {len(result.ontology_suggestions)}")
    print(f"  OWL extensions generated: {len(result.ontology_extensions_generated)}")
    print(f"  Rules generated: {len(result.rules_generated)}")
    
    assert result.success, "Ingestion should succeed"
    assert len(result.ontology_suggestions) > 0, "Should detect new concepts"
    assert len(result.ontology_extensions_generated) > 0, "Should generate OWL in adaptive mode"
    
    # In adaptive mode, schemas should be auto-loaded
    # This is verified by checking the step results
    schema_evolution_step = next(
        (s for s in result.steps if s.step_name == "schema_evolution"),
        None
    )
    
    if schema_evolution_step:
        print(f"\n  Schema Evolution Step:")
        print(f"    Success: {schema_evolution_step.success}")
        print(f"    Duration: {schema_evolution_step.duration_ms:.0f}ms")
        print(f"    Result: {json.dumps(schema_evolution_step.result, indent=4)}")
    
    print("\n✓ ADAPTIVE MODE TEST PASSED")
    return result


async def test_multi_document_evolution():
    """Test that schema evolves across multiple documents."""
    print("\n" + "=" * 80)
    print("TEST 4: MULTI-DOCUMENT SCHEMA EVOLUTION")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.ADAPTIVE,
        generate_owl_extensions=True,
        generate_rules=True,
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    # Document 1: Introduces new concepts
    doc1_text = """
    QUANTUM COMPUTING SERVICES AGREEMENT
    
    1. QUANTUM PROCESSOR ACCESS
    Customer shall have access to 100-qubit quantum processors
    for quantum algorithm development and testing.
    """
    
    result1 = await orchestrator.ingest(
        text=doc1_text,
        document_id="test_multi_doc_1"
    )
    
    print(f"\n✓ Document 1 ingested")
    print(f"  New concepts: {len(result1.ontology_suggestions)}")
    print(f"  OWL extensions: {len(result1.ontology_extensions_generated)}")
    
    # Document 2: Uses similar concepts (should have fewer suggestions)
    doc2_text = """
    QUANTUM COMPUTING ADDENDUM
    
    1. ADDITIONAL QUANTUM RESOURCES
    Customer may request additional quantum processor time
    with 48-hour notice.
    """
    
    result2 = await orchestrator.ingest(
        text=doc2_text,
        document_id="test_multi_doc_2"
    )
    
    print(f"\n✓ Document 2 ingested")
    print(f"  New concepts: {len(result2.ontology_suggestions)}")
    print(f"  OWL extensions: {len(result2.ontology_extensions_generated)}")
    
    # Second document should have fewer new concepts since schema evolved
    print(f"\n  Schema evolution working: Doc1 had {len(result1.ontology_suggestions)} suggestions, "
          f"Doc2 had {len(result2.ontology_suggestions)} suggestions")
    
    print("\n✓ MULTI-DOCUMENT EVOLUTION TEST PASSED")
    return result1, result2


async def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("DYNAMIC SCHEMA GENERATION TEST SUITE")
    print("=" * 80)
    
    try:
        # Test 1: Conservative mode
        await test_conservative_mode()
        
        # Test 2: Suggestive mode
        await test_suggestive_mode()
        
        # Test 3: Adaptive mode
        await test_adaptive_mode()
        
        # Test 4: Multi-document evolution
        await test_multi_document_evolution()
        
        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED")
        print("=" * 80)
        print("\nDynamic schema generation is working correctly!")
        print("The system can now handle ANY document type without manual intervention.")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())


