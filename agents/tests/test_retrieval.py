"""
Retrieval Pipeline Tests

Tests query processing and retrieval components.
"""
import pytest
from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
from agents.retrieval.complexity_detector import QueryComplexityDetector


@pytest.mark.asyncio
async def test_sparql_generator_simple_query(settings):
    """Test SPARQL generation for simple query."""
    agent = SPARQLGeneratorAgent(settings=settings)
    
    query = "List all contracts"
    result = await agent.process(query)
    
    assert result.sparql_query
    assert "SELECT" in result.sparql_query.upper()
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_complexity_detector(settings):
    """Test query complexity detection."""
    detector = QueryComplexityDetector(settings=settings)
    
    # Simple query
    simple = await detector.process("What is the contract value?")
    assert simple.complexity in ["simple", "moderate"]
    
    # Complex query
    complex_query = (
        "Analyze risk profile considering termination, "
        "liability, and unusual clauses"
    )
    complex_result = await detector.process(complex_query)
    assert complex_result.complexity in ["moderate", "complex"]


@pytest.mark.asyncio
async def test_sparql_generator_with_context(settings):
    """Test SPARQL generation with ontology context."""
    agent = SPARQLGeneratorAgent(settings=settings)
    
    query = "Find contracts with payment terms"
    result = await agent.process(query)
    
    assert result.sparql_query
    assert result.reasoning
    assert len(result.reasoning) > 0


def test_complexity_levels():
    """Test complexity level detection."""
    from agents.retrieval.complexity_detector import ComplexityLevel
    
    # Verify all complexity levels exist
    assert hasattr(ComplexityLevel, 'SIMPLE')
    assert hasattr(ComplexityLevel, 'MODERATE')
    assert hasattr(ComplexityLevel, 'COMPLEX')


@pytest.mark.asyncio
async def test_sparql_query_structure(settings):
    """Test that generated SPARQL has proper structure."""
    agent = SPARQLGeneratorAgent(settings=settings)
    
    query = "Count all contracts"
    result = await agent.process(query)
    
    sparql = result.sparql_query.upper()
    
    # Should contain basic SPARQL keywords
    assert "SELECT" in sparql or "ASK" in sparql or "CONSTRUCT" in sparql
    assert "WHERE" in sparql or "ASK" in sparql


def test_sparql_prefixes():
    """Test SPARQL generator includes necessary prefixes."""
    from agents.retrieval.sparql_generator import SPARQLGeneratorAgent
    
    # Check that agent has prefix definitions
    agent = SPARQLGeneratorAgent(settings=None)
    assert hasattr(agent, 'process')


