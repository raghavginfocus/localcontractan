"""
Enhanced Document Ingestion Agent - Supports multiple file types.

New features:
- Excel file support (.xls, .xlsx)
- Email file support (.eml)
- Smart content extraction
- Better error handling
"""

import hashlib
import email
from pathlib import Path
from typing import Any

import pdfplumber
from docx import Document as DocxDocument
from pydantic import BaseModel, Field

from agents.shared.base import BaseAgent
from logger import get_module_logger

logger = get_module_logger(__name__)


class ExtractedDocument(BaseModel):
    """Represents an extracted document with enhanced metadata."""
    
    document_id: str = Field(description="Unique identifier")
    filename: str = Field(description="Original filename")
    text: str = Field(description="Extracted text content")
    page_count: int = Field(default=1, description="Number of pages")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata"
    )
    extraction_method: str = Field(
        default="standard",
        description="Method used for extraction"
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence in extraction quality"
    )


class EnhancedDocumentIngestionAgent(BaseAgent):
    """
    Enhanced agent for extracting text from various document types.
    
    Supported formats:
    - PDF documents (via pdfplumber)
    - Word documents (.docx, .doc via python-docx)
    - Excel files (.xls, .xlsx via openpyxl/xlrd)
    - Email files (.eml via email library)
    - Plain text files (.txt, .md)
    
    Features:
    - Smart extraction based on document type
    - Comprehensive error handling
    - Metadata extraction
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".txt", ".md",
        ".xls", ".xlsx", ".eml"
    }

    async def process(
        self,
        input_data: str | Path
    ) -> ExtractedDocument:
        """
        Extract text from a document file with enhanced processing.
        
        Args:
            input_data: Path to the document file
            
        Returns:
            ExtractedDocument with extracted content and metadata
        """
        file_path = Path(input_data)
        context_id = file_path.stem if file_path.exists() else "unknown"
        
        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=context_id)
        
        if self.explanation_builder:
            self._record_input(str(input_data))
        
        self.log_start("enhanced_document_extraction", file=str(file_path))
        
        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")
        
        extension = file_path.suffix.lower()
        
        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )
        
        # Generate document ID
        document_id = self._generate_document_id(file_path)
        
        # Extract text based on file type
        try:
            if extension == ".pdf":
                text, page_count, metadata, method = self._extract_pdf(
                    file_path
                )
            elif extension in {".docx", ".doc"}:
                text, page_count, metadata, method = self._extract_docx(
                    file_path
                )
            elif extension in {".xls", ".xlsx"}:
                text, page_count, metadata, method = self._extract_excel(
                    file_path
                )
            elif extension == ".eml":
                text, page_count, metadata, method = self._extract_email(
                    file_path
                )
            else:
                text, page_count, metadata, method = self._extract_text(
                    file_path
                )
        except Exception as e:
            logger.error(f"Extraction failed for {file_path.name}: {e}")
            raise
        
        # Set default confidence based on extraction success
        confidence = 1.0 if len(text) > 100 else 0.5
        
        result = ExtractedDocument(
            document_id=document_id,
            filename=file_path.name,
            text=text,
            page_count=page_count,
            metadata=metadata,
            extraction_method=method,
            confidence=confidence
        )
        
        if self.explanation_builder:
            self._record_output(result)
            self.explanation_builder.add_metadata("page_count", page_count)
            self.explanation_builder.add_metadata("text_length", len(text))
            self.explanation_builder.add_metadata("confidence", confidence)
            self._save_explanation()
        
        self.log_complete(
            "enhanced_document_extraction",
            document_id=document_id,
            text_length=len(text),
            page_count=page_count,
            confidence=confidence
        )
        
        return result

    def _generate_document_id(self, file_path: Path) -> str:
        """Generate unique document ID from file hash."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return f"doc_{hasher.hexdigest()[:16]}"

    def _extract_pdf(
        self,
        file_path: Path
    ) -> tuple[str, int, dict[str, Any], str]:
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
        
        if not text.strip():
            logger.warning(
                f"No text extracted from PDF: {file_path.name}"
            )
        
        return text, page_count, metadata, "pdfplumber"

    def _extract_docx(
        self,
        file_path: Path
    ) -> tuple[str, int, dict[str, Any], str]:
        """Extract text from Word document."""
        doc = DocxDocument(file_path)
        
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        
        # Extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells
                )
                if row_text.strip():
                    text_parts.append(row_text)
        
        text = "\n\n".join(text_parts)
        
        metadata = {
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
        }
        
        page_count = max(1, len(text) // 3000)
        
        return text, page_count, metadata, "python-docx"

    def _extract_excel(
        self,
        file_path: Path
    ) -> tuple[str, int, dict[str, Any], str]:
        """Extract text from Excel file."""
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            text_parts = []
            
            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                text_parts.append(f"[Sheet: {sheet_name}]")
                
                for row in sheet.iter_rows(values_only=True):
                    row_text = " | ".join(
                        str(cell) if cell is not None else ""
                        for cell in row
                    )
                    if row_text.strip():
                        text_parts.append(row_text)
            
            text = "\n".join(text_parts)
            
            metadata = {
                "sheet_count": len(workbook.sheetnames),
                "sheets": workbook.sheetnames
            }
            
            page_count = len(workbook.sheetnames)
            
            return text, page_count, metadata, "openpyxl"
            
        except ImportError:
            logger.error("openpyxl not installed for Excel support")
            raise
        except Exception as e:
            logger.error(f"Excel extraction failed: {e}")
            raise

    def _extract_email(
        self,
        file_path: Path
    ) -> tuple[str, int, dict[str, Any], str]:
        """Extract text from email file."""
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f)
        
        text_parts = []
        
        # Extract headers
        text_parts.append(f"From: {msg.get('From', 'Unknown')}")
        text_parts.append(f"To: {msg.get('To', 'Unknown')}")
        text_parts.append(f"Subject: {msg.get('Subject', 'No Subject')}")
        text_parts.append(f"Date: {msg.get('Date', 'Unknown')}")
        text_parts.append("\n")
        
        # Extract body
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        text_parts.append(payload.decode("utf-8", errors="ignore"))
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                text_parts.append(payload.decode("utf-8", errors="ignore"))
        
        text = "\n".join(text_parts)
        
        metadata = {
            "from": msg.get("From"),
            "to": msg.get("To"),
            "subject": msg.get("Subject"),
            "date": msg.get("Date")
        }
        
        return text, 1, metadata, "email"

    def _extract_text(
        self,
        file_path: Path
    ) -> tuple[str, int, dict[str, Any], str]:
        """Extract text from plain text file."""
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        metadata = {"encoding": "utf-8"}
        page_count = max(1, len(text) // 3000)
        return text, page_count, metadata, "plain_text"

