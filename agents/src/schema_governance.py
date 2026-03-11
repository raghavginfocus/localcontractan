"""
Schema Governance - Manages schema evolution, versioning, conflicts, and rollback.

Features:
- Schema versioning
- Conflict detection and resolution
- Rollback capability
- Schema change tracking
"""

from datetime import datetime
from pathlib import Path
from typing import Any
from enum import Enum
import json
import shutil

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, OWL
from pydantic import BaseModel, Field

from config import get_settings
from logger import get_module_logger
from storage.object_storage import get_object_storage_from_config

logger = get_module_logger(__name__)


class ConflictType(str, Enum):
    """Types of schema conflicts."""
    NAMING = "naming"  # Duplicate class/property names
    HIERARCHY = "hierarchy"  # Conflicting subclass relationships
    PROPERTY = "property"  # Conflicting property definitions
    DISJOINT = "disjoint"  # Violates disjoint class constraints


class SchemaConflict(BaseModel):
    """Represents a schema conflict."""
    
    conflict_type: ConflictType
    description: str
    affected_classes: list[str]
    resolution: str | None = None
    resolved: bool = False


class SchemaVersion(BaseModel):
    """Represents a schema version."""
    
    version_id: str
    timestamp: datetime
    description: str
    ontology_files: list[str]
    rule_files: list[str]
    shacl_files: list[str]
    changes: list[str]
    created_by: str = "system"


