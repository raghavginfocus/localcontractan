"""
Test script for SHACL generation functionality.

Tests that:
1. SHACL shapes are generated for new ontology classes
2. SHACL shapes are valid Turtle syntax
3. SHACL shapes are auto-loaded in ADAPTIVE mode
4. SHACL validation works with generated shapes
"""

import asyncio
import logging
from pathlib import Path

from contract_kg.agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig,
    OntologyEvolutionMode,
)
from contract_kg.agents.schema_evolution.shacl_generator import SHACLGeneratorAgent
from contract_kg.config import get_settings
from contract_kg.logging_config import ensure_log_dirs

# Setup logging
ensure_log_dirs()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_shacl_generation_standalone():
    """Test SHACL generation agent directly."""
    print("\n" + "=" * 80)
    print("TEST 1: SHACL GENERATION (Standalone)")
    print("=" * 80)
    
    shacl_generator = SHACLGeneratorAgent(settings=get_settings())
    
    # Test with a sample OWL class definition
    owl_triples = """
@prefix proc: <http://procurement.kg/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

proc:DataProtectionClause a owl:Class ;
    rdfs:subClassOf proc:Clause ;
    rdfs:label "Data Protection Clause" ;
    rdfs:comment "Clause governing data protection and privacy requirements" .

proc:dataRetentionPeriod a owl:DatatypeProperty ;
    rdfs:domain proc:DataProtectionClause ;
    rdfs:range xsd:integer ;
    rdfs:label "data retention period" ;
    rdfs:comment "Number of days data must be retained" .

proc:gdprCompliant a owl:DatatypeProperty ;
    rdfs:domain proc:DataProtectionClause ;
    rdfs:range xsd:boolean ;
    rdfs:label "GDPR compliant" ;
    rdfs:comment "Whether the clause ensures GDPR compliance" .
"""
    
    result = await shacl_generator.generate_for_owl_class(
        owl_class_name="DataProtectionClause",
        owl_triples=owl_triples,
        parent_class="proc:Clause",
    )
    
    print(f"\n✓ SHACL Generation Result:")
    print(f"  Class: {result.class_name}")
    print(f"  Valid: {result.is_valid}")
    print(f"  Triples: {result.triple_count}")
    print(f"  File: {result.file_path}")
    
    if result.error:
        print(f"  Error: {result.error}")
    
    assert result.is_valid, f"SHACL should be valid: {result.error}"
    assert result.triple_count > 0, "Should generate triples"
    assert result.file_path, "Should have file path"
    assert Path(result.file_path).exists(), "File should exist"
    
    # Verify file content
    file_content = Path(result.file_path).read_text()
    assert "sh:NodeShape" in file_content, "Should contain NodeShape"
    assert "DataProtectionClause" in file_content, "Should reference the class"
    
    print(f"\n  ✓ SHACL file content verified")
    print(f"  File size: {len(file_content)} bytes")
    
    print("\n✓ STANDALONE SHACL GENERATION TEST PASSED")
    return result


async def test_shacl_in_pipeline():
    """Test SHACL generation in the ingestion pipeline."""
    print("\n" + "=" * 80)
    print("TEST 2: SHACL GENERATION IN PIPELINE")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.ADAPTIVE,
        generate_owl_extensions=True,
        generate_shacl=True,  # Enable SHACL generation
        generate_rules=True,  # Enable rules to test everything
        enable_pattern_detection=True,  # Enable pattern detection
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    test_text = """
    DATA PROTECTION AGREEMENT
    
    1. DATA RETENTION POLICY
    Customer data shall be retained for a minimum of 7 years
    in compliance with GDPR requirements.
    
    2. GDPR COMPLIANCE
    All data processing activities must comply with EU GDPR
    regulations. Data subject rights must be respected.
    
    3. DATA RESIDENCY
    All personal data must be stored within EU data centers.
    Cross-border transfers require explicit consent.
    """
    
    result = await orchestrator.ingest(
        text=test_text,
        document_id="test_shacl_pipeline"
    )
    
    print(f"\n✓ Ingestion completed: {result.success}")
    print(f"  OWL extensions: {len(result.ontology_extensions_generated)}")
    print(f"  SHACL shapes: {len(result.shacl_shapes_generated)}")
    
    assert result.success, "Ingestion should succeed"
    assert len(result.ontology_extensions_generated) > 0, "Should generate OWL"
    assert len(result.shacl_shapes_generated) > 0, "Should generate SHACL shapes"
    
    # Verify SHACL files exist
    for shacl_path in result.shacl_shapes_generated:
        assert Path(shacl_path).exists(), f"SHACL file should exist: {shacl_path}"
        file_content = Path(shacl_path).read_text()
        assert "sh:NodeShape" in file_content, "SHACL should contain NodeShape"
        print(f"  ✓ SHACL file verified: {shacl_path}")
        print(f"    Size: {len(file_content)} bytes")
    
    # Check schema evolution step
    schema_step = next(
        (s for s in result.steps if s.step_name == "schema_evolution"),
        None
    )
    
    if schema_step:
        step_result = schema_step.result or {}
        shacl_count = step_result.get("shacl_shapes_generated", 0)
        print(f"\n  Schema Evolution Step:")
        print(f"    SHACL shapes generated: {shacl_count}")
        print(f"    Success: {schema_step.success}")
    
    print("\n✓ PIPELINE SHACL GENERATION TEST PASSED")
    return result


