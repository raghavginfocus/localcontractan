"""
Metadata Loader - Loads contract metadata from cacheview.json.

This module provides utilities to load and map contract metadata from
CloudNotes database cache to document files during ingestion.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ContractMetadata:
    """Contract metadata from CloudNotes database."""
    
    # Core identifiers
    doc_id: str = ""
    contract_id: str = ""
    project_name: str = ""
    parent_contract: str = ""
    
    # Document info
    doc_name: str = ""
    doc_path: str = ""
    doc_type: str = ""
    status: str = ""
    
    # Supplier info
    supplier_name: str = ""
    supplier_id: str = ""
    
    # Owner info
    owner_name: str = ""
    owner_id: str = ""
    
    # Dates
    effective_date: str = ""
    expiration_date: str = ""
    
    # Contract details
    agreement_type: str = ""
    business_unit: str = ""
    signatories: Optional[str] = None
    
    # Additional fields (for extensibility)
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_cacheview_entry(cls, entry: Dict[str, Any]) -> "ContractMetadata":
        """
        Create ContractMetadata from a cacheview.json entry.
        
        Args:
            entry: Dict from cacheview.json value array
            
        Returns:
            ContractMetadata instance
        """
        # Extract known fields
        metadata = cls(
            doc_id=entry.get("_id", ""),
            contract_id=entry.get("Contract_ID", ""),
            project_name=entry.get("Project_Name", ""),
            parent_contract=entry.get("Parent_Contract", ""),
            doc_name=entry.get("Doc_Name", ""),
            doc_path=entry.get("Doc_Path", ""),
            doc_type=entry.get("Doc_Type", ""),
            status=entry.get("Status", ""),
            supplier_name=entry.get("Supplier_Name", ""),
            supplier_id=entry.get("Supplier_ID", ""),
            owner_name=entry.get("Owner_Name", ""),
            owner_id=entry.get("Owner_ID", ""),
            effective_date=entry.get("Effective_Date", ""),
            expiration_date=entry.get("Expiration_Date", ""),
            agreement_type=entry.get("Agreement_Type", ""),
            business_unit=entry.get("Business_Unit", ""),
            signatories=entry.get("Signaturies"),  # Note: typo in source
        )
        
        # Store any additional fields not in the dataclass
        known_fields = {
            "_id", "Contract_ID", "Project_Name", "Parent_Contract",
            "Doc_Name", "Doc_Path", "Doc_Type", "Status",
            "Supplier_Name", "Supplier_ID", "Owner_Name", "Owner_ID",
            "Effective_Date", "Expiration_Date", "Agreement_Type",
            "Business_Unit", "Signaturies"
        }
        
        for key, value in entry.items():
            if key not in known_fields and value is not None:
                metadata.extra_fields[key] = value
        
        return metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "doc_id": self.doc_id,
            "contract_id": self.contract_id,
            "project_name": self.project_name,
            "parent_contract": self.parent_contract,
            "doc_name": self.doc_name,
            "doc_path": self.doc_path,
            "doc_type": self.doc_type,
            "status": self.status,
            "supplier_name": self.supplier_name,
            "supplier_id": self.supplier_id,
            "owner_name": self.owner_name,
            "owner_id": self.owner_id,
            "effective_date": self.effective_date,
            "expiration_date": self.expiration_date,
            "agreement_type": self.agreement_type,
            "business_unit": self.business_unit,
            "signatories": self.signatories,
        }
        
        # Add extra fields
        result.update(self.extra_fields)
        
        return result


class MetadataLoader:
    """
    Loads and manages contract metadata from cacheview.json.
    
    Usage:
        loader = MetadataLoader("path/to/cacheview.json")
        metadata = loader.get_metadata_by_doc_id("Doc1384897746")
        metadata = loader.get_metadata_by_contract_id("4903JP0080")
        metadata = loader.get_metadata_by_filename("SOW Exhibit 1.doc")
    """
    
    def __init__(self, cacheview_path: str | Path):
        """
        Initialize metadata loader.
        
        Args:
            cacheview_path: Path to cacheview.json file
        """
        self.cacheview_path = Path(cacheview_path)
        self._metadata_cache: Dict[str, ContractMetadata] = {}
        self._doc_id_index: Dict[str, ContractMetadata] = {}
        self._contract_id_index: Dict[str, list[ContractMetadata]] = {}
        self._filename_index: Dict[str, ContractMetadata] = {}
        
        if self.cacheview_path.exists():
            self._load_metadata()
        else:
            logger.warning(
                "cacheview.json not found",
                path=str(self.cacheview_path)
            )
    
    def _load_metadata(self) -> None:
        """Load and index metadata from cacheview.json."""
        try:
            with open(self.cacheview_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Handle different cacheview.json structures
            if isinstance(data, list):
                entries = data
            elif isinstance(data, dict):
                # If it's a dict with "key" and "value" structure
                entries = []
                for item in data.get("rows", []):
                    if "value" in item and isinstance(item["value"], list):
                        entries.extend(item["value"])
                    elif "value" in item:
                        entries.append(item["value"])
                
                # If no rows, try direct entries
                if not entries and "value" in data:
                    if isinstance(data["value"], list):
                        entries = data["value"]
                    else:
                        entries = [data["value"]]
            else:
                logger.error("Unexpected cacheview.json format")
                return
            
            # Process each entry
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                
                metadata = ContractMetadata.from_cacheview_entry(entry)
                
                # Index by doc_id
                if metadata.doc_id:
                    self._doc_id_index[metadata.doc_id] = metadata
                
                # Index by contract_id (multiple docs can have same contract_id)
                if metadata.contract_id:
                    if metadata.contract_id not in self._contract_id_index:
                        self._contract_id_index[metadata.contract_id] = []
                    self._contract_id_index[metadata.contract_id].append(metadata)
                
                # Index by filename (normalized)
                if metadata.doc_name:
                    normalized_name = self._normalize_filename(metadata.doc_name)
                    self._filename_index[normalized_name] = metadata
                
                # Also index by doc_path if available
                if metadata.doc_path:
                    path_name = Path(metadata.doc_path).name
                    normalized_path = self._normalize_filename(path_name)
                    self._filename_index[normalized_path] = metadata
            
            logger.info(
                "Loaded contract metadata",
                total_entries=len(self._doc_id_index),
                unique_contracts=len(self._contract_id_index),
            )
            
        except Exception as e:
            logger.error("Failed to load cacheview.json", error=str(e))
    
    @staticmethod
    def _normalize_filename(filename: str) -> str:
        """Normalize filename for matching."""
        # Remove extension, lowercase, strip whitespace
        name = Path(filename).stem.lower().strip()
        # Remove special characters
        name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-"))
        return name
    
    def get_metadata_by_doc_id(self, doc_id: str) -> Optional[ContractMetadata]:
        """Get metadata by document ID."""
        return self._doc_id_index.get(doc_id)
    
    def get_metadata_by_contract_id(
        self, contract_id: str
    ) -> Optional[ContractMetadata]:
        """
        Get metadata by contract ID.
        
        Note: Returns first match if multiple documents share the same contract_id.
        Use get_all_metadata_by_contract_id() to get all matches.
        """
        matches = self._contract_id_index.get(contract_id, [])
        return matches[0] if matches else None
    
    def get_all_metadata_by_contract_id(
        self, contract_id: str
    ) -> list[ContractMetadata]:
        """Get all metadata entries for a contract ID."""
        return self._contract_id_index.get(contract_id, [])
    
    def get_metadata_by_filename(
        self, filename: str
    ) -> Optional[ContractMetadata]:
        """
        Get metadata by filename (fuzzy match).
        
        Args:
            filename: Original filename or path
            
        Returns:
            ContractMetadata if found, None otherwise
        """
        normalized = self._normalize_filename(filename)
        return self._filename_index.get(normalized)
    
    def get_metadata_by_path(self, file_path: str | Path) -> Optional[ContractMetadata]:
        """
        Get metadata by file path.
        
        Tries multiple strategies:
        1. Exact doc_path match
        2. Filename match
        3. Doc_id from filename (if filename is like "Doc1384897746.pdf")
        """
        path = Path(file_path)
        
        # Strategy 1: Try exact doc_path match
        for metadata in self._doc_id_index.values():
            if metadata.doc_path and Path(metadata.doc_path).name == path.name:
                return metadata
        
        # Strategy 2: Try filename match
        metadata = self.get_metadata_by_filename(path.name)
        if metadata:
            return metadata
        
        # Strategy 3: Extract doc_id from filename (e.g., "Doc1384897746.pdf")
        stem = path.stem
        if stem.startswith("Doc") and stem[3:].isdigit():
            doc_id = stem
            metadata = self.get_metadata_by_doc_id(doc_id)
            if metadata:
                return metadata
        
        logger.debug("No metadata found for file", path=str(file_path))
        return None
    
    def get_all_metadata(self) -> list[ContractMetadata]:
        """Get all loaded metadata entries."""
        return list(self._doc_id_index.values())
    
    def has_metadata(self) -> bool:
        """Check if any metadata was loaded."""
        return len(self._doc_id_index) > 0


# Global instance (singleton pattern)
_metadata_loader: Optional[MetadataLoader] = None


def get_metadata_loader(cacheview_path: Optional[str | Path] = None) -> MetadataLoader:
    """
    Get or create global metadata loader instance.
    
    Args:
        cacheview_path: Path to cacheview.json (required on first call)
        
    Returns:
        MetadataLoader instance
    """
    global _metadata_loader
    
    if _metadata_loader is None:
        if cacheview_path is None:
            # Try default locations
            default_paths = [
                Path("cacheview.json"),
                Path("data/cacheview.json"),
                Path("cache/cacheview.json"),
            ]
            
            for path in default_paths:
                if path.exists():
                    cacheview_path = path
                    break
            
            if cacheview_path is None:
                logger.warning("No cacheview.json found, creating empty loader")
                cacheview_path = Path("cacheview.json")  # Will log warning
        
        _metadata_loader = MetadataLoader(cacheview_path)
    
    return _metadata_loader


def reset_metadata_loader() -> None:
    """Reset global metadata loader (useful for testing)."""
    global _metadata_loader
    _metadata_loader = None

# Made with Bob
