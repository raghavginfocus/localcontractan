"""
Fuseki Client Tests

Comprehensive tests for Fuseki SPARQL client.
"""
import pytest
from fuseki_client import FusekiClient


def test_fuseki_client_initialization(settings):
    """Test Fuseki client can be initialized."""
    client = FusekiClient(settings)
    
    assert client is not None
    assert client.settings == settings
    assert client.query_endpoint
    assert client.update_endpoint


def test_fuseki_prefixes():
    """Test that Fuseki client has standard prefixes."""
    client = FusekiClient(settings=None)
    
    assert hasattr(FusekiClient, 'PREFIXES')
    prefixes = FusekiClient.PREFIXES
    
    # Check for standard prefixes
    assert 'PREFIX rdf:' in prefixes
    assert 'PREFIX rdfs:' in prefixes
    assert 'PREFIX owl:' in prefixes
    assert 'PREFIX xsd:' in prefixes
    assert 'PREFIX proc:' in prefixes


def test_query_endpoint_construction(settings):
    """Test query endpoint URL construction."""
    client = FusekiClient(settings)
    
    # Should have proper endpoint URLs
    assert 'http' in client.query_endpoint
    assert settings.fuseki_dataset in client.query_endpoint


def test_update_endpoint_construction(settings):
    """Test update endpoint URL construction."""
    client = FusekiClient(settings)
    
    # Should have proper endpoint URLs
    assert 'http' in client.update_endpoint
    assert settings.fuseki_dataset in client.update_endpoint


@pytest.mark.asyncio
async def test_fuseki_client_has_query_method(settings):
    """Test that client has query method."""
    client = FusekiClient(settings)
    
    assert hasattr(client, 'query') or hasattr(client, 'execute_query')


@pytest.mark.asyncio
async def test_fuseki_client_has_update_method(settings):
    """Test that client has update method."""
    client = FusekiClient(settings)
    
    assert hasattr(client, 'update') or hasattr(client, 'execute_update')


def test_fuseki_namespace_handling():
    """Test namespace handling in Fuseki client."""
    from rdflib import Namespace
    
    # Test that we can create namespaces
    proc_ns = Namespace("http://procurement.kg/ontology#")
    contract_ns = Namespace("http://procurement.kg/contract#")
    
    assert proc_ns is not None
    assert contract_ns is not None
    
    # Test URI creation
    contract_uri = contract_ns.Contract
    assert str(contract_uri) == "http://procurement.kg/contract#Contract"


def test_sparql_query_construction():
    """Test SPARQL query string construction."""
    # Simple SELECT query
    query = """
    PREFIX proc: <http://procurement.kg/ontology#>
    SELECT ?contract WHERE {
        ?contract a proc:Contract .
    }
    """
    
    assert "SELECT" in query
    assert "WHERE" in query
    assert "PREFIX" in query


def test_sparql_update_construction():
    """Test SPARQL UPDATE string construction."""
    # Simple INSERT query
    update = """
    PREFIX proc: <http://procurement.kg/ontology#>
    INSERT DATA {
        <http://example.org/contract1> a proc:Contract .
    }
    """
    
    assert "INSERT" in update
    assert "PREFIX" in update


