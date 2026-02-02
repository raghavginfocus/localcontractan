"""
Test Knowledge Graph Queries - Demonstrating RDFS Reasoning & Hybrid RAG

This test suite demonstrates:
1. Simple SPARQL queries (basic graph traversal)
2. RDFS reasoning queries (using ontology relationships)
3. Complex hybrid queries (SPARQL + Vector Search + LLM)

Purpose: Justify why we need a knowledge graph with proper ontology
"""

import asyncio
from pathlib import Path
import json
from datetime import datetime

from contract_kg.config import get_settings
from contract_kg.fuseki_client import FusekiClient
from contract_kg.vector_store import MilvusVectorStore
from contract_kg.agents.retrieval.rag_orchestrator import RAGOrchestratorAgent


class KnowledgeGraphQueryTester:
    """Test suite for demonstrating KG query capabilities."""
    
    def __init__(self):
        self.settings = get_settings()
        self.fuseki = FusekiClient(settings=self.settings)
        self.vector_store = MilvusVectorStore(settings=self.settings)
        self.rag_agent = RAGOrchestratorAgent(
            fuseki_client=self.fuseki,
            vector_store=self.vector_store,
            settings=self.settings
        )
        self.results = []
    
    def log_query_result(self, level: str, query_name: str, 
                        query: str, results: list, 
                        explanation: str, time_ms: float):
        """Log query results for analysis."""
        result = {
            "level": level,
            "query_name": query_name,
            "query": query,
            "result_count": len(results),
            "results": results[:5],  # First 5 results
            "explanation": explanation,
            "time_ms": time_ms,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        return result
    
    # =========================================================================
    # LEVEL 1: SIMPLE QUERIES (Basic Graph Traversal)
    # =========================================================================
    
    def test_level1_basic_contract_count(self):
        """
        Level 1: Count all contracts
        
        Why this matters:
        - Basic graph traversal
        - Tests data loading
        - Foundation for more complex queries
        """
        print("\n" + "="*70)
        print("LEVEL 1: SIMPLE QUERY - Count All Contracts")
        print("="*70)
        
        query = """
        SELECT (COUNT(DISTINCT ?contract) as ?count)
        WHERE {
            ?contract a proc:Contract .
        }
        """
        
        import time
        start = time.time()
        results = self.fuseki.execute_select(query)
        time_ms = (time.time() - start) * 1000
        
        count = int(results[0]['count']) if results else 0
        
        explanation = f"""
        Found {count} contracts in the knowledge graph.
        
        This simple query demonstrates:
        - Basic RDF triple pattern matching (?contract a proc:Contract)
        - Graph traversal using SPARQL
        - Data successfully loaded into Fuseki
        
        Without KG: Would need to scan all documents manually
        With KG: Instant answer from structured data
        """
        
        print(f"✅ Result: {count} contracts")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(explanation)
        
        self.log_query_result(
            "Level 1 - Simple",
            "Count All Contracts",
            query,
            results,
            explanation,
            time_ms
        )
        
        return results
    
    def test_level1_list_all_clause_types(self):
        """
        Level 1: List all distinct clause types
        
        Why this matters:
        - Shows ontology coverage
        - Identifies what clause types exist
        - Validates clause extraction
        """
        print("\n" + "="*70)
        print("LEVEL 1: SIMPLE QUERY - List All Clause Types")
        print("="*70)
        
        query = """
        SELECT DISTINCT ?clauseType (COUNT(?clause) as ?count)
        WHERE {
            ?clause a ?clauseType .
            ?clauseType rdfs:subClassOf* proc:Clause .
        }
        GROUP BY ?clauseType
        ORDER BY DESC(?count)
        """
        
        import time
        start = time.time()
        results = self.fuseki.execute_select(query)
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Found {len(results)} distinct clause types across all contracts.
        
        This query demonstrates:
        - RDFS reasoning (rdfs:subClassOf* finds all subclasses)
        - Aggregation (COUNT, GROUP BY)
        - Ontology structure utilization
        
        Top clause types:
        {chr(10).join([f"  • {r['clauseType'].split('#')[-1]}: {r['count']} instances" 
                       for r in results[:5]])}
        
        Without KG: Would need manual categorization
        With KG: Automatic classification using ontology
        """
        
        print(f"✅ Result: {len(results)} clause types")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(explanation)
        
        self.log_query_result(
            "Level 1 - Simple",
            "List All Clause Types",
            query,
            results,
            explanation,
            time_ms
        )
        
        return results
    
    # =========================================================================
    # LEVEL 2: RDFS REASONING QUERIES (Using Ontology Relationships)
    # =========================================================================
    
    def test_level2_find_termination_clauses_with_reasoning(self):
        """
        Level 2: Find all termination-related clauses using RDFS reasoning
        
        Why this matters:
        - Uses ontology hierarchy (subClassOf relationships)
        - Finds both direct instances AND subclass instances
        - Demonstrates semantic reasoning
        """
        print("\n" + "="*70)
        print("LEVEL 2: RDFS REASONING - Find Termination Clauses")
        print("="*70)
        
        query = """
        SELECT ?contract ?clause ?clauseType ?title ?summary
        WHERE {
            ?contract proc:hasClause ?clause .
            ?clause a ?clauseType .
            ?clauseType rdfs:subClassOf* proc:TerminationClause .
            
            OPTIONAL { ?clause rdfs:label ?title }
            OPTIONAL { ?clause proc:summary ?summary }
        }
        ORDER BY ?contract
        """
        
        import time
        start = time.time()
        results = self.fuseki.execute_select(query)
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Found {len(results)} termination-related clauses using RDFS reasoning.
        
        This query demonstrates:
        - RDFS transitive reasoning (rdfs:subClassOf*)
        - Finds TerminationClause AND any subclasses
        - Semantic search based on ontology structure
        
        Key insight: If we later add "EarlyTerminationClause" as a subclass
        of TerminationClause, this query will automatically find those too!
        
        Results:
        {chr(10).join([f"  • {r.get('title', 'Untitled')}: {r['clauseType'].split('#')[-1]}" 
                       for r in results[:3]])}
        
        Without RDFS: Would need to manually list all termination clause types
        With RDFS: Automatically finds all related clauses via hierarchy
        """
        
        print(f"✅ Result: {len(results)} termination clauses")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(explanation)
        
        self.log_query_result(
            "Level 2 - RDFS Reasoning",
            "Find Termination Clauses",
            query,
            results,
            explanation,
            time_ms
        )
        
        return results
    
    def test_level2_contracts_with_jurisdiction(self):
        """
        Level 2: Find contracts with specific jurisdiction
        
        Why this matters:
        - Demonstrates property-based filtering
        - Shows entity relationships
        - Useful for compliance queries
        """
        print("\n" + "="*70)
        print("LEVEL 2: RDFS REASONING - Contracts by Jurisdiction")
        print("="*70)
        
        query = """
        SELECT ?contract ?jurisdiction (COUNT(?clause) as ?clauseCount)
        WHERE {
            ?contract a proc:Contract .
            ?contract proc:hasClause ?clause .
            ?clause a ?clauseType .
            ?clauseType rdfs:subClassOf* proc:GoverningLawClause .
            
            OPTIONAL {
                ?clause proc:jurisdiction ?jurisdiction
            }
        }
        GROUP BY ?contract ?jurisdiction
        """
        
        import time
        start = time.time()
        results = self.fuseki.execute_select(query)
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Found {len(results)} contracts with jurisdiction information.
        
        This query demonstrates:
        - Property-based filtering (proc:jurisdiction)
        - RDFS reasoning to find GoverningLawClause and subclasses
        - Aggregation across contracts
        
        Jurisdictions found:
        {chr(10).join([f"  • {r.get('jurisdiction', 'Not specified')}" 
                       for r in results if r.get('jurisdiction')])}
        
        Use case: "Show me all contracts governed by New Zealand law"
        Answer: Instant, from structured data
        
        Without KG: Manual document review
        With KG: Structured query with semantic reasoning
        """
        
        print(f"✅ Result: {len(results)} contracts with jurisdiction")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(explanation)
        
        self.log_query_result(
            "Level 2 - RDFS Reasoning",
            "Contracts by Jurisdiction",
            query,
            results,
            explanation,
            time_ms
        )
        
        return results
    
    # =========================================================================
    # LEVEL 3: HYBRID QUERIES (SPARQL + Vector Search + LLM)
    # =========================================================================
    
    async def test_level3_hybrid_risk_analysis(self):
        """
        Level 3: Complex risk analysis using hybrid approach
        
        Why this matters:
        - Combines structured (SPARQL) + unstructured (vector) + reasoning (LLM)
        - Answers complex questions requiring context
        - Demonstrates full RAG pipeline
        """
        print("\n" + "="*70)
        print("LEVEL 3: HYBRID QUERY - Risk Analysis")
        print("="*70)
        
        question = """
        What are the termination risks in our contracts? 
        Specifically, which contracts have short notice periods or 
        unfavorable termination conditions?
        """
        
        import time
        start = time.time()
        
        # This uses the full RAG pipeline:
        # 1. Vector search for relevant clauses
        # 2. SPARQL for structured data
        # 3. LLM for synthesis and reasoning
        response = await self.rag_agent.process(question)
        
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Hybrid query combining three approaches:
        
        1. VECTOR SEARCH:
           - Semantic search for "termination", "notice period", "risks"
           - Found {len(response.retrieved_clauses)} relevant clauses
           - Uses embeddings to find semantically similar content
        
        2. SPARQL QUERY:
           - Structured query for TerminationClause instances
           - Extract notice periods, conditions
           - Filter by risk criteria
        
        3. LLM REASONING:
           - Synthesize findings from both sources
           - Identify patterns and risks
           - Generate human-readable analysis
        
        Why hybrid is powerful:
        - Vector search: Finds relevant content even with different wording
        - SPARQL: Precise structured queries on known relationships
        - LLM: Understands context and generates insights
        
        Answer quality: {response.confidence:.2%} confidence
        Sources used: {len(response.sources)} documents
        """
        
        print(f"✅ Answer generated")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(f"\n📊 Answer:\n{response.answer}\n")
        print(explanation)
        
        self.log_query_result(
            "Level 3 - Hybrid",
            "Risk Analysis",
            question,
            [{
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": len(response.sources),
                "clauses_retrieved": len(response.retrieved_clauses)
            }],
            explanation,
            time_ms
        )
        
        return response
    
    async def test_level3_hybrid_compliance_check(self):
        """
        Level 3: Compliance checking across contracts
        
        Why this matters:
        - Real-world use case
        - Requires understanding of multiple clauses
        - Demonstrates reasoning capabilities
        """
        print("\n" + "="*70)
        print("LEVEL 3: HYBRID QUERY - Compliance Check")
        print("="*70)
        
        question = """
        Do our contracts have adequate confidentiality and 
        intellectual property protection clauses? 
        What are the key terms?
        """
        
        import time
        start = time.time()
        
        response = await self.rag_agent.process(question)
        
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Compliance check using hybrid approach:
        
        1. VECTOR SEARCH:
           - Find clauses about "confidentiality", "IP", "intellectual property"
           - Semantic matching across different phrasings
           - Retrieved {len(response.retrieved_clauses)} relevant clauses
        
        2. SPARQL QUERY:
           - Find ConfidentialityClause instances
           - Find IntellectualPropertyClause instances
           - Extract key terms and conditions
        
        3. LLM ANALYSIS:
           - Assess adequacy of protections
           - Identify gaps or weaknesses
           - Compare against best practices
        
        Business value:
        - Automated compliance checking
        - Consistent across all contracts
        - Identifies gaps proactively
        
        Confidence: {response.confidence:.2%}
        Sources: {len(response.sources)} contracts analyzed
        """
        
        print(f"✅ Compliance check complete")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(f"\n📊 Analysis:\n{response.answer}\n")
        print(explanation)
        
        self.log_query_result(
            "Level 3 - Hybrid",
            "Compliance Check",
            question,
            [{
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": len(response.sources),
                "clauses_retrieved": len(response.retrieved_clauses)
            }],
            explanation,
            time_ms
        )
        
        return response
    
    async def test_level3_hybrid_comparative_analysis(self):
        """
        Level 3: Compare clauses across contracts
        
        Why this matters:
        - Identifies inconsistencies
        - Helps standardize contracts
        - Supports negotiation
        """
        print("\n" + "="*70)
        print("LEVEL 3: HYBRID QUERY - Comparative Analysis")
        print("="*70)
        
        question = """
        Compare the limitation of action periods across our contracts. 
        Are there any outliers or inconsistencies?
        """
        
        import time
        start = time.time()
        
        response = await self.rag_agent.process(question)
        
        time_ms = (time.time() - start) * 1000
        
        explanation = f"""
        Comparative analysis using hybrid approach:
        
        1. VECTOR SEARCH:
           - Find all clauses mentioning "limitation", "action period", "statute"
           - Semantic search across different legal phrasings
           - Retrieved {len(response.retrieved_clauses)} clauses
        
        2. SPARQL QUERY:
           - Find LimitationOfActionClause instances
           - Extract limitation_period values
           - Group by contract for comparison
        
        3. LLM REASONING:
           - Compare periods across contracts
           - Identify outliers (too short/long)
           - Assess business implications
        
        Why this is powerful:
        - Automated contract comparison
        - Identifies inconsistencies that could be risks
        - Supports standardization efforts
        
        Analysis confidence: {response.confidence:.2%}
        Contracts compared: {len(response.sources)}
        """
        
        print(f"✅ Comparative analysis complete")
        print(f"⏱️  Query time: {time_ms:.2f}ms")
        print(f"\n📊 Comparison:\n{response.answer}\n")
        print(explanation)
        
        self.log_query_result(
            "Level 3 - Hybrid",
            "Comparative Analysis",
            question,
            [{
                "answer": response.answer,
                "confidence": response.confidence,
                "sources": len(response.sources),
                "clauses_retrieved": len(response.retrieved_clauses)
            }],
            explanation,
            time_ms
        )
        
        return response
    
    def save_results(self):
        """Save all test results to file."""
        output_dir = Path("agents/logs/tests")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"kg_query_tests_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Results saved to: {output_file}")
        return output_file


async def main():
    """Run all query tests."""
    print("\n" + "="*70)
    print("KNOWLEDGE GRAPH QUERY TEST SUITE")
    print("Demonstrating RDFS Reasoning & Hybrid RAG")
    print("="*70)
    
    tester = KnowledgeGraphQueryTester()
    
    # Level 1: Simple queries
    tester.test_level1_basic_contract_count()
    tester.test_level1_list_all_clause_types()
    
    # Level 2: RDFS reasoning
    tester.test_level2_find_termination_clauses_with_reasoning()
    tester.test_level2_contracts_with_jurisdiction()
    
    # Level 3: Hybrid queries
    await tester.test_level3_hybrid_risk_analysis()
    await tester.test_level3_hybrid_compliance_check()
    await tester.test_level3_hybrid_comparative_analysis()
    
    # Save results
    output_file = tester.save_results()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETE")
    print("="*70)
    print(f"\nResults saved to: {output_file}")
    print("\nKey Takeaways:")
    print("1. Simple queries: Fast, precise answers from structured data")
    print("2. RDFS reasoning: Semantic queries using ontology relationships")
    print("3. Hybrid queries: Best of both worlds - structure + semantics + reasoning")
    print("\nThis demonstrates WHY we need a knowledge graph with proper ontology!")


if __name__ == "__main__":
    asyncio.run(main())


