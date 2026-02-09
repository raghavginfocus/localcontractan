"""
Utility Functions Tests

Tests for helper functions and utilities.
"""
import pytest
from pathlib import Path


def test_logger_initialization():
    """Test logger can be initialized."""
    from logger import get_module_logger
    
    logger = get_module_logger("test_module")
    assert logger is not None
    assert logger.name == "test_module"


def test_settings_singleton():
    """Test that settings returns same instance."""
    from config import get_settings
    
    settings1 = get_settings()
    settings2 = get_settings()
    
    # Should be same instance (cached)
    assert settings1 is settings2


def test_llm_provider_factory():
    """Test LLM provider factory."""
    from llm.provider_factory import get_llm_provider
    from config import get_settings
    
    settings = get_settings()
    provider = get_llm_provider(settings)
    
    assert provider is not None
    assert hasattr(provider, 'invoke') or hasattr(provider, 'generate')


def test_service_factory_sparql():
    """Test SPARQL store factory."""
    from service_factory import get_sparql_store
    from config import get_settings
    
    settings = get_settings()
    store = get_sparql_store(settings)
    
    assert store is not None
    assert hasattr(store, 'query') or hasattr(store, 'execute_query')


def test_service_factory_vector():
    """Test vector store factory."""
    from service_factory import get_vector_store
    from config import get_settings
    
    settings = get_settings()
    store = get_vector_store(settings)
    
    assert store is not None


def test_path_utilities():
    """Test path handling utilities."""
    test_path = Path("/test/path/file.pdf")
    
    assert test_path.suffix == ".pdf"
    assert test_path.stem == "file"
    assert test_path.name == "file.pdf"


def test_file_extension_detection():
    """Test file extension detection."""
    from agents.ingestion.directory_scanner import DirectoryScannerAgent
    
    scanner = DirectoryScannerAgent(settings=None)
    
    # Test various extensions
    assert ".pdf" in scanner.SUPPORTED_EXTENSIONS
    assert ".docx" in scanner.SUPPORTED_EXTENSIONS
    assert ".doc" in scanner.SUPPORTED_EXTENSIONS


def test_document_type_enum():
    """Test document type enumeration."""
    from agents.ingestion.directory_scanner import DocumentType
    
    assert DocumentType.CONTRACT
    assert DocumentType.AMENDMENT
    assert DocumentType.ATTACHMENT
    assert DocumentType.TERMS
    assert DocumentType.UNKNOWN


def test_file_category_enum():
    """Test file category enumeration."""
    from agents.ingestion.directory_scanner import FileCategory
    
    assert FileCategory.PRIMARY
    assert FileCategory.SECONDARY
    assert FileCategory.REFERENCE
    assert FileCategory.UNSUPPORTED


