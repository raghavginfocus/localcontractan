#!/usr/bin/env python3
"""
Test SPARQL generation for specific queries to verify correctness.
"""
import asyncio
import requests
import json

API_URL = "http://localhost:8001"

async def test_query(question: str):
    """Test a single query and show the SPARQL generated."""
    print(f"\n{'='*80}")
    print(f"QUESTION: {question}")
    print(f"{'='*80}")
    
    response = requests.post(
        f"{API_URL}/api/v1/query",
        json={"query": question},
        timeout=120
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\nANSWER: {result.get('answer', 'No answer')}")
        print(f"\nCONFIDENCE: {result.get('confidence', 0)}")
        print(f"\nSOURCES: {len(result.get('sources', []))} sources")
        
        # Print sources
        for i, source in enumerate(result.get('sources', [])[:3], 1):
            print(f"\nSource {i}:")
            print(f"  Content: {source.get('content', '')[:200]}...")
            print(f"  Score: {source.get('score', 0)}")
    else:
        print(f"\nERROR: {response.status_code}")
        print(response.text)

async def main():
    """Run test queries."""
    
    # Test queries from the logs
    queries = [
        "What are the termination clauses in the contracts?",
        "What are the specific risks associated with termination clauses?",
        "What are the notice periods for termination clauses?",
    ]
    
    for query in queries:
        await test_query(query)
        await asyncio.sleep(2)  # Brief pause between queries

if __name__ == "__main__":
    asyncio.run(main())


