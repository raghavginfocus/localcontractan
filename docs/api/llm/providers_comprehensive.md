# LLM Providers API Reference

Comprehensive API documentation for LLM provider abstraction layer supporting IBM WatsonX.ai and Ollama.

## Overview

The LLM Providers module provides a unified interface for different Large Language Model providers, enabling easy switching between cloud-based (WatsonX) and local (Ollama) models without code changes. It supports chat models, batch processing, and streaming responses.

**Key Features:**
- Provider abstraction with factory pattern
- Support for IBM WatsonX.ai and Ollama
- Unified chat model interface via LangChain
- Batch processing for high throughput
- Streaming responses for better UX
- Configuration validation
- Extensible architecture for new providers

---

## LLMProviderFactory

Factory class for creating LLM provider instances.

### Class Definition

```python
from llm.provider_factory import LLMProviderFactory

class LLMProviderFactory:
    """
    Factory for creating LLM providers.
    
    Usage:
        provider = LLMProviderFactory.create_provider("ollama")
        llm = provider.create_chat_model(settings)
    """
```

### Methods

#### create_provider

```python
@classmethod
def create_provider(
    cls,
    provider_name: str
) -> LLMProvider
```

Create a provider instance by name.

**Parameters:**

- **provider_name** : `str`
  - Name of the provider: "ollama" or "watsonx"
  - Case-insensitive

**Returns:**

- **provider** : `LLMProvider`
  - Provider instance ready to create models

**Raises:**

- **ValueError**
  - If provider name is not recognized
  - Includes list of available providers in error message

**Example:**

```python
from llm.provider_factory import LLMProviderFactory
from config import get_settings

# Create Ollama provider
provider = LLMProviderFactory.create_provider("ollama")

# Create WatsonX provider
provider = LLMProviderFactory.create_provider("watsonx")

# Get settings
settings = get_settings()

# Create chat model
llm = provider.create_chat_model(settings, temperature=0.7)

# Use model
response = llm.invoke("What is a knowledge graph?")
print(response.content)
```

**Error Handling:**

```python
try:
    provider = LLMProviderFactory.create_provider("unknown")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Unknown LLM provider: 'unknown'. Available providers: ollama, watsonx
```

---

#### register_provider

```python
@classmethod
def register_provider(
    cls,
    name: str,
    provider_class: Type[LLMProvider]
) -> None
```

Register a new provider for extensibility.

**Parameters:**

- **name** : `str`
  - Provider name identifier (case-insensitive)
  
- **provider_class** : `Type[LLMProvider]`
  - Provider class implementing LLMProvider protocol

**Example:**

```python
from llm.providers.base import LLMProvider

class CustomProvider(LLMProvider):
    def create_chat_model(self, settings, **kwargs):
        # Implementation
        pass
    
    def validate_config(self, settings):
        # Implementation
        pass

# Register custom provider
LLMProviderFactory.register_provider("custom", CustomProvider)

# Use custom provider
provider = LLMProviderFactory.create_provider("custom")
```

---

#### list_providers

```python
@classmethod
def list_providers(cls) -> list[str]
```

List all registered provider names.

**Returns:**

- **providers** : `list[str]`
  - List of available provider names

**Example:**

```python
providers = LLMProviderFactory.list_providers()
print(f"Available providers: {', '.join(providers)}")

# Output: Available providers: ollama, watsonx
```

---

#### is_provider_available

```python
@classmethod
def is_provider_available(
    cls,
    provider_name: str
) -> bool
```

Check if a provider is registered.

**Parameters:**

- **provider_name** : `str`
  - Provider name to check

**Returns:**

- **available** : `bool`
  - True if provider is registered, False otherwise

**Example:**

```python
if LLMProviderFactory.is_provider_available("watsonx"):
    provider = LLMProviderFactory.create_provider("watsonx")
else:
    print("WatsonX provider not available")
```

---

## Convenience Function

### create_llm_provider

```python
def create_llm_provider(
    provider_name: str
) -> LLMProvider
```

Convenience function to create an LLM provider.

