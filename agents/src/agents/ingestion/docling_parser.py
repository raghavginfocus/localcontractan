"""
Docling Parser - Parse PDF/DOCX to DocTags JSON.

Uses IBM Docling for structured document extraction. Output is stored
in object storage (MinIO / IBM COS) under procurement-contracts/parsed/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Supported extensions for Docling
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx"}


def parse_document(source: str | Path) -> dict[str, Any]:
    """
    Parse a document with Docling and return DocTags-style JSON dict.

    Args:
        source: Path to PDF, DOCX, or other supported file.

    Returns:
        Dict representation of the document (DocTags-compatible structure).

    Raises:
        FileNotFoundError: If source does not exist.
        ValueError: If file type is not supported.
        RuntimeError: If Docling conversion fails.
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {suffix}. "
            f"Supported: {SUPPORTED_EXTENSIONS}"
        )

    try:
        from docling.document_converter import DocumentConverter
    except ImportError as e:
        raise ImportError(
            "docling is required for Docling parsing. "
            "Install with: uv add docling"
        ) from e

    converter = DocumentConverter()
    result = converter.convert(str(path))

    if result.document is None:
        raise RuntimeError(f"Docling conversion failed for {path}")

    doc_dict = result.document.export_to_dict()
    pages = doc_dict.get("pages", []) if isinstance(doc_dict, dict) else []
    logger.info(
        "docling_parsed",
        path=str(path),
        page_count=len(pages),
    )
    return doc_dict


def parse_document_to_json_bytes(source: str | Path) -> bytes:
    """
    Parse a document and return its DocTags JSON as UTF-8 bytes.

    Convenience for uploading to object storage.
    """
    doc_dict = parse_document(source)
    return json.dumps(doc_dict, ensure_ascii=False, indent=2).encode("utf-8")
