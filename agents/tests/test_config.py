"""
Configuration Tests

Tests that settings load correctly and environment variables work.
"""
import pytest
from config import get_settings


def test_settings_load(settings):
    """Test that settings load successfully."""
    assert settings is not None
    assert settings.fuseki_url
    assert settings.fuseki_dataset


def test_llm_provider_configured(settings):
    """Test that LLM provider is configured."""
    assert settings.llm_provider in ["openai", "anthropic", "ollama", "watsonx"]
    
    if settings.llm_provider == "ollama":
        assert settings.ollama_base_url
        assert settings.ollama_model


def test_fuseki_configuration(settings):
    """Test Fuseki configuration."""
    assert "http" in settings.fuseki_url
    assert settings.fuseki_dataset
    # fuseki_user and fuseki_password can be empty (no auth)


def test_milvus_configuration(settings):
    """Test Milvus configuration."""
    assert settings.milvus_host
    assert settings.milvus_port > 0
    assert settings.milvus_collection