**Parameters:**

- **provider_name** : `str`
  - Name of the provider

**Returns:**

- **provider** : `LLMProvider`
  - Provider instance

**Example:**

```python
from llm.provider_factory import create_llm_provider

# Quick provider creation
provider = create_llm_provider("ollama")
llm = provider.create_chat_model(settings)
```

---

## WatsonXProvider

IBM WatsonX.ai LLM provider for enterprise-grade foundation models.

### Class Definition

```python
from llm.providers.watsonx_provider import WatsonXProvider

class WatsonXProvider(LLMProvider):
    """
    IBM WatsonX.ai provider implementation.
    
    Supports various IBM foundation models including:
    - IBM Granite (chat, code, instruct)
    - Meta Llama 2/3 (7B-70B)
    - Mistral/Mixtral
    - Other WatsonX foundation models
    """
```

### Configuration

**Required Environment Variables:**

```bash
# .env file
WATSONX_API_KEY=your_api_key_here
WATSONX_PROJECT_ID=your_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=meta-llama/llama-3-70b-instruct
```

**Configuration in Settings:**

```python
from config import Settings

settings = Settings()
settings.watsonx_api_key = "your_api_key"
settings.watsonx_project_id = "your_project_id"
settings.watsonx_url = "https://us-south.ml.cloud.ibm.com"
settings.watsonx_model_id = "meta-llama/llama-3-70b-instruct"
```

### Methods

#### create_chat_model

```python
def create_chat_model(
    self,
    settings: Settings,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    **kwargs
) -> BaseChatModel
```

Create WatsonX chat model instance.

**Parameters:**

- **settings** : `Settings`
  - Application settings with WatsonX configuration
  
- **temperature** : `float`, default=`0.0`
  - Sampling temperature (0.0-2.0)
  - 0.0 = deterministic, 1.0 = balanced, 2.0 = creative
  
- **max_tokens** : `int`, default=`2048`
  - Maximum tokens in response
  - Range: 1-4096 (model-dependent)
  
- ****kwargs** : Additional model parameters
  - `top_p`: Nucleus sampling (0.0-1.0)
  - `top_k`: Top-k sampling
  - `repetition_penalty`: Penalty for repetition (1.0-2.0)

**Returns:**

- **model** : `BaseChatModel`
  - LangChain chat model ready for use

**Example:**

```python
from llm.providers.watsonx_provider import WatsonXProvider
from config import get_settings

provider = WatsonXProvider()
settings = get_settings()

# Create model with default parameters
model = provider.create_chat_model(settings)

# Create model with custom parameters
model = provider.create_chat_model(
    settings=settings,
    temperature=0.7,
    max_tokens=1024,
    top_p=0.9,
    repetition_penalty=1.1
)

# Use model
response = model.invoke("Explain SPARQL queries")
print(response.content)
```

**Advanced Example - Structured Output:**

```python
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

class ContractSummary(BaseModel):
    parties: list[str] = Field(description="Contract parties")
    value: float = Field(description="Contract value")
    term: str = Field(description="Contract term")

parser = PydanticOutputParser(pydantic_object=ContractSummary)

prompt = f"""
Extract contract information:
{contract_text}

{parser.get_format_instructions()}
"""

response = model.invoke(prompt)
summary = parser.parse(response.content)

print(f"Parties: {summary.parties}")
print(f"Value: ${summary.value:,.2f}")
print(f"Term: {summary.term}")
```

---

#### validate_config

```python
def validate_config(
    self,
    settings: Settings
) -> bool
```

Validate WatsonX configuration.

**Parameters:**

- **settings** : `Settings`
  - Application settings to validate

**Returns:**

- **valid** : `bool`
  - True if configuration is valid

**Raises:**

- **ValueError**
  - If required configuration is missing

**Example:**

```python
provider = WatsonXProvider()

try:
    is_valid = provider.validate_config(settings)
    if is_valid:
        print("✅ WatsonX configuration is valid")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
```

---

### Supported Models