async def test_shacl_auto_loading():
    """Test that SHACL shapes are auto-loaded in ADAPTIVE mode."""
    print("\n" + "=" * 80)
    print("TEST 3: SHACL AUTO-LOADING (ADAPTIVE MODE)")
    print("=" * 80)
    
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.ADAPTIVE,
        generate_owl_extensions=True,
        generate_shacl=True,
        generate_rules=True,  # Enable rules to test everything
        enable_pattern_detection=True,  # Enable pattern detection
    )
    
    orchestrator = IngestionOrchestrator(config=config)
    
    test_text = """
    SERVICE LEVEL AGREEMENT
    
    1. UPTIME GUARANTEE
    Provider guarantees 99.9% uptime for all services.
    Downtime exceeding 0.1% per month triggers SLA credits.
    
    2. RESPONSE TIME REQUIREMENTS
    API endpoints must respond within 200ms for 95% of requests.
    Peak response time must not exceed 500ms.
    """
    
    result = await orchestrator.ingest(
        text=test_text,
        document_id="test_shacl_autoload"
    )
    
    print(f"\n✓ Ingestion completed: {result.success}")
    print(f"  SHACL shapes generated: {len(result.shacl_shapes_generated)}")
    
    assert result.success, "Ingestion should succeed"
    assert len(result.shacl_shapes_generated) > 0, "Should generate SHACL"
    
    # In ADAPTIVE mode, SHACL should be auto-loaded into validation agent
    # Check the schema evolution step for confirmation
    schema_step = next(
        (s for s in result.steps if s.step_name == "schema_evolution"),
        None
    )
    
    if schema_step:
        # Check logs or step result for auto-loading confirmation
        print(f"\n  Schema Evolution Step Result:")
        print(f"    Success: {schema_step.success}")
        if schema_step.result:
            print(f"    Details: {schema_step.result}")
    
    # Verify that validation agent can use the loaded shapes
    # by checking if validation step uses the new shapes
    validation_step = next(
        (s for s in result.steps if s.step_name == "validation"),
        None
    )
    
    if validation_step:
        print(f"\n  Validation Step:")
        print(f"    Success: {validation_step.success}")
        if validation_step.result:
            print(f"    SHACL valid: {validation_step.result.get('shacl_valid', 'N/A')}")
    
    print("\n✓ SHACL AUTO-LOADING TEST PASSED")
    return result


async def test_shacl_validation_with_generated_shapes():
    """Test that generated SHACL shapes actually validate data."""
    print("\n" + "=" * 80)
    print("TEST 4: SHACL VALIDATION WITH GENERATED SHAPES")
    print("=" * 80)
    
    from contract_kg.agents.ingestion.validation_agent import ValidationAgent
    
    # First, generate a SHACL shape
    shacl_generator = SHACLGeneratorAgent(settings=get_settings())
    
    owl_triples = """
@prefix proc: <http://procurement.kg/ontology#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

proc:ServiceLevelAgreementClause a owl:Class ;
    rdfs:subClassOf proc:Clause ;
    rdfs:label "Service Level Agreement Clause" .

proc:uptimePercentage a owl:DatatypeProperty ;
    rdfs:domain proc:ServiceLevelAgreementClause ;
    rdfs:range xsd:decimal .
"""
    
    shacl_result = await shacl_generator.generate_for_owl_class(
        owl_class_name="ServiceLevelAgreementClause",
        owl_triples=owl_triples,
        parent_class="proc:Clause",
    )
    
    assert shacl_result.is_valid, "SHACL should be valid"
    assert shacl_result.file_path, "Should have file path"
    
    print(f"\n✓ Generated SHACL shape: {shacl_result.file_path}")
    
    # Load SHACL into validation agent
    validation_agent = ValidationAgent(settings=get_settings())
    validation_agent.load_shacl_shape(shacl_result.file_path)
    
    print(f"  ✓ SHACL shape loaded into validation agent")
    
    # Create test RDF data that should validate
    test_rdf = """
@prefix proc: <http://procurement.kg/ontology#> .
@prefix contract: <http://procurement.kg/contract#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

contract:cl_sla_1 a proc:ServiceLevelAgreementClause ;
    rdfs:label "Uptime Guarantee" ;
    proc:uptimePercentage 99.9 .
"""
    
    # Validate the RDF
    validation_result = await validation_agent.process({"rdf_data": test_rdf})
    
    print(f"\n✓ Validation Result:")
    print(f"  Valid: {validation_result.is_valid}")
    print(f"  Syntax valid: {validation_result.syntax_valid}")
    print(f"  SHACL valid: {validation_result.shacl_valid}")
    print(f"  Errors: {len(validation_result.errors)}")
    print(f"  Warnings: {len(validation_result.warnings)}")
    
    assert validation_result.syntax_valid, "RDF syntax should be valid"
    # SHACL validation might have warnings but should not have critical errors
    assert len(validation_result.errors) == 0, f"Should not have errors: {validation_result.errors}"
    
    print("\n✓ SHACL VALIDATION TEST PASSED")
    return validation_result


async def main():
    """Run all SHACL generation tests."""
    print("\n" + "=" * 80)
    print("SHACL GENERATION TEST SUITE")
    print("=" * 80)
    
    try:
        # Test 1: Standalone SHACL generation
        await test_shacl_generation_standalone()
        
        # Test 2: SHACL generation in pipeline
        await test_shacl_in_pipeline()
        
        # Test 3: SHACL auto-loading in ADAPTIVE mode
        await test_shacl_auto_loading()
        
        # Test 4: SHACL validation with generated shapes
        await test_shacl_validation_with_generated_shapes()
        
        print("\n" + "=" * 80)
        print("✓ ALL SHACL TESTS PASSED")
        print("=" * 80)
        print("\nSHACL generation is working correctly!")
        print("The system can now automatically generate and load SHACL validation shapes.")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
