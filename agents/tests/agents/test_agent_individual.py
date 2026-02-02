#!/usr/bin/env python3
"""
Individual Agent Testing Framework

Tests each agent individually with detailed process explanations.
Each agent produces:
1. Standard output/results
2. Process explanation file (what was covered, why, gaps, etc.)

Usage:
    cd agents
    PYTHONPATH=src uv run python ../scripts/test_agent_individual.py --agent clause_extraction
    PYTHONPATH=src uv run python ../scripts/test_agent_individual.py --agent all
    PYTHONPATH=src uv run python ../scripts/test_agent_individual.py --agent ontology_designer --input-doc examples/sample_contract.pdf
"""

import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from agent_explanation import AgentExplanationBuilder
from logging_config import get_log_dir


async def test_clause_extraction_agent(document_path: Path):
    """Test ClauseExtractionAgent individually."""
    from agents.ingestion import DocumentIngestionAgent, ClauseExtractionAgent
    
    print("\n" + "="*70)
    print("🧪 TESTING: ClauseExtractionAgent")
    print("="*70)
    
    settings = get_settings()
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_dir = get_log_dir("ingestion") / "agent_tests"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    builder = AgentExplanationBuilder(
        agent_name="ClauseExtractionAgent",
        agent_type="extraction",
        session_id=session_id,
    )
    
    try:
        # Step 1: Document ingestion
        print("\n1️⃣ Ingesting document...")
        doc_agent = DocumentIngestionAgent(settings=settings)
        doc_result = await doc_agent.process(str(document_path))
        
        builder.set_input({
            "document_path": str(document_path),
            "document_type": doc_result.document_type,
            "page_count": doc_result.page_count,
            "text_length": len(doc_result.text),
        }, size=doc_result.page_count)
        
        print(f"   ✅ Document ingested: {doc_result.page_count} pages, {len(doc_result.text)} chars")
        
        # Step 2: Clause extraction
        print("\n2️⃣ Extracting clauses...")
        clause_agent = ClauseExtractionAgent(settings=settings)
        clause_result = await clause_agent.process(doc_result.text)
        
        builder.set_output({
            "clauses_extracted": len(clause_result.clauses),
            "clause_types": list(set(c.clause_type for c in clause_result.clauses)),
        }, count=len(clause_result.clauses))
        
        print(f"   ✅ Extracted {len(clause_result.clauses)} clauses")
        print(f"   📋 Clause types: {', '.join(set(c.clause_type for c in clause_result.clauses))}")
        
        # Coverage analysis
        print("\n3️⃣ Analyzing coverage...")
        expected_clause_types = [
            "TerminationClause", "PaymentClause", "ConfidentialityClause",
            "WarrantyClause", "LiabilityClause", "GoverningLawClause"
        ]
        
        found_types = set(c.clause_type for c in clause_result.clauses)
        missing_types = [t for t in expected_clause_types if t not in found_types]
        
        for clause_type in expected_clause_types:
            builder.add_coverage(
                clause_type,
                clause_type in found_types,
                f"{'Found' if clause_type in found_types else 'Not found'} in document"
            )
        
        coverage_pct = (len(found_types) / len(expected_clause_types)) * 100 if expected_clause_types else 0
        builder.set_coverage_analysis({
            "expected_types": expected_clause_types,
            "found_types": list(found_types),
            "missing_types": missing_types,
        }, percentage=coverage_pct)
        
        print(f"   📊 Coverage: {coverage_pct:.1f}% ({len(found_types)}/{len(expected_clause_types)} types)")
        if missing_types:
            print(f"   ⚠️  Missing types: {', '.join(missing_types)}")
        
        # Check for specific properties
        print("\n4️⃣ Checking extracted properties...")
        termination_clauses = [c for c in clause_result.clauses if c.clause_type == "TerminationClause"]
        if termination_clauses:
            has_notice_period = any(
                "notice" in str(c.attributes).lower() or "period" in str(c.attributes).lower()
                for c in termination_clauses
            )
            builder.add_coverage(
                "TerminationClause.noticePeriod",
                has_notice_period,
                "Notice period information in attributes" if has_notice_period else "Notice period not found in attributes"
            )
            if not has_notice_period:
                builder.add_gap("Notice period extraction", "Termination clauses found but notice periods not extracted")
        
        # Decisions and reasoning
        builder.add_decision(
            "Clause extraction strategy",
            f"Used LLM-based extraction to identify {len(clause_result.clauses)} clauses from {doc_result.page_count} pages",
            alternatives_considered=["Rule-based extraction", "Template matching"]
        )
        
        # Quality metrics
        avg_clause_length = sum(len(c.raw_text) for c in clause_result.clauses) / len(clause_result.clauses) if clause_result.clauses else 0
        builder.add_quality_metric("avg_clause_length", avg_clause_length)
        builder.add_quality_metric("clauses_per_page", len(clause_result.clauses) / doc_result.page_count if doc_result.page_count > 0 else 0)
        
        # Confidence
        if len(clause_result.clauses) > 0 and coverage_pct > 50:
            builder.set_confidence("high")
        elif len(clause_result.clauses) > 0:
            builder.set_confidence("medium")
        else:
            builder.set_confidence("low")
        
        # Limitations
        builder.add_limitation("LLM-based extraction may miss clauses with non-standard formatting")
        builder.add_limitation("Clause boundaries may not be perfectly accurate")
        
        # Save explanation
        explanation_file = builder.save(log_dir, "clause_extraction")
        print(f"\n✅ Explanation saved: {explanation_file}")
        
        return True
        
    except Exception as e:
        builder.add_error(str(e))
        explanation_file = builder.save(log_dir, "clause_extraction")
        print(f"\n❌ Error: {e}")
        print(f"   Explanation saved: {explanation_file}")
        return False