| Model ID | Size | Context | Use Case |
|----------|------|---------|----------|
| ibm/granite-13b-chat-v2 | 13B | 8K | General chat |
| ibm/granite-20b-code-instruct | 20B | 8K | Code generation |
| meta-llama/llama-3-70b-instruct | 70B | 8K | Complex reasoning |
| meta-llama/llama-3-8b-instruct | 8B | 8K | Fast inference |
| mistralai/mixtral-8x7b-instruct-v01 | 8x7B | 32K | Long context |
| mistralai/mistral-large | 176B | 32K | Best quality |

**Model Selection Guide:**

```python
# Fast, cost-effective
settings.watsonx_model_id = "meta-llama/llama-3-8b-instruct"

# Balanced performance
settings.watsonx_model_id = "ibm/granite-13b-chat-v2"

# Best quality, slower
settings.watsonx_model_id = "meta-llama/llama-3-70b-instruct"

# Long context (32K tokens)
settings.watsonx_model_id = "mistralai/mixtral-8x7b-instruct-v01"
```

---

### Performance Characteristics

| Model | Latency | Throughput | Cost/1K tokens |
|-------|---------|------------|----------------|
| Llama-3-8B | 1-2s | 20 req/s | $0.001 |
| Granite-13B | 2-3s | 10 req/s | $0.002 |
| Llama-3-70B | 5-8s | 5 req/s | $0.005 |
| Mixtral-8x7B | 3-5s | 8 req/s | $0.003 |

---

## OllamaProvider

Ollama provider for local LLM inference without API calls.

### Class Definition

```python
from llm.providers.ollama_provider import OllamaProvider

class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.
    
    Supports running models locally without API calls,
    ideal for:
    - Development and testing
    - Privacy-sensitive scenarios
    - Offline operation
    - Cost-free inference
    """
```

### Configuration

**Environment Variables:**

```bash
# .env file
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3:8b
OLLAMA_FALLBACK_MODEL=llama3:8b
```

**Settings:**

```python
settings = Settings()
settings.ollama_base_url = "http://localhost:11434"
settings.ollama_model = "llama3:8b"
settings.ollama_fallback_model = "llama3:8b"
```

### Installation

```bash
# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Install Ollama (Windows)
# Download from https://ollama.com/download

# Pull a model
ollama pull llama3:8b

# List available models
ollama list

# Run Ollama server
ollama serve
```

### Methods

#### create_chat_model

```python
def create_chat_model(
    self,
    settings: Settings,
    temperature: float = 0.0,
    **kwargs
) -> BaseChatModel
```

Create Ollama chat model instance.

**Parameters:**

- **settings** : `Settings`
  - Application settings with Ollama configuration
  
- **temperature** : `float`, default=`0.0`
  - Sampling temperature (0.0-2.0)
  
- ****kwargs** : Additional parameters
  - `num_predict`: Max tokens to generate
  - `top_k`: Top-k sampling
  - `top_p`: Nucleus sampling
  - `repeat_penalty`: Repetition penalty

**Returns:**

- **model** : `BaseChatModel`
  - LangChain chat model

**Example:**

```python
from llm.providers.ollama_provider import OllamaProvider

provider = OllamaProvider()

# Create model
model = provider.create_chat_model(
    settings=settings,
    temperature=0.7,
    num_predict=1024
)

# Use model
response = model.invoke("Explain RDF triples")
print(response.content)
```

**Model Fallback:**

```python
# If configured model not available, uses fallback
settings.ollama_model = "llama3:70b"  # Not pulled
settings.ollama_fallback_model = "llama3:8b"  # Available

# Automatically falls back to llama3:8b
model = provider.create_chat_model(settings)
```

---

### Supported Models

| Model | Size | Context | Speed | Use Case |
|-------|------|---------|-------|----------|
| llama3:8b | 8B | 8K | Fast | General purpose |
| llama3:70b | 70B | 8K | Slow | Best quality |
| mistral:7b | 7B | 8K | Fast | Balanced |
| mixtral:8x7b | 8x7B | 32K | Medium | Long context |
| codellama:7b | 7B | 16K | Fast | Code tasks |
| codellama:34b | 34B | 16K | Medium | Complex code |
| phi3:mini | 3.8B | 4K | Very fast | Simple tasks |

