#!/usr/bin/env python3
"""
Test script for multi-hop retrieval questions on master agreement documents.

Tests the hybrid RAG strategy with questions ranging from simple to complex.
"""

import argparse
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents" / "src"))

from config import get_settings
from fuseki_client import FusekiClient
from vector_store import MilvusVectorStore
from agents import SPARQLGeneratorAgent, RAGOrchestratorAgent


# Multi-hop questions from simple to complex
MULTIHOP_QUESTIONS = [
    {
        "id": 1,
        "difficulty": "Simple",
        "question": "What is the total contract value?",
        "description": "Single-hop: Direct value lookup",
        "expected_sources": ["KG", "Vector"]
    },
    {
        "id": 2,
        "difficulty": "Medium",
        "question": "Which contracts have termination notice periods shorter than 30 days?",
        "description": "Two-hop: Find termination clauses, then filter by notice period",
        "expected_sources": ["KG", "Vector"]
    },
    {
        "id": 3,
        "difficulty": "Medium-Hard",
        "question": "What are the payment terms and associated late payment penalties?",
        "description": "Multi-hop: Find payment clauses, then find related penalty clauses",
        "expected_sources": ["KG", "Vector"]
    },
    {
        "id": 4,
        "difficulty": "Hard",
        "question": "Which contracts have high termination risk and what are their payment obligations?",
        "description": "Complex: Combine termination risk analysis with payment terms",
        "expected_sources": ["KG", "Vector"]
    },
    {
        "id": 5,
        "difficulty": "Expert",
        "question": "Analyze the compliance risks: identify contracts with short termination notice, high value, and late payment penalties, then summarize the overall risk profile",
        "description": "Expert: Multi-dimensional analysis combining termination, value, and payment risks",
        "expected_sources": ["KG", "Vector"]
    }
]


def print_header(text: str):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_question_header(q: dict, index: int, total: int):
    """Print question header."""
    print(f"\n{'─' * 70}")
    print(f"  Question {index}/{total} [{q['difficulty']}]")
    print(f"  {q['question']}")
    print(f"  Description: {q['description']}")
    print(f"  Expected Sources: {', '.join(q['expected_sources'])}")
    print(f"{'─' * 70}\n")


async def test_question(
    rag_agent: RAGOrchestratorAgent,
    question_data: dict,
    verbose: bool = True
) -> dict:
    """Test a single question."""
    question = question_data["question"]
    
    if verbose:
        print(f"  ⏳ Processing...")
    
    start_time = datetime.now()
    
    try:
        result = await rag_agent.process(question, enable_logging=True)
        
        duration = (datetime.now() - start_time).total_seconds()
        
        return {
            "question_id": question_data["id"],
            "difficulty": question_data["difficulty"],
            "question": question,
            "success": result.success,
            "answer": result.answer,
            "confidence": result.confidence,
            "kg_facts_count": len(result.kg_facts),
            "vector_context_count": len(result.vector_context),
            "sparql_query": result.sparql_query,
            "log_file": result.log_file,
            "duration_seconds": duration,
            "error": result.error,
        }
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        return {
            "question_id": question_data["id"],
            "difficulty": question_data["difficulty"],
            "question": question,
            "success": False,
            "error": str(e),
            "duration_seconds": duration,
        }


async def main():
    parser = argparse.ArgumentParser(description="Test multi-hop retrieval questions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--question", "-q", type=int, help="Test specific question by ID (1-5)")
    parser.add_argument("--output", "-o", type=str, help="Save results to JSON file")
    args = parser.parse_args()
    
    print_header("🧪 MULTI-HOP RETRIEVAL TEST")
    print("\n  Testing hybrid RAG strategy with questions ranging from simple to complex")
    print("  All sessions are logged to logs/retrieval/sessions/")
    
    # Initialize components
    print("\n  Initializing components...")
    settings = get_settings()
    client = FusekiClient(settings)
    vector_store = MilvusVectorStore(settings)
    sparql_agent = SPARQLGeneratorAgent(fuseki_client=client, settings=settings)
    
    # Use proper log_dir for retrieval (defaults to logs/retrieval)
    rag_agent = RAGOrchestratorAgent(
        fuseki_client=client,
        sparql_agent=sparql_agent,
        vector_store=vector_store,
        settings=settings,
        # Don't override log_dir - let it use default logs/retrieval
    )
    print("  ✅ Components ready")
    
    # Select questions to test
    if args.question:
        questions = [q for q in MULTIHOP_QUESTIONS if q["id"] == args.question]
        if not questions:
            print(f"  ❌ Question {args.question} not found")
            return
    else:
        questions = MULTIHOP_QUESTIONS
    
    print(f"\n  Testing {len(questions)} question(s)...")
    
    # Test each question
    results = []
    for i, question_data in enumerate(questions, 1):
        print_question_header(question_data, i, len(questions))
        
        result = await test_question(rag_agent, question_data, args.verbose)
        results.append(result)
        
        # Print results
        if result["success"]:
            print(f"  ✅ SUCCESS")
            print(f"     Confidence: {result['confidence']:.0%}")
            print(f"     KG Facts: {result['kg_facts_count']}")
            print(f"     Vector Results: {result['vector_context_count']}")
            print(f"     Duration: {result['duration_seconds']:.1f}s")
            
            if args.verbose:
                print(f"\n  📝 Answer Preview:")
                preview = result["answer"][:300]
                for line in preview.split('\n')[:4]:
                    print(f"     {line[:65]}")
                if len(result["answer"]) > 300:
                    print("     ...")
            
            if result["log_file"]:
                print(f"\n  📄 Log: {result['log_file']}")
        else:
            print(f"  ❌ FAILED: {result.get('error', 'Unknown error')}")
        
        print()
    
    # Print summary
    print_header("📊 TEST SUMMARY")
    
    successful = sum(1 for r in results if r["success"])
    total = len(results)
    avg_confidence = sum(r.get("confidence", 0) for r in results if r["success"]) / successful if successful > 0 else 0
    avg_duration = sum(r["duration_seconds"] for r in results) / total if total > 0 else 0
    
    print(f"\n  Total Questions: {total}")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {total - successful}")
    print(f"  📈 Average Confidence: {avg_confidence:.0%}")
    print(f"  ⏱️  Average Duration: {avg_duration:.1f}s")
    
    print(f"\n  By Difficulty:")
    for difficulty in ["Simple", "Medium", "Medium-Hard", "Hard", "Expert"]:
        diff_results = [r for r in results if r.get("difficulty") == difficulty]
        if diff_results:
            diff_success = sum(1 for r in diff_results if r["success"])
            print(f"     {difficulty}: {diff_success}/{len(diff_results)} passed")
    
    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "successful": successful,
                    "failed": total - successful,
                    "avg_confidence": avg_confidence,
                    "avg_duration": avg_duration,
                },
                "results": results,
            }, f, indent=2)
        print(f"\n  💾 Results saved to: {output_path}")
    else:
        # Auto-save to logs/retrieval
        from logging_config import get_log_dir
        output_dir = get_log_dir("retrieval")
        output_file = output_dir / f"multihop_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "summary": {
                    "total": total,
                    "successful": successful,
                    "failed": total - successful,
                    "avg_confidence": avg_confidence,
                    "avg_duration": avg_duration,
                },
                "results": results,
            }, f, indent=2)
        print(f"\n  💾 Results auto-saved to: {output_file}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    import argparse
    asyncio.run(main())
