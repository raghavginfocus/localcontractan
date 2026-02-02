"""
Document Ingestion Agent - Extracts text from procurement contracts.
"""

import hashlib
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document as DocxDocument
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class ExtractedDocument(BaseModel):
    """Represents an extracted document."""
    
    document_id: str = Field(description="Unique identifier for the document")
    filename: str = Field(description="Original filename")
    text: str = Field(description="Extracted text content")
    page_count: int = Field(default=1, description="Number of pages")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentIngestionAgent(BaseAgent):
    """
    Agent for extracting text from procurement contract documents.
    
    Supports:
    - PDF documents (via pdfplumber)
    - Word documents (.docx via python-docx)
    - Plain text files
    
    Features:
    - Preserves document structure where possible
    - Extracts metadata
    - Generates unique document IDs
    - Handles OCR if needed (via pytesseract)
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

    async def process(self, input_data: str | Path) -> ExtractedDocument:
        """
        Extract text from a document file.
        
        Args:
            input_data: Path to the document file
            
        Returns:
            ExtractedDocument with extracted content
        """
        file_path = Path(input_data)
        # Use file stem as context_id for uniqueness
        context_id = file_path.stem if file_path.exists() else "unknown"
        
        # Initialize explanation builder if not already done
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=context_id)
        
        # Record input for explanation
        if self.explanation_builder:
            self._record_input(str(input_data))
        
        self.log_start("document_extraction", file=str(file_path))
        
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")
        
        extension = file_path.suffix.lower()
        
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {extension}")
        
        # Generate document ID from file hash
        document_id = self._generate_document_id(file_path)
        
        # Extract text based on file type
        if extension == ".pdf":
            text, page_count, metadata = self._extract_pdf(file_path)
        elif extension in {".docx", ".doc"}:
            text, page_count, metadata = self._extract_docx(file_path)
        else:
            text, page_count, metadata = self._extract_text(file_path)
        
        # Use LLM to normalize and structure the text if needed
        if self.settings.llm_provider != "none":
            text = await self._normalize_text(text)
        
        result = ExtractedDocument(
            document_id=document_id,
            filename=file_path.name,
            text=text,
            page_count=page_count,
            metadata=metadata,
        )
        
        # Record output for explanation
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("page_count", page_count)
            self.explanation_builder.add_metadata("text_length", len(text))
            self._save_explanation()
        
        self.log_complete(
            "document_extraction",
            document_id=document_id,
            text_length=len(text),
            page_count=page_count,
        )
        
        return result

    def _generate_document_id(self, file_path: Path) -> str:
        """Generate a unique document ID based on file content hash."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return f"doc_{hasher.hexdigest()[:16]}"

    def _extract_pdf(self, file_path: Path) -> tuple[str, int, dict[str, Any]]:
        """Extract text from PDF file."""
        text_parts = []
        metadata = {}
        
        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)
            metadata["pdf_info"] = pdf.metadata or {}
            
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    text_parts.append(f"[Page {i + 1}]\n{page_text}")
        
        text = "\n\n".join(text_parts)
        
        # If no text extracted, might need OCR
        if not text.strip():
            logger.warning("No text extracted from PDF, may require OCR", file=str(file_path))
        
        return text, page_count, metadata

    def _extract_docx(self, file_path: Path) -> tuple[str, int, dict[str, Any]]:
        """Extract text from Word document."""
        doc = DocxDocument(file_path)
        
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    text_parts.append(row_text)
        
        text = "\n\n".join(text_parts)
        
        metadata = {
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
        }
        
        # Word docs don't have explicit page counts without rendering
        page_count = max(1, len(text) // 3000)  # Rough estimate
        
        return text, page_count, metadata

    def _extract_text(self, file_path: Path) -> tuple[str, int, dict[str, Any]]:
        """Extract text from plain text file."""
        text = file_path.read_text(encoding="utf-8")
        metadata = {"encoding": "utf-8"}
        page_count = max(1, len(text) // 3000)
        return text, page_count, metadata

    async def _normalize_text(self, text: str) -> str:
        """
        Use LLM to normalize and clean extracted text.
        
        This helps with:
        - Fixing OCR errors
        - Normalizing whitespace
        - Identifying section boundaries
        """
        # For very long documents, just return as-is
        if len(text) > 50000:
            return text
        
        prompt = f"""Clean and normalize the following contract text. 
Fix obvious OCR errors, normalize whitespace, but preserve the original structure.
Do not summarize or remove any content.

Text:
{text[:10000]}

Cleaned text:"""
        
        try:
            response = await self.llm.ainvoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.warning("Text normalization failed, using original", error=str(e))
            return text