**Model Selection:**

```python
# Fast inference
settings.ollama_model = "llama3:8b"

# Best quality (requires GPU)
settings.ollama_model = "llama3:70b"

# Code generation
settings.ollama_model = "codellama:34b"

# Long context
settings.ollama_model = "mixtral:8x7b"

# Lightweight
settings.ollama_model = "phi3:mini"
```

---

### Performance Characteristics

| Model | Latency (CPU) | Latency (GPU) | Memory |
|-------|--------------|---------------|--------|
| llama3:8b | 5-10s | 1-2s | 8GB |
| llama3:70b | 60-120s | 5-10s | 48GB |
| mistral:7b | 4-8s | 1-2s | 7GB |
| mixtral:8x7b | 15-30s | 3-5s | 32GB |
| codellama:7b | 4-8s | 1-2s | 7GB |
| phi3:mini | 2-4s | 0.5-1s | 4GB |

**Hardware Requirements:**

```python
# Minimum (CPU only)
# - 16GB RAM
# - Models: llama3:8b, mistral:7b, phi3:mini

# Recommended (GPU)
# - NVIDIA GPU with 8GB+ VRAM
# - 32GB RAM
# - Models: llama3:8b, mistral:7b, codellama:7b

# High-end (GPU)
# - NVIDIA GPU with 48GB+ VRAM
# - 64GB RAM
# - Models: llama3:70b, mixtral:8x7b
```

---

## Usage Patterns

### Basic Chat

```python
from llm.provider_factory import create_llm_provider
from config import get_settings

# Setup
settings = get_settings()
provider = create_llm_provider(settings.llm_provider)
model = provider.create_chat_model(settings, temperature=0.7)

# Single query
response = model.invoke("What is a contract?")
print(response.content)
```

### Structured Extraction

```python
from langchain.prompts import ChatPromptTemplate

# Define extraction prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a contract analysis expert. Extract key information."),
    ("human", "Extract parties, value, and term from:\n{contract_text}")
])

# Create chain
chain = prompt | model

# Extract
result = chain.invoke({"contract_text": contract_text})
print(result.content)
```

### Batch Processing

```python
# Process multiple documents
documents = [doc1, doc2, doc3, ...]

results = []
for doc in documents:
    response = model.invoke(f"Summarize: {doc}")
    results.append(response.content)

print(f"Processed {len(results)} documents")
```

### Streaming Responses

```python
# Stream for better UX
prompt = "Explain knowledge graphs in detail"

print("Response: ", end="", flush=True)
for chunk in model.stream(prompt):
    print(chunk.content, end="", flush=True)
print()
```

### With LangChain Chains

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

# Define prompt
template = """
Analyze this contract clause:
{clause_text}

Identify:
1. Clause type
2. Key obligations
3. Potential risks
"""

prompt = PromptTemplate(
    input_variables=["clause_text"],
    template=template
)

# Create chain
chain = LLMChain(llm=model, prompt=prompt)

# Run
result = chain.run(clause_text="Either party may terminate...")
print(result)
```

---

## Integration with Agents

### BaseAgent Integration

```python
from agents.shared.base import BaseAgent

