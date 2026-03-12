"""
Ingestion Orchestrator - Complete agentic pipeline for contract ingestion.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from enum import Enum

from pydantic import BaseModel, Field

from agents.ingestion.document_ingestion import DocumentIngestionAgent
from logger import get_module_logger
from agents.ingestion.clause_extraction import (
    ClauseExtractionAgent, ExtractedClause
)
from agents.ingestion.entity_extraction import (
    EntityExtractionAgent, EntityExtractionResult
)
from agents.ingestion.obligation_risk import ObligationRiskAgent
from agents.ingestion.ontology_alignment import (
    OntologyAlignmentAgent, AlignmentResult
)
from agents.ingestion.rdf_generator import RDFGeneratorAgent
from agents.ingestion.validation_agent import ValidationAgent, ValidationResult
from agents.ingestion.fuseki_loader import FusekiLoaderAgent, LoadResult
from agents.ingestion.reasoning_agent import ReasoningAgent, ReasoningResult
from agents.ingestion.vector_index import VectorIndexAgent, IndexResult
from agents.ingestion.ontology_sync_agent import OntologySyncAgent
from agents.schema_evolution.ontology_designer import OntologyDesignerAgent
from agents.schema_evolution.rule_generator import RuleGeneratorAgent, RulePattern
from agents.schema_evolution.shacl_generator import SHACLGeneratorAgent
from agents.schema_evolution.pattern_detection import PatternDetectionAgent
from agents.ingestion.resource_manager import get_resource_manager
from agents.shared.error_recovery import ErrorRecoveryAgent
from schema_governance import SchemaGovernance, SchemaVersion, SchemaConflict
from artifact_store import ArtifactStore
from config import Settings, get_settings
from ontology_manager import initialize_ontology, get_ontology_manager

logger = get_module_logger(__name__)


class OntologyEvolutionMode(str, Enum):
    """Mode for handling ontology gaps."""
    CONSERVATIVE = "conservative"  # Never auto-extend, log for review
    SUGGESTIVE = "suggestive"      # Propose extensions, require approval
    ADAPTIVE = "adaptive"          # Auto-extend for common patterns


class IngestionConfig(BaseModel):
    """Configuration for the ingestion pipeline."""
    
    ontology_evolution_mode: OntologyEvolutionMode = OntologyEvolutionMode.CONSERVATIVE
    auto_extend_threshold: int = 5
    enable_shacl_validation: bool = True
    fail_on_validation_error: bool = False  # Continue with warnings
    enable_reasoning: bool = True
    enable_vector_indexing: bool = True
    log_all_steps: bool = True
    save_artifacts: bool = True  # Save intermediate files for transparency
    # Use data/generated for all artifacts (consistent with schema evolution agents)
    artifact_dir: str = "data/generated"  # Directory for artifacts
    generate_owl_extensions: bool = True  # Generate OWL for new concepts
    generate_rules: bool = True  # Generate inference rules for patterns
    generate_shacl: bool = True  # Generate SHACL validation shapes
    enable_pattern_detection: bool = True  # Enable comprehensive pattern detection
    enable_schema_governance: bool = True  # Enable schema versioning and conflict resolution


class IngestionStep(BaseModel):
    """Represents a step in the ingestion pipeline."""
    
    step_name: str
    started_at: datetime
    completed_at: datetime | None = None
    success: bool = False
    duration_ms: float = 0.0
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class IngestionResult(BaseModel):
    """Result of the complete ingestion pipeline."""
    
    document_id: str = Field(description="ID of the ingested document")
    success: bool = Field(description="Whether ingestion completed successfully")
    steps: list[IngestionStep] = Field(default_factory=list, description="Details of each step")
    
    # Summary metrics
    clauses_extracted: int = Field(default=0)
    entities_extracted: int = Field(default=0)
    obligations_extracted: int = Field(default=0)
    risks_extracted: int = Field(default=0)
    triples_generated: int = Field(default=0)
    triples_loaded: int = Field(default=0)
    facts_inferred: int = Field(default=0)
    vectors_indexed: int = Field(default=0)
    
    # Ontology suggestions
    ontology_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    ontology_extensions_generated: list[str] = Field(default_factory=list)
    rules_generated: list[str] = Field(default_factory=list)
    shacl_shapes_generated: list[str] = Field(default_factory=list)
    
    # Pattern detection
    patterns_detected: list[dict[str, Any]] = Field(default_factory=list)
    
    # Schema governance
    schema_version: str | None = Field(default=None, description="Schema version ID if governance enabled")
    conflicts_detected: list[dict[str, Any]] = Field(default_factory=list)
    
    # Validation
    validation_errors: list[str] = Field(default_factory=list)
    validation_warnings: list[str] = Field(default_factory=list)
    
    # Extraction gaps (missing critical attributes)
    extraction_gaps: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Clauses with missing critical attributes"
    )
    
    # Timing
    total_duration_ms: float = Field(default=0.0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    
    # Artifacts (file paths for transparency)
    artifact_paths: dict[str, str] = Field(default_factory=dict, description="Paths to saved artifacts")
    
    # Errors
    error: str | None = None


class IngestionOrchestrator:
    """
    Complete agentic pipeline for contract ingestion.
    
    Pipeline Flow:
    1. Document intake → raw text + metadata
    2. Clause extraction → identified clauses with types
    3. Entity extraction → parties, dates, amounts
    4. Obligation/Risk extraction → obligations, risks, severity
    5. Ontology alignment → mapped to schema (+ suggestions)
    6. RDF generation → valid Turtle
    7. Validation → syntax + SHACL
    8. Load to Fuseki → stored in triplestore
    9. Apply reasoning → inferred facts
    10. Vector indexing → embeddings in Milvus
    """

    def __init__(
        self,
        config: IngestionConfig | None = None,
        settings: Settings | None = None,
    ):
        """
        Initialize the ingestion orchestrator.
        
        Args:
            config: Pipeline configuration
            settings: Application settings
        """
        self.settings = settings or get_settings()
        
        # Initialize config from settings if not provided
        if config is None:
            config = IngestionConfig(
                ontology_evolution_mode=OntologyEvolutionMode(
                    self.settings.ontology_evolution_mode
                ),
                generate_owl_extensions=self.settings.generate_owl_extensions,
                generate_rules=self.settings.generate_rules,
            )
        self.config = config
        self.logger = logger.bind(orchestrator="IngestionOrchestrator")
        
        # Initialize resource manager for rate limiting and coordination
        self.resource_manager = get_resource_manager(self.settings)
        
        # CRITICAL: Initialize ontology manager if not already loaded
        # This ensures dynamic ontology loading is available
        try:
            ontology_manager = get_ontology_manager()
            if ontology_manager.active_schema is None:
                self.logger.info("Initializing ontology manager...")
                initialize_ontology()
                self.logger.info("Ontology manager initialized successfully")
        except Exception as e:
            self.logger.warning(
                "Failed to initialize ontology manager, continuing without it",
                error=str(e)
            )
        
        # Initialize artifact store for transparency
        if self.config.save_artifacts:
            self.artifact_store = ArtifactStore(
                base_dir=self.config.artifact_dir,
                settings=self.settings,
            )
        else:
            self.artifact_store = None
        
        # Get service instances via dependency injection
        # When docling, use docling targets (contracts_docling, contract_clauses_docling)
        from service_factory import get_service_factory
        if self.settings.ingestion_source == "docling":
            ingestion_settings = self.settings.model_copy(update={
                "fuseki_dataset": self.settings.docling_fuseki_dataset,
                "milvus_collection_v2": self.settings.docling_milvus_collection,
            })
            service_factory = get_service_factory(settings=ingestion_settings)
        else:
            service_factory = get_service_factory(settings=self.settings)
        sparql_store = service_factory.get_sparql_store()
        vector_store = service_factory.get_vector_store()

        # Document agent: Docling (MinIO) or legacy (PyPDF2/python-docx)
        if self.settings.ingestion_source == "docling":
            from agents.ingestion.docling_document_ingestion import (
                DoclingDocumentIngestionAgent,
            )
            self.document_agent = DoclingDocumentIngestionAgent(settings=self.settings)
        else:
            self.document_agent = DocumentIngestionAgent(settings=self.settings)
        self.clause_agent = ClauseExtractionAgent(settings=self.settings)
        self.entity_agent = EntityExtractionAgent(settings=self.settings)
        self.obligation_risk_agent = ObligationRiskAgent(settings=self.settings)
        self.ontology_agent = OntologyAlignmentAgent(settings=self.settings)
        self.rdf_agent = RDFGeneratorAgent(settings=self.settings)
        self.validation_agent = ValidationAgent(settings=self.settings)
        
        # Initialize agents with dependency injection
        self.fuseki_agent = FusekiLoaderAgent(sparql_store=sparql_store, settings=self.settings)
        self.reasoning_agent = ReasoningAgent(sparql_store=sparql_store, settings=self.settings)
        self.vector_agent = VectorIndexAgent(vector_store=vector_store, settings=self.settings)
        self.ontology_sync_agent = OntologySyncAgent(sparql_store=sparql_store, settings=self.settings)
        
        # Initialize schema evolution agents
        self.ontology_designer = OntologyDesignerAgent(
            output_dir=Path(self.config.artifact_dir) / "ontology",
            settings=self.settings,
        )
        self.rule_generator = RuleGeneratorAgent(
            output_dir=Path(self.config.artifact_dir) / "rules",
            settings=self.settings,
        )
        self.shacl_generator = SHACLGeneratorAgent(
            output_dir=Path(self.config.artifact_dir) / "shacl",
            settings=self.settings,
        )
        self.pattern_detector = PatternDetectionAgent(settings=self.settings)
        
        # Initialize schema governance if enabled
        if self.config.enable_schema_governance:
            self.schema_governance = SchemaGovernance(
                version_dir=Path(self.config.artifact_dir) / "schema_versions"
            )
            # Cache latest schema version id (if any) for stamping results
            latest = self.schema_governance.get_latest_version()
            self.active_schema_version_id: str | None = (
                latest.version_id if latest else None
            )
        else:
            self.schema_governance = None
            self.active_schema_version_id = None
        
        # Initialize document registry for duplicate detection
        if self.settings.enable_duplicate_check:
            from document_registry import DocumentRegistry, ProcessingStatus
            self.ProcessingStatus = ProcessingStatus  # Store for later use
            self.document_registry = DocumentRegistry(
                backend=self.settings.document_registry_backend,
            )
        else:
            self.document_registry = None
        
        # Initialize all agents
        self._initialize_agents()
    
    async def _execute_with_recovery(
        self,
        operation: Any,
        operation_name: str,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute an agent operation with automatic error recovery.
        
        This wrapper provides:
        - Automatic retry with exponential backoff (max 3 attempts)
        - Error diagnosis and fix suggestions
        - Recovery attempt tracking
        - Graceful degradation
        
        Args:
            operation: The agent method to call
            operation_name: Name for logging
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation
        
        Returns:
            Result from operation, or None if all recovery attempts fail
        """
        recovery_agent = ErrorRecoveryAgent(max_retries=3)
        
        try:
            # Try the operation first
            return await operation(*args, **kwargs)
        except Exception as e:
            # Log the initial failure
            logger.warning(
                f"{operation_name} failed, attempting recovery...",
                error=str(e)
            )
            
            # Attempt recovery
            recovery_result = await recovery_agent.process({
                "operation": operation,
                "args": args,
                "kwargs": kwargs,
                "error": e,
                "context": {"operation_name": operation_name}
            })
            
            if recovery_result.success:
                logger.info(
                    f"✓ {operation_name} recovered after "
                    f"{len(recovery_result.attempts)} attempts"
                )
                return recovery_result.result
            else:
                logger.error(
                    f"✗ {operation_name} failed after "
                    f"{len(recovery_result.attempts)} recovery attempts"
                )
                # Log all attempts for debugging
                for i, attempt in enumerate(recovery_result.attempts, 1):
                    logger.debug(
                        f"  Attempt {i}: {attempt.error_type.value} - "
                        f"{attempt.diagnosis}"
                    )
                
                # Return None to allow graceful degradation
                return None
    
    def _initialize_agents(self) -> None:
        """Initialize all pipeline agents."""
        from service_factory import get_service_factory

        factory = get_service_factory()
        sparql_store = factory.get_sparql_store()
        vector_store = factory.get_vector_store()

        # Document agent: Docling or legacy (set in __init__, preserve)
        if self.settings.ingestion_source != "docling":
            self.document_agent = DocumentIngestionAgent(settings=self.settings)
        self.clause_agent = ClauseExtractionAgent(settings=self.settings)
        self.entity_agent = EntityExtractionAgent(settings=self.settings)
        self.obligation_agent = ObligationRiskAgent(settings=self.settings)
        self.alignment_agent = OntologyAlignmentAgent(settings=self.settings)
        self.rdf_agent = RDFGeneratorAgent(settings=self.settings)
        self.validation_agent = ValidationAgent(settings=self.settings)
        self.fuseki_agent = FusekiLoaderAgent(
            sparql_store=sparql_store,
            settings=self.settings
        )
        self.reasoning_agent = ReasoningAgent(
            sparql_store=sparql_store,
            settings=self.settings
        )
        self.vector_agent = VectorIndexAgent(
            vector_store=vector_store,
            settings=self.settings
        )
        
        # Schema evolution agents (optional)
        if self.config.generate_owl_extensions:
            self.ontology_designer = OntologyDesignerAgent(settings=self.settings)
            self.shacl_generator = SHACLGeneratorAgent(settings=self.settings)
        
        if self.config.generate_rules:
            self.rule_generator = RuleGeneratorAgent(settings=self.settings)
            self.pattern_detector = PatternDetectionAgent(settings=self.settings)
        
        # Ontology sync agent
        self.ontology_sync = OntologySyncAgent(
            sparql_store=sparql_store,
            settings=self.settings
        )

    async def ingest(
        self,
        file_path: str | None = None,
        text: str | None = None,
        document_id: str | None = None,
        override: bool = False,
        job_id: str | None = None,
    ) -> IngestionResult:
        """
        Process a contract document through the full pipeline.
        
        Args:
            file_path: Path to the contract file
            text: Or raw text content
            document_id: Optional ID (auto-generated if not provided)
            override: If True, reprocess even if document was already processed
            
        Returns:
            IngestionResult with complete status
        """
        # Check for duplicate if registry enabled and not overriding
        if self.document_registry and file_path and not override:
            is_processed, record = self.document_registry.is_processed(file_path=file_path)
            if is_processed and record.status == self.ProcessingStatus.COMPLETED:
                self.logger.info(
                    "⏭️  Document already processed - skipping",
                    file_path=file_path,
                    document_id=record.document_id,
                    processed_at=record.processed_at.isoformat(),
                )
                print(f"\n⏭️  Document already processed!")
                print(f"   • File: {Path(file_path).name}")
                print(f"   • Document ID: {record.document_id}")
                print(f"   • Previously processed: {record.processed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   • Status: {record.status.value}")
                if record.metadata:
                    print(f"   • Previous metrics:")
                    if "clauses" in record.metadata:
                        print(f"     - Clauses: {record.metadata.get('clauses', 0)}")
                    if "triples" in record.metadata:
                        print(f"     - Triples: {record.metadata.get('triples', 0)}")
                print(f"\n   To reprocess this document, use: --override flag")
                print()
                
                # Return a result indicating it was skipped
                result = IngestionResult(
                    document_id=record.document_id,
                    success=True,
                    started_at=datetime.now(),
                )
                # Add warning message to validation_warnings if it exists
                if hasattr(result, 'validation_warnings'):
                    result.validation_warnings.append(
                        f"Document already processed on {record.processed_at.isoformat()}. "
                        f"Use --override flag to reprocess."
                    )
                return result
        
        # Generate document ID
        if not document_id:
            document_id = f"doc_{uuid.uuid4().hex[:8]}"
        
        result = IngestionResult(
            document_id=document_id,
            success=False,
            started_at=datetime.now(),
        )
        # Stamp active schema version if known
        if self.active_schema_version_id and not result.schema_version:
            result.schema_version = self.active_schema_version_id
        
        self.logger.info("Starting ingestion pipeline", document_id=document_id, override=override)
        
        try:
            # Step 1: Document Intake
            doc_text, metadata = await self._step_document_intake(
                result, file_path, text, document_id
            )
            if not doc_text:
                return result
            
            # Extract DocTags data from metadata (Docling pipeline only)
            doc_sections = metadata.get("sections")
            structural_hints = metadata.get("structural_hints")
            
            # Step 2: Clause Extraction (with sections if available)
            clauses = await self._step_clause_extraction(
                result, document_id, doc_text, sections=doc_sections,
            )
            if not clauses:
                return result
            
            # Step 2.5: Validate extracted clauses for missing critical attributes
            self._validate_clause_attributes(result, document_id, clauses)
            
            # Save clauses immediately (async)
            if self.artifact_store:
                clause_path = await self.artifact_store.save_extraction_results(
                    document_id=document_id,
                    clauses=[c.model_dump() for c in clauses],
                    entities={},
                    obligations=[],
                    risks=[],
                )
                result.artifact_paths["clauses"] = str(clause_path)
                self.logger.info("Clauses saved to file", path=str(clause_path))
            
            # Steps 3 & 4: Parallel Extraction (Entity + Obligation/Risk)
            entity_task = self._step_entity_extraction(
                result, document_id, doc_text, structural_hints=structural_hints,
            )
            oblig_risk_task = self._step_obligation_risk_extraction(
                result, document_id, clauses
            )
            
            # Run both extractions in parallel
            entities, (obligations, risks) = await asyncio.gather(
                entity_task, oblig_risk_task
            )
            
            # Save entities immediately (async)
            if self.artifact_store and entities:
                entity_path = await self.artifact_store.save_extraction_results(
                    document_id=document_id,
                    clauses=[],
                    entities=entities.model_dump(),
                    obligations=[],
                    risks=[],
                )
                result.artifact_paths["entities"] = str(entity_path)
                self.logger.info("Entities saved to file", path=str(entity_path))
            
            # Save obligations and risks immediately (async)
            if self.artifact_store:
                oblig_risk_path = await self.artifact_store.save_extraction_results(
                    document_id=document_id,
                    clauses=[],
                    entities={},
                    obligations=[o.model_dump() for o in obligations] if obligations else [],
                    risks=[r.model_dump() for r in risks] if risks else [],
                )
                result.artifact_paths["obligations_risks"] = str(oblig_risk_path)
                self.logger.info("Obligations/Risks saved to file", path=str(oblig_risk_path))
            
            # Step 5: Ontology Alignment
            alignment = await self._step_ontology_alignment(
                result, document_id, clauses, entities
            )
            
            # Save alignment results immediately (async)
            if self.artifact_store and alignment:
                alignment_data = {
                    "document_id": document_id,
                    "timestamp": datetime.now().isoformat(),
                    "alignment": alignment.model_dump(),
                }
                # Alignment JSON logging disabled - using Phoenix tracing
                self.logger.debug("Alignment logged (Phoenix tracing)", document_id=document_id)
            
            # Step 5.5: Schema Evolution (if suggestions exist)
            # Coordinate schema evolution to prevent conflicts in parallel processing
            if alignment and alignment.suggestions:
                # Try to acquire schema evolution lock
                can_proceed = await self.resource_manager.coordinate_schema_evolution({
                    "document_id": document_id,
                    "suggestions": [s.model_dump() for s in alignment.suggestions],
                    "type": "schema_evolution",
                })
                
                if can_proceed:
                    try:
                        await self._step_schema_evolution(
                            result, document_id, alignment, clauses, entities
                        )
                    finally:
                        self.resource_manager.release_schema_evolution()
                else:
                    # Schema evolution is locked, queue for later
                    self.logger.info(
                        "Schema evolution queued (another document is processing)",
                        document_id=document_id,
                        suggestions_count=len(alignment.suggestions)
                    )
                    # Store suggestions for later processing
                    result.ontology_suggestions = alignment.suggestions
            
            # Step 6: RDF Generation (with document structure sections if available)
            rdf_data = await self._step_rdf_generation(
                result, document_id, clauses, obligations, risks, entities,
                sections=doc_sections,
            )
            if not rdf_data:
                return result
            
            # Step 6.5: Save RDF immediately (before Fuseki load, for resilience) - async
            if self.artifact_store:
                rdf_path = await self.artifact_store.save_rdf(
                    document_id=document_id,
                    rdf_data=rdf_data,
                    metadata={
                        "clauses": result.clauses_extracted,
                        "entities": result.entities_extracted,
                        "triples": result.triples_generated,
                    },
                )
                result.artifact_paths["rdf"] = str(rdf_path)
                self.logger.info("RDF saved to file", path=str(rdf_path))
            
            # Step 7: Validation
            validation_ok = await self._step_validation(result, rdf_data)
            
            # Validation JSON logging disabled - using Phoenix tracing
            if self.artifact_store:
                self.logger.debug("Validation logged (Phoenix tracing)",
                                document_id=document_id, validation_ok=validation_ok)
            
            if not validation_ok and self.config.fail_on_validation_error:
                return result
            
            # Steps 8, 9, 10: Parallel execution where possible
            # Step 8: Load to Fuseki (must complete before reasoning)
            load_ok = await self._step_fuseki_load(result, rdf_data, document_id)
            if not load_ok:
                # Don't return early - RDF is already saved, continue with other steps
                self.logger.warning("Fuseki load failed, but continuing with remaining steps")
            
            # Steps 9 & 10: Reasoning and Vector Indexing can run in parallel
            # Reasoning depends on Fuseki data, but Vector Indexing is independent
            # Prepare vector indexing task (independent of Fuseki/Reasoning)
            vector_task = None
            if self.config.enable_vector_indexing:
                rdf_uris = self._extract_rdf_uris_from_turtle(rdf_data, clauses)
                pipeline_tag = (
                    "docling"
                    if self.settings.ingestion_source == "docling"
                    else "legacy"
                )
                vector_task = self._step_vector_indexing(
                    result, document_id, clauses, rdf_uris,
                    source_pipeline=pipeline_tag,
                )
            
            # Reasoning task (depends on Fuseki load, but can run with vector indexing)
            reasoning_task = None
            if self.config.enable_reasoning and load_ok:
                reasoning_task = self._step_reasoning(result)
            
            # Execute reasoning and vector indexing in parallel
            if reasoning_task and vector_task:
                await asyncio.gather(reasoning_task, vector_task, return_exceptions=True)
            elif reasoning_task:
                await reasoning_task
            elif vector_task:
                await vector_task
            
            # Reasoning JSON logging disabled - using Phoenix tracing
            if self.config.enable_reasoning and load_ok:
                if self.artifact_store:
                    self.logger.debug("Reasoning logged (Phoenix tracing)",
                                    document_id=document_id, facts_inferred=result.facts_inferred)
            
            # Step 11: Ontology Evolution (if suggestions exist)
            if result.ontology_suggestions and self.config.generate_owl_extensions:
                await self._step_ontology_evolution(result, document_id)
            
            # Step 12: Rule Generation (for risk patterns)
            if self.config.generate_rules:
                await self._step_rule_generation(result, document_id, clauses)
            
            # Step 13: Save Artifacts (for transparency)
            if self.artifact_store:
                await self._step_save_artifacts(
                    result, document_id, doc_text, clauses, entities,
                    obligations, risks, rdf_data, job_id=job_id,
                )
            
            # Mark success
            result.success = True
            
            # Register document in registry after successful processing
            if self.document_registry and file_path:
                try:
                    self.document_registry.register(
                        file_path=file_path,
                        document_id=document_id,
                        status=self.ProcessingStatus.COMPLETED,
                        metadata={
                            "clauses": result.clauses_extracted,
                            "entities": result.entities_extracted,
                            "obligations": result.obligations_extracted,
                            "risks": result.risks_extracted,
                            "triples": result.triples_generated,
                            "facts_inferred": result.facts_inferred,
                        },
                    )
                    self.logger.info(
                        "Document registered in registry",
                        document_id=document_id,
                        file_path=file_path,
                    )
                except Exception as reg_error:
                    self.logger.warning(
                        "Failed to register document in registry",
                        error=str(reg_error),
                        document_id=document_id,
                    )
            
        except Exception as e:
            self.logger.error("Ingestion failed", error=str(e), document_id=document_id)
            result.error = str(e)
            
            # Register as failed if registry enabled
            if self.document_registry and file_path:
                try:
                    self.document_registry.register(
                        file_path=file_path,
                        document_id=document_id,
                        status=self.ProcessingStatus.FAILED,
                        metadata={"error": str(e)},
                    )
                except Exception:
                    pass  # Don't fail on registry errors
        
        # Finalize timing
        result.completed_at = datetime.now()
        if result.started_at:
            result.total_duration_ms = (
                result.completed_at - result.started_at
            ).total_seconds() * 1000
        
        self.logger.info(
            "Ingestion completed",
            document_id=document_id,
            success=result.success,
            duration_ms=result.total_duration_ms,
        )
        
        return result

    async def _step_document_intake(
        self,
        result: IngestionResult,
        file_path: str | None,
        text: str | None,
        document_id: str,
    ) -> tuple[str | None, dict[str, Any]]:
        """Step 1: Document intake.

        Returns (text, metadata) where metadata may contain 'sections' and
        'structural_hints' from DocTags preprocessing (Docling pipeline only).
        """
        step = IngestionStep(step_name="document_intake", started_at=datetime.now())
        
        try:
            if file_path:
                doc_result = await self.document_agent.process(file_path)
                doc_text = doc_result.text
                metadata = {
                    "filename": doc_result.filename,
                    "page_count": doc_result.page_count,
                }
                # Carry DocTags sections + hints through metadata for downstream agents
                if doc_result.sections:
                    metadata["sections"] = doc_result.sections
                if doc_result.structural_hints:
                    metadata["structural_hints"] = doc_result.structural_hints
            elif text:
                doc_text = text
                metadata = {"source": "raw_text"}
            else:
                raise ValueError("Either file_path or text must be provided")
            
            step.success = True
            step.result = {
                "text_length": len(doc_text),
                "has_sections": bool(metadata.get("sections")),
                **{k: v for k, v in metadata.items() if k not in ("sections", "structural_hints")},
            }
            
            return doc_text, metadata
            
        except Exception as e:
            step.error = str(e)
            result.error = f"Document intake failed: {e}"
            return None, {}
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def _step_clause_extraction(
        self,
        result: IngestionResult,
        document_id: str,
        text: str,
        sections: list[dict] | None = None,
    ) -> list[ExtractedClause]:
        """Step 2: Clause extraction with self-healing."""
        step = IngestionStep(step_name="clause_extraction", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 2: CLAUSE EXTRACTION - {document_id}")
        logger.info(f"Input text length: {len(text)} chars, sections: {len(sections) if sections else 0}")
        logger.info("Calling LLM for clause identification... (this may take 2-5 minutes)")
        
        try:
            input_data: dict[str, Any] = {"document_id": document_id, "text": text}
            if sections:
                input_data["sections"] = sections

            extraction_result = await self._execute_with_recovery(
                self.clause_agent.process,
                "clause_extraction",
                input_data,
            )
            
            if extraction_result is None:
                # Recovery failed, return empty list
                logger.warning("Clause extraction failed after recovery attempts")
                return []
            
            clauses = extraction_result.clauses
            result.clauses_extracted = len(clauses)
            
            step.success = True
            step.result = {
                "clause_count": len(clauses),
                "clause_types": list(set(c.clause_type for c in clauses)),
            }
            logger.info(f"✓ Extracted {len(clauses)} clauses")
            logger.info(f"Types: {step.result['clause_types']}")
            
            return clauses
            
        except Exception as e:
            step.error = str(e)
            result.error = f"Clause extraction failed: {e}"
            logger.error(f"  ✗ FAILED: {e}")
            return []
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_entity_extraction(
        self,
        result: IngestionResult,
        document_id: str,
        text: str,
        structural_hints: dict | None = None,
    ) -> EntityExtractionResult | None:
        """Step 3: Entity extraction with self-healing."""
        step = IngestionStep(step_name="entity_extraction", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 3: ENTITY EXTRACTION - {document_id}")
        logger.info("  Extracting parties, dates, amounts, jurisdictions...")
        logger.info("  Calling LLM... (this may take 2-3 minutes)")
        
        try:
            input_data: dict[str, Any] = {"document_id": document_id, "text": text}
            if structural_hints:
                input_data["structural_hints"] = structural_hints

            entity_result = await self._execute_with_recovery(
                self.entity_agent.process,
                "entity_extraction",
                input_data,
            )
            
            if entity_result is None:
                # Recovery failed, return None
                logger.warning("Entity extraction failed after recovery attempts")
                return None
            
            entity_count = (
                len(entity_result.parties) +
                len(entity_result.dates) +
                len(entity_result.amounts) +
                len(entity_result.jurisdictions)
            )
            result.entities_extracted = entity_count
            
            step.success = True
            step.result = {
                "parties": len(entity_result.parties),
                "dates": len(entity_result.dates),
                "amounts": len(entity_result.amounts),
                "jurisdictions": len(entity_result.jurisdictions),
            }
            logger.info(f"  ✓ Extracted {entity_count} entities")
            logger.info(f"    Parties: {len(entity_result.parties)}, Dates: {len(entity_result.dates)}, Amounts: {len(entity_result.amounts)}")
            
            return entity_result
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Entity extraction failed: {e}")
            logger.error(f"  ✗ FAILED: {e}")
            return None
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_obligation_risk_extraction(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
    ) -> tuple[list, list]:
        """Step 4: Obligation and risk extraction."""
        step = IngestionStep(step_name="obligation_risk_extraction", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 4: OBLIGATION/RISK EXTRACTION - {document_id}")
        logger.info(f"  Processing {len(clauses)} clauses for obligations and risks...")
        logger.info("  Calling LLM... (this may take 2-3 minutes)")
        
        try:
            obl_risk_result = await self.obligation_risk_agent.process({
                "document_id": document_id,
                "clauses": clauses,
            })
            
            obligations = obl_risk_result.obligations
            risks = obl_risk_result.risks
            
            result.obligations_extracted = len(obligations)
            result.risks_extracted = len(risks)
            
            step.success = True
            step.result = {
                "obligations": len(obligations),
                "risks": len(risks),
            }
            logger.info(f"  ✓ Extracted {len(obligations)} obligations, {len(risks)} risks")
            
            return obligations, risks
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Obligation/risk extraction failed: {e}")
            logger.error(f"  ✗ FAILED: {e}")
            return [], []
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_ontology_alignment(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
        entities: EntityExtractionResult | None,
    ) -> AlignmentResult | None:
        """Step 5: Ontology alignment."""
        step = IngestionStep(step_name="ontology_alignment", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 5: ONTOLOGY ALIGNMENT - {document_id}")
        logger.info("  Mapping extracted data to ontology concepts...")
        logger.info("  Calling LLM... (this may take 2-4 minutes)")
        
        try:
            alignment_result = await self.ontology_agent.process({
                "document_id": document_id,
                "clauses": clauses,
                "entities": entities,
            })
            
            # Store ontology suggestions for review
            if alignment_result.suggestions:
                result.ontology_suggestions = [
                    {
                        "type": s.suggestion_type,
                        "name": s.name,
                        "description": s.description,
                        "occurrences": s.occurrences,
                    }
                    for s in alignment_result.suggestions
                ]
            
            step.success = True
            step.result = {
                "mappings": len(alignment_result.mappings),
                "unmapped": len(alignment_result.unmapped_entities),
                "suggestions": len(alignment_result.suggestions),
                "alignment_score": alignment_result.alignment_score,
            }
            logger.info(f"  ✓ Mapped {len(alignment_result.mappings)} concepts")
            logger.info(f"    Score: {alignment_result.alignment_score:.2f}, Suggestions: {len(alignment_result.suggestions)}")
            
            return alignment_result
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Ontology alignment failed: {e}")
            logger.error(f"  ✗ FAILED: {e}")
            return None
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_schema_evolution(
        self,
        result: IngestionResult,
        document_id: str,
        alignment: AlignmentResult,
        clauses: list[ExtractedClause],
        entities: EntityExtractionResult | None = None,
    ) -> None:
        """Step 5.5: Schema Evolution - Generate OWL, Rules, and SHACL for new concepts."""
        step = IngestionStep(step_name="schema_evolution", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 5.5: SCHEMA EVOLUTION - {document_id}")
        logger.info(f"  Found {len(alignment.suggestions)} new concepts to process...")
        
        try:
            ontology_manager = get_ontology_manager()
            generated_extensions = []
            generated_rules = []
            generated_shacl = []
            
            # Process suggestions - parallelize OWL + SHACL generation where possible
            # First, generate OWL for all suggestions in parallel
            owl_tasks = []
            suggestion_owl_map = {}  # Map (suggestion.name, suggestion.suggestion_type) to owl_result
            
            if self.config.generate_owl_extensions:
                for suggestion in alignment.suggestions:
                    logger.info(f"  Processing: {suggestion.name} ({suggestion.suggestion_type})")
                    owl_tasks.append(
                        (suggestion, self.ontology_designer.process(input_data=suggestion))
                    )
            
            # Execute all OWL generation tasks in parallel
            if owl_tasks:
                owl_results = await asyncio.gather(
                    *[task[1] for task in owl_tasks],
                    return_exceptions=True
                )
                
                # Process OWL results and prepare for SHACL generation
                shacl_tasks = []
                for (suggestion, _), owl_result in zip(owl_tasks, owl_results):
                    if isinstance(owl_result, Exception):
                        logger.warning(f"    ⚠ OWL generation error for {suggestion.name}: {owl_result}")
                        continue
                    
                    if owl_result.is_valid:
                        generated_extensions.append(owl_result.file_path)
                        result.ontology_extensions_generated.append(owl_result.file_path)
                        logger.info(f"    ✓ OWL saved: {owl_result.file_path}")
                        # Use hashable tuple key instead of unhashable OntologySuggestion object
                        suggestion_key = (suggestion.name, suggestion.suggestion_type)
                        suggestion_owl_map[suggestion_key] = owl_result
                        
                        # Sync extension to Fuseki (ADAPTIVE mode)
                        if self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE:
                            try:
                                sync_result = await self.ontology_sync_agent.sync_extension(
                                    owl_result.file_path,
                                    reload_ontology=False  # Batch reload later
                                )
                                if sync_result.success:
                                    logger.info(
                                        f"    ✓ OWL synced to Fuseki "
                                        f"({sync_result.triples_loaded} triples)"
                                    )
                                else:
                                    logger.warning(
                                        f"    ⚠ Failed to sync OWL to Fuseki: "
                                        f"{sync_result.error}"
                                    )
                            except Exception as e:
                                logger.warning(f"    ⚠ Fuseki sync error: {e}")
                        
                        # Prepare SHACL generation task (depends on OWL)
                        if self.config.generate_shacl:
                            shacl_tasks.append(
                                (suggestion, owl_result, self.shacl_generator.generate_for_owl_class(
                                    owl_class_name=suggestion.name,
                                    owl_triples=owl_result.owl_triples,
                                    parent_class=suggestion.parent_class or "proc:Clause",
                                ))
                            )
                    else:
                        logger.warning(f"    ⚠ OWL generation failed for {suggestion.name}: {owl_result.error}")
            
            # Generate SHACL shapes in parallel (after OWL is ready)
            if shacl_tasks:
                shacl_results = await asyncio.gather(
                    *[task[2] for task in shacl_tasks],
                    return_exceptions=True
                )
                
                for (suggestion, owl_result, _), shacl_result in zip(shacl_tasks, shacl_results):
                    if isinstance(shacl_result, Exception):
                        logger.warning(f"    ⚠ SHACL generation error for {suggestion.name}: {shacl_result}")
                        continue
                    
                    if shacl_result.is_valid:
                        generated_shacl.append(shacl_result.file_path)
                        result.shacl_shapes_generated.append(shacl_result.file_path)
                        logger.info(f"    ✓ SHACL saved: {shacl_result.file_path}")
                        
                        # Auto-load SHACL shape into validation agent in ADAPTIVE mode
                        if self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE:
                            try:
                                self.validation_agent.load_shacl_shape(shacl_result.file_path)
                                logger.info(f"    ✓ SHACL loaded into validation agent")
                            except Exception as e:
                                logger.warning(f"    ⚠ Failed to load SHACL: {e}")
                    else:
                        logger.warning(f"    ⚠ SHACL generation failed for {suggestion.name}: {shacl_result.error}")
            
            # Generate inference rules sequentially (if needed)
            for suggestion in alignment.suggestions:
                if self.config.generate_rules and "risk" in suggestion.description.lower():
                    try:
                        logger.info(f"    → Generating inference rules for {suggestion.name}...")
                        # Create a rule pattern from the suggestion
                        rule_pattern = RulePattern(
                            pattern_name=f"{suggestion.name}Risk",
                            condition_class=f"proc:{suggestion.name}",
                            condition_property="proc:hasAttribute",
                            condition_operator="exists",
                            condition_value="true",
                            inferred_property="proc:hasRiskLevel",
                            inferred_value="MEDIUM",
                            description=f"Auto-generated rule for {suggestion.name}"
                        )
                        
                        rule_result = await self.rule_generator.generate_rule(
                            pattern=rule_pattern,
                            document_id=document_id
                        )
                        
                        if rule_result.is_valid:
                            generated_rules.append(rule_result.file_path)
                            result.rules_generated.append(rule_result.file_path)
                            logger.info(f"    ✓ Rules saved: {rule_result.file_path}")
                            
                            # Auto-apply rules if in adaptive mode
                            if self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE:
                                try:
                                    await self.reasoning_agent.load_and_apply_rules(
                                        rule_file=rule_result.file_path
                                    )
                                    logger.info(f"    ✓ Rules applied to Fuseki")
                                except Exception as e:
                                    logger.warning(f"    ⚠ Failed to apply rules: {e}")
                        else:
                            logger.warning(f"    ⚠ Rule generation failed: {rule_result.error}")
                    except Exception as e:
                        logger.warning(f"    ⚠ Rule generation error: {e}")
            
            # 4. Enhanced Pattern Detection (beyond just risk patterns)
            if self.config.enable_pattern_detection:
                try:
                    logger.info("  → Detecting patterns across all clauses...")
                    
                    # Convert clauses to format expected by pattern detector
                    clause_dicts = []
                    for clause in clauses:
                        clause_dicts.append({
                            "clause_type": clause.clause_type,
                            "attributes": clause.attributes,
                            "raw_text": clause.raw_text,
                            "contract_id": document_id,
                        })
                    
                    # Build contract info for pattern detection
                    contract_dicts = []
                    if entities:
                        contract_value = None
                        governed_by = None
                        for amount in entities.amounts:
                            if amount.amount_type.lower() in ["contractvalue", "contract_value", "total_value"]:
                                contract_value = amount.value
                                break
                        for jurisdiction in entities.jurisdictions:
                            governed_by = jurisdiction.name
                            break
                        
                        if contract_value or governed_by:
                            contract_dicts.append({
                                "contract_id": document_id,
                                "contract_value": contract_value,
                                "governed_by": governed_by,
                            })
                    
                    # Detect patterns
                    pattern_result = await self.pattern_detector.detect_patterns(
                        clauses=clause_dicts,
                        contracts=contract_dicts,
                    )
                    
                    if pattern_result.patterns:
                        logger.info(f"    ✓ Detected {len(pattern_result.patterns)} patterns")
                        result.patterns_detected = [
                            p.model_dump() for p in pattern_result.patterns
                        ]
                        
                        # Generate rules from detected patterns
                        if self.config.generate_rules:
                            rule_patterns = self.pattern_detector.patterns_to_rule_patterns(
                                pattern_result.patterns
                            )
                            
                            if rule_patterns:
                                rule_set_result = await self.rule_generator.generate_rules(
                                    patterns=rule_patterns,
                                    apply_to_fuseki=(
                                        self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE
                                    ),
                                )
                                
                                for rule in rule_set_result.rules:
                                    if rule.file_path:
                                        generated_rules.append(rule.file_path)
                                        result.rules_generated.append(rule.file_path)
                                
                                logger.info(f"    ✓ Generated {len(rule_set_result.rules)} rules from patterns")
                except Exception as e:
                    logger.warning(f"    ⚠ Pattern detection error: {e}")
            
            # 5. Schema Governance (conflict detection and versioning)
            if self.config.enable_schema_governance and generated_extensions:
                try:
                    logger.info("  → Checking for schema conflicts...")
                    
                    # Load new ontology to check for conflicts
                    from rdflib import Graph
                    new_ontology = Graph()
                    for ext_path in generated_extensions:
                        if Path(ext_path).exists():
                            new_ontology.parse(ext_path, format="turtle")
                    
                    # Get existing ontology
                    existing_ontology = Graph()
                    ontology_manager = get_ontology_manager()
                    active_schema = ontology_manager.get_active_schema()
                    if active_schema:
                        existing_ontology = active_schema.graph
                    
                    # Detect conflicts
                    conflicts = self.schema_governance.detect_conflicts(
                        new_ontology=new_ontology,
                        existing_ontology=existing_ontology,
                    )
                    
                    if conflicts:
                        logger.warning(f"    ⚠ Detected {len(conflicts)} conflicts")
                        result.conflicts_detected = [
                            {
                                "type": c.conflict_type.value,
                                "description": c.description,
                                "affected_classes": c.affected_classes,
                            }
                            for c in conflicts
                        ]
                        
                        # Auto-resolve conflicts in ADAPTIVE mode
                        if self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE:
                            for conflict in conflicts:
                                resolved = self.schema_governance.resolve_conflict(
                                    conflict,
                                    resolution_strategy="merge",  # Default strategy
                                )
                                logger.info(f"    ✓ Resolved: {resolved.resolution}")
                    else:
                        logger.info("    ✓ No conflicts detected")
                    
                    # Create schema version snapshot
                    if generated_extensions or generated_rules or generated_shacl:
                        version = self.schema_governance.create_version(
                            description=f"Schema evolution for document {document_id}",
                            ontology_files=generated_extensions,
                            rule_files=generated_rules,
                            shacl_files=generated_shacl,
                            changes=[
                                f"Added {len(generated_extensions)} ontology extensions",
                                f"Added {len(generated_rules)} rules",
                                f"Added {len(generated_shacl)} SHACL shapes",
                            ],
                        )
                        result.schema_version = version.version_id
                        logger.info(f"    ✓ Created schema version: {version.version_id}")
                        
                except Exception as e:
                    logger.warning(f"    ⚠ Schema governance error: {e}")
            
            # Final step: Reload ontology from Fuseki if extensions were synced
            if generated_extensions and self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE:
                try:
                    logger.info("  → Reloading ontology from Fuseki with all extensions...")
                    ontology_manager = get_ontology_manager()
                    await asyncio.to_thread(
                        ontology_manager.reload_from_fuseki,
                        self.fuseki_agent.sparql_store,
                        "http://procurement.org/ontology"
                    )
                    logger.info(f"    ✓ Ontology reloaded - retrieval agents can now use new concepts")
                except Exception as e:
                    
                    # Load SHACL shapes and reasoning rules into Fuseki
                    if generated_shacl or generated_rules:
                        logger.info("  → Loading SHACL shapes and reasoning rules into Fuseki...")
                        
                        # Load SHACL shapes
                        if generated_shacl:
                            try:
                                shacl_stats = await self.ontology_sync_agent.sync_shacl_shapes()
                                logger.info(
                                    f"    ✓ SHACL shapes loaded: {shacl_stats['loaded']}/{shacl_stats['total']} "
                                    f"(failed: {shacl_stats['failed']})"
                                )
                            except Exception as e:
                                logger.warning(f"    ⚠ Failed to load SHACL shapes: {e}")
                        
                        # Load reasoning rules
                        if generated_rules:
                            try:
                                rules_stats = await self.ontology_sync_agent.sync_reasoning_rules()
                                logger.info(
                                    f"    ✓ Reasoning rules loaded: {rules_stats['loaded']}/{rules_stats['total']} "
                                    f"(failed: {rules_stats['failed']})"
                                )
                            except Exception as e:
                                logger.warning(f"    ⚠ Failed to load reasoning rules: {e}")
                    logger.warning(f"    ⚠ Failed to reload ontology: {e}")
            
            step.success = True
            step.result = {
                "suggestions_processed": len(alignment.suggestions),
                "owl_extensions_generated": len(generated_extensions),
                "rules_generated": len(generated_rules),
                "shacl_shapes_generated": len(generated_shacl),
                "patterns_detected": len(result.patterns_detected),
                "conflicts_detected": len(result.conflicts_detected),
                "schema_version": result.schema_version,
                "mode": self.config.ontology_evolution_mode.value,
            }
            
            logger.info(f"  ✓ Schema evolution complete:")
            logger.info(f"    OWL extensions: {len(generated_extensions)}")
            logger.info(f"    Rules generated: {len(generated_rules)}")
            logger.info(f"    SHACL shapes: {len(generated_shacl)}")
            logger.info(f"    Patterns detected: {len(result.patterns_detected)}")
            logger.info(f"    Conflicts: {len(result.conflicts_detected)}")
            logger.info(f"    Mode: {self.config.ontology_evolution_mode.value}")
            
        except Exception as e:
            step.error = str(e)
            self.logger.error(f"Schema evolution failed: {e}")
            logger.error(f"  ✗ FAILED: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_rdf_generation(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
        obligations: list,
        risks: list,
        entities: EntityExtractionResult | None,
        sections: list[dict] | None = None,
    ) -> str | None:
        """Step 6: RDF generation."""
        step = IngestionStep(step_name="rdf_generation", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 6: RDF GENERATION - {document_id}")
        logger.info(f"  Generating Turtle/RDF from {len(clauses)} clauses...")
        
        try:
            # Build contract_info from extracted entities
            contract_info = {}
            
            if entities:
                # Extract contract value from amounts
                contract_value = None
                for amount in entities.amounts:
                    if amount.amount_type.lower() in ["contractvalue", "contract_value", "total_value", "totalvalue"]:
                        contract_value = amount.value
                        break
                
                if contract_value:
                    contract_info["value"] = contract_value
                
                # Extract dates
                for date in entities.dates:
                    if date.date_type.lower() in ["effectivedate", "effective_date", "start_date"]:
                        contract_info["effective_date"] = date.date_value
                    elif date.date_type.lower() in ["expirationdate", "expiration_date", "end_date", "termination_date"]:
                        contract_info["expiration_date"] = date.date_value
                
                # Extract jurisdiction
                if entities.jurisdictions:
                    # Use first jurisdiction
                    jurisdiction = entities.jurisdictions[0].name
                    # Map common names to ontology instances
                    jurisdiction_map = {
                        "California": "California",
                        "Delaware": "Delaware",
                        "New York": "NewYork",
                        "State of California": "California",
                        "State of Delaware": "Delaware",
                    }
                    contract_info["jurisdiction"] = jurisdiction_map.get(jurisdiction, jurisdiction.replace(" ", ""))
                
                # Extract parties
                if entities.parties:
                    contract_info["parties"] = [
                        {
                            "id": p.party_id,
                            "name": p.name,
                            "role": p.role,
                        }
                        for p in entities.parties
                    ]
            
            # Add document metadata
            contract_info["id"] = document_id.replace("doc_", "Contract_")
            contract_info["title"] = entities.contract_title if entities and entities.contract_title else f"Contract {document_id}"
            contract_info["status"] = "Active"
            
            rdf_input: dict[str, Any] = {
                "document_id": document_id,
                "contract_info": contract_info,
                "clauses": clauses,
                "obligations": obligations,
                "risks": risks,
            }
            if sections:
                rdf_input["sections"] = sections
            rdf_result = await self.rdf_agent.process(rdf_input)
            
            result.triples_generated = rdf_result.triple_count
            
            step.success = True
            step.result = {
                "triple_count": rdf_result.triple_count,
                "entities": rdf_result.entity_counts,
            }
            logger.info(f"  ✓ Generated {rdf_result.triple_count} RDF triples")
            
            return rdf_result.turtle
            
        except Exception as e:
            step.error = str(e)
            result.error = f"RDF generation failed: {e}"
            logger.error(f"  ✗ FAILED: {e}")
            return None
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_validation(
        self,
        result: IngestionResult,
        rdf_data: str,
    ) -> bool:
        """Step 7: Validation."""
        step = IngestionStep(step_name="validation", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info("STEP 7: VALIDATION")
        logger.info("  Validating RDF syntax and SHACL shapes...")
        
        try:
            validation_result = await self.validation_agent.process({
                "rdf_data": rdf_data,
            })
            
            # Collect errors and warnings
            result.validation_errors = [e.message for e in validation_result.errors]
            result.validation_warnings = [w.message for w in validation_result.warnings]
            
            step.success = validation_result.is_valid
            step.result = {
                "is_valid": validation_result.is_valid,
                "syntax_valid": validation_result.syntax_valid,
                "shacl_valid": validation_result.shacl_valid,
                "error_count": len(validation_result.errors),
                "warning_count": len(validation_result.warnings),
            }
            
            if not validation_result.syntax_valid:
                result.error = "RDF syntax validation failed"
                logger.error("  ✗ RDF syntax validation failed")
                return False
            
            logger.info(f"  ✓ Validation passed (syntax: {validation_result.syntax_valid}, SHACL: {validation_result.shacl_valid})")
            return True
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Validation failed: {e}")
            logger.warning(f"  ⚠ Validation error (continuing): {e}")
            return True  # Continue on validation errors
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_fuseki_load(
        self,
        result: IngestionResult,
        rdf_data: str,
        document_id: str,
    ) -> bool:
        """Step 8: Load to Fuseki."""
        step = IngestionStep(step_name="fuseki_load", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info(f"STEP 8: FUSEKI LOAD - {document_id}")
        logger.info("  Loading RDF into Fuseki triplestore...")
        
        try:
            # Use document-specific named graph
            graph_uri = f"{self.settings.contract_namespace}graph/{document_id}"
            
            load_result = await self.fuseki_agent.process({
                "rdf_data": rdf_data,
                "graph_uri": graph_uri,
            })
            
            result.triples_loaded = load_result.triple_count
            
            step.success = load_result.success
            step.result = {
                "success": load_result.success,
                "triple_count": load_result.triple_count,
                "graph_uri": graph_uri,
            }
            
            if not load_result.success:
                step.error = load_result.error
                result.error = f"Fuseki load failed: {load_result.error}"
                logger.error(f"  ✗ FAILED: {load_result.error}")
                return False
            
            logger.info(f"  ✓ Loaded {load_result.triple_count} triples to graph: {graph_uri}")
            return True
            
        except Exception as e:
            step.error = str(e)
            result.error = f"Fuseki load failed: {e}"
            logger.error(f"  ✗ FAILED: {e}")
            return False
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_reasoning(self, result: IngestionResult) -> None:
        """Step 9: Apply reasoning rules with proper graph context."""
        step = IngestionStep(step_name="reasoning", started_at=datetime.now())
        logger.info("=" * 60)
        logger.info("STEP 9: REASONING")
        logger.info("  Applying inference rules...")
        
        try:
            # Get the graph URI for this document
            graph_uri = f"{self.settings.contract_namespace}graph/{result.document_id}"
            
            # Collect all generated rules from schema evolution
            from pathlib import Path
            rule_files = []
            
            # Add generated rules from schema evolution step
            if hasattr(result, 'rules_generated') and result.rules_generated:
                rule_files.extend([str(Path(r)) for r in result.rules_generated])
                logger.info(f"  Using {len(rule_files)} generated rule file(s)")
            
            # Get default rule file if exists and no generated rules
            if not rule_files:
                # Try multiple possible locations for default rules
                possible_rules = [
                    Path("src/schemas/rules/jena_rules.txt"),
                    Path("src/schemas/rules/risk_rules.rules"),
                    Path("rules/procurement.rules"),
                ]
                for rule_file in possible_rules:
                    if rule_file.exists():
                        rule_files = [str(rule_file)]
                        logger.info(f"  Using default rule file: {rule_file}")
                        break
            
            reasoning_result = await self.reasoning_agent.process({
                "graph_uri": graph_uri,
                "rule_files": rule_files,
                "reasoning_type": "both",  # Both Jena rules and OWL reasoning
            })
            
            result.facts_inferred = reasoning_result.inferred_triples
            
            step.success = reasoning_result.success
            step.result = {
                "success": reasoning_result.success,
                "inferred_count": reasoning_result.inferred_triples,
                "rules_applied": reasoning_result.rules_applied,
                "reasoning_time_ms": reasoning_result.reasoning_time_ms,
            }
            
            if reasoning_result.error:
                step.error = reasoning_result.error
                logger.warning(f"  ⚠ Reasoning completed with errors: {reasoning_result.error}")
            else:
                logger.info(f"  ✓ Inferred {reasoning_result.inferred_triples} new facts")
                if reasoning_result.rules_applied:
                    logger.info(f"    Rules applied: {', '.join(reasoning_result.rules_applied)}")
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Reasoning failed: {e}")
            logger.warning(f"  ⚠ Reasoning error: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            logger.info(f"  Duration: {step.duration_ms:.0f}ms")
            result.steps.append(step)

    async def _step_vector_indexing(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
        rdf_uris: dict[str, str] | None = None,
        source_pipeline: str = "legacy",
    ) -> None:
        """Step 10: Vector indexing with RDF URI linking."""
        step = IngestionStep(step_name="vector_indexing", started_at=datetime.now())
        
        try:
            index_result = await self.vector_agent.process({
                "clauses": clauses,
                "contract_id": document_id,
                "document_id": document_id,
                "rdf_uris": rdf_uris or {},
                "source_pipeline": source_pipeline,
            })
            
            result.vectors_indexed = index_result.indexed_count
            
            step.success = index_result.success
            step.result = {
                "success": index_result.success,
                "indexed_count": index_result.indexed_count,
                "skipped_count": index_result.skipped_count,
            }
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Vector indexing failed: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)
    
    def _extract_rdf_uris_from_turtle(
        self,
        turtle_data: str,
        clauses: list[ExtractedClause],
    ) -> dict[str, str]:
        """
        Extract RDF URIs for clauses from generated Turtle.
        
        Returns:
            Dict mapping clause_id to RDF URI
        """
        from rdflib import Graph, Namespace, RDF, RDFS
        from config import get_settings
        
        settings = get_settings()
        CONTRACT = Namespace(settings.contract_namespace)
        
        rdf_uris = {}
        
        try:
            g = Graph()
            g.parse(data=turtle_data, format="turtle")
            
            # Map clause IDs to URIs
            for clause in clauses:
                clause_id = clause.clause_id or ""
                # Try to find the clause URI in the graph
                # Look for triples with this clause's label or ID
                for s, p, o in g.triples((None, RDFS.label, None)):
                    clause_title = clause.title or ""
                    if clause_id in str(s) or (clause_title and clause_title in str(o)):
                        rdf_uris[clause_id] = str(s)
                        break
                
                # Fallback: construct URI from namespace
                if clause_id not in rdf_uris:
                    rdf_uris[clause_id] = f"{settings.contract_namespace}{clause_id}"
        
        except Exception as e:
            self.logger.warning(f"Failed to extract RDF URIs: {e}")
            # Fallback: construct URIs from clause IDs
            for clause in clauses:
                clause_id = clause.clause_id or ""
                if clause_id:
                    rdf_uris[clause_id] = f"{settings.contract_namespace}{clause_id}"
        
        return rdf_uris

    async def _step_ontology_evolution(
        self,
        result: IngestionResult,
        document_id: str,
    ) -> None:
        """Step 11: Generate OWL extensions for new ontology concepts."""
        step = IngestionStep(step_name="ontology_evolution", started_at=datetime.now())
        
        try:
            from agents.ingestion.ontology_alignment import OntologySuggestion
            
            # Convert dict suggestions back to OntologySuggestion objects
            # Handle both dict and OntologySuggestion object cases
            suggestions = []
            for s in result.ontology_suggestions:
                if isinstance(s, OntologySuggestion):
                    # Already an OntologySuggestion object
                    suggestions.append(s)
                elif isinstance(s, dict):
                    # Convert dict to OntologySuggestion
                    suggestions.append(OntologySuggestion(
                        suggestion_type=s.get("type", "NewClass"),
                        name=s.get("name", "Unknown"),
                        description=s.get("description", ""),
                        parent_class=s.get("parent_class"),
                        examples=s.get("examples", []),
                        occurrences=s.get("occurrences", 1),
                    ))
                else:
                    # Fallback: try to create from object attributes
                    suggestions.append(OntologySuggestion(
                        suggestion_type=getattr(s, "suggestion_type", getattr(s, "type", "NewClass")),
                        name=getattr(s, "name", "Unknown"),
                        description=getattr(s, "description", ""),
                        parent_class=getattr(s, "parent_class", None),
                        examples=getattr(s, "examples", []),
                        occurrences=getattr(s, "occurrences", 1),
                    ))
            
            if not suggestions:
                step.success = True
                step.result = {"message": "No ontology suggestions to process"}
                return
            
            # Generate OWL extensions
            extension_result = await self.ontology_designer.extend_ontology(
                suggestions=suggestions,
                load_to_fuseki=self.config.ontology_evolution_mode == OntologyEvolutionMode.ADAPTIVE,
            )
            
            # Track generated files
            for ext in extension_result.extensions:
                if ext.file_path:
                    result.ontology_extensions_generated.append(ext.file_path)
                    result.artifact_paths[f"owl_{ext.suggestion_name}"] = ext.file_path
            
            if extension_result.combined_owl_path:
                result.artifact_paths["owl_combined"] = extension_result.combined_owl_path
            
            step.success = True
            step.result = {
                "extensions_generated": len(extension_result.extensions),
                "total_triples": extension_result.total_triples,
                "loaded_to_fuseki": extension_result.loaded_to_fuseki,
            }
            
            self.logger.info(
                "Ontology evolution complete",
                document_id=document_id,
                extensions=len(extension_result.extensions),
            )
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Ontology evolution failed: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def _step_rule_generation(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
    ) -> None:
        """Step 12: Generate inference rules for risk patterns."""
        step = IngestionStep(step_name="rule_generation", started_at=datetime.now())
        
        try:
            # Generate risk rules based on extracted clauses
            risk_patterns = []
            
            # Look for termination clauses to generate termination risk rules
            for clause in clauses:
                if clause.clause_type == "TerminationClause":
                    # Check if there's a notice period attribute
                    notice_period = clause.attributes.get("notice_period")
                    if notice_period and isinstance(notice_period, int):
                        # Determine risk threshold based on the notice period
                        if notice_period < 30:
                            risk_patterns.append(RulePattern(
                                pattern_name=f"HighTerminationRisk_{document_id}",
                                condition_class="proc:TerminationClause",
                                condition_property="proc:noticePeriod",
                                condition_operator="lessThan",
                                condition_value=30,
                                inferred_property="proc:hasRiskLevel",
                                inferred_value="proc:HighTerminationRisk",
                                description=f"Short notice period ({notice_period} days) indicates high termination risk",
                            ))
                
                # Data protection clauses - new patterns
                if clause.clause_type in ["DataProtectionClause", "DataRetentionClause"]:
                    retention = clause.attributes.get("retention_period")
                    if retention:
                        risk_patterns.append(RulePattern(
                            pattern_name=f"DataRetentionRisk_{document_id}",
                            condition_class=f"proc:{clause.clause_type}",
                            condition_property="proc:dataRetentionPeriod",
                            condition_operator="lessThan",
                            condition_value=2,
                            inferred_property="proc:hasRisk",
                            inferred_value="proc:ShortRetentionRisk",
                            description="Short data retention period may indicate compliance risk",
                        ))
            
            if not risk_patterns:
                step.success = True
                step.result = {"message": "No new risk patterns identified"}
                return
            
            # Generate rules
            rule_set_result = await self.rule_generator.generate_rules(
                patterns=risk_patterns,
                apply_to_fuseki=False,  # Don't auto-apply for safety
            )
            
            # Track generated files
            for rule in rule_set_result.rules:
                if rule.file_path:
                    result.rules_generated.append(rule.file_path)
                    result.artifact_paths[f"rule_{rule.rule_name}"] = rule.file_path
            
            if rule_set_result.combined_rules_path:
                result.artifact_paths["rules_combined"] = rule_set_result.combined_rules_path
            
            if rule_set_result.combined_sparql_path:
                result.artifact_paths["sparql_combined"] = rule_set_result.combined_sparql_path
            
            step.success = True
            step.result = {
                "rules_generated": len(rule_set_result.rules),
                "valid_rules": sum(1 for r in rule_set_result.rules if r.is_valid),
            }
            
            self.logger.info(
                "Rule generation complete",
                document_id=document_id,
                rules=len(rule_set_result.rules),
            )
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Rule generation failed: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    def _validate_clause_attributes(
        self,
        result: IngestionResult,
        document_id: str,
        clauses: list[ExtractedClause],
    ) -> None:
        """Validate that critical attributes are present in extracted clauses."""
        gaps = []
        
        for clause in clauses:
            attrs = clause.attributes or {}
            
            # Check TerminationClause for notice_period
            if clause.clause_type == "TerminationClause":
                if not attrs.get("notice_period") and not attrs.get("notice_period_days"):
                    gaps.append({
                        "clause_id": clause.clause_id,
                        "clause_type": clause.clause_type,
                        "missing_attribute": "notice_period",
                        "severity": "high",
                        "clause_preview": clause.raw_text[:200],
                    })
            
            # Check PaymentClause for payment information
            elif clause.clause_type == "PaymentClause":
                if not attrs.get("payment_terms") and not attrs.get("payment_days"):
                    gaps.append({
                        "clause_id": clause.clause_id,
                        "clause_type": clause.clause_type,
                        "missing_attribute": "payment_terms/payment_days",
                        "severity": "high",
                        "clause_preview": clause.raw_text[:200],
                    })
            
            # Check PenaltyClause for penalty information
            elif clause.clause_type == "PenaltyClause":
                if not attrs.get("penalty_amount") and not attrs.get("penalty_percentage"):
                    gaps.append({
                        "clause_id": clause.clause_id,
                        "clause_type": clause.clause_type,
                        "missing_attribute": "penalty_amount/penalty_percentage",
                        "severity": "medium",
                        "clause_preview": clause.raw_text[:200],
                    })
        
        # Log gaps if any
        if gaps:
            self.logger.warning(
                "Critical attributes missing from extracted clauses",
                document_id=document_id,
                gaps_count=len(gaps),
            )
            logger.warning(f"  ⚠ Found {len(gaps)} clauses with missing critical attributes:")
            for gap in gaps:
                logger.warning(
                    f"    • {gap['clause_type']} ({gap['clause_id']}): "
                    f"Missing {gap['missing_attribute']}"
                )
            
            # Store gaps in result for explanation
            result.extraction_gaps.extend(gaps)
        else:
            logger.info("  ✓ All critical attributes present in extracted clauses")

    async def _step_save_artifacts(
        self,
        result: IngestionResult,
        document_id: str,
        text: str,
        clauses: list[ExtractedClause],
        entities: EntityExtractionResult | None,
        obligations: list,
        risks: list,
        rdf_data: str,
        job_id: str | None = None,
    ) -> None:
        """Step 13: Save all intermediate artifacts for transparency."""
        step = IngestionStep(step_name="save_artifacts", started_at=datetime.now())
        
        try:
            # RDF is already saved in Step 6.5, so skip here
            # Just save extraction results and log
            
            # Save extraction results
            extraction_data = {
                "clauses": [c.model_dump() for c in clauses] if clauses else [],
                "entities": entities.model_dump() if entities else {},
                "obligations": [o.model_dump() for o in obligations] if obligations else [],
                "risks": [r.model_dump() for r in risks] if risks else [],
            }
            extraction_path = await self.artifact_store.save_extraction_results(
                document_id=document_id,
                clauses=extraction_data["clauses"],
                entities=extraction_data["entities"],
                obligations=extraction_data["obligations"],
                risks=extraction_data["risks"],
            )
            result.artifact_paths["extractions"] = str(extraction_path)
            
            # Save full ingestion log (async)
            log_path = await self.artifact_store.save_ingestion_log(
                document_id=document_id,
                result=result.model_dump(),
            )
            result.artifact_paths["log"] = str(log_path)

            # If configured, upload artifacts to object storage (MinIO/COS) and
            # optionally cleanup local files to keep containers light.
            if self.artifact_store:
                result.artifact_paths = await self.artifact_store.maybe_upload_artifact_paths(
                    result.artifact_paths,
                    document_id=document_id,
                    job_id=job_id,
                )
            
            step.success = True
            step.result = {
                "artifacts_saved": len(result.artifact_paths),
            }
            
            self.logger.info(
                "Artifacts saved",
                document_id=document_id,
                artifacts=len(result.artifact_paths),
            )
            
        except Exception as e:
            step.error = str(e)
            self.logger.warning(f"Artifact saving failed: {e}")
        finally:
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            result.steps.append(step)

    async def ingest_batch(
        self,
        items: list[dict[str, Any]],
        max_concurrent: int = 10,  # Increased from 5 to 10 for better throughput
        extract_documents_parallel: bool = True,
        progress_callback: Any | None = None,
        override: bool = False,
        job_id: str | None = None,
    ) -> list[IngestionResult]:
        """
        Process multiple documents concurrently with full pipeline parallelization.
        
        Features:
        - Parallel document extraction (I/O bound)
        - Full pipeline parallelization per document
        - Schema evolution coordination
        - LLM rate limiting
        - Graceful error handling
        
        Args:
            items: List of dicts with 'file_path' or 'text' and optional 'document_id'
            max_concurrent: Maximum number of documents to process concurrently
            extract_documents_parallel: Whether to extract documents in parallel first
            
        Returns:
            List of IngestionResult objects
        """
        import asyncio
        
        self.logger.info(
            "Starting batch ingestion",
            total_documents=len(items),
            max_concurrent=max_concurrent,
            parallel_extraction=extract_documents_parallel
        )

        # IMPORTANT: In Docling mode, pre-extracting into raw text loses DocTags
        # sections/hints which downstream agents rely on. Prefer ingest(file_path)
        # so DoclingDocumentIngestionAgent runs inside the pipeline and preserves
        # structured sections.
        if self.settings.ingestion_source == "docling":
            extract_documents_parallel = False
        
        # Process documents with streaming: extract → ingest immediately (no waiting)
        semaphore = asyncio.Semaphore(max_concurrent)
        completed_count = 0
        
        async def extract_and_ingest(item: dict[str, Any]) -> IngestionResult:
            """
            Extract document (if needed) and immediately start ingestion pipeline.
            This allows extraction and ingestion to overlap across documents.
            """
            nonlocal completed_count
            async with semaphore:
                # Step 1: Extract document if file_path provided and parallel extraction enabled
                if extract_documents_parallel and item.get("file_path"):
                    try:
                        from agents.ingestion.document_ingestion import DocumentIngestionAgent
                        doc_agent = DocumentIngestionAgent(settings=self.settings)
                        extracted_doc = await doc_agent.process(item["file_path"])
                        
                        # Update item with extracted content
                        item["text"] = extracted_doc.text
                        item["document_id"] = extracted_doc.document_id
                        item["file_path"] = None  # Already extracted
                        
                        self.logger.debug(
                            "Document extracted, starting ingestion",
                            document_id=extracted_doc.document_id
                        )
                    except Exception as e:
                        self.logger.error(
                            "Document extraction failed",
                            file_path=item.get("file_path"),
                            error=str(e)
                        )
                        return IngestionResult(
                            document_id=item.get("document_id", "unknown"),
                            success=False,
                            error=f"Extraction failed: {e}",
                        )
                
                # Step 2: Start ingestion pipeline immediately (no waiting for other documents)
                # Note: We rely on cloud provider's built-in rate limiting + retry logic
                # No proactive rate limiting needed - providers handle 429 errors, we retry
                result = await self.ingest(
                    file_path=item.get("file_path"),
                    text=item.get("text"),
                    document_id=item.get("document_id"),
                    override=override,
                    job_id=job_id,
                )

                # Update batch-level progress if callback provided
                if progress_callback:
                    try:
                        completed_count += 1
                        # progress_callback(done, total)
                        maybe_coro = progress_callback(
                            completed_count,
                            len(items),
                        )
                        # Support both async and sync callbacks
                        if hasattr(maybe_coro, "__await__"):
                            await maybe_coro
                    except Exception as cb_err:
                        self.logger.warning(
                            "Batch progress callback failed",
                            error=str(cb_err),
                        )

                return result
        
        # Process all items concurrently - each document extracts then ingests immediately
        # This allows extraction and ingestion to overlap across documents
        tasks = [extract_and_ingest(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(
                    "Batch ingestion failed for item",
                    index=i,
                    error=str(result)
                )
                processed_results.append(
                    IngestionResult(
                        document_id=items[i].get("document_id", f"doc_{i}"),
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)
        
        # Process any queued schema evolution changes
        pending_changes = self.resource_manager.schema_lock.get_pending_changes()
        if pending_changes:
            self.logger.info(
                "Processing queued schema evolution changes",
                pending_count=len(pending_changes)
            )
            # Process queued changes sequentially to avoid conflicts
            for change in pending_changes:
                if await self.resource_manager.coordinate_schema_evolution(change):
                    try:
                        # Re-process schema evolution for the document
                        # (This is a simplified approach - in production, you might
                        # want to store the alignment results and process them here)
                        self.logger.info(
                            "Processing queued schema change",
                            document_id=change.get("document_id")
                        )
                    finally:
                        self.resource_manager.release_schema_evolution()
        
        self.logger.info(
            "Batch ingestion completed",
            total=len(items),
            successful=sum(1 for r in processed_results if r.success),
            failed=sum(1 for r in processed_results if not r.success),
        )
        
        return processed_results
    
    async def _extract_documents_parallel(
        self,
        items: list[dict[str, Any]],
    ) -> list[Any]:
        """
        Extract documents in parallel (I/O bound operation).
        
        Args:
            items: List of items with 'file_path' or 'text'
            
        Returns:
            List of ExtractedDocument objects (None for items without file_path)
        """
        from agents.ingestion.document_ingestion import DocumentIngestionAgent
        
        extraction_tasks = []
        doc_agent = DocumentIngestionAgent(settings=self.settings)
        
        for item in items:
            file_path = item.get("file_path")
            if file_path:
                # Extract document
                extraction_tasks.append(doc_agent.process(file_path))
            else:
                # Already has text, no extraction needed
                extraction_tasks.append(None)
        
        # Execute extractions in parallel
        results = await asyncio.gather(
            *[task for task in extraction_tasks if task is not None],
            return_exceptions=True
        )
        
        # Map results back to items
        extracted_docs = []
        result_idx = 0
        for task in extraction_tasks:
            if task is None:
                extracted_docs.append(None)
            else:
                if isinstance(results[result_idx], Exception):
                    self.logger.error(
                        "Document extraction failed",
                        error=str(results[result_idx]),
                        file_path=items[len(extracted_docs)].get("file_path")
                    )
                    extracted_docs.append(None)
                else:
                    extracted_docs.append(results[result_idx])
                result_idx += 1
        
        return extracted_docs

    def get_pipeline_summary(self, result: IngestionResult) -> dict[str, Any]:
        """Get a summary of the pipeline execution."""
        step_summary = {}
        for step in result.steps:
            step_summary[step.step_name] = {
                "success": step.success,
                "duration_ms": step.duration_ms,
                "error": step.error,
            }
        
        return {
            "document_id": result.document_id,
            "success": result.success,
            "total_duration_ms": result.total_duration_ms,
            "metrics": {
                "clauses": result.clauses_extracted,
                "entities": result.entities_extracted,
                "obligations": result.obligations_extracted,
                "risks": result.risks_extracted,
                "triples_generated": result.triples_generated,
                "triples_loaded": result.triples_loaded,
                "facts_inferred": result.facts_inferred,
                "vectors_indexed": result.vectors_indexed,
            },
            "steps": step_summary,
            "ontology_suggestions": len(result.ontology_suggestions),
            "validation_errors": len(result.validation_errors),
            "validation_warnings": len(result.validation_warnings),
        }