async def test_ontology_designer_agent(suggestions: list[dict]):
    """Test OntologyDesignerAgent individually."""
    from agents.schema_evolution import OntologyDesignerAgent
    
    print("\n" + "="*70)
    print("🧪 TESTING: OntologyDesignerAgent")
    print("="*70)
    
    settings = get_settings()
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_dir = get_log_dir("ontology") / "agent_tests"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    builder = AgentExplanationBuilder(
        agent_name="OntologyDesignerAgent",
        agent_type="generation",
        session_id=session_id,
    )
    
    try:
        builder.set_input({
            "suggestions_count": len(suggestions),
            "suggestions": suggestions,
        }, size=len(suggestions))
        
        print(f"\n1️⃣ Processing {len(suggestions)} ontology suggestions...")
        
        ontology_agent = OntologyDesignerAgent(settings=settings)
        
        results = []
        for i, suggestion in enumerate(suggestions, 1):
            print(f"\n   [{i}/{len(suggestions)}] Generating ontology for: {suggestion.get('name', 'Unknown')}")
            
            result = await ontology_agent.extend_ontology(
                concept_name=suggestion.get("name"),
                description=suggestion.get("description"),
                parent_class=suggestion.get("parent_class", "proc:Clause"),
            )
            
            results.append(result)
            
            builder.add_coverage(
                suggestion.get("name", "Unknown"),
                result.is_valid,
                result.error if not result.is_valid else "Successfully generated"
            )
            
            if result.is_valid:
                print(f"      ✅ Generated: {result.owl_class_name}")
                builder.add_output_file(result.file_path)
            else:
                print(f"      ❌ Failed: {result.error}")
                builder.add_error(f"Failed to generate {suggestion.get('name')}: {result.error}")
        
        valid_count = sum(1 for r in results if r.is_valid)
        builder.set_output({
            "ontologies_generated": valid_count,
            "ontologies_failed": len(results) - valid_count,
        }, count=valid_count)
        
        coverage_pct = (valid_count / len(suggestions)) * 100 if suggestions else 0
        builder.set_coverage_analysis({
            "total_suggestions": len(suggestions),
            "successful": valid_count,
            "failed": len(results) - valid_count,
        }, percentage=coverage_pct)
        
        builder.add_decision(
            "Ontology generation strategy",
            f"Generated {valid_count} valid ontologies from {len(suggestions)} suggestions using LLM-based OWL generation",
            alternatives_considered=["Manual OWL creation", "Template-based generation"]
        )
        
        builder.set_confidence("high" if coverage_pct > 80 else "medium" if coverage_pct > 50 else "low")
        
        explanation_file = builder.save(log_dir, "ontology_designer")
        print(f"\n✅ Explanation saved: {explanation_file}")
        
        return True
        
    except Exception as e:
        builder.add_error(str(e))
        explanation_file = builder.save(log_dir, "ontology_designer")
        print(f"\n❌ Error: {e}")
        print(f"   Explanation saved: {explanation_file}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test individual agents with detailed explanations")
    parser.add_argument("--agent", type=str, required=True, help="Agent to test: clause_extraction, ontology_designer, all")
    parser.add_argument("--input-doc", type=str, help="Input document path for extraction agents")
    parser.add_argument("--examples-dir", type=str, default="examples", help="Directory with example documents")
    
    args = parser.parse_args()
    
    if args.agent == "clause_extraction" or args.agent == "all":
        if args.input_doc:
            doc_path = Path(args.input_doc)
        else:
            # Find first example document
            examples_dir = Path(args.examples_dir)
            docs = list(examples_dir.glob("*.pdf")) + list(examples_dir.glob("*.docx"))
            if not docs:
                print(f"❌ No documents found in {examples_dir}")
                return
            doc_path = docs[0]
            print(f"📄 Using document: {doc_path}")
        
        if not doc_path.exists():
            print(f"❌ Document not found: {doc_path}")
            return
        
        await test_clause_extraction_agent(doc_path)
    
    if args.agent == "ontology_designer" or args.agent == "all":
        # Test with sample suggestions
        suggestions = [
            {
                "name": "DataProtectionClause",
                "description": "Clause related to data protection and privacy requirements",
                "parent_class": "proc:Clause",
            },
            {
                "name": "IntellectualPropertyClause",
                "description": "Clause covering intellectual property rights and ownership",
                "parent_class": "proc:Clause",
            },
        ]
        await test_ontology_designer_agent(suggestions)
    
    print("\n" + "="*70)
    print("✅ Agent testing complete!")
    print("="*70)
    print("\n📁 All explanations saved to logs/ingestion/agent_tests/ or logs/ontology/agent_tests/")


if __name__ == "__main__":
    asyncio.run(main())
