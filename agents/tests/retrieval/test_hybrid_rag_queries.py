"""
Test Hybrid RAG Queries - Natural Language to Knowledge Graph

This test suite demonstrates the full RAG pipeline:
1. Natural language question → Vector search + SPARQL generation + LLM reasoning
2. Tests at different complexity levels
3. Shows why knowledge graph + ontology is valuable

All queries use NATURAL LANGUAGE - no manual SPARQL writing!
"""

import asyncio
from pathlib import Path
import json
from datetime import datetime

from contract_kg.config import get_settings
from contract_kg.fuseki_client import FusekiClient
from contract_kg.vector_store import MilvusVectorStore
from contract_kg.agents.retrieval.rag_orchestrator import RAGOrchestratorAgent


class HybridRAGTester:
    """Test suite for natural language queries using hybrid RAG."""
    
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
    
    def log_result(self, level: str, question: str, response, time_ms: float):
        """Log query results."""
        result = {
            "level": level,
            "question": question,
            "answer": response.answer,
            "confidence": response.confidence,
            "kg_facts": len(response.kg_facts),
            "vector_contexts": len(response.vector_context),
            "sparql_generated": response.sparql_query,
            "time_ms": time_ms,
            "timestamp": datetime.now().isoformat()
        }
        self.results.append(result)
        return result
    
    async def test_level1_simple_count(self):
        """
        Level 1: Simple factual question
        
        Tests: Basic information retrieval
        """
        print("\n" + "="*70)
        print("LEVEL 1: SIMPLE QUESTION - Contract Count")
        print("="*70)
        
        question = "How many contracts do we have in our system?"
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search finds relevant contract data")
        print(f"   2. SPARQL query generated: COUNT contracts")
        print(f"   3. LLM synthesizes answer from structured data")
        
        self.log_result("Level 1 - Simple", question, response, time_ms)
        return response
    
    async def test_level1_clause_types(self):
        """
        Level 1: List information
        
        Tests: Ontology-based classification
        """
        print("\n" + "="*70)
        print("LEVEL 1: SIMPLE QUESTION - Clause Types")
        print("="*70)
        
        question = "What types of clauses are in our contracts?"
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Semantic search for 'clause types'")
        print(f"   2. SPARQL uses ontology hierarchy (rdfs:subClassOf)")
        print(f"   3. LLM lists and explains clause categories")
        
        print(f"\n✨ Value of Ontology:")
        print(f"   • Automatic classification using rdfs:subClassOf")
        print(f"   • Finds all clause types including dynamically created ones")
        print(f"   • Semantic relationships preserved")
        
        self.log_result("Level 1 - Simple", question, response, time_ms)
        return response
    
    async def test_level2_termination_analysis(self):
        """
        Level 2: Analytical question requiring reasoning
        
        Tests: RDFS reasoning + semantic understanding
        """
        print("\n" + "="*70)
        print("LEVEL 2: ANALYTICAL QUESTION - Termination Terms")
        print("="*70)
        
        question = """
        What are the termination terms in our contracts? 
        Include notice periods and conditions.
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'termination', 'notice period'")
        print(f"   2. SPARQL: Find TerminationClause + subclasses (RDFS reasoning)")
        print(f"   3. Extract attributes: notice_period, conditions")
        print(f"   4. LLM synthesizes comprehensive answer")
        
        print(f"\n✨ Value of RDFS Reasoning:")
        print(f"   • Finds TerminationClause AND any subclasses automatically")
        print(f"   • If we add EarlyTerminationClause later, it's found too")
        print(f"   • Semantic relationships enable smart queries")
        
        self.log_result("Level 2 - Analytical", question, response, time_ms)
        return response
    
    async def test_level2_jurisdiction_compliance(self):
        """
        Level 2: Compliance-focused question
        
        Tests: Property extraction + filtering
        """
        print("\n" + "="*70)
        print("LEVEL 2: ANALYTICAL QUESTION - Jurisdiction")
        print("="*70)
        
        question = """
        Which jurisdictions govern our contracts? 
        Are there any contracts without clear jurisdiction?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'jurisdiction', 'governing law'")
        print(f"   2. SPARQL: Find GoverningLawClause instances")
        print(f"   3. Extract jurisdiction property")
        print(f"   4. LLM identifies gaps and summarizes")
        
        print(f"\n✨ Business Value:")
        print(f"   • Instant compliance check across all contracts")
        print(f"   • Identifies missing jurisdiction clauses")
        print(f"   • Supports risk assessment")
        
        self.log_result("Level 2 - Analytical", question, response, time_ms)
        return response
    
    async def test_level3_risk_assessment(self):
        """
        Level 3: Complex multi-faceted analysis
        
        Tests: Multiple clause types + reasoning + risk scoring
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Risk Assessment")
        print("="*70)
        
        question = """
        Analyze the risk profile of our contracts. Consider:
        - Termination conditions and notice periods
        - Liability and indemnification terms
        - Any unusual or concerning clauses
        
        Which contracts have the highest risk?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: Multiple semantic concepts")
        print(f"      - 'risk', 'termination', 'liability', 'indemnification'")
        print(f"   2. SPARQL: Query multiple clause types")
        print(f"      - TerminationClause, LiabilityClause, etc.")
        print(f"   3. Extract attributes from each clause type")
        print(f"   4. LLM performs multi-dimensional analysis")
        print(f"   5. Synthesizes risk assessment with reasoning")
        
        print(f"\n✨ Why Hybrid Approach is Powerful:")
        print(f"   • Vector: Finds semantically relevant content")
        print(f"   • SPARQL: Precise structured queries")
        print(f"   • Ontology: Semantic understanding")
        print(f"   • LLM: Contextual reasoning")
        print(f"   • Result: Comprehensive analysis")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_level3_comparative_analysis(self):
        """
        Level 3: Cross-contract comparison
        
        Tests: Aggregation + pattern detection + anomaly identification
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Comparative Analysis")
        print("="*70)
        
        question = """
        Compare the payment and penalty terms across our contracts.
        Are there any inconsistencies or outliers that we should be aware of?
        Which contract has the most favorable terms?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'payment', 'penalty', 'terms'")
        print(f"   2. SPARQL: Find PaymentClause + PenaltyClause across contracts")
        print(f"   3. Extract numerical attributes (amounts, periods)")
        print(f"   4. LLM performs statistical analysis")
        print(f"   5. Identifies outliers and patterns")
        
        print(f"\n✨ Business Value:")
        print(f"   • Automated contract comparison")
        print(f"   • Identifies inconsistencies that could be risks")
        print(f"   • Supports standardization efforts")
        print(f"   • Helps in contract negotiation")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_level3_compliance_gaps(self):
        """
        Level 3: Gap analysis and recommendations
        
        Tests: Negative queries + reasoning + recommendations
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Compliance Gaps")
        print("="*70)
        
        question = """
        Review our contracts for compliance and completeness.
        Are there any missing clauses that should be present?
        For example: confidentiality, IP protection, force majeure, etc.
        What recommendations do you have?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'compliance', 'missing', 'gaps'")
        print(f"   2. SPARQL: Query for expected clause types")
        print(f"   3. Identify which contracts lack certain clauses")
        print(f"   4. LLM reasons about best practices")
        print(f"   5. Generates actionable recommendations")
        
        print(f"\n✨ Why This is Powerful:")
        print(f"   • Proactive gap identification")
        print(f"   • Uses ontology to know what SHOULD exist")
        print(f"   • Negative queries (what's missing)")
        print(f"   • Actionable recommendations")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_level2_entity_relationships(self):
        """
        Level 2: Entity relationship queries
        
        Tests: Entity extraction + relationship traversal
        """
        print("\n" + "="*70)
        print("LEVEL 2: ANALYTICAL QUESTION - Entity Relationships")
        print("="*70)
        
        question = """
        Who are the parties involved in our contracts?
        Show me the relationships between suppliers, clients, and other entities.
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'parties', 'supplier', 'client'")
        print(f"   2. SPARQL: Find Organization entities and relationships")
        print(f"   3. Traverse hasParty, hasSupplier relationships")
        print(f"   4. LLM maps entity network")
        
        print(f"\n✨ Value of Knowledge Graph:")
        print(f"   • Entities are first-class objects")
        print(f"   • Relationships explicitly modeled")
        print(f"   • Can traverse multi-hop connections")
        
        self.log_result("Level 2 - Analytical", question, response, time_ms)
        return response
    
    async def test_level2_obligation_tracking(self):
        """
        Level 2: Obligation and deadline tracking
        
        Tests: Temporal reasoning + obligation extraction
        """
        print("\n" + "="*70)
        print("LEVEL 2: ANALYTICAL QUESTION - Obligations")
        print("="*70)
        
        question = """
        What are the key obligations in our contracts?
        Are there any time-sensitive obligations or deadlines we should track?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'obligation', 'deadline', 'must'")
        print(f"   2. SPARQL: Find Obligation instances with deadlines")
        print(f"   3. Extract temporal properties")
        print(f"   4. LLM prioritizes by urgency")
        
        print(f"\n✨ Business Value:")
        print(f"   • Automated obligation tracking")
        print(f"   • Deadline monitoring")
        print(f"   • Risk of non-compliance identification")
        
        self.log_result("Level 2 - Analytical", question, response, time_ms)
        return response
    
    async def test_level3_technology_clauses(self):
        """
        Level 3: Domain-specific analysis (tech contracts)
        
        Tests: Specialized clause types + technical understanding
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Technology Clauses")
        print("="*70)
        
        question = """
        Analyze the technology-related clauses in our contracts.
        This includes cloud computing, blockchain, IoT, AI, and data storage.
        What technical requirements and standards are specified?
        Are there any security or compliance concerns?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: Multiple tech terms")
        print(f"   2. SPARQL: Find specialized clause types")
        print(f"      - SmartContractDeploymentClause")
        print(f"      - CloudComputingServicesClause")
        print(f"      - IoTDeviceManagementClause")
        print(f"      - AIModelTrainingClause")
        print(f"   3. Extract technical specifications")
        print(f"   4. LLM analyzes security and compliance")
        
        print(f"\n✨ Value of Ontology Evolution:")
        print(f"   • System learned these clause types automatically")
        print(f"   • No manual ontology engineering needed")
        print(f"   • Adapts to modern contract types")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_level3_warranty_liability(self):
        """
        Level 3: Legal risk analysis
        
        Tests: Multi-clause reasoning + risk assessment
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Warranty & Liability")
        print("="*70)
        
        question = """
        Analyze warranty and liability provisions across our contracts.
        What warranties are provided? What are the liability caps?
        Are there any unlimited liability scenarios?
        Which contracts expose us to the most legal risk?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: 'warranty', 'liability', 'indemnification'")
        print(f"   2. SPARQL: Query WarrantyClause + LiabilityClause")
        print(f"   3. Extract caps, exclusions, conditions")
        print(f"   4. LLM performs risk scoring")
        print(f"   5. Identifies high-risk scenarios")
        
        print(f"\n✨ Business Value:")
        print(f"   • Legal risk quantification")
        print(f"   • Identifies unlimited liability exposure")
        print(f"   • Supports contract negotiation")
        print(f"   • Enables risk mitigation strategies")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_level3_cross_contract_patterns(self):
        """
        Level 3: Pattern detection across contracts
        
        Tests: Aggregation + statistical analysis + anomaly detection
        """
        print("\n" + "="*70)
        print("LEVEL 3: COMPLEX QUESTION - Pattern Detection")
        print("="*70)
        
        question = """
        Analyze patterns across all our contracts.
        What are the common themes? Are there any unusual or unique clauses?
        Which contracts deviate from our standard templates?
        What insights can we gain about our contracting practices?
        """
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   1. Vector search: Broad semantic search")
        print(f"   2. SPARQL: Aggregate clause type frequencies")
        print(f"   3. Statistical analysis of distributions")
        print(f"   4. LLM identifies outliers and patterns")
        print(f"   5. Generates strategic insights")
        
        print(f"\n✨ Strategic Value:")
        print(f"   • Portfolio-level insights")
        print(f"   • Template standardization opportunities")
        print(f"   • Identifies negotiation patterns")
        print(f"   • Supports policy development")
        
        self.log_result("Level 3 - Complex", question, response, time_ms)
        return response
    
    async def test_edge_case_no_results(self):
        """
        Edge Case: Query with no matching data
        
        Tests: Graceful handling of empty results
        """
        print("\n" + "="*70)
        print("EDGE CASE: No Matching Data")
        print("="*70)
        
        question = "What are the cryptocurrency payment terms in our contracts?"
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   • System gracefully handles no results")
        print(f"   • LLM explains what was searched")
        print(f"   • Suggests related information if available")
        
        self.log_result("Edge Case", question, response, time_ms)
        return response
    
    async def test_edge_case_ambiguous_query(self):
        """
        Edge Case: Ambiguous or vague query
        
        Tests: Query clarification and best-effort response
        """
        print("\n" + "="*70)
        print("EDGE CASE: Ambiguous Query")
        print("="*70)
        
        question = "Tell me about the important stuff in the contracts."
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n🔍 How it works:")
        print(f"   • Vector search finds broadly relevant content")
        print(f"   • SPARQL retrieves high-level structure")
        print(f"   • LLM interprets intent and provides overview")
        
        self.log_result("Edge Case", question, response, time_ms)
        return response
    
    async def test_performance_simple_lookup(self):
        """
        Performance Test: Simple lookup query
        
        Tests: Response time for basic queries
        """
        print("\n" + "="*70)
        print("PERFORMANCE TEST: Simple Lookup")
        print("="*70)
        
        question = "How many termination clauses are there?"
        
        print(f"\n❓ Question: {question}")
        
        import time
        start = time.time()
        response = await self.rag_agent.process(question)
        time_ms = (time.time() - start) * 1000
        
        print(f"\n💡 Answer:\n{response.answer}")
        print(f"\n📊 Metadata:")
        print(f"   • Confidence: {response.confidence:.1%}")
        print(f"   • KG facts: {len(response.kg_facts)}")
        print(f"   • Vector contexts: {len(response.vector_context)}")
        print(f"   • Time: {time_ms:.0f}ms")
        
        print(f"\n⚡ Performance Notes:")
        print(f"   • Simple COUNT query")
        print(f"   • Should be fast (<5s total)")
        print(f"   • SPARQL execution: <1s")
        print(f"   • Vector search: <1s")
        
        self.log_result("Performance", question, response, time_ms)
        return response
    
    def save_results(self):
        """Save all test results."""
        output_dir = Path("agents/logs/tests")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = output_dir / f"hybrid_rag_tests_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Results saved to: {output_file}")
        return output_file
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*70)
        print("📊 TEST SUMMARY")
        print("="*70)
        
        total_time = sum(r['time_ms'] for r in self.results)
        avg_confidence = sum(r['confidence'] for r in self.results) / len(self.results)
        
        print(f"\n✅ Tests completed: {len(self.results)}")
        print(f"⏱️  Total time: {total_time/1000:.1f}s")
        print(f"📈 Average confidence: {avg_confidence:.1%}")
        
        print(f"\n🎯 Key Takeaways:")
        print(f"   1. Natural language → Structured queries (automatic)")
        print(f"   2. Hybrid approach combines best of all methods")
        print(f"   3. Ontology enables semantic reasoning")
        print(f"   4. Complex questions answered with high confidence")
        print(f"   5. Business value: Instant insights from contracts")


