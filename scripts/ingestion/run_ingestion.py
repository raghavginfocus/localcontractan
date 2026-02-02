#!/usr/bin/env python3
"""
Run the full ingestion pipeline on a contract document.

Usage:
    # From text
    uv run python scripts/run_ingestion.py --text "Your contract text here..."
    
    # From file
    uv run python scripts/run_ingestion.py --file path/to/contract.pdf
    
    # Sample contract
    uv run python scripts/run_ingestion.py --sample
"""

import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from agents import (
    IngestionOrchestrator,
    IngestionConfig,
    OntologyEvolutionMode,
)
from config import get_settings


# Sample contract text for testing
SAMPLE_CONTRACT = """
IT SERVICES AGREEMENT

This IT Services Agreement ("Agreement") is entered into as of January 1, 2024 
("Effective Date") between:

ABC Corporation, a Delaware corporation with offices at 123 Tech Park, 
San Francisco, CA 94105 ("Buyer")

and

XYZ Solutions Inc., a California corporation with offices at 456 Innovation Way, 
Palo Alto, CA 94301 ("Supplier")

RECITALS

WHEREAS, Buyer desires to engage Supplier to provide certain information technology 
services; and WHEREAS, Supplier has the expertise and capability to provide such services;

NOW, THEREFORE, in consideration of the mutual covenants contained herein, 
the parties agree as follows:

ARTICLE 1 - SCOPE OF SERVICES

1.1 Services. Supplier shall provide cloud infrastructure management, software 
development, and technical support services as described in Exhibit A.

1.2 Service Levels. Supplier shall maintain a minimum uptime of 99.9% for all 
production systems.

ARTICLE 2 - TERM AND TERMINATION

2.1 Term. This Agreement shall commence on the Effective Date and continue for 
a period of twenty-four (24) months, unless earlier terminated.

2.2 Termination for Convenience. Either party may terminate this Agreement for 
convenience by providing fifteen (15) days prior written notice to the other party.

2.3 Termination for Cause. Either party may terminate this Agreement immediately 
upon written notice if the other party materially breaches this Agreement and fails 
to cure such breach within thirty (30) days of receiving written notice.

ARTICLE 3 - COMPENSATION

3.1 Fees. Buyer shall pay Supplier a total amount of Five Hundred Thousand Dollars 
($500,000.00) for the services described herein.

3.2 Payment Terms. Buyer shall pay all invoices within thirty (30) days of receipt. 
Invoices not paid within such period shall accrue interest at 1.5% per month.

3.3 Late Payment Penalty. If payment is not received within forty-five (45) days, 
Supplier may charge a late payment penalty of 2% of the outstanding amount.

ARTICLE 4 - CONFIDENTIALITY

4.1 Confidential Information. Each party agrees to maintain the confidentiality of 
all proprietary information disclosed by the other party for a period of three (3) 
years following termination of this Agreement.

ARTICLE 5 - INDEMNIFICATION

5.1 Indemnification by Supplier. Supplier shall indemnify, defend, and hold harmless 
Buyer from any claims arising from Supplier's negligence or breach of this Agreement.

5.2 Indemnification by Buyer. Buyer shall indemnify, defend, and hold harmless 
Supplier from any claims arising from Buyer's misuse of the services.

ARTICLE 6 - LIMITATION OF LIABILITY

6.1 Cap on Liability. Neither party's total liability under this Agreement shall 
exceed the total amount paid or payable under this Agreement.

6.2 Exclusion of Damages. Neither party shall be liable for any indirect, incidental, 
consequential, or punitive damages.

ARTICLE 7 - GOVERNING LAW

7.1 Governing Law. This Agreement shall be governed by and construed in accordance 
with the laws of the State of California.

7.2 Dispute Resolution. Any disputes arising under this Agreement shall be resolved 
through binding arbitration in San Francisco, California.

IN WITNESS WHEREOF, the parties have executed this Agreement as of the date first 
written above.

ABC Corporation                    XYZ Solutions Inc.
By: ____________________          By: ____________________
Name: John Smith                   Name: Jane Doe
Title: CEO                         Title: President
Date: January 1, 2024             Date: January 1, 2024
"""


def print_banner():
    """Print script banner."""
    print("\n" + "=" * 70)
    print("  🏭 CONTRACT INGESTION PIPELINE")
    print("=" * 70 + "\n")


