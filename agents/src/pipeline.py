"""
End-to-end pipeline for processing procurement contracts.

This module orchestrates the complete flow:
1. Document ingestion
2. Clause extraction
3. Obligation/risk analysis
4. RDF generation
5. Knowledge graph population
6. Reasoning application
"""

from pathlib import Path
from typing import Any

from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, XSD

from config import Settings, get_settings
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from logger import get_module_logger
from agents import (
    DocumentIngestionAgent,
    ClauseExtractionAgent,
    ObligationRiskAgent,
    RAGOrchestratorAgent,
)

logger = get_module_logger(__name__)


class ContractProcessingPipeline:
    """
    End-to-end pipeline for processing procurement contracts.
    
    Flow:
    1. Ingest document (PDF/DOCX)
    2. Extract clauses using LLM
    3. Analyze obligations and risks
    4. Generate RDF triples
    5. Load into Jena/Fuseki
    6. Apply reasoning rules
    7. Index in vector store for RAG
    """

    def __init__(
        self,
        settings: Settings | None = None,
        sparql_store: SPARQLStore | None = None,
        vector_store: VectorStore | None = None,
    ):
        """
        Initialize the pipeline with dependency injection.
        
        Args:
            settings: Application settings
            sparql_store: Optional SPARQL store (injected via dependency injection)
            vector_store: Optional vector store (injected via dependency injection)
        """
        self.settings = settings or get_settings()
        
        # Use dependency injection - get from service factory if not provided
        service_factory = get_service_factory(settings=self.settings)
        self.sparql_store = sparql_store or service_factory.get_sparql_store()
        self.vector_store = vector_store or service_factory.get_vector_store()
        
        # Backward compatibility (deprecated)
        self.fuseki = self.sparql_store
        
        # Initialize agents
        self.ingestion_agent = DocumentIngestionAgent(settings=self.settings)
        self.clause_agent = ClauseExtractionAgent(settings=self.settings)
        self.risk_agent = ObligationRiskAgent(settings=self.settings)
        self.rag_agent = RAGOrchestratorAgent(
            sparql_store=self.sparql_store,
            vector_store=self.vector_store,
            settings=self.settings,
        )
        
        # Namespaces
        self.PROC = Namespace(self.settings.procurement_namespace)
        self.CONTRACT = Namespace(self.settings.contract_namespace)
        
        logger.info("ContractProcessingPipeline initialized")

    async def process_document(
        self,
        file_path: str | Path,
        contract_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process a complete contract document through the pipeline.
        
        Args:
            file_path: Path to the contract document
            contract_metadata: Optional metadata (value, dates, jurisdiction)
            
        Returns:
            Processing results including extracted data and KG URIs
        """
        metadata = contract_metadata or {}
        
        logger.info("Starting document processing", file=str(file_path))
        
        # Step 1: Document Ingestion
        logger.info("Step 1: Ingesting document...")
        doc = await self.ingestion_agent.process(file_path)
        
        # Step 2: Clause Extraction
        logger.info("Step 2: Extracting clauses...")
        clause_result = await self.clause_agent.process({
            "document_id": doc.document_id,
            "text": doc.text,
        })
        
        # Step 3: Obligation and Risk Analysis
        logger.info("Step 3: Analyzing obligations and risks...")
        risk_result = await self.risk_agent.process({
            "document_id": doc.document_id,
            "clauses": clause_result.clauses,
        })
        
        # Step 4: Generate RDF
        logger.info("Step 4: Generating RDF triples...")
        rdf_graph = self._generate_rdf(
            doc.document_id,
            metadata,
            clause_result.clauses,
            risk_result.obligations,
            risk_result.risks,
        )
        
        # Step 5: Load into Fuseki
        logger.info("Step 5: Loading into knowledge graph...")
        self.fuseki.load_graph(rdf_graph)
        
        # Step 6: Index clauses in Milvus vector store
        logger.info("Step 6: Indexing in Milvus vector store...")
        self._index_clauses(clause_result.clauses, doc.document_id)
        
        # Prepare result
        contract_uri = f"{self.settings.contract_namespace}{doc.document_id}"
        
        result = {
            "contract_uri": contract_uri,
            "document_id": doc.document_id,
            "clause_count": len(clause_result.clauses),
            "obligation_count": len(risk_result.obligations),
            "risk_count": len(risk_result.risks),
            "risk_score": self.risk_agent.calculate_risk_score(risk_result),
            "high_severity_risks": [
                r.model_dump() 
                for r in self.risk_agent.get_high_severity_risks(risk_result)
            ],
            "summary": risk_result.summary,
        }
        
        logger.info(
            "Document processing complete",
            contract_uri=contract_uri,
            clauses=result["clause_count"],
            risks=result["risk_count"],
        )
        
        return result

    def _generate_rdf(
        self,
        document_id: str,
        metadata: dict[str, Any],
        clauses: list,
        obligations: list,
        risks: list,
    ) -> Graph:
        """Generate RDF graph from extracted data."""
        g = Graph()
        
        # Bind prefixes
        g.bind("proc", self.PROC)
        g.bind("contract", self.CONTRACT)
        g.bind("rdf", RDF)
        g.bind("rdfs", RDFS)
        g.bind("xsd", XSD)
        
        # Create contract
        contract_uri = URIRef(f"{self.CONTRACT}{document_id}")
        g.add((contract_uri, RDF.type, self.PROC.Contract))
        
        # Add metadata
        if "value" in metadata:
            g.add((contract_uri, self.PROC.contractValue, 
                   Literal(metadata["value"], datatype=XSD.decimal)))
        
        if "effective_date" in metadata:
            g.add((contract_uri, self.PROC.effectiveDate,
                   Literal(metadata["effective_date"], datatype=XSD.date)))
        
        if "expiration_date" in metadata:
            g.add((contract_uri, self.PROC.expirationDate,
                   Literal(metadata["expiration_date"], datatype=XSD.date)))
        
        if "jurisdiction" in metadata:
            jurisdiction_uri = URIRef(f"{self.PROC}{metadata['jurisdiction']}")
            g.add((contract_uri, self.PROC.governedBy, jurisdiction_uri))
        
        # Add clauses
        for clause in clauses:
            clause_uri = URIRef(f"{self.CONTRACT}{clause.clause_id}")
            clause_type_uri = URIRef(f"{self.PROC}{clause.clause_type}")
            
            g.add((clause_uri, RDF.type, clause_type_uri))
            g.add((contract_uri, self.PROC.hasClause, clause_uri))
            g.add((clause_uri, self.PROC.rawText, Literal(clause.raw_text)))
            
            if clause.title:
                g.add((clause_uri, RDFS.label, Literal(clause.title)))
            
            # Add specific attributes
            if clause.clause_type == "TerminationClause":
                notice_period = clause.attributes.get("notice_period")
                if notice_period is not None:
                    g.add((clause_uri, self.PROC.noticePeriod,
                           Literal(notice_period, datatype=XSD.integer)))
            
            if clause.clause_type == "PenaltyClause":
                penalty = clause.attributes.get("penalty_amount")
                if penalty is not None:
                    g.add((clause_uri, self.PROC.penaltyAmount,
                           Literal(penalty, datatype=XSD.decimal)))
        
        return g

    def _index_clauses(self, clauses: list, contract_id: str = "") -> None:
        """Index clause texts in Milvus vector store for RAG."""
        clause_data = [
            {
                "clause_id": clause.clause_id,
                "text": clause.raw_text,
                "contract_id": contract_id,
                "clause_type": clause.clause_type,
            }
            for clause in clauses
        ]
        
        if clause_data:
            self.vector_store.add_clauses_batch(clause_data)

    async def query(self, question: str) -> dict[str, Any]:
        """
        Query the knowledge graph using natural language.
        
        Args:
            question: Natural language question
            
        Returns:
            RAG response with answer and sources
        """
        response = await self.rag_agent.process(question)
        return response.model_dump()

    def get_contract_summary(self, contract_uri: str) -> dict[str, Any]:
        """
        Get a summary of a contract from the knowledge graph.
        
        Args:
            contract_uri: URI of the contract
            
        Returns:
            Summary including clauses, risks, and compliance issues
        """
        # Get basic info
        details = self.fuseki.execute_select(f"""
            SELECT ?property ?value
            WHERE {{
                <{contract_uri}> ?property ?value .
            }}
        """)
        
        # Get risks
        risks = self.fuseki.get_contract_risks(contract_uri)
        
        # Get compliance issues
        issues = self.fuseki.get_compliance_issues(contract_uri)
        
        return {
            "contract_uri": contract_uri,
            "properties": details,
            "risks": risks,
            "compliance_issues": issues,
        }


# Convenience function for simple usage
async def process_contract(
    file_path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Process a contract document (convenience function).
    
    Example:
        result = await process_contract(
            "contract.pdf",
            metadata={"jurisdiction": "EU", "value": 500000}
        )
    """
    pipeline = ContractProcessingPipeline()
    return await pipeline.process_document(file_path, metadata)
