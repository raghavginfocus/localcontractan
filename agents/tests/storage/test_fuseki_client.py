"""
Tests for Fuseki client.
"""

import pytest
from unittest.mock import Mock, patch

from contract_kg.config import Settings
from contract_kg.fuseki_client import FusekiClient


class TestFusekiClient:
    """Tests for FusekiClient."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            fuseki_url="http://localhost:3030",
            fuseki_dataset="test_contracts",
        )

    @pytest.fixture
    def client(self, settings):
        """Create test client."""
        return FusekiClient(settings=settings)

    def test_endpoint_configuration(self, client, settings):
        """Test that endpoints are correctly configured."""
        assert client.query_endpoint == "http://localhost:3030/test_contracts/query"
        assert client.update_endpoint == "http://localhost:3030/test_contracts/update"
        assert client.graph_store_endpoint == "http://localhost:3030/test_contracts/data"

    def test_namespaces(self, client, settings):
        """Test namespace configuration."""
        assert str(client.PROC) == settings.procurement_namespace
        assert str(client.CONTRACT) == settings.contract_namespace

    @patch("contract_kg.fuseki_client.SPARQLWrapper")
    def test_execute_select(self, mock_sparql_wrapper, client):
        """Test SELECT query execution."""
        # Mock response
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        mock_instance.query.return_value.convert.return_value = {
            "results": {
                "bindings": [
                    {"contract": {"type": "uri", "value": "http://test/c1"}},
                    {"contract": {"type": "uri", "value": "http://test/c2"}},
                ]
            }
        }

        results = client.execute_select("SELECT ?contract WHERE { ?contract a proc:Contract }")

        assert len(results) == 2
        assert results[0]["contract"] == "http://test/c1"

    @patch("contract_kg.fuseki_client.SPARQLWrapper")
    def test_execute_ask(self, mock_sparql_wrapper, client):
        """Test ASK query execution."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        mock_instance.query.return_value.convert.return_value = {"boolean": True}

        result = client.execute_ask("ASK { ?s ?p ?o }")

        assert result is True


class TestContractOperations:
    """Tests for contract-specific operations."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked settings."""
        settings = Settings(
            fuseki_url="http://localhost:3030",
            fuseki_dataset="contracts",
        )
        return FusekiClient(settings=settings)

    @patch.object(FusekiClient, "execute_update")
    def test_insert_contract(self, mock_update, client):
        """Test contract insertion."""
        uri = client.insert_contract(
            contract_id="test_001",
            value=500000.0,
            jurisdiction="EU",
        )

        assert "test_001" in uri
        mock_update.assert_called_once()

    @patch.object(FusekiClient, "execute_update")
    def test_insert_clause(self, mock_update, client):
        """Test clause insertion."""
        contract_uri = "http://procurement.kg/contract#test_001"
        
        uri = client.insert_clause(
            clause_id="clause_001",
            contract_uri=contract_uri,
            clause_type="TerminationClause",
            raw_text="Either party may terminate...",
            notice_period=30,
        )

        assert "clause_001" in uri
        mock_update.assert_called_once()
