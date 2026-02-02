"""
Configuration management for the Contract KG Agents.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Fuseki SPARQL Endpoint
    fuseki_url: str = Field(
        default="http://localhost:3030",
        description="Base URL of the Fuseki SPARQL server",
    )
    fuseki_dataset: str = Field(
        default="contracts",
        description="Name of the Fuseki dataset",
    )
    fuseki_user: str = Field(
        default="",
        description="Fuseki admin username (leave empty if no auth required)",
    )
    fuseki_password: str = Field(
        default="",
        description="Fuseki admin password (leave empty if no auth required)",
    )

    # LLM Configuration - OpenAI (optional, not used by default)
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key for LLM access",
    )
    openai_model: str = Field(
        default="gpt-4-turbo-preview",
        description="OpenAI model to use",
    )
    
    # Alternative LLM (Anthropic) - optional
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude access",
    )
    anthropic_model: str = Field(
        default="claude-3-opus-20240229",
        description="Anthropic model to use",
    )
    
    # IBM watsonx.ai
    watsonx_api_key: str = Field(
        default="",
        description="Watsonx API key (WATSONX_API_KEY)",
    )
    watsonx_project_id: str = Field(
        default="",
        description="Watsonx project ID (WATSONX_PROJECT_ID)",
    )
    watsonx_model_id: str = Field(
        default="",
        description="Watsonx model ID, e.g. meta-llama/llama-3-70b-instruct",
    )
    watsonx_url: str = Field(
        default="",
        description="Watsonx service URL, e.g. https://us-south.ml.cloud.ibm.com",
    )
    
    # Local LLM (Ollama)
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL for local LLM",
    )
    ollama_model: str = Field(
        default="llama3:8b",
        description="Ollama model to use",
    )
    ollama_fallback_model: str = Field(
        default="llama3:8b",
        description="Fallback Ollama model to use if the configured model is not available",
    )
    
    # LLM Provider Selection
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider to use: ollama, watsonx",
    )
    
    # Storage Provider Selection
    sparql_store: str = Field(
        default="fuseki",
        description="SPARQL store to use: fuseki",
    )
    vector_store: str = Field(
        default="milvus",
        description="Vector store to use: milvus",
    )
    
    # Document Registry (Duplicate Detection)
    document_registry_backend: str = Field(
        default="sqlite",
        description="Document registry backend: redis, sqlite, fuseki",
    )
    document_registry_redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for document registry (if backend=redis)",
    )
    enable_duplicate_check: bool = Field(
        default=True,
        description="Enable duplicate document detection",
    )

    # Milvus Vector Database
    milvus_host: str = Field(
        default="localhost",
        description="Milvus server host",
    )
    milvus_port: int = Field(
        default=19530,
        description="Milvus server port",
    )
    milvus_collection: str = Field(
        default="contract_clauses",
        description="Milvus collection name for clause embeddings",
    )
    milvus_collection_v2: str = Field(
        default="contract_clauses_v2",
        description="Milvus collection name for v2 schema (dual embeddings + summaries)",
    )
    enable_text_embedding_fallback: bool = Field(
        default=True,
        description="When searching, fallback to full-text embeddings if needed",
    )
    
    # Embedding Model
    embedding_model: str = Field(
        default="intfloat/e5-large-v2",
        description="Sentence transformer model for embeddings",
    )
    embedding_dim: int = Field(
        default=1024,
        description="Embedding dimension (must match the model)",
    )

    # Ontology
    ontology_path: str = Field(
        default="src/schemas/ontology/procurement.owl",
        description="Path to the OWL ontology file",
    )
    procurement_namespace: str = Field(
        default="http://procurement.kg/ontology#",
        description="Namespace for procurement ontology",
    )
    contract_namespace: str = Field(
        default="http://procurement.kg/contract#",
        description="Namespace for contract instances",
    )

    # Document Processing
    upload_directory: str = Field(
        default="./data/uploads",
        description="Directory for uploaded documents",
    )
    max_file_size_mb: int = Field(
        default=50,
        description="Maximum file size in MB",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    enable_agent_explanations: bool = Field(
        default=True,
        description="Whether to automatically generate process explanations for all agents",
    )
    
    # Observability / Phoenix Tracing
    phoenix_enabled: bool = Field(
        default=True,
        description="Enable Phoenix tracing and observability integration",
    )
    phoenix_collector_endpoint: str = Field(
        default="http://phoenix:4317",
        description="OTLP gRPC endpoint for Phoenix collector",
    )
    
    # Schema Evolution
    ontology_evolution_mode: str = Field(
        default="conservative",
        description="Schema evolution mode: conservative, suggestive, or adaptive",
    )
    generate_owl_extensions: bool = Field(
        default=False,
        description="Whether to generate OWL extensions for new concepts",
    )
    generate_rules: bool = Field(
        default=False,
        description="Whether to generate inference rules for patterns",
    )
    generate_shacl: bool = Field(
        default=True,
        description="Whether to generate SHACL validation shapes for new classes",
    )
    enable_pattern_detection: bool = Field(
        default=True,
        description="Whether to enable comprehensive pattern detection (risk, compliance, obligations)",
    )
    enable_schema_governance: bool = Field(
        default=True,
        description="Whether to enable schema versioning, conflict resolution, and rollback",
    )
    
    # Performance Optimizations (currently disabled by default)
    enable_query_cache: bool = Field(
        default=False,
        description="Enable query result caching for faster repeated queries",
    )
    query_cache_size: int = Field(
        default=100,
        description="Maximum number of queries to cache",
    )
    query_cache_ttl: int = Field(
        default=3600,
        description="Cache time-to-live in seconds (default: 1 hour)",
    )
    enable_sparql_templates: bool = Field(
        default=False,
        description="Enable SPARQL template matching for common queries",
    )
    enable_fast_complexity_detection: bool = Field(
        default=False,
        description="Enable fast rule-based complexity detection",
    )
    skip_vector_when_kg_sufficient: bool = Field(
        default=False,
        description="Skip vector search when KG results are sufficient",
    )
    kg_sufficient_threshold: int = Field(
        default=3,
        description="Minimum KG facts to consider sufficient",
    )
    
    # ReAct Configuration
    always_use_react: bool = Field(
        default=True,
        description="Always use ReAct agent for all queries (simplified architecture)",
    )

    class Config:
        extra = "ignore"  # Ignore extra fields from environment
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def sparql_query_endpoint(self) -> str:
        """Get the SPARQL query endpoint URL."""
        return f"{self.fuseki_url}/{self.fuseki_dataset}/query"

    @property
    def sparql_update_endpoint(self) -> str:
        """Get the SPARQL update endpoint URL."""
        return f"{self.fuseki_url}/{self.fuseki_dataset}/update"

    @property
    def graph_store_endpoint(self) -> str:
        """Get the Graph Store Protocol endpoint URL."""
        return f"{self.fuseki_url}/{self.fuseki_dataset}/data"
    
    @property
    def milvus_uri(self) -> str:
        """Get the Milvus connection URI."""
        return f"http://{self.milvus_host}:{self.milvus_port}"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
