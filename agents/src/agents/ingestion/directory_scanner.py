"""
Directory Scanner Agent - Recursively discovers contract documents.

This agent discovers all contract documents in a directory with:
- Recursive directory traversal
- Simple path-based file classification
- Relationship detection (parent/child contracts)
- Batch organization by supplier
- Support for PDF, DOCX, and DOC files
"""

import asyncio
from pathlib import Path
from typing import Any, List, Dict, Optional
from enum import Enum
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class DocumentType(str, Enum):
    """Types of documents that can be processed."""
    CONTRACT = "contract"
    AMENDMENT = "amendment"
    ATTACHMENT = "attachment"
    TERMS = "terms"
    UNKNOWN = "unknown"


class FileCategory(str, Enum):
    """Categories for file processing priority."""
    PRIMARY = "primary"  # Main contract documents
    SECONDARY = "secondary"  # Amendments, attachments
    REFERENCE = "reference"  # Terms, conditions
    UNSUPPORTED = "unsupported"  # Cannot process


@dataclass
class DiscoveredFile:
    """Represents a discovered file with metadata."""
    path: Path
    filename: str
    extension: str
    size_bytes: int
    document_type: DocumentType = DocumentType.UNKNOWN
    category: FileCategory = FileCategory.PRIMARY
    supplier: Optional[str] = None
    batch_id: Optional[str] = None
    is_parent: bool = False
    is_child: bool = False
    related_files: List[Path] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ScanResult(BaseModel):
    """Result of directory scanning."""
    total_files: int = Field(description="Total files discovered")
    supported_files: int = Field(description="Files that can be processed")
    unsupported_files: int = Field(description="Files that cannot be processed")
    files_by_type: Dict[str, int] = Field(default_factory=dict)
    files_by_supplier: Dict[str, int] = Field(default_factory=dict)
    discovered_files: List[DiscoveredFile] = Field(default_factory=list)
    scan_duration_ms: float = Field(default=0.0)


class DirectoryScannerAgent(BaseAgent):
    """
    Agent for discovering and classifying contract documents.
    
    Features:
    - Recursive directory traversal
    - Simple path-based file classification (no LLM)
    - Relationship detection (parent/child contracts)
    - Batch organization by supplier
    - Support for PDF, DOCX, and DOC files
    """
    
    # Supported file extensions - ONLY PDF and DOCX
    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc"
    }
    
    
    async def process(self, input_data: str | Path) -> ScanResult:
        """
        Scan directory recursively and discover all contract documents.
        
        Args:
            input_data: Path to directory to scan
            
        Returns:
            ScanResult with discovered files and metadata
        """
        import time
        start_time = time.time()
        
        directory = Path(input_data)
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        logger.info(f"Starting directory scan: {directory}")
        
        # Discover all files recursively
        all_files = self._discover_files(directory)
        logger.info(f"Discovered {len(all_files)} total files")
        
        # Classify files
        discovered_files = await self._classify_files(all_files)
        
        # Calculate statistics
        supported_files = [f for f in discovered_files if f.category != FileCategory.UNSUPPORTED]
        unsupported_files = [f for f in discovered_files if f.category == FileCategory.UNSUPPORTED]
        
        files_by_type = {}
        for file in discovered_files:
            ext = file.extension
            files_by_type[ext] = files_by_type.get(ext, 0) + 1
        
        files_by_supplier = {}
        for file in discovered_files:
            if file.supplier:
                files_by_supplier[file.supplier] = files_by_supplier.get(file.supplier, 0) + 1
        
        duration_ms = (time.time() - start_time) * 1000
        
        result = ScanResult(
            total_files=len(all_files),
            supported_files=len(supported_files),
            unsupported_files=len(unsupported_files),
            files_by_type=files_by_type,
            files_by_supplier=files_by_supplier,
            discovered_files=discovered_files,
            scan_duration_ms=duration_ms
        )
        
        logger.info(f"Scan complete: {result.supported_files}/{result.total_files} files supported")
        logger.info(f"Files by type: {result.files_by_type}")
        logger.info(f"Files by supplier: {result.files_by_supplier}")
        
        return result
    
    def _discover_files(self, directory: Path) -> List[Path]:
        """Recursively discover all files in directory."""
        files = []
        
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    # Skip hidden files and system files
                    if not item.name.startswith(".") and not item.name.startswith("~"):
                        files.append(item)
        except PermissionError as e:
            logger.warning(f"Permission denied accessing {directory}: {e}")
        
        return files
    
    async def _classify_files(self, files: List[Path]) -> List[DiscoveredFile]:
        """Classify discovered files using simple path-based classification."""
        discovered = []
        
        # Process files in batches for efficient async processing
        batch_size = 10
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batch_results = await asyncio.gather(
                *[self._classify_single_file(f) for f in batch],
                return_exceptions=True
            )
            
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Classification error: {result}")
                else:
                    discovered.append(result)
        
        return discovered
    
    async def _classify_single_file(self, file_path: Path) -> DiscoveredFile:
        """Classify a single file using simple path-based classification."""
        extension = file_path.suffix.lower()
        
        # Determine category based on extension
        if extension in self.SUPPORTED_EXTENSIONS:
            category = FileCategory.PRIMARY
        else:
            category = FileCategory.UNSUPPORTED
        
        # Create base discovered file
        discovered = DiscoveredFile(
            path=file_path,
            filename=file_path.name,
            extension=extension,
            size_bytes=file_path.stat().st_size,
            category=category
        )
        
        # Simple classification without LLM
        self._simple_classify(discovered)
        
        return discovered
    
    def _simple_classify(self, discovered: DiscoveredFile):
        """Simple classification without LLM."""
        path_str = str(discovered.path).lower()
        filename_lower = discovered.filename.lower()
        
        # Detect document type from filename
        if "amendment" in filename_lower or "amd" in filename_lower:
            discovered.document_type = DocumentType.AMENDMENT
        elif "terms" in filename_lower or "conditions" in filename_lower:
            discovered.document_type = DocumentType.TERMS
        elif "attachment" in filename_lower or "exhibit" in filename_lower:
            discovered.document_type = DocumentType.ATTACHMENT
        else:
            discovered.document_type = DocumentType.CONTRACT
        
        # Extract supplier from path
        parts = discovered.path.parts
        for part in parts:
            if "supplier" not in part.lower() and not part.startswith("child_") and not part.startswith("parent_"):
                # Potential supplier name
                if part not in ["examples", "contracts", "documents"]:
                    discovered.supplier = part
                    break
        
        # Detect parent/child
        if "parent_contract" in path_str:
            discovered.is_parent = True
        elif "child_contract" in path_str:
            discovered.is_child = True
        
        # Extract batch ID (UUID pattern)
        import re
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        match = re.search(uuid_pattern, path_str)
        if match:
            discovered.batch_id = match.group(0)


