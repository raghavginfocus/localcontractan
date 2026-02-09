"""
Pytest configuration and shared fixtures for test suite.
"""
import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def settings():
    """Get application settings."""
    from config import get_settings
    return get_settings()


@pytest.fixture
def sample_pdf_path():
    """Path to sample PDF for testing."""
    return Path(__file__).parent.parent.parent / "examples" / "CW3150589.NZ.(22Mar21)CBRE sig only.pdf"


@pytest.fixture
def sample_docx_path():
    """Path to sample DOCX for testing."""
    return Path(__file__).parent.parent.parent / "examples" / "P_SRA_SMA_PA_Hong_Kong-English_v6_17.docx"

# Made with Bob
