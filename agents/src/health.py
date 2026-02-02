"""
Health check module for system components.

Provides comprehensive health checks for:
- Fuseki server
- Milvus vector store
- LLM connectivity
- Ontology manager
"""

from typing import Any
from datetime import datetime

from pydantic import BaseModel, Field

from config import Settings, get_settings
from storage.sparql.base import SPARQLStore
from storage.vector.base import VectorStore
from service_factory import get_service_factory
from ontology_manager import get_ontology_manager
from logger import get_module_logger


class ComponentHealth(BaseModel):
    """Health status of a single component."""
    
    name: str = Field(description="Component name")
    healthy: bool = Field(description="Whether component is healthy")
    status: str = Field(default="unknown", description="Status message")
    response_time_ms: float = Field(default=0.0, description="Response time")
    error: str | None = Field(default=None, description="Error if unhealthy")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")


class SystemHealth(BaseModel):
    """Overall system health status."""
    
    timestamp: datetime = Field(default_factory=datetime.now)
    overall_healthy: bool = Field(description="Whether all critical components are healthy")
    components: list[ComponentHealth] = Field(default_factory=list)
    version: str = Field(default="1.0.0", description="System version")


class HealthChecker:
    """Comprehensive health checker for all system components."""
    
    def __init__(self, settings: Settings | None = None):
        """Initialize health checker."""
        self.settings = settings or get_settings()
        self.logger = get_module_logger(__name__).bind(
            component="HealthChecker"
        )
    
    async def check_all(self) -> SystemHealth:
        """
        Check health of all system components.
        
        Returns:
            SystemHealth with status of all components
        """
        components = []
        
        # Check Fuseki
        components.append(await self.check_fuseki())
        
        # Check Milvus
        components.append(await self.check_milvus())
        
        # Check LLM connectivity
        components.append(await self.check_llm())
        
        # Check Ontology Manager
        components.append(await self.check_ontology_manager())
        
        # Determine overall health (all critical components must be healthy)
        critical_components = ["fuseki", "milvus", "ontology_manager"]
        overall_healthy = all(
            c.healthy for c in components
            if c.name in critical_components
        )
        
        return SystemHealth(
            overall_healthy=overall_healthy,
            components=components,
        )
    
    async def check_fuseki(self) -> ComponentHealth:
        """Check Fuseki server health."""
        import time
        start = time.time()
        
        try:
            # Use SPARQL store abstraction
            service_factory = get_service_factory(settings=self.settings)
            sparql_store = service_factory.get_sparql_store()
            
            # Try a simple query
            query = "SELECT (COUNT(*) as ?count) WHERE { ?s ?p ?o }"
            results = sparql_store.execute_select(query, add_prefixes=False)
            
            response_time = (time.time() - start) * 1000
            
            # Get triple count
            triple_count = int(results[0]["count"]) if results else 0
            
            return ComponentHealth(
                name="fuseki",
                healthy=True,
                status="operational",
                response_time_ms=response_time,
                details={
                    "url": self.settings.fuseki_url,
                    "dataset": self.settings.fuseki_dataset,
                    "triple_count": triple_count,
                }
            )
        
        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.logger.error("Fuseki health check failed", error=str(e))
            return ComponentHealth(
                name="fuseki",
                healthy=False,
                status="unavailable",
                response_time_ms=response_time,
                error=str(e),
            )
    
    async def check_milvus(self) -> ComponentHealth:
        """Check Milvus vector store health."""
        import time
        start = time.time()
        
        try:
            # Use vector store abstraction
            service_factory = get_service_factory(settings=self.settings)
            vector_store = service_factory.get_vector_store()
            
            # Get collection stats
            stats = vector_store.get_collection_stats()
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="milvus",
                healthy=True,
                status="operational",
                response_time_ms=response_time,
                details=stats,
            )
        
        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.logger.error("Milvus health check failed", error=str(e))
            return ComponentHealth(
                name="milvus",
                healthy=False,
                status="unavailable",
                response_time_ms=response_time,
                error=str(e),
            )
    
    async def check_llm(self) -> ComponentHealth:
        """Check LLM provider connectivity using provider abstraction."""
        import time
        start = time.time()
        
        try:
            from llm.provider_factory import LLMProviderFactory
            
            # Get provider instance
            provider = LLMProviderFactory.create_provider(self.settings.llm_provider)
            
            # Validate configuration
            config_valid = provider.validate_config(self.settings)
            
            # Provider-specific connectivity checks
            is_accessible = config_valid
            if provider.name == "ollama":
                # Ollama doesn't need a key, check if base URL is accessible
                import httpx
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        response = await client.get(self.settings.ollama_base_url)
                        is_accessible = response.status_code in (200, 404)  # 404 is OK, means server is up
                except:
                    is_accessible = False
            elif provider.name == "watsonx":
                # WatsonX not yet integrated, mark as not accessible
                is_accessible = False
            
            response_time = (time.time() - start) * 1000
            
            if is_accessible:
                # Get model name from settings based on provider
                model_attr = f"{provider.name}_model"
                model = getattr(self.settings, model_attr, "unknown")
                
                return ComponentHealth(
                    name="llm",
                    healthy=True,
                    status="configured",
                    response_time_ms=response_time,
                    details={
                        "provider": provider.name,
                        "model": model,
                    }
                )
            else:
                return ComponentHealth(
                    name="llm",
                    healthy=False,
                    status="not_configured",
                    response_time_ms=response_time,
                    error=f"{provider.name} provider configuration is invalid or not accessible",
                )
        
        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.logger.error("LLM health check failed", error=str(e))
            return ComponentHealth(
                name="llm",
                healthy=False,
                status="error",
                response_time_ms=response_time,
                error=str(e),
            )
    
    async def check_ontology_manager(self) -> ComponentHealth:
        """Check ontology manager health."""
        import time
        start = time.time()
        
        try:
            manager = get_ontology_manager()
            
            if manager.active_schema is None:
                return ComponentHealth(
                    name="ontology_manager",
                    healthy=False,
                    status="not_initialized",
                    response_time_ms=(time.time() - start) * 1000,
                    error="Ontology manager not initialized - no active schema",
                )
            
            schema = manager.active_schema
            class_count = len(schema.get_all_classes())
            property_count = len(schema.get_all_properties())
            
            response_time = (time.time() - start) * 1000
            
            return ComponentHealth(
                name="ontology_manager",
                healthy=True,
                status="operational",
                response_time_ms=response_time,
                details={
                    "classes": class_count,
                    "properties": property_count,
                    "namespace": str(schema.namespace),
                    "version": schema.version,
                }
            )
        
        except Exception as e:
            response_time = (time.time() - start) * 1000
            self.logger.error("Ontology manager health check failed", error=str(e))
            return ComponentHealth(
                name="ontology_manager",
                healthy=False,
                status="error",
                response_time_ms=response_time,
                error=str(e),
            )


async def check_health() -> SystemHealth:
    """Convenience function to check system health."""
    checker = HealthChecker()
    return await checker.check_all()
