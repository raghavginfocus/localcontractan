"""
Ontology Synchronization Agent - Ensures ontology updates are reflected in Fuseki.

This agent handles the critical task of synchronizing ontology extensions from
the ingestion pipeline to the Fuseki triplestore, ensuring retrieval agents
can immediately use new concepts.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from rdflib import Graph

from agents.shared.base import BaseAgent
from logger import get_module_logger
from ontology_manager import get_ontology_manager

logger = get_module_logger(__name__)


class SyncResult(BaseModel):
    """Result of ontology synchronization."""
    
    extension_file: str = Field(description="Path to the extension file")
    triples_loaded: int = Field(default=0, description="Number of triples loaded")
    success: bool = Field(default=False, description="Whether sync succeeded")
    fuseki_graph_uri: str | None = Field(default=None, description="Fuseki graph URI where loaded")
    error: str | None = Field(default=None, description="Error if sync failed")
    synced_at: datetime = Field(default_factory=datetime.now)


class OntologySyncResult(BaseModel):
    """Result of synchronizing multiple ontology extensions."""
    
    total_extensions: int = Field(default=0)
    successful_syncs: int = Field(default=0)
    failed_syncs: int = Field(default=0)
    total_triples: int = Field(default=0)
    sync_results: list[SyncResult] = Field(default_factory=list)
    ontology_reloaded: bool = Field(default=False, description="Whether ontology was reloaded in memory")


class OntologySyncAgent(BaseAgent):
    """
    Agent for synchronizing ontology extensions to Fuseki.
    
    This agent ensures that:
    1. Generated OWL extensions are loaded into Fuseki's ontology graph
    2. The in-memory ontology manager is updated
    3. Retrieval agents can immediately query new concepts
    4. Changes are persisted across restarts
    
    Workflow:
    1. Load OWL extension file
    2. Validate RDF syntax
    3. Push to Fuseki ontology graph
    4. Reload ontology manager
    5. Verify synchronization
    """
    
    def __init__(
        self,
        sparql_store: Any,
        ontology_graph_uri: str = "http://procurement.org/ontology",
        **kwargs: Any
    ):
        super().__init__(**kwargs)
        self.sparql_store = sparql_store
        self.ontology_graph_uri = ontology_graph_uri
        self.ontology_manager = get_ontology_manager()
    
    async def process(self, input_data: Any) -> OntologySyncResult:
        """
        Process method required by BaseAgent.
        
        Args:
            input_data: Can be:
                - str/Path: Single extension file path
                - list: Multiple extension file paths
                - dict with 'extensions' key: Multiple files
                
        Returns:
            OntologySyncResult
        """
        if isinstance(input_data, (str, Path)):
            # Single file
            result = await self.sync_extension(input_data)
            return OntologySyncResult(
                total_extensions=1,
                successful_syncs=1 if result.success else 0,
                failed_syncs=0 if result.success else 1,
                total_triples=result.triples_loaded,
                sync_results=[result],
                ontology_reloaded=True
            )
        elif isinstance(input_data, list):
            # Multiple files
            return await self.sync_multiple_extensions(input_data)
        elif isinstance(input_data, dict) and 'extensions' in input_data:
            # Dict with extensions key
            return await self.sync_multiple_extensions(
                input_data['extensions']
            )
        else:
            raise ValueError(
                f"Invalid input_data type: {type(input_data)}. "
                "Expected str, Path, list, or dict with 'extensions' key"
            )
    
    async def sync_extension(
        self,
        extension_file: str | Path,
        reload_ontology: bool = True,
    ) -> SyncResult:
        """
        Synchronize a single ontology extension to Fuseki.
        
        Args:
            extension_file: Path to the OWL extension file
            reload_ontology: Whether to reload the ontology manager after sync
            
        Returns:
            SyncResult with sync status
        """
        extension_path = Path(extension_file)
        result = SyncResult(extension_file=str(extension_path))
        
        try:
            # Step 1: Load and validate OWL file
            logger.info("Loading OWL extension", file=str(extension_path))
            graph = Graph()
            graph.parse(str(extension_path), format="turtle")
            triple_count = len(graph)
            
            if triple_count == 0:
                result.error = "No triples found in extension file"
                logger.warning("Empty OWL extension", file=str(extension_path))
                return result
            
            logger.info("OWL extension loaded", triples=triple_count)
            
            # Step 2: Push to Fuseki ontology graph
            logger.info("Pushing to Fuseki", graph_uri=self.ontology_graph_uri)
            
            # Serialize to Turtle for Fuseki
            turtle_data = graph.serialize(format="turtle")
            
            # Parse Turtle to N-Triples for valid SPARQL INSERT DATA syntax
            from rdflib import Graph as RDFGraph
            temp_graph = RDFGraph()
            temp_graph.parse(data=turtle_data, format='turtle')
            ntriples = temp_graph.serialize(format='nt')
            
            # Use SPARQL UPDATE to add triples to ontology graph
            # This preserves existing ontology while adding new concepts
            update_query = f"""
            INSERT DATA {{
                GRAPH <{self.ontology_graph_uri}> {{
                    {ntriples}
                }}
            }}
            """
            
            # Execute update
            await asyncio.to_thread(
                self.sparql_store.update,
                update_query
            )
            
            result.triples_loaded = triple_count
            result.fuseki_graph_uri = self.ontology_graph_uri
            result.success = True
            
            logger.info(
                "✓ OWL extension synced to Fuseki",
                triples=triple_count,
                graph=self.ontology_graph_uri
            )
            
            # Step 3: Reload ontology manager (if requested)
            if reload_ontology:
                try:
                    logger.info("Reloading ontology manager with new extensions")
                    # Reload from Fuseki to get the updated ontology
                    await asyncio.to_thread(
                        self.ontology_manager.reload_from_fuseki,
                        self.sparql_store,
                        self.ontology_graph_uri
                    )
                    logger.info("✓ Ontology manager reloaded")
                except Exception as reload_error:
                    logger.warning(
                        "Failed to reload ontology manager",
                        error=str(reload_error)
                    )
                    # Don't fail the sync - Fuseki has the data
            
        except Exception as e:
            result.error = str(e)
            result.success = False
            logger.error(
                "Failed to sync OWL extension",
                file=str(extension_path),
                error=str(e)
            )
        
        return result
    
    async def sync_multiple_extensions(
        self,
        extension_files: list[str | Path],
        reload_ontology_after_all: bool = True,
    ) -> OntologySyncResult:
        """
        Synchronize multiple ontology extensions to Fuseki.
        
        Args:
            extension_files: List of OWL extension file paths
            reload_ontology_after_all: Reload ontology once after all syncs
            
        Returns:
            OntologySyncResult with overall status
        """
        result = OntologySyncResult(total_extensions=len(extension_files))
        
        if not extension_files:
            logger.info("No extensions to sync")
            return result
        
        logger.info(
            "Starting batch ontology synchronization",
            extensions=len(extension_files)
        )
        
        # Sync all extensions (don't reload after each one)
        sync_tasks = [
            self.sync_extension(ext_file, reload_ontology=False)
            for ext_file in extension_files
        ]
        
        sync_results = await asyncio.gather(*sync_tasks, return_exceptions=True)
        
        # Process results
        for sync_result in sync_results:
            if isinstance(sync_result, Exception):
                result.failed_syncs += 1
                result.sync_results.append(
                    SyncResult(
                        extension_file="unknown",
                        success=False,
                        error=str(sync_result)
                    )
                )
            else:
                result.sync_results.append(sync_result)
                if sync_result.success:
                    result.successful_syncs += 1
                    result.total_triples += sync_result.triples_loaded
                else:
                    result.failed_syncs += 1
        
        # Reload ontology once after all syncs
        if reload_ontology_after_all and result.successful_syncs > 0:
            try:
                logger.info("Reloading ontology manager with all new extensions")
                await asyncio.to_thread(
                    self.ontology_manager.reload_from_fuseki,
                    self.sparql_store,
                    self.ontology_graph_uri
                )
                result.ontology_reloaded = True
                logger.info("✓ Ontology manager reloaded with all extensions")
            except Exception as reload_error:
                logger.warning(
                    "Failed to reload ontology manager",
                    error=str(reload_error)
                )
        
        logger.info(
            "Batch ontology synchronization complete",
            total=result.total_extensions,
            successful=result.successful_syncs,
            failed=result.failed_syncs,
            triples=result.total_triples,
            ontology_reloaded=result.ontology_reloaded
        )
        
        return result
    
    async def sync_shacl_shapes(
        self,
        shacl_dir: Path | str | None = None
    ) -> dict[str, Any]:
        """
        Load all SHACL shapes into Fuseki.
        
        Args:
            shacl_dir: Directory containing SHACL .ttl files (defaults to data/generated/shacl)
            
        Returns:
            Dict with loading statistics
        """
        if shacl_dir is None:
            shacl_dir = Path("data/generated/shacl")
        else:
            shacl_dir = Path(shacl_dir)
        
        if not shacl_dir.exists():
            logger.warning("SHACL directory not found", path=str(shacl_dir))
            return {"loaded": 0, "failed": 0, "total": 0}
        
        shacl_files = list(shacl_dir.glob("*.ttl"))
        logger.info("Loading SHACL shapes", count=len(shacl_files))
        
        loaded_count = 0
        failed_count = 0
        
        for shacl_file in shacl_files:
            try:
                with open(shacl_file, 'r') as f:
                    content = f.read()
                
                # Load into a SHACL-specific graph
                graph_uri = f"http://procurement.kg/shacl#{shacl_file.stem}"
                
                # Use FusekiClient's load_turtle method
                success = await asyncio.to_thread(
                    self.sparql_store.load_turtle,
                    content,
                    graph_uri=graph_uri
                )
                
                if success:
                    loaded_count += 1
                    logger.info("✓ Loaded SHACL shape", file=shacl_file.name, graph=graph_uri)
                else:
                    failed_count += 1
                    logger.warning("✗ Failed to load SHACL shape", file=shacl_file.name)
                    
            except Exception as e:
                failed_count += 1
                logger.error(
                    "Error loading SHACL shape",
                    file=shacl_file.name,
                    error=str(e)
                )
        
        logger.info(
            "SHACL shapes loading complete",
            loaded=loaded_count,
            failed=failed_count,
            total=len(shacl_files)
        )
        
        return {
            "loaded": loaded_count,
            "failed": failed_count,
            "total": len(shacl_files)
        }
    
    async def sync_reasoning_rules(
        self,
        rules_dir: Path | str | None = None
    ) -> dict[str, Any]:
        """
        Load reasoning rules into Fuseki.
        
        Args:
            rules_dir: Directory containing .sparql rule files (defaults to data/generated/rules)
            
        Returns:
            Dict with loading statistics
        """
        if rules_dir is None:
            rules_dir = Path("data/generated/rules")
        else:
            rules_dir = Path(rules_dir)
        
        if not rules_dir.exists():
            logger.warning("Rules directory not found", path=str(rules_dir))
            return {"loaded": 0, "failed": 0, "total": 0}
        
        # Load .sparql files (SPARQL CONSTRUCT rules)
        rule_files = list(rules_dir.glob("*.sparql"))
        logger.info("Loading reasoning rules", count=len(rule_files))
        
        loaded_count = 0
        failed_count = 0
        
        for rule_file in rule_files:
            try:
                with open(rule_file, 'r') as f:
                    sparql_query = f.read()
                
                # Store rule definition as metadata in a rules graph
                graph_uri = f"http://procurement.kg/rules#{rule_file.stem}"
                
                # Create rule metadata in Turtle format
                rule_metadata = f"""
