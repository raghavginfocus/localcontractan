#!/usr/bin/env python3
"""
Ingest a single document into the knowledge graph.

This script processes a single PDF or DOCX file through the full agentic pipeline
without reprocessing existing documents.

Usage:
    cd agents
    uv run python ../scripts/ingest_single_document.py /path/to/document.pdf
    
    # Or from project root:
    cd agents && uv run python ../scripts/ingest_single_document.py ../examples/new_contract.docx
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

import structlog

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig,
    OntologyEvolutionMode,
)
from config import get_settings

logger = structlog.get_logger()


async def main():
    """Ingest a single document."""
    
    if len(sys.argv) < 2:
        print("❌ Error: No document path provided")
        print("\nUsage:")
        print("  cd agents")
        print("  uv run python ../scripts/ingest_single_document.py /path/to/document.pdf")
        print("\nExample:")
        print("  uv run python ../scripts/ingest_single_document.py ../examples/new_contract.docx")
        sys.exit(1)
    
    doc_path = Path(sys.argv[1])
    
    # Validate file exists
    if not doc_path.exists():
        print(f"❌ Error: File not found: {doc_path}")
        sys.exit(1)
    
    # Validate file type
    if doc_path.suffix.lower() not in ['.pdf', '.docx']:
        print(f"❌ Error: Unsupported file type: {doc_path.suffix}")
        print("   Supported types: .pdf, .docx")
        sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"🚀 Single Document Ingestion")
    print(f"{'='*70}")
    print(f"\n📄 Document: {doc_path.name}")
    print(f"📁 Path: {doc_path.absolute()}")
    print(f"📏 Size: {doc_path.stat().st_size / 1024:.2f} KB")
    print()
    
    # Initialize settings
    settings = get_settings()
    
    # Configure ingestion pipeline
    config = IngestionConfig(
        ontology_evolution_mode=OntologyEvolutionMode.ADAPTIVE,
        auto_extend_threshold=3,
        enable_shacl_validation=True,
        fail_on_validation_error=False,
        enable_reasoning=True,
        enable_vector_indexing=True,
        log_all_steps=True,
        save_artifacts=True,
        generate_owl_extensions=True,
        generate_rules=True,
    )
    
    print(f"⚙️  Pipeline Configuration:")
    print(f"   • Ontology Evolution: {config.ontology_evolution_mode.value}")
    print(f"   • SHACL Validation: {'Enabled' if config.enable_shacl_validation else 'Disabled'}")
    print(f"   • Reasoning: {'Enabled' if config.enable_reasoning else 'Disabled'}")
    print(f"   • Vector Indexing: {'Enabled' if config.enable_vector_indexing else 'Disabled'}")
    print(f"   • Auto-extend Threshold: {config.auto_extend_threshold}")
    print()
    
    # Initialize orchestrator
    orchestrator = IngestionOrchestrator(config=config, settings=settings)
    
    # Process document
    print(f"{'─'*70}")
    print(f"🔄 Processing Document...")
    print(f"{'─'*70}\n")
    
    start_time = datetime.now()
    
    try:
        result = await orchestrator.ingest(file_path=str(doc_path))
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Print detailed results
        print(f"\n{'='*70}")
        print(f"✅ Document Processed Successfully!")
        print(f"{'='*70}")
        
        print(f"\n📊 Extraction Results:")
        print(f"   • Document ID: {result.document_id}")
        print(f"   • Clauses extracted: {result.clauses_extracted}")
        print(f"   • Entities extracted: {result.entities_extracted}")
        print(f"   • Obligations: {result.obligations_extracted}")
        print(f"   • Risks: {result.risks_extracted}")
        
        print(f"\n🔗 Knowledge Graph:")
        print(f"   • RDF triples generated: {result.triples_generated}")
        print(f"   • Triples loaded to Fuseki: {result.triples_loaded}")
        print(f"   • Facts inferred by reasoner: {result.facts_inferred}")
        
        print(f"\n🔍 Vector Search:")
        print(f"   • Vectors indexed in Milvus: {result.vectors_indexed}")
        
        print(f"\n⏱️  Performance:")
        print(f"   • Total duration: {duration:.2f}s")
        print(f"   • Processing time: {result.total_duration_ms/1000:.2f}s")
        
        if result.ontology_extensions_generated:
            print(f"\n🔧 Ontology Evolution:")
            print(f"   • Extensions generated: {len(result.ontology_extensions_generated)}")
            for ext in result.ontology_extensions_generated:
                print(f"     - {Path(ext).name}")
        
        if result.rules_generated:
            print(f"\n📜 Rules Generated:")
            print(f"   • Rule files: {len(result.rules_generated)}")
            for rule in result.rules_generated:
                print(f"     - {Path(rule).name}")
        
        if result.validation_warnings:
            print(f"\n⚠️  Validation Warnings: {len(result.validation_warnings)}")
            for warning in result.validation_warnings[:5]:
                print(f"     - {warning}")
            if len(result.validation_warnings) > 5:
                print(f"     ... and {len(result.validation_warnings) - 5} more")
        
        if result.validation_errors:
            print(f"\n❌ Validation Errors: {len(result.validation_errors)}")
            for error in result.validation_errors[:5]:
                print(f"     - {error}")
            if len(result.validation_errors) > 5:
                print(f"     ... and {len(result.validation_errors) - 5} more")
        
        print(f"\n📁 Artifacts Saved:")
        print(f"   • RDF: agents/data/generated/rdf/")
        print(f"   • Ontology: agents/data/generated/ontology/")
        print(f"   • Rules: agents/data/generated/rules/")
        print(f"   • Logs: agents/logs/ingestion/")
        
        print(f"\n{'='*70}")
        print(f"✨ Ingestion Complete!")
        print(f"{'='*70}\n")
        
        print(f"💡 Next Steps:")
        print(f"   • Query the data: cd agents && uv run python tests/test_hybrid_rag_queries.py")
        print(f"   • View in Fuseki: http://localhost:3030/contracts")
        print(f"   • Check logs: agents/logs/ingestion/")
        
    except Exception as e:
        print(f"\n❌ Error processing document: {e}")
        logger.exception("Document processing failed", file=str(doc_path))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

