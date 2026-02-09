#!/usr/bin/env python3
"""
Directly generate and display SPARQL queries for test questions.
"""
import asyncio
import sys
sys.path.insert(0, 'src')

from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from config import get_settings

async def show_query(question: str):
    """Generate and display SPARQL for a question."""
    print(f"\n{'='*80}")
    print(f"QUESTION: {question}")
    print(f"{'='*80}\n")
    
    settings = get_settings()
    generator = SPARQLGeneratorAgent(settings=settings)
    
    result = await generator.process(question)
    
    print(f"QUERY TYPE: {result.query_type}")
    print(f"\nSPARQL QUERY:")
    print("-" * 80)
    print(result.query)
    print("-" * 80)
    print(f"\nEXPLANATION: {result.explanation}\n")

async def main():
    """Show SPARQL for test queries."""
    
    queries = [
        "What are the termination clauses in the contracts?",
        "What are the specific risks associated with termination clauses?",
        "What are the notice periods for termination clauses?",
        "What are the common types of termination clauses?",
    ]
    
    for query in queries:
        await show_query(query)

if __name__ == "__main__":
    asyncio.run(main())