class SchemaGovernance:
    """
    Manages schema evolution with versioning, conflict resolution, and rollback.
    """
    
    def __init__(self, version_dir: Path | None = None):
        """
        Initialize schema governance.
        
        Args:
            version_dir: Directory for storing schema versions
        """
        self.settings = get_settings()
        self.version_dir = version_dir or Path("data/generated/schema_versions")
        self.version_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger.bind(component="SchemaGovernance")
        self.PROC = Namespace(self.settings.procurement_namespace)
        self._latest_pointer_name = "latest.json"

    def _update_latest_pointer(
        self,
        version: SchemaVersion,
        storage,
        prefix_root: str = "schema_versions",
    ) -> None:
        """
        Update the pointer to the latest schema version.

        Writes:
        - Local file: version_dir/latest.json
        - MinIO object: schema_versions/latest.json (best effort)
        """
        latest_data = {
            "version_id": version.version_id,
            "timestamp": version.timestamp.isoformat(),
            "description": version.description,
        }
        # Local pointer
        latest_path = self.version_dir / self._latest_pointer_name
        try:
            with open(latest_path, "w", encoding="utf-8") as f:
                json.dump(latest_data, f, indent=2)
        except Exception as e:
            self.logger.warning(
                "Failed to write local latest schema pointer",
                error=str(e),
            )

        # Remote pointer (object storage)
        try:
            if storage:
                storage.upload(
                    key=f"{prefix_root}/{self._latest_pointer_name}",
                    data=json.dumps(latest_data, indent=2).encode("utf-8"),
                    content_type="application/json",
                )
        except Exception as e:
            self.logger.warning(
                "Failed to upload latest schema pointer to object storage",
                error=str(e),
            )
    
    def create_version(
        self,
        description: str,
        ontology_files: list[str],
        rule_files: list[str] | None = None,
        shacl_files: list[str] | None = None,
        changes: list[str] | None = None,
    ) -> SchemaVersion:
        """
        Create a new schema version snapshot.
        
        Args:
            description: Description of this version
            ontology_files: List of ontology file paths
            rule_files: List of rule file paths
            shacl_files: List of SHACL file paths
            changes: List of change descriptions
        
        Returns:
            SchemaVersion object
        """
        version_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        version_path = self.version_dir / version_id
        version_path.mkdir(parents=True, exist_ok=True)
        
        # Copy files to version directory
        copied_ontology = []
        for file_path in ontology_files:
            if Path(file_path).exists():
                dest = version_path / Path(file_path).name
                shutil.copy2(file_path, dest)
                copied_ontology.append(str(dest))
        
        copied_rules = []
        if rule_files:
            for file_path in rule_files:
                if Path(file_path).exists():
                    dest = version_path / Path(file_path).name
                    shutil.copy2(file_path, dest)
                    copied_rules.append(str(dest))
        
        copied_shacl = []
        if shacl_files:
            for file_path in shacl_files:
                if Path(file_path).exists():
                    dest = version_path / Path(file_path).name
                    shutil.copy2(file_path, dest)
                    copied_shacl.append(str(dest))
        
        # Save version metadata
        version = SchemaVersion(
            version_id=version_id,
            timestamp=datetime.now(),
            description=description,
            ontology_files=copied_ontology,
            rule_files=copied_rules,
            shacl_files=copied_shacl,
            changes=changes or [],
        )
        
        # Save metadata
        metadata_path = version_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(version.model_dump(mode="json"), f, indent=2, default=str)

        # Best-effort: also persist schema version bundle to object storage (MinIO/COS)
        # so schema history survives container restarts in production, and update
        # the latest-version pointer.
        try:
            storage = get_object_storage_from_config()
            if storage:
                prefix = f"schema_versions/{version_id}"
                storage.upload(
                    key=f"{prefix}/metadata.json",
                    data=metadata_path.read_bytes(),
                    content_type="application/json",
                )
                for fp in copied_ontology + copied_rules + copied_shacl:
                    p = Path(fp)
                    if p.exists():
                        storage.upload(
                            key=f"{prefix}/{p.name}",
                            data=p.read_bytes(),
                            content_type="text/plain",
                        )
                # Update latest pointer after successful upload
                self._update_latest_pointer(version, storage, prefix_root="schema_versions")
                self.logger.info(
                    "Schema version uploaded to object storage",
                    version_id=version_id,
                    prefix=prefix,
                )
        except Exception as e:
            self.logger.warning(
                "Failed to upload schema version to object storage",
                version_id=version_id,
                error=str(e),
            )
        
        self.logger.info(
            "Schema version created",
            version_id=version_id,
            description=description,
            ontology_files=len(copied_ontology),
        )
        
        return version
    
    def detect_conflicts(
        self,
        new_ontology: Graph,
        existing_ontology: Graph,
    ) -> list[SchemaConflict]:
        """
        Detect conflicts between new and existing ontology.
        
        Args:
            new_ontology: New ontology graph
            existing_ontology: Existing ontology graph
        
        Returns:
            List of detected conflicts
        """
        conflicts = []
        
        # 1. Check for naming conflicts (duplicate class names)
        new_classes = set()
        existing_classes = set()
        
        for s, p, o in new_ontology.triples((None, RDF.type, OWL.Class)):
            class_name = self._get_local_name(s)
            if class_name in new_classes:
                conflicts.append(SchemaConflict(
                    conflict_type=ConflictType.NAMING,
                    description=f"Duplicate class name in new ontology: {class_name}",
                    affected_classes=[class_name],
                ))
            new_classes.add(class_name)
        
        for s, p, o in existing_ontology.triples((None, RDF.type, OWL.Class)):
            class_name = self._get_local_name(s)
            existing_classes.add(class_name)
        
        # Check for conflicts between new and existing
        overlapping = new_classes.intersection(existing_classes)
        if overlapping:
            conflicts.append(SchemaConflict(
                conflict_type=ConflictType.NAMING,
                description=f"Class names already exist: {', '.join(overlapping)}",
                affected_classes=list(overlapping),
            ))
        
        # 2. Check for hierarchy conflicts
        # (This is simplified - full implementation would check for cycles, etc.)
        
        # 3. Check for property conflicts
        new_props = set()
        existing_props = set()
        
        for s, p, o in new_ontology.triples((None, RDF.type, OWL.ObjectProperty)):
            prop_name = self._get_local_name(s)
            new_props.add(prop_name)
        
        for s, p, o in new_ontology.triples((None, RDF.type, OWL.DatatypeProperty)):
            prop_name = self._get_local_name(s)
            new_props.add(prop_name)
        
        for s, p, o in existing_ontology.triples((None, RDF.type, OWL.ObjectProperty)):
            prop_name = self._get_local_name(s)
            existing_props.add(prop_name)
        
        for s, p, o in existing_ontology.triples((None, RDF.type, OWL.DatatypeProperty)):
            prop_name = self._get_local_name(s)
            existing_props.add(prop_name)
        
        overlapping_props = new_props.intersection(existing_props)
        if overlapping_props:
            conflicts.append(SchemaConflict(
                conflict_type=ConflictType.PROPERTY,
                description=f"Property names already exist: {', '.join(overlapping_props)}",
                affected_classes=list(overlapping_props),
            ))
        
        return conflicts
    
    def resolve_conflict(
        self,
        conflict: SchemaConflict,
        resolution_strategy: str = "merge",
    ) -> SchemaConflict:
        """
        Resolve a schema conflict.
        
        Args:
            conflict: Conflict to resolve
            resolution_strategy: Strategy: "merge", "rename", "skip", "override"
        
        Returns:
            Resolved conflict
        """
        if resolution_strategy == "merge":
            conflict.resolution = f"Merge with existing: {', '.join(conflict.affected_classes)}"
        elif resolution_strategy == "rename":
            conflict.resolution = f"Rename new classes: {', '.join(conflict.affected_classes)}"
        elif resolution_strategy == "skip":
            conflict.resolution = f"Skip conflicting classes: {', '.join(conflict.affected_classes)}"
        elif resolution_strategy == "override":
            conflict.resolution = f"Override existing: {', '.join(conflict.affected_classes)}"
        
        conflict.resolved = True
        return conflict
    
    def rollback_to_version(
        self,
        version_id: str,
        target_dir: Path,
    ) -> bool:
        """
        Rollback to a specific schema version.
        
        Args:
            version_id: Version ID to rollback to
            target_dir: Directory to restore files to
        
        Returns:
            True if rollback successful
        """
        version_path = self.version_dir / version_id
        if not version_path.exists():
            self.logger.error("Version not found", version_id=version_id)
            return False
        
        # Load metadata
        metadata_path = version_path / "metadata.json"
        if not metadata_path.exists():
            self.logger.error("Version metadata not found", version_id=version_id)
            return False
        
        with open(metadata_path) as f:
            metadata = json.load(f)
        
        # Restore files
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in metadata.get("ontology_files", []):
            source = Path(file_path)
            if source.exists():
                dest = target_dir / source.name
                shutil.copy2(source, dest)
                self.logger.info("Restored ontology file", file=dest)
        
        for file_path in metadata.get("rule_files", []):
            source = Path(file_path)
            if source.exists():
                dest = target_dir / source.name
                shutil.copy2(source, dest)
                self.logger.info("Restored rule file", file=dest)
        
        for file_path in metadata.get("shacl_files", []):
            source = Path(file_path)
            if source.exists():
                dest = target_dir / source.name
                shutil.copy2(source, dest)
                self.logger.info("Restored SHACL file", file=dest)
        
        self.logger.info("Rollback completed", version_id=version_id, target_dir=str(target_dir))
        return True
    
    def list_versions(self) -> list[SchemaVersion]:
        """List all schema versions."""
        versions = []
        
        for version_dir in sorted(self.version_dir.iterdir()):
            if version_dir.is_dir():
                metadata_path = version_dir / "metadata.json"
                if metadata_path.exists():
                    with open(metadata_path) as f:
                        data = json.load(f)
                        versions.append(SchemaVersion(**data))
        
        return sorted(versions, key=lambda v: v.timestamp, reverse=True)
    
    def get_latest_version(self) -> SchemaVersion | None:
        """Get the latest schema version."""
        versions = self.list_versions()
        return versions[0] if versions else None
    
    def _get_local_name(self, uri: URIRef) -> str:
        """Extract local name from URI."""
        uri_str = str(uri)
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        elif "/" in uri_str:
            return uri_str.split("/")[-1]
        return uri_str