def print_result(result):
    """Print ingestion result in a nice format."""
    print("\n" + "-" * 70)
    print("  📊 INGESTION RESULTS")
    print("-" * 70 + "\n")
    
    status_icon = "✅" if result.success else "❌"
    print(f"  Status: {status_icon} {'SUCCESS' if result.success else 'FAILED'}")
    print(f"  Document ID: {result.document_id}")
    print(f"  Total Duration: {result.total_duration_ms:.0f}ms\n")
    
    print("  📈 EXTRACTION METRICS:")
    print("  " + "-" * 66)
    print(f"  • Clauses extracted: {result.clauses_extracted}")
    print(f"  • Entities extracted: {result.entities_extracted}")
    print(f"  • Obligations extracted: {result.obligations_extracted}")
    print(f"  • Risks extracted: {result.risks_extracted}")
    print(f"  • Triples generated: {result.triples_generated}")
    print(f"  • Triples loaded: {result.triples_loaded}")
    print(f"  • Facts inferred: {result.facts_inferred}")
    print(f"  • Vectors indexed: {result.vectors_indexed}\n")
    
    print("  📋 PIPELINE STEPS:")
    print("  " + "-" * 66)
    for step in result.steps:
        step_icon = "✅" if step.success else "❌"
        print(f"  {step_icon} {step.step_name}: {step.duration_ms:.0f}ms")
        if step.error:
            print(f"       └─ Error: {step.error}")
    
    if result.validation_errors:
        print("\n  ⚠️ VALIDATION ERRORS:")
        print("  " + "-" * 66)
        for error in result.validation_errors[:5]:
            print(f"  • {error}")
        if len(result.validation_errors) > 5:
            print(f"  ... and {len(result.validation_errors) - 5} more")
    
    if result.validation_warnings:
        print("\n  ℹ️ VALIDATION WARNINGS:")
        print("  " + "-" * 66)
        for warning in result.validation_warnings[:5]:
            print(f"  • {warning}")
        if len(result.validation_warnings) > 5:
            print(f"  ... and {len(result.validation_warnings) - 5} more")
    
    if result.ontology_suggestions:
        print("\n  💡 ONTOLOGY SUGGESTIONS:")
        print("  " + "-" * 66)
        for suggestion in result.ontology_suggestions[:3]:
            print(f"  • {suggestion['type']}: {suggestion['name']}")
            print(f"    {suggestion['description']}")
    
    if result.error:
        print(f"\n  ❌ ERROR: {result.error}")
    
    print("\n" + "=" * 70 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Run the contract ingestion pipeline."
    )
    parser.add_argument(
        "--text",
        type=str,
        help="Contract text to ingest",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to contract file (PDF, DOCX, TXT)",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use sample contract text",
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        help="Document ID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--skip-reasoning",
        action="store_true",
        help="Skip reasoning step",
    )
    parser.add_argument(
        "--skip-vectors",
        action="store_true",
        help="Skip vector indexing step",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="Save result to JSON file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    # Determine input
    if args.sample:
        print("  📄 Using sample contract text")
        text = SAMPLE_CONTRACT
        file_path = None
    elif args.text:
        print(f"  📄 Using provided text ({len(args.text)} chars)")
        text = args.text
        file_path = None
    elif args.file:
        print(f"  📄 Using file: {args.file}")
        text = None
        file_path = args.file
    else:
        print("  ❌ Error: Please provide --text, --file, or --sample")
        return
    
    # Configure pipeline
    config = IngestionConfig(
        enable_reasoning=not args.skip_reasoning,
        enable_vector_indexing=not args.skip_vectors,
        fail_on_validation_error=False,
    )
    
    settings = get_settings()
    print(f"  🤖 Using LLM: {settings.llm_provider} ({settings.ollama_model})")
    print(f"  🗄️ Fuseki: {settings.fuseki_url}/{settings.fuseki_dataset}")
    print(f"  📦 Milvus: {settings.milvus_host}:{settings.milvus_port}")
    
    # Create orchestrator and run
    orchestrator = IngestionOrchestrator(config=config, settings=settings)
    
    print("\n  ⏳ Starting ingestion pipeline...\n")
    
    start = datetime.now()
    result = await orchestrator.ingest(
        file_path=file_path,
        text=text,
        document_id=args.doc_id,
    )
    
    print_result(result)
    
    # Save JSON if requested
    if args.output_json:
        output_path = Path(args.output_json)
        with open(output_path, "w") as f:
            json.dump(
                orchestrator.get_pipeline_summary(result),
                f,
                indent=2,
                default=str,
            )
        print(f"  📁 Saved result to: {output_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
