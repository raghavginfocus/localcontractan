"""
Dynamic Ontology Manager - Loads and manages ontology schemas at runtime.

This module provides dynamic ontology loading capabilities, eliminating hardcoded
class mappings and enabling true schema evolution.
"""

from pathlib import Path
from typing import Any
from datetime import datetime

from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL
from rdflib.term import Node

from config import Settings, get_settings
from logger import get_module_logger

logger = get_module_logger(__name__)


class OntologySchema:
    """Represents a loaded ontology schema with its classes and properties."""
    
    def __init__(
        self,
        graph: Graph,
        namespace: str,
        version: str | None = None,
        loaded_at: datetime | None = None,
    ):
        self.graph = graph
        self.namespace = Namespace(namespace)
        self.version = version or "1.0.0"
        self.loaded_at = loaded_at or datetime.now()
        
        # Extract classes and properties
        self._classes = self._extract_classes()
        self._properties = self._extract_properties()
        self._class_hierarchy = self._build_hierarchy()
    
    def _extract_classes(self) -> dict[str, URIRef]:
        """Extract all OWL classes from the ontology."""
        classes = {}
        
        for s, p, o in self.graph.triples((None, RDF.type, OWL.Class)):
            class_uri = s
            # Get local name (e.g., "TerminationClause" from full URI)
            local_name = str(class_uri).split('#')[-1].split('/')[-1]
            classes[local_name] = class_uri
            
            # Also store with proc: prefix for compatibility
            classes[f"proc:{local_name}"] = class_uri
        
        logger.info("Extracted OWL classes", count=len(classes) // 2)
        return classes
    
    def _extract_properties(self) -> dict[str, URIRef]:
        """Extract all properties (ObjectProperty and DatatypeProperty)."""
        properties = {}
        
        # Object properties
        for s, p, o in self.graph.triples((None, RDF.type, OWL.ObjectProperty)):
            prop_uri = s
            local_name = str(prop_uri).split('#')[-1].split('/')[-1]
            properties[local_name] = prop_uri
            properties[f"proc:{local_name}"] = prop_uri
        
        # Datatype properties
        for s, p, o in self.graph.triples((None, RDF.type, OWL.DatatypeProperty)):
            prop_uri = s
            local_name = str(prop_uri).split('#')[-1].split('/')[-1]
            properties[local_name] = prop_uri
            properties[f"proc:{local_name}"] = prop_uri
        
        logger.info("Extracted properties", count=len(properties) // 2)
        return properties
    
    def _build_hierarchy(self) -> dict[str, list[str]]:
        """Build class hierarchy (subclass relationships)."""
        hierarchy = {}
        
        for s, p, o in self.graph.triples((None, RDFS.subClassOf, None)):
            child = str(s).split('#')[-1].split('/')[-1]
            parent = str(o).split('#')[-1].split('/')[-1]
            
            if parent not in hierarchy:
                hierarchy[parent] = []
            hierarchy[parent].append(child)
        
        return hierarchy
    
    def get_class_uri(self, class_name: str) -> URIRef | None:
        """Get URI for a class name (with or without prefix)."""
        return self._classes.get(class_name)
    
    def get_property_uri(self, property_name: str) -> URIRef | None:
        """Get URI for a property name (with or without prefix)."""
        return self._properties.get(property_name)
    
    def has_class(self, class_name: str) -> bool:
        """Check if class exists in ontology."""
        return class_name in self._classes
    
    def has_property(self, property_name: str) -> bool:
        """Check if property exists in ontology."""
        return property_name in self._properties
    
    def get_subclasses(self, class_name: str) -> list[str]:
        """Get all subclasses of a given class."""
        return self._class_hierarchy.get(class_name, [])
    
    def get_all_classes(self) -> list[str]:
        """Get all class names (without duplicates)."""
        # Return only names without proc: prefix
        return [name for name in self._classes.keys() if not name.startswith("proc:")]
    
    def get_all_properties(self) -> list[str]:
        """Get all property names (without duplicates)."""
        return [name for name in self._properties.keys() if not name.startswith("proc:")]
    
    def is_subclass_of(self, child: str, parent: str) -> bool:
        """Check if child is a subclass of parent."""
        if child == parent:
            return True
        
        # Recursive check
        for subclass in self.get_subclasses(parent):
            if child == subclass or self.is_subclass_of(child, subclass):
                return True
        
        return False

    def _local_name(self, uri: Node) -> str:
        """Get local name from URI (e.g. Contract from proc:Contract full URI)."""
        s = str(uri)
        return s.split("#")[-1].split("/")[-1]

    def to_sparql_context_text(self) -> str:
        """
        Build full schema summary for SPARQL generation (LLM prompt).
        Lists all classes (with optional label/comment/subclass) and all
        properties (with domain/range and optional label/comment).
        """
        lines = [
            "PROCUREMENT CONTRACT KNOWLEDGE GRAPH SCHEMA (from ontology):",
            "",
            "CLASSES (use in SPARQL as proc:ClassName):",
        ]
        seen_classes = set()
        for s, _p, o in self.graph.triples((None, RDF.type, OWL.Class)):
            local = self._local_name(s)
            if local in seen_classes:
                continue
            seen_classes.add(local)
            label = ""
            comment = ""
            parent = ""
            for _s, p, val in self.graph.triples((s, None, None)):
                if p == RDFS.label:
                    label = str(val)
                elif p == RDFS.comment:
                    comment = str(val)
                elif p == RDFS.subClassOf:
                    parent = self._local_name(val)
            part = f"- proc:{local}"
            if parent:
                part += f" (subClassOf proc:{parent})"
            if label:
                part += f" - {label}"
            if comment:
                part += f". {comment}"
            lines.append(part)

        lines.append("")
        lines.append("OBJECT PROPERTIES (domain -> range):")
        for s, _p, o in self.graph.triples((None, RDF.type, OWL.ObjectProperty)):
            local = self._local_name(s)
            domain = ""
            range_ = ""
            label = ""
            for _s, p, val in self.graph.triples((s, None, None)):
                if p == RDFS.domain:
                    domain = self._local_name(val)
                elif p == RDFS.range:
                    range_ = self._local_name(val)
                elif p == RDFS.label:
                    label = str(val)
            part = f"- proc:{local}: proc:{domain} -> proc:{range_}"
            if label:
                part += f" ({label})"
            lines.append(part)

        lines.append("")
        lines.append("DATATYPE PROPERTIES (domain -> xsd type or string):")
        for s, _p, o in self.graph.triples((None, RDF.type, OWL.DatatypeProperty)):
            local = self._local_name(s)
            domain = ""
            range_ = ""
            label = ""
            for _s, p, val in self.graph.triples((s, None, None)):
                if p == RDFS.domain:
                    domain = self._local_name(val)
                elif p == RDFS.range:
                    range_ = str(val).split("#")[-1].split("/")[-1] if val else ""
                elif p == RDFS.label:
                    label = str(val)
            part = f"- proc:{local}: on proc:{domain}"
            if range_:
                part += f", range {range_}"
            if label:
                part += f" ({label})"
            lines.append(part)

        lines.append("")
        lines.append("Use these exact proc: names in SPARQL. Do not add GRAPH clauses.")
        return "\n".join(lines)


class OntologyManager:
    """
    Manages ontology schemas dynamically.
    
    Features:
    - Load ontologies from OWL files at runtime
    - Support multiple ontology versions
    - Merge ontology extensions
    - Provide class and property mappings
    - Enable schema evolution without code changes
    """
    
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.schemas: dict[str, OntologySchema] = {}
        self.active_schema: OntologySchema | None = None
        self.logger = logger.bind(component="OntologyManager")
    
    def load_ontology(
        self,
        path: str | Path,
        schema_id: str = "default",
        set_active: bool = True,
    ) -> OntologySchema:
        """
        Load an ontology from an OWL file.
        
        Args:
            path: Path to OWL file (Turtle, RDF/XML, etc.)
            schema_id: Identifier for this schema
            set_active: Whether to set as active schema
            
        Returns:
            Loaded OntologySchema
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Ontology file not found: {path}")
        
        self.logger.info("Loading ontology", path=str(path), schema_id=schema_id)
        
        # Create graph and parse
        graph = Graph()
        
        # Detect format from extension
        format_map = {
            ".ttl": "turtle",
            ".owl": "turtle",  # Changed: Try Turtle first for .owl files
            ".rdf": "xml",
            ".n3": "n3",
            ".jsonld": "json-ld",
        }
        
        file_format = format_map.get(path.suffix.lower(), "turtle")
        
        try:
            graph.parse(str(path), format=file_format)
        except Exception as e:
            # If Turtle fails for .owl, try XML format
            if path.suffix.lower() == ".owl" and file_format == "turtle":
                self.logger.warning(
                    "Turtle parsing failed for .owl file, trying XML format",
                    path=str(path)
                )
                try:
                    graph.parse(str(path), format="xml")
                except Exception as xml_error:
                    self.logger.error(
                        "Failed to parse ontology in both Turtle and XML formats",
                        error=str(e),
                        xml_error=str(xml_error),
                        path=str(path)
                    )
                    raise
            else:
                self.logger.error(
                    "Failed to parse ontology",
                    error=str(e),
                    path=str(path)
                )
                raise
        
        # Extract version if present
        version = None
        for s, p, o in graph.triples((None, OWL.versionInfo, None)):
            version = str(o)
            break
        
        # Create schema
        schema = OntologySchema(
            graph=graph,
            namespace=self.settings.procurement_namespace,
            version=version,
        )
        
        # Store schema
        self.schemas[schema_id] = schema
        
        if set_active:
            self.active_schema = schema
            self.logger.info(
                "Set active schema",
                schema_id=schema_id,
                classes=len(schema.get_all_classes()),
                properties=len(schema.get_all_properties()),
            )
        
        return schema
    
    def load_extension(
        self,
        path: str | Path,
        merge_into: str = "default",
    ) -> None:
        """
        Load an ontology extension and merge into existing schema.
        
        Args:
            path: Path to extension OWL/TTL file
            merge_into: Schema ID to merge into
        """
        if merge_into not in self.schemas:
            raise ValueError(f"Schema '{merge_into}' not found")
        
        path = Path(path)
        self.logger.info("Loading ontology extension", path=str(path))
        
        # Load extension with format detection
        ext_graph = Graph()
        
        # Try Turtle first (most common for generated extensions)
        try:
            ext_graph.parse(str(path), format="turtle")
        except Exception as e:
            # Fallback to XML for .owl files
            if path.suffix.lower() == ".owl":
                try:
                    ext_graph.parse(str(path), format="xml")
                except Exception:
                    self.logger.error(
                        "Failed to parse extension",
                        error=str(e),
                        path=str(path)
                    )
                    raise
            else:
                raise
        
        # Merge into existing schema
        base_schema = self.schemas[merge_into]
        for triple in ext_graph:
            base_schema.graph.add(triple)
        
        # Rebuild schema indexes
        base_schema._classes = base_schema._extract_classes()
        base_schema._properties = base_schema._extract_properties()
        base_schema._class_hierarchy = base_schema._build_hierarchy()
        
        self.logger.info(
            "Merged extension",
            schema_id=merge_into,
            total_classes=len(base_schema.get_all_classes()),
        )
    
    def load_generated_extensions(
        self,
        extensions_dir: str | Path,
        merge_into: str = "default",
        pattern: str = "*.ttl"
    ) -> int:
        """
        Load all generated ontology extensions from a directory.
        
        Args:
            extensions_dir: Directory containing generated extensions
            merge_into: Schema ID to merge into
            pattern: File pattern to match (default: *.ttl)
            
        Returns:
            Number of extensions loaded
        """
        extensions_dir = Path(extensions_dir)
        
        if not extensions_dir.exists():
            self.logger.warning(
                "Extensions directory not found",
                path=str(extensions_dir)
            )
            return 0
        
        # Find all extension files
        extension_files = list(extensions_dir.glob(pattern))
        
        if not extension_files:
            self.logger.info(
                "No extension files found",
                path=str(extensions_dir),
                pattern=pattern
            )
            return 0
        
        self.logger.info(
            f"Loading {len(extension_files)} generated extensions",
            path=str(extensions_dir)
        )
        
        loaded_count = 0
        for ext_file in extension_files:
            try:
                self.load_extension(ext_file, merge_into=merge_into)
                loaded_count += 1
            except Exception as e:
                self.logger.warning(
                    "Failed to load extension",
                    file=str(ext_file),
                    error=str(e)
                )
                continue
        
        self.logger.info(
            f"Loaded {loaded_count}/{len(extension_files)} extensions successfully"
        )
        
        return loaded_count
    
    def reload_from_fuseki(
        self,
        sparql_store: Any,
        ontology_graph_uri: str = "http://procurement.org/ontology",
        schema_id: str = "default",
    ) -> None:
        """
        Reload ontology from Fuseki triplestore.
        
        This method queries Fuseki for the complete ontology graph and
        reloads it into memory, ensuring the OntologyManager has the
        latest schema including any extensions that were added.
        
        Args:
            sparql_store: SPARQL store instance
            ontology_graph_uri: URI of the ontology graph in Fuseki
            schema_id: Schema ID to reload (default: "default")
        """
        self.logger.info(
            "Reloading ontology from Fuseki",
            graph_uri=ontology_graph_uri,
            schema_id=schema_id
        )
        
        try:
            # Query Fuseki for all triples in the ontology graph
            query = f"""
            CONSTRUCT {{
                ?s ?p ?o
            }}
            WHERE {{
                GRAPH <{ontology_graph_uri}> {{
                    ?s ?p ?o
                }}
            }}
            """
            
            # Execute query and get graph
            result_graph = sparql_store.query(query)
            
            # Create new schema from the result
            schema = OntologySchema(
                graph=result_graph,
                namespace=self.settings.procurement_namespace,
                version=None,
                loaded_at=datetime.now(),
            )
            
            # Update or create schema
            self.schemas[schema_id] = schema
            self.active_schema = schema
            
            self.logger.info(
                "Ontology reloaded from Fuseki",
                schema_id=schema_id,
                classes=len(schema.get_all_classes()),
                properties=len(schema.get_all_properties()),
                triples=len(schema.graph)
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to reload ontology from Fuseki",
                error=str(e),
                graph_uri=ontology_graph_uri
            )
            raise
    
    def get_schema(self, schema_id: str = "default") -> OntologySchema | None:
        """Get a specific schema by ID."""
        return self.schemas.get(schema_id)
    
    def get_active_schema(self) -> OntologySchema:
        """Get the currently active schema."""
        if self.active_schema is None:
            raise RuntimeError("No active ontology schema loaded")
        return self.active_schema
    
    def set_active_schema(self, schema_id: str) -> None:
        """Set the active schema."""
        if schema_id not in self.schemas:
            raise ValueError(f"Schema '{schema_id}' not found")
        self.active_schema = self.schemas[schema_id]
        self.logger.info("Changed active schema", schema_id=schema_id)
    
    def get_class_mapping(self) -> dict[str, str]:
        """
        Get class name to URI mapping for the active schema.
        
        Returns:
            Dict mapping class names to full URIs
        """
        schema = self.get_active_schema()
        return {
            name: str(uri)
            for name, uri in schema._classes.items()
            if not name.startswith("proc:")
        }
    
    def get_property_mapping(self) -> dict[str, str]:
        """
        Get property name to URI mapping for the active schema.
        
        Returns:
            Dict mapping property names to full URIs
        """
        schema = self.get_active_schema()
        return {
            name: str(uri)
            for name, uri in schema._properties.items()
            if not name.startswith("proc:")
        }

    def get_schema_context_for_sparql(self) -> str:
        """
        Full ontology schema as text for SPARQL generation (LLM prompt).
        Use when active schema is already loaded.
        """
        schema = self.get_active_schema()
        return schema.to_sparql_context_text()

    def validate_class(self, class_name: str) -> bool:
        """Check if a class exists in the active schema."""
        schema = self.get_active_schema()
        return schema.has_class(class_name)
    
    def validate_property(self, property_name: str) -> bool:
        """Check if a property exists in the active schema."""
        schema = self.get_active_schema()
        return schema.has_property(property_name)
    
    def suggest_similar_class(self, class_name: str, max_suggestions: int = 3) -> list[str]:
        """
        Suggest similar class names for unmapped concepts.
        
        Uses simple string similarity for now.
        """
        schema = self.get_active_schema()
        all_classes = schema.get_all_classes()
        
        # Simple similarity: check if class_name is substring or vice versa
        suggestions = []
        class_lower = class_name.lower()
        
        for existing_class in all_classes:
            existing_lower = existing_class.lower()
            if class_lower in existing_lower or existing_lower in class_lower:
                suggestions.append(existing_class)
        
        return suggestions[:max_suggestions]
    
    def export_schema_summary(self, schema_id: str = "default") -> dict[str, Any]:
        """Export schema summary for documentation/debugging."""
        schema = self.schemas.get(schema_id)
        if not schema:
            return {}
        
        return {
            "schema_id": schema_id,
            "version": schema.version,
            "loaded_at": schema.loaded_at.isoformat(),
            "namespace": str(schema.namespace),
            "classes": {
                "count": len(schema.get_all_classes()),
                "names": sorted(schema.get_all_classes()),
            },
            "properties": {
                "count": len(schema.get_all_properties()),
                "names": sorted(schema.get_all_properties()),
            },
            "hierarchy": schema._class_hierarchy,
        }


# Global instance for easy access
_ontology_manager: OntologyManager | None = None


def get_ontology_manager() -> OntologyManager:
    """Get or create the global ontology manager instance."""
    global _ontology_manager
    if _ontology_manager is None:
        _ontology_manager = OntologyManager()
    return _ontology_manager


def initialize_ontology(
    ontology_path: str | Path | None = None,
    load_extensions: bool = True
) -> OntologyManager:
    """
    Initialize the global ontology manager with base ontology and extensions.
    
    Args:
        ontology_path: Path to base ontology file. If None, uses default.
        load_extensions: Whether to load generated extensions (default: True)
        
    Returns:
        Initialized OntologyManager
    """
    manager = get_ontology_manager()
    
    if ontology_path is None:
        # Try default locations (repo root, container /app, or relative)
        possible_paths = [
            Path("src/schemas/ontology/procurement.owl"),  # container cwd /app
            Path("agents/src/schemas/ontology/procurement.owl"),
            Path("ontology/procurement.owl"),
            Path("../ontology/procurement.owl"),
        ]
        
        for path in possible_paths:
            if path.exists():
                ontology_path = path
                break
        
        if ontology_path is None:
            raise FileNotFoundError("No ontology file found in default locations")
    
    # Load base ontology
    manager.load_ontology(ontology_path, schema_id="default", set_active=True)
    
    logger.info(
        "Base ontology loaded",
        path=str(ontology_path),
        classes=len(manager.get_active_schema().get_all_classes()),
    )
    
    # Load generated extensions if enabled
    if load_extensions:
        extensions_paths = [
            Path("data/generated/ontology"),  # container cwd /app
            Path("agents/data/generated/ontology"),  # repo root
        ]
        
        for ext_path in extensions_paths:
            if ext_path.exists():
                loaded = manager.load_generated_extensions(
                    ext_path,
                    merge_into="default"
                )
                if loaded > 0:
                    logger.info(
                        "Generated extensions loaded",
                        count=loaded,
                        total_classes=len(manager.get_active_schema().get_all_classes()),
                        total_properties=len(manager.get_active_schema().get_all_properties())
                    )
                break
    
    return manager


