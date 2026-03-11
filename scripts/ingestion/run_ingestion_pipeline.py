#!/usr/bin/env python3
"""
Run the complete ingestion pipeline on documents in the examples folder.

This script processes PDF and DOCX files through the full agentic pipeline:
1. Document ingestion
2. Clause extraction
3. Entity extraction
4. Obligation/risk analysis
5. Ontology alignment
6. RDF generation
7. Validation
8. Fuseki loading
9. Reasoning
10. Vector indexing

Usage:
    cd agents
    uv run python ../scripts/ingestion/run_ingestion_pipeline.py
    
    # With Docling pipeline
    uv run python ../scripts/ingestion/run_ingestion_pipeline.py --use-docling
    
    # Override existing documents
    uv run python ../scripts/ingestion/run_ingestion_pipeline.py --override
"""  # noqa: E501

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig,
    OntologyEvolutionMode,
)
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning("tqdm not available. Install with: uv add tqdm")


async def main():
    """Run ingestion pipeline on example documents."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run ingestion pipeline")
    parser.add_argument(
        "--override",
        action="store_true",
        help="Reprocess documents even if already processed",
    )
    parser.add_argument(
        "--skip-duplicates",
        action="store_true",
        help="Skip documents that have already been processed (default behavior)",
    )
    args = parser.parse_args()
    
    # Get project root
    project_root = Path(__file__).parent.parent
    examples_dir = project_root / "examples"
    
    # Find all PDF and DOCX files
    documents = []
    for ext in ["*.pdf", "*.docx"]:
        documents.extend(examples_dir.glob(ext))
    
    # Filter out the "copy" file to avoid duplicates
    documents = [d for d in documents if "copy" not in d.name.lower()]
    
    if not documents:
        print("❌ No PDF or DOCX files found in examples folder")
        return
    
    print(f"\n{'='*70}")
    print(f"🚀 Contract Ingestion Pipeline")
    print(f"{'='*70}")
    print(f"\n📁 Found {len(documents)} document(s) to process:")
    for doc in documents:
        print(f"   • {doc.name}")
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
        generate_shacl=True,  # Enable SHACL auto-generation
        enable_pattern_detection=True,  # Enable pattern detection for rule generation
        enable_schema_governance=True,  # Enable schema versioning
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
    
    # Prepare batch items for parallel processing
    batch_items = [
        {
            "file_path": str(doc_path),
            "document_id": None,  # Will be auto-generated
        }
        for doc_path in documents
    ]
    
    print(f"\n🚀 Processing {len(batch_items)} documents in parallel...")
    print(f"   • Max concurrent: 10 documents")
    print(f"   • Parallel extraction: Enabled")
    print()
    
    # Process all documents in parallel using batch processing
    start_time = datetime.now()
    
    try:
        # Use tqdm progress bar if available
        if TQDM_AVAILABLE:
            print("📊 Progress:")
            with tqdm(total=len(batch_items), desc="Ingesting", unit="doc",
                     bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]") as pbar:
                results = await orchestrator.ingest_batch(
                    items=batch_items,
                    max_concurrent=10,
                    extract_documents_parallel=True,
                    progress_callback=lambda: pbar.update(0)  # Callback for updates
                )
                pbar.n = len(batch_items)  # Complete the bar
                pbar.refresh()
        else:
            results = await orchestrator.ingest_batch(
                items=batch_items,
                max_concurrent=10,
                extract_documents_parallel=True,
            )
        
        # Print summary for each document
        for i, (result, doc_path) in enumerate(zip(results, documents), 1):
            if result and result.success:
                print(f"\n{'─'*70}")
                print(f"✅ Document {i}/{len(documents)}: {doc_path.name}")
                print(f"{'─'*70}")
                print(f"   • Document ID: {result.document_id}")
                print(f"   • Clauses extracted: {result.clauses_extracted}")
                print(f"   • Entities extracted: {result.entities_extracted}")
                print(f"   • Obligations: {result.obligations_extracted}")
                print(f"   • Risks: {result.risks_extracted}")
                print(f"   • Triples generated: {result.triples_generated}")
                print(f"   • Triples loaded: {result.triples_loaded}")
                print(f"   • Facts inferred: {result.facts_inferred}")
                print(f"   • Vectors indexed: {result.vectors_indexed}")
                print(f"   • Duration: {result.total_duration_ms/1000:.2f}s")
                
                if result.ontology_extensions_generated:
                    print(f"   • Ontology extensions: {len(result.ontology_extensions_generated)}")
                
                if result.rules_generated:
                    print(f"   • Rules generated: {len(result.rules_generated)}")
                
                if result.shacl_shapes_generated:
                    print(f"   • SHACL shapes generated: {len(result.shacl_shapes_generated)}")
                
                if result.patterns_detected:
                    print(f"   • Patterns detected: {len(result.patterns_detected)}")
                
                if result.validation_warnings:
                    print(f"   ⚠️  Validation warnings: {len(result.validation_warnings)}")
                
                if result.validation_errors:
                    print(f"   ❌ Validation errors: {len(result.validation_errors)}")
            elif result:
                print(f"\n❌ Document {i}/{len(documents)}: {doc_path.name} - Failed")
                if result.error:
                    print(f"   Error: {result.error}")
            else:
                print(f"\n❌ Document {i}/{len(documents)}: {doc_path.name} - No result")
                
    except Exception as e:
        print(f"\n❌ Batch processing error: {e}")
        logger.exception("Batch processing failed")
        results = [None] * len(documents)
    
    # Overall summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    successful = sum(1 for r in results if r and r.success)
    failed = len(results) - successful
    
    print(f"\n{'='*70}")
    print(f"📊 Pipeline Summary")
    print(f"{'='*70}")
    print(f"\n📈 Overall Statistics:")
    print(f"   • Total documents: {len(documents)}")
    print(f"   • Successful: {successful}")
    print(f"   • Failed: {failed}")
    print(f"   • Total duration: {total_duration:.2f}s")
    
    if successful > 0:
        total_clauses = sum(r.clauses_extracted for r in results if r)
        total_entities = sum(r.entities_extracted for r in results if r)
        total_obligations = sum(r.obligations_extracted for r in results if r)
        total_risks = sum(r.risks_extracted for r in results if r)
        total_triples = sum(r.triples_generated for r in results if r)
        total_vectors = sum(r.vectors_indexed for r in results if r)
        
        print(f"\n📊 Aggregated Metrics:")
        print(f"   • Total clauses: {total_clauses}")
        print(f"   • Total entities: {total_entities}")
        print(f"   • Total obligations: {total_obligations}")
        print(f"   • Total risks: {total_risks}")
        print(f"   • Total triples: {total_triples}")
        print(f"   • Total vectors: {total_vectors}")
        
        # Ontology evolution summary
        all_extensions = []
        all_rules = []
        for r in results:
            if r:
                all_extensions.extend(r.ontology_extensions_generated)
                all_rules.extend(r.rules_generated)
        
        if all_extensions:
            print(f"\n🔧 Ontology Evolution:")
            print(f"   • Extensions generated: {len(all_extensions)}")
            for ext in all_extensions[:5]:  # Show first 5
                print(f"     - {Path(ext).name}")
            if len(all_extensions) > 5:
                print(f"     ... and {len(all_extensions) - 5} more")
        
        if all_rules:
            print(f"\n📜 Rules Generated:")
            print(f"   • Rule files: {len(all_rules)}")
            for rule in all_rules[:5]:  # Show first 5
                print(f"     - {Path(rule).name}")
            if len(all_rules) > 5:
                print(f"     ... and {len(all_rules) - 5} more")
    
    print(f"\n{'='*70}")
    print(f"✨ Pipeline execution complete!")
    print(f"{'='*70}\n")
    
    # Exit with error code if any failed
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


