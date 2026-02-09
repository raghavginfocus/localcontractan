"""
Artifact Store - Manages storage of generated artifacts for transparency and review.

Stores:
- Generated RDF/Turtle for each document
- Generated OWL extensions
- Generated inference rules
- Ingestion logs and metadata

Now uses async file I/O for better performance.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from logger import get_module_logger

logger = get_module_logger(__name__)

# Default base directory for artifacts
# Detect if running in container or locally
import os
if os.path.exists("/app/data"):
    # Running in container
    DEFAULT_ARTIFACT_DIR = Path("/app/data/generated")
else:
    # Running locally
    DEFAULT_ARTIFACT_DIR = Path("agents/data/generated")


class ArtifactStore:
    """
    Manages storage of all generated artifacts during ingestion.
    
    Directory Structure:
    data/generated/
    ├── rdf/                    # Generated RDF for each document
    │   ├── doc_001_20240110.ttl
    │   └── doc_002_20240110.ttl
    ├── ontology/               # Generated OWL extensions
    │   ├── dataprotectionclause_20240110.ttl
    │   └── extensions_combined_20240110.ttl
    ├── rules/                  # Generated Jena rules and SPARQL
    │   ├── highdataretentionrisk_20240110.rules
    │   └── highdataretentionrisk_20240110.sparql
    └── logs/                   # Ingestion logs and metadata
        ├── doc_001_20240110.json
        └── doc_002_20240110.json
    """

    def __init__(self, base_dir: Path | str | None = None):
        """
        Initialize the artifact store.
        
        Args:
            base_dir: Base directory for all artifacts
        """
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_ARTIFACT_DIR
        
        # Create subdirectories for artifacts
        self.rdf_dir = self.base_dir / "rdf"
        self.ontology_dir = self.base_dir / "ontology"
        self.rules_dir = self.base_dir / "rules"
        
        # Use centralized logging for ingestion logs
        from logging_config import get_module_log_dir
        self.logs_dir = get_module_log_dir("ingestion")
        
        for dir_path in [self.rdf_dir, self.ontology_dir, self.rules_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info("ArtifactStore initialized", base_dir=str(self.base_dir))

    async def save_rdf(
        self,
        document_id: str,
        rdf_data: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Save generated RDF for a document (async).
        
        Args:
            document_id: Document identifier
            rdf_data: RDF data in Turtle format
            metadata: Optional metadata to include as comments
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{document_id}_{timestamp}.ttl"
        file_path = self.rdf_dir / filename
        
        content = f"# Generated RDF for document: {document_id}\n"
        content += f"# Generated: {datetime.now().isoformat()}\n"
        if metadata:
            for key, value in metadata.items():
                content += f"# {key}: {value}\n"
        content += "\n"
        content += rdf_data
        
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
        
        logger.info("Saved RDF artifact", document_id=document_id, path=str(file_path))
        return file_path
    
    async def save_json_file(
        self,
        file_path: Path,
        data: dict[str, Any],
    ) -> None:
        """
        Async helper to save JSON data to a file.
        
        Args:
            file_path: Path to save the file
            data: Data to save as JSON
        """
        content = json.dumps(data, indent=2, default=str)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)
    
    def save_rdf_sync(
        self,
        document_id: str,
        rdf_data: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """
        Synchronous version of save_rdf (for backward compatibility).
        
        Args:
            document_id: Document identifier
            rdf_data: RDF data in Turtle format
            metadata: Optional metadata to include as comments
            
        Returns:
            Path to saved file
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're in an async context, use the async version
                # This is a fallback - prefer using save_rdf() directly
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.save_rdf(document_id, rdf_data, metadata)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.save_rdf(document_id, rdf_data, metadata)
                )
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.save_rdf(document_id, rdf_data, metadata))

    async def save_ontology_extension(
        self,
        name: str,
        owl_data: str,
        description: str = "",
    ) -> Path:
        """
        Save generated OWL ontology extension (async).
        
        Args:
            name: Name of the concept/extension
            owl_data: OWL data in Turtle format
            description: Description of the extension
            
        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name.lower().replace(' ', '_')}_{timestamp}.ttl"
        file_path = self.ontology_dir / filename
        
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(f"# Generated OWL Extension: {name}\n")
            await f.write(f"# Generated: {datetime.now().isoformat()}\n")
            await f.write(f"# Description: {description}\n")
            await f.write("\n")
            await f.write(owl_data)
        
        logger.info("Saved ontology extension", name=name, path=str(file_path))
        return file_path

    async def save_rule(
        self,
        rule_name: str,
        jena_rule: str,
        sparql_rule: str,
        description: str = "",
    ) -> tuple[Path, Path]:
        """
        Save generated inference rule (both Jena and SPARQL formats, async).
        
        Args:
            rule_name: Name of the rule
            jena_rule: Jena rule syntax
            sparql_rule: SPARQL INSERT equivalent
            description: Description of the rule
            
        Returns:
            Tuple of (jena_path, sparql_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        jena_filename = f"{rule_name.lower().replace(' ', '_')}_{timestamp}.rules"
        sparql_filename = f"{rule_name.lower().replace(' ', '_')}_{timestamp}.sparql"
        
        jena_path = self.rules_dir / jena_filename
        sparql_path = self.rules_dir / sparql_filename
        
        async with aiofiles.open(jena_path, "w", encoding="utf-8") as f:
            await f.write(f"# Generated Jena Rule: {rule_name}\n")
            await f.write(f"# Generated: {datetime.now().isoformat()}\n")
            await f.write(f"# Description: {description}\n")
            await f.write("\n")
            await f.write(jena_rule)

        async with aiofiles.open(sparql_path, "w", encoding="utf-8") as f:
            await f.write(f"# Generated SPARQL Rule: {rule_name}\n")
            await f.write(f"# Generated: {datetime.now().isoformat()}\n")
            await f.write(f"# Description: {description}\n")
            await f.write("\n")
            await f.write(sparql_rule)
        
        logger.info("Saved rule artifacts", rule_name=rule_name, 
                   jena_path=str(jena_path), sparql_path=str(sparql_path))
        return jena_path, sparql_path

    async def save_ingestion_log(
        self,
        document_id: str,
        result: dict[str, Any],
    ) -> Path:
        """
        Ingestion log saving disabled - using Phoenix tracing instead.
        Phoenix captures all ingestion steps and results.
        
        Args:
            document_id: Document identifier
            result: Full ingestion result as dict
            
        Returns:
            Path (not created, for compatibility)
        """
        # Disabled for performance - Phoenix provides better observability
        logger.debug("Ingestion log saving disabled (using Phoenix)", document_id=document_id)
        return Path(f"/dev/null/{document_id}")

    async def save_extraction_results(
        self,
        document_id: str,
        clauses: list[dict[str, Any]],
        entities: dict[str, Any],
        obligations: list[dict[str, Any]],
        risks: list[dict[str, Any]],
    ) -> Path:
        """
        Extraction results saving disabled - using Phoenix tracing instead.
        Phoenix captures all extraction steps and intermediate results.
        
        Args:
            document_id: Document identifier
            clauses: Extracted clauses
            entities: Extracted entities
            obligations: Extracted obligations
            risks: Extracted risks
            
        Returns:
            Path (not created, for compatibility)
        """
        # Disabled for performance - Phoenix provides better observability
        logger.debug("Extraction results saving disabled (using Phoenix)", document_id=document_id)
        return Path(f"/dev/null/{document_id}_extractions")

    def get_all_rdf_files(self) -> list[Path]:
        """List all generated RDF files."""
        return sorted(self.rdf_dir.glob("*.ttl"), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_all_ontology_files(self) -> list[Path]:
        """List all generated ontology extension files."""
        return sorted(self.ontology_dir.glob("*.ttl"), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_all_rule_files(self) -> list[Path]:
        """List all generated rule files."""
        return sorted(self.rules_dir.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_all_logs(self) -> list[Path]:
        """List all ingestion log files."""
        return sorted(self.logs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def get_document_artifacts(self, document_id: str) -> dict[str, list[Path]]:
        """
        Get all artifacts for a specific document.
        
        Args:
            document_id: Document identifier
            
        Returns:
            Dict with lists of artifact paths by type
        """
        return {
            "rdf": list(self.rdf_dir.glob(f"{document_id}_*.ttl")),
            "logs": list(self.logs_dir.glob(f"{document_id}_*.json")),
        }

    def cleanup_old_artifacts(self, days: int = 30) -> int:
        """
        Remove artifacts older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of files removed
        """
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0
        
        for dir_path in [self.rdf_dir, self.ontology_dir, self.rules_dir, self.logs_dir]:
            for file_path in dir_path.iterdir():
                if file_path.is_file():
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if mtime < cutoff:
                        file_path.unlink()
                        removed += 1
        
        logger.info("Cleaned up old artifacts", removed=removed, days=days)
        return removed

    def get_summary(self) -> dict[str, Any]:
        """Get summary of all stored artifacts."""
        return {
            "base_dir": str(self.base_dir),
            "rdf_files": len(list(self.rdf_dir.glob("*.ttl"))),
            "ontology_files": len(list(self.ontology_dir.glob("*.ttl"))),
            "rule_files": len(list(self.rules_dir.glob("*.rules"))),
            "sparql_files": len(list(self.rules_dir.glob("*.sparql"))),
            "log_files": len(list(self.logs_dir.glob("*.json"))),
        }
