"""
Docling Document Ingestion - Parse with Docling, preprocess DocTags, store in MinIO.

When ingestion_source=docling, this agent replaces DocumentIngestionAgent.

Flow: PDF/DOCX → Docling → DocTags JSON → DocTags Preprocessor → structured sections
     → MinIO (raw/parsed/metadata) + ExtractedDocument with sections for downstream.

The key improvement: instead of just export_to_markdown() (flat text), we walk the
DocTags tree to produce pre-segmented sections with titles, tables, and formatting
hints. Downstream LLM agents get structured input instead of a wall of text.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from agents.ingestion.doctags_storage import store_document
from agents.ingestion.docling_parser import SUPPORTED_EXTENSIONS
from agents.ingestion.doctags_preprocessor import (
    preprocess_doctags,
    sections_to_llm_text,
    extract_structural_hints,
)
from agents.ingestion.document_ingestion import ExtractedDocument
from agents.shared.base import BaseAgent
from logger import get_module_logger
from storage.object_storage import get_object_storage_from_config

logger = get_module_logger(__name__)


class DoclingDocumentIngestionAgent(BaseAgent):
    """
    Document ingestion via Docling + DocTags preprocessing + MinIO.

    Parses PDF/DOCX with Docling, walks the DocTags tree to extract structured
    sections (titles, tables, formatting), stores raw + DocTags + metadata in
    object storage, and returns ExtractedDocument with both structured sections
    and fallback flat text.
    """

    SUPPORTED_EXTENSIONS = SUPPORTED_EXTENSIONS

    async def process(self, input_data: str | Path) -> ExtractedDocument:
        file_path = Path(input_data)
        context_id = file_path.stem if file_path.exists() else "unknown"

        if self.enable_explanations and not self.explanation_builder:
            self._init_explanation(context_id=context_id)
        if self.explanation_builder:
            self._record_input(str(input_data))

        self.log_start("docling_extraction", file=str(file_path))

        if not file_path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                f"Supported: {self.SUPPORTED_EXTENSIONS}"
            )

        document_id = self._generate_document_id(file_path)

        # --- Parse with Docling ---
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as e:
            raise ImportError(
                "docling is required. Install with: uv add docling"
            ) from e

        converter = DocumentConverter()
        result = converter.convert(str(file_path))

        if result.document is None:
            raise RuntimeError(f"Docling conversion failed for {file_path}")

        doc = result.document
        doctags_dict = doc.export_to_dict()

        # --- DocTags Preprocessing (the key improvement) ---
        sections = preprocess_doctags(doctags_dict)
        structural_hints = extract_structural_hints(sections)

        # Structured text from sections (replaces flat markdown for downstream agents)
        structured_text = sections_to_llm_text(sections)

        # Fallback: plain markdown for backward compat / empty sections edge case
        if not structured_text.strip():
            structured_text = doc.export_to_markdown()

        page_count = len(doctags_dict.get("pages", {}))
        if not page_count:
            page_count = max(1, len(structured_text) // 3000)

        # --- Store in MinIO ---
        storage = get_object_storage_from_config()
        if storage:
            raw_bytes = file_path.read_bytes()
            meta = {
                "document_id": document_id,
                "original_filename": file_path.name,
                "page_count": page_count,
                "sections_count": len(sections),
                "tables_count": sum(len(s.tables) for s in sections),
            }
            store_document(
                storage=storage,
                document_id=document_id,
                raw_bytes=raw_bytes,
                raw_filename=file_path.name,
                doctags_json=doctags_dict,
                metadata=meta,
            )
        else:
            logger.warning(
                "object_storage_not_configured",
                msg="DocTags not stored (MinIO/COS not configured)",
            )

        # Serialize sections for ExtractedDocument (Pydantic-safe dicts)
        sections_dicts = [s.model_dump() for s in sections]

        extracted = ExtractedDocument(
            document_id=document_id,
            filename=file_path.name,
            text=structured_text,
            page_count=page_count,
            metadata={
                "source": "docling",
                "stored_in_minio": storage is not None,
                "sections_count": len(sections),
                "tables_count": sum(len(s.tables) for s in sections),
            },
            sections=sections_dicts,
            structural_hints=structural_hints,
        )

        if self.explanation_builder:
            self._record_output(extracted)
            self.explanation_builder.add_metadata("page_count", page_count)
            self.explanation_builder.add_metadata("text_length", len(structured_text))
            self.explanation_builder.add_metadata("sections_count", len(sections))
            self._save_explanation()

        self.log_complete(
            "docling_extraction",
            document_id=document_id,
            text_length=len(structured_text),
            page_count=page_count,
            sections=len(sections),
            tables=sum(len(s.tables) for s in sections),
        )
        return extracted

    def _generate_document_id(self, file_path: Path) -> str:
        """Generate document ID from file content hash."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return f"doc_{hasher.hexdigest()[:16]}"