class ClauseAnalyzer(BaseAgent):
    """Agent that analyzes contract clauses."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.llm automatically initialized from settings
    
    def analyze_clause(self, clause_text: str) -> dict:
        """Analyze a clause using LLM."""
        prompt = f"""
        Analyze this clause:
        {clause_text}
        
        Return JSON with: type, obligations, risks
        """
        
        response = self.llm.invoke(prompt)
        return self._parse_response(response.content)
```

### Custom Provider Selection

```python
class CustomAgent(BaseAgent):
    """Agent with custom LLM provider."""
    
    def __init__(self, provider_name: str = "ollama", **kwargs):
        # Override provider
        kwargs['llm_provider'] = provider_name
        super().__init__(**kwargs)
    
    def process(self, text: str) -> str:
        return self.llm.invoke(text).content

# Use with Ollama
agent = CustomAgent(provider_name="ollama")

# Use with WatsonX
agent = CustomAgent(provider_name="watsonx")
```

---

## Best Practices

### 1. Choose Appropriate Temperature

```python
# Deterministic tasks (extraction, classification)
model = provider.create_chat_model(
    settings=settings,
    temperature=0.0  # Consistent output
)

# Balanced tasks (summarization, Q&A)
model = provider.create_chat_model(
    settings=settings,
    temperature=0.3  # Slight variation
)

# Creative tasks (generation, brainstorming)
model = provider.create_chat_model(
    settings=settings,
    temperature=0.7  # More creative
)
```

### 2. Handle Errors Gracefully

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_llm_with_retry(model, prompt):
    try:
        return model.invoke(prompt)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise

# Use with automatic retries
response = call_llm_with_retry(model, prompt)
```

### 3. Optimize Prompts

```python
# ❌ Vague prompt
prompt = "Analyze this"

# ✅ Specific prompt
prompt = """
Analyze this termination clause:
{clause_text}

Extract:
1. Notice period (in days)
2. Termination conditions
3. Penalties or fees

Format as JSON.
"""
```

### 4. Monitor Token Usage

```python
# Track tokens for cost management
total_tokens = 0

for doc in documents:
    response = model.invoke(f"Process: {doc}")
    # Estimate tokens (rough: 1 token ≈ 4 characters)
    tokens = len(doc) // 4 + len(response.content) // 4
    total_tokens += tokens

print(f"Total tokens used: {total_tokens:,}")
print(f"Estimated cost: ${total_tokens * 0.002 / 1000:.4f}")
```

### 5. Use Caching for Repeated Queries

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_llm_call(prompt: str) -> str:
    response = model.invoke(prompt)
    return response.content

# First call - hits LLM
result1 = cached_llm_call("What is RDF?")

# Second call - returns cached result
result2 = cached_llm_call("What is RDF?")  # Instant
```

---

## Troubleshooting

### WatsonX Issues

**Problem:** Authentication failed

**Solutions:**
```python
# 1. Verify API key
print(f"API Key: {settings.watsonx_api_key[:10]}...")

# 2. Check project ID
print(f"Project ID: {settings.watsonx_project_id}")

# 3. Verify URL
print(f"URL: {settings.watsonx_url}")

# 4. Test connection
try:
    provider = WatsonXProvider()
    provider.validate_config(settings)
    print("✅ Configuration valid")
except Exception as e:
    print(f"❌ Error: {e}")
```

**Problem:** Model not found

**Solutions:**
```python
# List available models (via WatsonX UI or API)
# Use exact model ID
settings.watsonx_model_id = "meta-llama/llama-3-70b-instruct"
```

### Ollama Issues

**Problem:** Connection refused

**Solutions:**
```bash
# 1. Check if Ollama is running
ps aux | grep ollama

# 2. Start Ollama
ollama serve

# 3. Verify endpoint
curl http://localhost:11434/api/tags

# 4. Check firewall
sudo ufw allow 11434
```

**Problem:** Model not found

**Solutions:**
```bash
# 1. List available models
ollama list

# 2. Pull missing model
ollama pull llama3:8b

# 3. Verify model name
ollama show llama3:8b
```

**Problem:** Out of memory

**Solutions:**
```python
# 1. Use smaller model
settings.ollama_model = "llama3:8b"  # Instead of llama3:70b

# 2. Reduce context
model = provider.create_chat_model(
    settings=settings,
    num_predict=512  # Reduce max tokens
)

# 3. Close other applications
# 4. Use GPU if available
```

---

## Performance Optimization

### Batch Processing

```python
# Process multiple prompts efficiently
prompts = [
    "Summarize clause 1",
    "Summarize clause 2",
    "Summarize clause 3"
]

# Sequential (slow)
results = [model.invoke(p).content for p in prompts]

# Parallel (faster)
from concurrent.futures import ThreadPoolExecutor

def process_prompt(prompt):
    return model.invoke(prompt).content

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(process_prompt, prompts))
```

### Prompt Optimization

```python
# ❌ Long prompt (more tokens, slower)
prompt = f"""
Here is a very long introduction about contracts...
{long_intro}

