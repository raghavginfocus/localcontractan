#!/usr/bin/env python3
"""
Full Ingestion Pipeline Test Script

Tests the complete agentic ingestion pipeline with sample contracts.
Saves all artifacts for transparency and review.

Usage:
    cd agents
    PYTHONPATH=src LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5-coder:14b uv run python ../scripts/test_full_ingestion.py

Or with specific contract:
    PYTHONPATH=src uv run python ../scripts/test_full_ingestion.py --contract MSA_001

View logs in real-time:
    tail -f data/logs/ingestion_*.log
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "contracts"))

from sample_contracts import ALL_CONTRACTS, get_contract

from agents import (
    IngestionOrchestrator,
    IngestionConfig,
    IngestionResult,
    OntologyEvolutionMode,
)
from config import get_settings
from file_logger import setup_file_logging


# =============================================================================
# Console Formatting
# =============================================================================

def print_header(text: str, char: str = "=", width: int = 80):
    """Print a formatted header."""
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def print_section(text: str):
    """Print a section header."""
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def print_step(step_name: str, success: bool, duration_ms: float, error: str = None):
    """Print a pipeline step result."""
    icon = "✅" if success else "❌"
    print(f"  {icon} {step_name:25} {duration_ms:8.0f}ms")
    if error:
        print(f"      └─ Error: {error[:60]}...")


def print_metric(name: str, value: Any, unit: str = ""):
    """Print a metric."""
    print(f"  • {name:25} {value} {unit}")


# =============================================================================
# Test Runner
# =============================================================================

async def test_single_contract(
    contract_id: str,
    orchestrator: IngestionOrchestrator,
    verbose: bool = True,
) -> IngestionResult:
    """Test ingestion for a single contract."""
    
    contract = get_contract(contract_id)
    if not contract:
        print(f"❌ Contract {contract_id} not found!")
        return None
    
    print_header(f"TESTING: {contract['name']}")
    
    if verbose:
        print(f"\n  Contract ID: {contract['id']}")
        print(f"  Expected Risk: {contract['expected_risk']}")
        print(f"  Reason: {contract['reason']}")
        print(f"  Contract Value: ${contract['contract_value']:,}")
        print(f"  Jurisdiction: {contract['jurisdiction']}")
        print(f"  Text Length: {len(contract['text'])} chars")
    
    # Run ingestion
    print_section("Running Ingestion Pipeline")
    
    result = await orchestrator.ingest(
        text=contract["text"],
        document_id=contract["id"],
    )
    
    # Print results
    print_section("Pipeline Steps")
    for step in result.steps:
        print_step(
            step.step_name,
            step.success,
            step.duration_ms,
            step.error,
        )
    
    print_section("Extraction Metrics")
    print_metric("Clauses Extracted", result.clauses_extracted)
    print_metric("Entities Extracted", result.entities_extracted)
    print_metric("Obligations Extracted", result.obligations_extracted)
    print_metric("Risks Extracted", result.risks_extracted)
    print_metric("Triples Generated", result.triples_generated)
    print_metric("Triples Loaded", result.triples_loaded)
    print_metric("Facts Inferred", result.facts_inferred)
    print_metric("Vectors Indexed", result.vectors_indexed)
    
    if result.ontology_suggestions:
        print_section("Ontology Suggestions")
        for s in result.ontology_suggestions:
            print(f"  📋 {s['type']}: {s['name']}")
            print(f"     {s['description'][:60]}...")
    
    if result.ontology_extensions_generated:
        print_section("Generated OWL Extensions")
        for path in result.ontology_extensions_generated:
            print(f"  📄 {Path(path).name}")
    
    if result.rules_generated:
        print_section("Generated Rules")
        for path in result.rules_generated:
            print(f"  📜 {Path(path).name}")
    
    if result.artifact_paths:
        print_section("Saved Artifacts")
        for name, path in result.artifact_paths.items():
            print(f"  💾 {name}: {Path(path).name}")
    
    if result.validation_errors:
        print_section("Validation Errors")
        for err in result.validation_errors:
            print(f"  ⚠️  {err}")
    
    if result.validation_warnings:
        print_section("Validation Warnings")
        for warn in result.validation_warnings[:5]:  # Limit to 5
            print(f"  ⚠️  {warn}")
    
    # Final status
    status_icon = "✅" if result.success else "❌"
    print_section("RESULT")
    print(f"  {status_icon} Status: {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  ⏱️  Total Duration: {result.total_duration_ms:.0f}ms")
    
    if result.error:
        print(f"  ❌ Error: {result.error}")
    
    return result


async def test_all_contracts(verbose: bool = True) -> dict[str, IngestionResult]:
    """Test all sample contracts."""
    
    settings = get_settings()
    
    # Setup file logging - logs will be written to data/logs/ingestion_*.log
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = setup_file_logging(
        log_dir=Path("data/logs"),
        session_id=session_id,
        log_level="INFO",
    )
    
    print_header("CONTRACT KG - FULL INGESTION PIPELINE TEST")
    print(f"\n  Date: {datetime.now().isoformat()}")
    print(f"  LLM Provider: {settings.llm_provider}")
    print(f"  Model: {settings.ollama_model if settings.llm_provider == 'ollama' else settings.openai_model}")
    print(f"  Fuseki: {settings.fuseki_url}/{settings.fuseki_dataset}")
    print(f"  Contracts to Test: {len(ALL_CONTRACTS)}")
    print(f"  📝 Log File: {log_file}")
    print(f"  👀 Watch logs: tail -f {log_file}")
    
    # Initialize orchestrator with full configuration
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.CONSERVATIVE,
        enable_shacl_validation=True,
        fail_on_validation_error=False,
        enable_reasoning=True,
        enable_vector_indexing=False,  # Disable for faster testing
        save_artifacts=True,
        artifact_dir="data/generated",
        generate_owl_extensions=True,
        generate_rules=True,
    )
    
    orchestrator = IngestionOrchestrator(config=config, settings=settings)
    
    # Test each contract
    results = {}
    
    for contract_id in ALL_CONTRACTS.keys():
        result = await test_single_contract(contract_id, orchestrator, verbose)
        if result:
            results[contract_id] = result
    
    # Print summary
    print_header("TEST SUMMARY", "═")
    
    successful = sum(1 for r in results.values() if r.success)
    failed = len(results) - successful
    
    print(f"\n  Total Contracts: {len(results)}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    
    # Per-contract summary
    print_section("Per-Contract Results")
    for contract_id, result in results.items():
        contract = ALL_CONTRACTS[contract_id]
        icon = "✅" if result.success else "❌"
        print(f"  {icon} {contract_id}: {result.clauses_extracted} clauses, "
              f"{result.triples_generated} triples, {result.total_duration_ms:.0f}ms")
    
    # Save summary
    summary_path = Path("data/generated/logs") / f"test_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary_data = {
        "timestamp": datetime.now().isoformat(),
        "total_contracts": len(results),
        "successful": successful,
        "failed": failed,
        "results": {
            cid: {
                "success": r.success,
                "clauses": r.clauses_extracted,
                "triples": r.triples_generated,
                "duration_ms": r.total_duration_ms,
                "error": r.error,
            }
            for cid, r in results.items()
        },
    }
    
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"\n  📊 Summary saved to: {summary_path}")
    
    return results


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Test the full contract ingestion pipeline"
    )
    parser.add_argument(
        "--contract",
        type=str,
        choices=list(ALL_CONTRACTS.keys()),
        help="Specific contract to test (default: all)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity",
    )
    
    args = parser.parse_args()
    
    if args.contract:
        # Test single contract - setup logging first
        session_id = f"{args.contract}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        log_file = setup_file_logging(
            log_dir=Path("data/logs"),
            session_id=session_id,
            log_level="INFO",
        )
        print(f"\n  📝 Log File: {log_file}")
        print(f"  👀 Watch logs: tail -f {log_file}\n")
        
        settings = get_settings()
        config = IngestionConfig(
            ontology_evolution_mode=OntologyEvolutionMode.CONSERVATIVE,
            enable_reasoning=True,
            enable_vector_indexing=False,
            save_artifacts=True,
            generate_owl_extensions=True,
            generate_rules=True,
        )
        orchestrator = IngestionOrchestrator(config=config, settings=settings)
        await test_single_contract(args.contract, orchestrator, not args.quiet)
    else:
        # Test all contracts
        await test_all_contracts(not args.quiet)


if __name__ == "__main__":
    asyncio.run(main())
