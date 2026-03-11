"""
DocTags Storage - Store raw, parsed, and metadata in MinIO/IBM COS.

Bucket layout (procurement-contracts):
  raw/YYYY/MM/DD/{document_id}.pdf
  parsed/YYYY/MM/DD/{document_id}.json   # DocTags
  metadata/YYYY/MM/DD/{document_id}_meta.json
  rejected/YYYY/MM/DD/{document_id}_reason.txt  # Failed quality
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

from storage.object_storage import ObjectStorageBackend

logger = structlog.get_logger(__name__)


def _date_prefix() -> str:
    """Return YYYY/MM/DD for object keys."""
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}/{now.month:02d}/{now.day:02d}"


def store_document(
    storage: ObjectStorageBackend,
    document_id: str,
    raw_bytes: bytes,
    raw_filename: str,
    doctags_json: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> dict[str, str]:
    """
    Store raw file, parsed DocTags, and metadata in object storage.

    Returns dict with keys: raw_key, parsed_key, metadata_key.
    """
    prefix = _date_prefix()
    raw_ext = Path(raw_filename).suffix or ".bin"
    raw_key = f"raw/{prefix}/{document_id}{raw_ext}"
    parsed_key = f"parsed/{prefix}/{document_id}.json"
    meta_key = f"metadata/{prefix}/{document_id}_meta.json"

    # Upload raw
    content_type = "application/pdf" if raw_ext.lower() == ".pdf" else "application/octet-stream"
    storage.upload(raw_key, raw_bytes, content_type=content_type)

    # Upload parsed DocTags
    parsed_bytes = json.dumps(doctags_json, ensure_ascii=False, indent=2).encode("utf-8")
    storage.upload(parsed_key, parsed_bytes, content_type="application/json")

    # Upload metadata
    meta = metadata or {}
    meta.setdefault("document_id", document_id)
    meta.setdefault("original_filename", raw_filename)
    meta.setdefault("stored_at", datetime.now(timezone.utc).isoformat())
    meta_bytes = json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8")
    storage.upload(meta_key, meta_bytes, content_type="application/json")

    logger.info(
        "doctags_stored",
        document_id=document_id,
        raw_key=raw_key,
        parsed_key=parsed_key,
    )
    return {"raw_key": raw_key, "parsed_key": parsed_key, "metadata_key": meta_key}


def store_rejected(
    storage: ObjectStorageBackend,
    document_id: str,
    raw_bytes: bytes,
    raw_filename: str,
    reason: str,
) -> str:
    """Store rejected document and reason. Returns raw_key."""
    prefix = _date_prefix()
    raw_ext = Path(raw_filename).suffix or ".bin"
    raw_key = f"rejected/{prefix}/{document_id}{raw_ext}"
    reason_key = f"rejected/{prefix}/{document_id}_reason.txt"

    content_type = "application/pdf" if raw_ext.lower() == ".pdf" else "application/octet-stream"
    storage.upload(raw_key, raw_bytes, content_type=content_type)
    storage.upload(reason_key, reason.encode("utf-8"), content_type="text/plain")
    logger.info("document_rejected", document_id=document_id, reason=reason)
    return raw_key