Now analyze this clause:
{clause_text}
"""

# ✅ Concise prompt (fewer tokens, faster)
prompt = f"Analyze clause: {clause_text}"
```

### Model Selection

```python
# Use appropriate model for task complexity

# Simple tasks (classification, extraction)
settings.ollama_model = "llama3:8b"  # Fast

# Complex tasks (reasoning, generation)
settings.ollama_model = "llama3:70b"  # Slow but better
```

---

## Complete Example

```python
from llm.provider_factory import create_llm_provider
from config import get_settings
import structlog

logger = structlog.get_logger(__name__)

# Initialize
settings = get_settings()
logger.info("llm_provider", provider=settings.llm_provider)

# Create provider
provider = create_llm_provider(settings.llm_provider)

# Validate configuration
try:
    provider.validate_config(settings)
    logger.info("llm_config_valid")
except ValueError as e:
    logger.error("llm_config_invalid", error=str(e))
    raise

# Create model
model = provider.create_chat_model(
    settings=settings,
    temperature=0.3,
    max_tokens=1024
)

# Process contract clauses
clauses = [
    "Either party may terminate with 30 days notice.",
    "Payment due within 30 days of invoice.",
    "All information shall remain confidential."
]

results = []
for i, clause in enumerate(clauses, 1):
    logger.info("processing_clause", clause_num=i)
    
    prompt = f"""
    Analyze this contract clause:
    {clause}
    
    Extract:
    1. Clause type
    2. Key terms
    3. Obligations
    
    Format as JSON.
    """
    
    try:
        response = model.invoke(prompt)
        results.append({
            "clause": clause,
            "analysis": response.content
        })
        logger.info("clause_processed", clause_num=i)
    except Exception as e:
        logger.error("clause_processing_failed", clause_num=i, error=str(e))
        results.append({
            "clause": clause,
            "analysis": None,
            "error": str(e)
        })

# Summary
successful = sum(1 for r in results if r.get("analysis"))
logger.info("processing_complete", 
           total=len(clauses),
           successful=successful,
           failed=len(clauses) - successful)

# Display results
for i, result in enumerate(results, 1):
    print(f"\n=== Clause {i} ===")
    print(f"Text: {result['clause']}")
    if result.get("analysis"):
        print(f"Analysis: {result['analysis'][:200]}...")
    else:
        print(f"Error: {result.get('error')}")
```

**Output:**
```
llm_provider provider='ollama'
llm_config_valid
processing_clause clause_num=1
clause_processed clause_num=1
processing_clause clause_num=2
clause_processed clause_num=2
processing_clause clause_num=3
clause_processed clause_num=3
processing_complete total=3 successful=3 failed=0

=== Clause 1 ===
Text: Either party may terminate with 30 days notice.
Analysis: {"clause_type": "Termination", "key_terms": ["30 days notice"], "obligations": ["Provide written notice 30 days before termination"]}...

=== Clause 2 ===
Text: Payment due within 30 days of invoice.
Analysis: {"clause_type": "Payment", "key_terms": ["30 days", "invoice"], "obligations": ["Pay within 30 days of receiving invoice"]}...

=== Clause 3 ===
Text: All information shall remain confidential.
Analysis: {"clause_type": "Confidentiality", "key_terms": ["confidential"], "obligations": ["Maintain confidentiality of all information"]}...
```

---

## See Also

- **[Ingestion Agents](../agents/ingestion_comprehensive.md)** - Document ingestion pipeline
- **[Retrieval Agents](../agents/retrieval_comprehensive.md)** - Query orchestration
- **[Configuration](../core/config.md)** - Settings and environment variables
- **[BaseAgent](../agents/shared/base.md)** - Agent foundation class