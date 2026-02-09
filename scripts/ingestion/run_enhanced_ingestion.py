"""
Enhanced Ingestion Pipeline - End-to-end script for batch document processing.

This script demonstrates the complete enhanced ingestion pipeline:
1. Scan directory recursively for documents
2. Classify and organize files
3. Process documents in parallel batches
4. Extract entities and clauses
5. Generate RDF and load to Fuseki
6. Update ontology dynamically
7. Index vectors for retrieval

Usage:
    python scripts/ingestion/run_enhanced_ingestion.py --directory examples
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents/src"))

from agents.ingestion.directory_scanner import DirectoryScannerAgent
from agents.ingestion.batch_processor import BatchProcessorAgent
from agents.ingestion.enhanced_document_ingestion import (
    EnhancedDocumentIngestionAgent
)
from agents.ingestion.ingestion_orchestrator import (
    IngestionOrchestrator,
    IngestionConfig
)
from config import get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


async def progress_callback(progress):
    """Callback for batch processing progress."""
    logger.info(
        f"Progress: {progress.completed}/{progress.total_tasks} completed, "
        f"{progress.failed} failed, {progress.in_progress} in progress"
    )


async def process_single_document(discovered_file, override: bool = False):
    """Process a single discovered file through the pipeline."""
    settings = get_settings()
    
    try:
        # Step 1: Extract document text
        doc_agent = EnhancedDocumentIngestionAgent(settings=settings)
        extracted_doc = await doc_agent.process(discovered_file.path)
        
        logger.info(
            f"Extracted {discovered_file.filename}: "
            f"{len(extracted_doc.text)} chars, "
            f"confidence: {extracted_doc.confidence:.2f}"
        )
        
        # Step 2: Run through full ingestion pipeline
        orchestrator = IngestionOrchestrator(
            settings=settings,
            config=IngestionConfig(
                enable_shacl_validation=True,
                enable_reasoning=True,
                enable_vector_indexing=True,
                enable_pattern_detection=True,
                enable_schema_governance=True
            )
        )
        
        result = await orchestrator.ingest(
            str(discovered_file.path),
            override=override
        )
        
        return {
            "file": discovered_file.filename,
            "success": result.success,
            "clauses": result.clauses_extracted,
            "entities": result.entities_extracted,
            "triples": result.triples_loaded,
            "confidence": extracted_doc.confidence
        }
        
    except Exception as e:
        logger.error(
            f"Failed to process {discovered_file.filename}: {e}",
            exc_info=True
        )
        return {
            "file": discovered_file.filename,
            "success": False,
            "error": str(e)
        }


async def main(directory: str, max_files: int = None, no_llm_classify: bool = False, override: bool = False):
    """
    Main ingestion pipeline.
    
    Args:
        directory: Directory to scan for documents
        max_files: Maximum number of files to process (for testing)
        no_llm_classify: Skip LLM classification during scanning (faster, less accurate)
        override: Force reprocess documents even if already processed
    """
    start_time = datetime.now()
    settings = get_settings()
    
    logger.info("=" * 60)
    logger.info("Enhanced Ingestion Pipeline Starting")
    logger.info("=" * 60)
    logger.info(f"Directory: {directory}")
    logger.info(f"Max files: {max_files or 'unlimited'}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    logger.info(f"LLM Classification: {'disabled' if no_llm_classify else 'enabled'}")
    logger.info(f"Override mode: {'enabled' if override else 'disabled'}")
    logger.info("")
    
    # Step 1: Scan directory
    logger.info("Step 1: Scanning directory...")
    # Create scanner - if no_llm_classify, we'll manually set llm to None after init
    scanner = DirectoryScannerAgent(settings=settings)
    if no_llm_classify:
        scanner.llm = None  # Disable LLM classification
        logger.info("LLM classification disabled - using simple file-based classification")
    scan_result = await scanner.process(directory)
    
    logger.info(f"Scan complete:")
    logger.info(f"  Total files: {scan_result.total_files}")
    logger.info(f"  Supported: {scan_result.supported_files}")
    logger.info(f"  Unsupported: {scan_result.unsupported_files}")
    logger.info(f"  By type: {scan_result.files_by_type}")
    logger.info(f"  By supplier: {scan_result.files_by_supplier}")
    logger.info("")
    
    # Filter to supported files
    files_to_process = [
        f for f in scan_result.discovered_files
        if f.category.value != "unsupported"
    ]
    
    # Limit if requested
    if max_files:
        files_to_process = files_to_process[:max_files]
        logger.info(f"Limited to {max_files} files for testing")
    
    if not files_to_process:
        logger.warning("No files to process!")
        return
    
    # Step 2: Batch process documents
    logger.info(
        f"Step 2: Processing {len(files_to_process)} documents..."
    )
    
    batch_processor = BatchProcessorAgent(
        settings=settings,
        max_concurrent=3,  # Process 3 files at a time
        max_retries=1
    )
    
    # Create a wrapper function that includes override parameter
    async def process_with_override(file):
        return await process_single_document(file, override=override)
    
    batch_result = await batch_processor.process({
        "files": files_to_process,
        "processor_fn": process_with_override,
        "progress_callback": progress_callback
    })
    
    # Step 3: Report results
    logger.info("")
    logger.info("=" * 60)
    logger.info("Ingestion Complete!")
    logger.info("=" * 60)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    logger.info(f"Total duration: {duration:.1f}s")
    logger.info(f"Files processed: {batch_result.total_files}")
    logger.info(f"Successful: {batch_result.successful}")
    logger.info(f"Failed: {batch_result.failed}")
    logger.info(f"Skipped: {batch_result.skipped}")
    
    if batch_result.successful > 0:
        avg_time = (
            batch_result.total_duration_ms / batch_result.successful
        )
        logger.info(f"Average time per file: {avg_time:.0f}ms")
    
    # Show successful files
    if batch_result.successful > 0:
        logger.info("")
        logger.info("Successfully processed files:")
        for task in batch_result.tasks:
            if task.status == "completed" and task.result:
                result = task.result
                logger.info(
                    f"  ✓ {result['file']}: "
                    f"{result.get('clauses', 0)} clauses, "
                    f"{result.get('entities', 0)} entities, "
                    f"{result.get('triples', 0)} triples"
                )
    
    # Show errors
    if batch_result.errors:
        logger.info("")
        logger.info("Errors:")
        for error in batch_result.errors:
            logger.error(f"  ✗ {error['file']}: {error['error']}")
    
    logger.info("")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enhanced ingestion pipeline for contract documents"
    )
    parser.add_argument(
        "--directory",
        type=str,
        default="examples",
        help="Directory to scan for documents"
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of files to process (for testing)"
    )
    parser.add_argument(
        "--no-llm-classify",
        action="store_true",
        help="Skip LLM classification during scanning (faster, use if LLM issues)"
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="Force reprocess documents even if already processed"
    )
    
    args = parser.parse_args()
    
    # Run the pipeline
    asyncio.run(main(args.directory, args.max_files, args.no_llm_classify, args.override))