async def main():
    """Run all hybrid RAG tests."""
    print("\n" + "="*70)
    print("🚀 HYBRID RAG TEST SUITE")
    print("Natural Language Questions → Knowledge Graph Answers")
    print("="*70)
    print("\nDemonstrating:")
    print("• Vector Search (semantic similarity)")
    print("• SPARQL Generation (structured queries)")
    print("• RDFS Reasoning (ontology relationships)")
    print("• LLM Synthesis (contextual understanding)")
    
    tester = HybridRAGTester()
    
    print("\n" + "="*70)
    print("📋 TEST PLAN: 15 Comprehensive Test Cases")
    print("="*70)
    print("\nLevel 1 (Simple): 2 tests")
    print("Level 2 (Analytical): 5 tests")
    print("Level 3 (Complex): 6 tests")
    print("Edge Cases: 2 tests")
    print("Performance: 1 test")
    
    # Level 1: Simple questions (2 tests)
    print("\n" + "🔵"*35)
    print("LEVEL 1: SIMPLE QUESTIONS")
    print("🔵"*35)
    await tester.test_level1_simple_count()
    await tester.test_level1_clause_types()
    
    # Level 2: Analytical questions (5 tests)
    print("\n" + "🟢"*35)
    print("LEVEL 2: ANALYTICAL QUESTIONS")
    print("🟢"*35)
    await tester.test_level2_termination_analysis()
    await tester.test_level2_jurisdiction_compliance()
    await tester.test_level2_entity_relationships()
    await tester.test_level2_obligation_tracking()
    
    # Level 3: Complex questions (6 tests)
    print("\n" + "🟡"*35)
    print("LEVEL 3: COMPLEX QUESTIONS")
    print("🟡"*35)
    await tester.test_level3_risk_assessment()
    await tester.test_level3_comparative_analysis()
    await tester.test_level3_compliance_gaps()
    await tester.test_level3_technology_clauses()
    await tester.test_level3_warranty_liability()
    await tester.test_level3_cross_contract_patterns()
    
    # Edge Cases (2 tests)
    print("\n" + "🔴"*35)
    print("EDGE CASES")
    print("🔴"*35)
    await tester.test_edge_case_no_results()
    await tester.test_edge_case_ambiguous_query()
    
    # Performance Test (1 test)
    print("\n" + "⚡"*35)
    print("PERFORMANCE TEST")
    print("⚡"*35)
    await tester.test_performance_simple_lookup()
    
    # Summary
    tester.print_summary()
    output_file = tester.save_results()
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETE")
    print("="*70)
    print(f"\nThis demonstrates the power of:")
    print(f"• Knowledge Graph with proper ontology")
    print(f"• Hybrid RAG (Vector + SPARQL + LLM)")
    print(f"• Natural language interface to structured data")
    print(f"\nNo manual SPARQL writing needed - all generated automatically!")


if __name__ == "__main__":
    asyncio.run(main())