@prefix rule: <http://procurement.kg/rules#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<{graph_uri}> a rule:ReasoningRule ;
    rdfs:label "{rule_file.stem}" ;
    rule:sparqlQuery \"\"\"
{sparql_query}
\"\"\" .
"""
                
                # Use FusekiClient's load_turtle method
                success = await asyncio.to_thread(
                    self.sparql_store.load_turtle,
                    rule_metadata,
                    graph_uri=graph_uri
                )
                
                if success:
                    loaded_count += 1
                    logger.info("✓ Loaded reasoning rule", file=rule_file.name, graph=graph_uri)
                else:
                    failed_count += 1
                    logger.warning("✗ Failed to load reasoning rule", file=rule_file.name)
                    
            except Exception as e:
                failed_count += 1
                logger.error(
                    "Error loading reasoning rule",
                    file=rule_file.name,
                    error=str(e)
                )
        
        logger.info(
            "Reasoning rules loading complete",
            loaded=loaded_count,
            failed=failed_count,
            total=len(rule_files)
        )
        
        return {
            "loaded": loaded_count,
            "failed": failed_count,
            "total": len(rule_files)
        }
    
    async def verify_sync(
        self,
        class_name: str,
    ) -> bool:
        """
        Verify that a class exists in Fuseki after synchronization.
        
        Args:
            class_name: Name of the class to verify (e.g., "DataProtectionClause")
            
        Returns:
            True if class exists in Fuseki
        """
        try:
            # Query Fuseki to check if class exists
            query = f"""
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX proc: <http://procurement.org/ontology#>
            
            ASK {{
                GRAPH <{self.ontology_graph_uri}> {{
                    proc:{class_name} a owl:Class .
                }}
            }}
            """
            
            result = await asyncio.to_thread(
                self.sparql_store.query,
                query
            )
            
            # ASK query returns boolean
            exists = bool(result)
            
            if exists:
                logger.info("✓ Class verified in Fuseki", class_name=class_name)
            else:
                logger.warning("✗ Class not found in Fuseki", class_name=class_name)
            
            return exists
            
        except Exception as e:
            logger.error(
                "Failed to verify class in Fuseki",
                class_name=class_name,
                error=str(e)
            )
            return False


