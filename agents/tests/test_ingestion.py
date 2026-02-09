"""
Ingestion Pipeline Tests

Tests document ingestion components.
"""
import pytest
from pathlib import Path
from agents.ingestion.directory_scanner import DirectoryScannerAgent
from agents.ingestion.enhanced_document_ingestion import (
    EnhancedDocumentIngestionAgent
)
from agents.ingestion.batch_processor import BatchProcessorAgent


@pytest.mark.asyncio
async def test_directory_scanner(settings):
    """Test directory scanner discovers files."""
    scanner = DirectoryScannerAgent(settings=settings)
    
    # Scan examples directory
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    if not examples_dir.exists():
        pytest.skip("Examples directory not found")
    
    result = await scanner.process(str(examples_dir))
    
    assert result.total_files > 0
    assert result.supported_files > 0
    assert len(result.discovered_files) > 0


@pytest.mark.asyncio
async def test_pdf_extraction(settings, sample_pdf_path):
    """Test PDF document extraction."""
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found")
    
    agent = EnhancedDocumentIngestionAgent(settings=settings)
    result = await agent.process(sample_pdf_path)
    
    assert result.document_id
    assert result.filename
    assert len(result.text) > 0
    assert result.page_count > 0
    assert result.confidence > 0


@pytest.mark.asyncio
async def test_docx_extraction(settings, sample_docx_path):
    """Test DOCX document extraction."""
    if not sample_docx_path.exists():
        pytest.skip("Sample DOCX not found")
    
    agent = EnhancedDocumentIngestionAgent(settings=settings)
    result = await agent.process(sample_docx_path)
    
    assert result.document_id
    assert result.filename
    assert len(result.text) > 0
    assert result.extraction_method == "python-docx"


@pytest.mark.asyncio
async def test_batch_processor_initialization(settings):
    """Test batch processor can be initialized."""
    processor = BatchProcessorAgent(
        settings=settings,
        max_concurrent=3,
        max_retries=1
    )
    
    assert processor.max_concurrent == 3
    assert processor.max_retries == 1
    assert processor.semaphore is not None


@pytest.mark.asyncio
async def test_document_id_generation(settings, sample_pdf_path):
    """Test document ID generation is consistent."""
    if not sample_pdf_path.exists():
        pytest.skip("Sample PDF not found")
    
    agent = EnhancedDocumentIngestionAgent(settings=settings)
    
    # Generate ID twice for same file
    doc_id1 = agent._generate_document_id(sample_pdf_path)
    doc_id2 = agent._generate_document_id(sample_pdf_path)
    
    # Should be identical (deterministic)
    assert doc_id1 == doc_id2
    assert doc_id1.startswith("doc_")
    assert len(doc_id1) == 20  # "doc_" + 16 hex chars


def test_file_classification():
    """Test file classification logic."""
    from agents.ingestion.directory_scanner import (
        DirectoryScannerAgent,
        DiscoveredFile,
        DocumentType,
        FileCategory
    )
    from pathlib import Path
    
    scanner = DirectoryScannerAgent(settings=None)
    
    # Test amendment detection
    discovered = DiscoveredFile(
        path=Path("/test/amendment_contract.pdf"),
        filename="amendment_contract.pdf",
        extension=".pdf",
        size_bytes=1000,
        category=FileCategory.PRIMARY
    )
    scanner._simple_classify(discovered)
    assert discovered.document_type == DocumentType.AMENDMENT
    
    # Test terms detection
    discovered2 = DiscoveredFile(
        path=Path("/test/terms_and_conditions.pdf"),
        filename="terms_and_conditions.pdf",
        extension=".pdf",
        size_bytes=1000,
        category=FileCategory.PRIMARY
    )
    scanner._simple_classify(discovered2)
    assert discovered2.document_type == DocumentType.TERMS


def test_supported_extensions():
    """Test that scanner recognizes supported file types."""
    from agents.ingestion.directory_scanner import DirectoryScannerAgent
    
    scanner = DirectoryScannerAgent(settings=None)
    
    assert ".pdf" in scanner.SUPPORTED_EXTENSIONS
    assert ".docx" in scanner.SUPPORTED_EXTENSIONS
    assert ".doc" in scanner.SUPPORTED_EXTENSIONS
    assert ".txt" not in scanner.SUPPORTED_EXTENSIONS  # Not in current list


def test_enhanced_ingestion_supported_formats():
    """Test enhanced ingestion supports multiple formats."""
    from agents.ingestion.enhanced_document_ingestion import (
        EnhancedDocumentIngestionAgent
    )
    
    agent = EnhancedDocumentIngestionAgent(settings=None)
    
    # Check all supported extensions
    assert ".pdf" in agent.SUPPORTED_EXTENSIONS
    assert ".docx" in agent.SUPPORTED_EXTENSIONS
    assert ".xls" in agent.SUPPORTED_EXTENSIONS
    assert ".xlsx" in agent.SUPPORTED_EXTENSIONS
    assert ".eml" in agent.SUPPORTED_EXTENSIONS


