# LLM Providers API Reference

API documentation for LLM provider abstraction layer.

## LLMProvider (Base Class)

Abstract base class for LLM providers.

### Class Definition

```python
from llm.providers.base import LLMProvider

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Provides a unified interface for different LLM providers
    (WatsonX, Ollama, OpenAI, etc.) allowing easy switching
    without code changes.
    """
```

### Abstract Methods

#### create_chat_model

```python
@abstractmethod
def create_chat_model(
    self,
    settings: Settings,
    temperature: float = 0.0,
    **kwargs
) -> BaseChatModel
```

Create a chat model instance.

**Parameters:**

- `settings` (Settings): Application settings
- `temperature` (float): Model temperature
- `**kwargs`: Provider-specific parameters

**Returns:**

- `BaseChatModel`: LangChain chat model

#### validate_config

```python
@abstractmethod
def validate_config(
    self,
    settings: Settings
) -> bool
```

Validate provider configuration.

**Parameters:**

- `settings` (Settings): Application settings

**Returns:**

- `bool`: True if configuration is valid

## WatsonXProvider

IBM WatsonX.ai LLM provider.

### Class Definition

```python
from llm.providers.watsonx_provider import WatsonXProvider

class WatsonXProvider(LLMProvider):
    """
    IBM WatsonX.ai provider implementation.
    
    Supports various IBM foundation models including
    Granite, Llama, and Mistral.
    """
```

### Configuration

```python
# In .env or settings
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL=ibm/granite-13b-chat-v2
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

Create WatsonX chat model.

**Example:**

```python
from llm.providers.watsonx_provider import WatsonXProvider
from config import get_settings

provider = WatsonXProvider()
settings = get_settings()

model = provider.create_chat_model(
    settings=settings,
    temperature=0.7,
    max_tokens=2048
)

# Use model
response = model.invoke("What is a contract?")
print(response.content)
```

### Supported Models

| Model | Size | Use Case |
|-------|------|----------|
| ibm/granite-13b-chat-v2 | 13B | General chat |
| ibm/granite-20b-code | 20B | Code generation |
| meta-llama/llama-2-70b-chat | 70B | Complex reasoning |
| mistralai/mixtral-8x7b-instruct | 8x7B | Instruction following |

## OllamaProvider

Ollama local LLM provider.

### Class Definition

```python
from llm.providers.ollama_provider import OllamaProvider

class OllamaProvider(LLMProvider):
    """
    Ollama provider for local LLM inference.
    
    Supports running models locally without API calls,
    ideal for development and privacy-sensitive scenarios.
    """
```

### Configuration

```python
# In .env or settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2
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

Create Ollama chat model.

**Example:**

```python
from llm.providers.ollama_provider import OllamaProvider

provider = OllamaProvider()

model = provider.create_chat_model(
    settings=settings,
    temperature=0.7
)

response = model.invoke("Explain SPARQL")
print(response.content)
```

### Supported Models

| Model | Size | Use Case |
|-------|------|----------|
| llama2 | 7B-70B | General purpose |
| mistral | 7B | Fast inference |
| codellama | 7B-34B | Code tasks |
| mixtral | 8x7B | Complex reasoning |

### Installation

```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull model
ollama pull llama2

# Run Ollama server
ollama serve
```

## LLMProviderFactory

Factory for creating LLM provider instances.

### Class Definition

```python
from llm.provider_factory import LLMProviderFactory

class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
```

### Methods

#### create_provider

```python
@staticmethod
def create_provider(
    provider_name: str
) -> LLMProvider
```

Create provider instance.

**Parameters:**

- `provider_name` (str): Provider name ("watsonx", "ollama")

**Returns:**

- `LLMProvider`: Provider instance

**Example:**

```python
# Create WatsonX provider
provider = LLMProviderFactory.create_provider("watsonx")

# Create chat model
model = provider.create_chat_model(settings)

# Use model
response = model.invoke("What is RDF?")
```

#### get_available_providers

```python
@staticmethod
def get_available_providers() -> list[str]
```

Get list of available providers.

**Returns:**

- `list[str]`: Provider names

**Example:**

```python
providers = LLMProviderFactory.get_available_providers()
print(f"Available providers: {providers}")
# Output: ['watsonx', 'ollama']
```

## Batch Processing

Efficient batch LLM calls for high throughput.

### BatchHelper

```python
from llm.batch_helper import BatchHelper

class BatchHelper:
    """Helper for batch LLM processing."""
```

### Methods

#### batch_invoke

```python
def batch_invoke(
    self,
    model: BaseChatModel,
    prompts: list[str],
    batch_size: int = 10
) -> list[str]
```

Process prompts in batches.

**Parameters:**

- `model` (BaseChatModel): LLM model
- `prompts` (list): List of prompts
- `batch_size` (int): Prompts per batch

**Returns:**

- `list[str]`: Responses

**Example:**

```python
helper = BatchHelper()

prompts = [
    "Summarize this clause: ...",
    "Extract entities from: ...",
    "Classify this text: ..."
]

responses = helper.batch_invoke(
    model=model,
    prompts=prompts,
    batch_size=10
)

for prompt, response in zip(prompts, responses):
    print(f"Prompt: {prompt[:50]}...")
    print(f"Response: {response[:100]}...")
```

## Streaming

Real-time response streaming for better UX.

### StreamingHelper

```python
from llm.streaming_helper import StreamingHelper

class StreamingHelper:
    """Helper for streaming LLM responses."""
```

### Methods

#### stream_response

```python
def stream_response(
    self,
    model: BaseChatModel,
    prompt: str
) -> Iterator[str]
```

Stream model response.

**Parameters:**

- `model` (BaseChatModel): LLM model
- `prompt` (str): Input prompt

**Yields:**

- `str`: Response chunks

**Example:**

```python
helper = StreamingHelper()

for chunk in helper.stream_response(model, "Explain contracts"):
    print(chunk, end="", flush=True)
```

## Configuration

### Settings

```python
from config import Settings

class Settings(BaseSettings):
    # LLM Provider
    llm_provider: str = "watsonx"  # or "ollama"
    
    # WatsonX
    watsonx_api_key: str
    watsonx_project_id: str
    watsonx_url: str
    watsonx_model: str = "ibm/granite-13b-chat-v2"
    
    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"
    
    # Model parameters
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2048
```

### Environment Variables

```bash
# .env file
LLM_PROVIDER=watsonx

# WatsonX
WATSONX_API_KEY=your_api_key
WATSONX_PROJECT_ID=your_project_id
WATSONX_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL=ibm/granite-13b-chat-v2

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Model parameters
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2048
```

## Usage Examples

### Basic Usage

```python
from llm.provider_factory import LLMProviderFactory
from config import get_settings

# Get settings
settings = get_settings()

# Create provider
provider = LLMProviderFactory.create_provider(
    settings.llm_provider
)

# Create model
model = provider.create_chat_model(
    settings=settings,
    temperature=0.7
)

# Use model
response = model.invoke("What is a knowledge graph?")
print(response.content)
```

### With Agents

```python
from agents.shared.base import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # LLM automatically initialized from settings
    
    def process(self, text: str) -> str:
        # Use self.llm
        response = self.llm.invoke(f"Process: {text}")
        return response.content
```

### Switching Providers

```python
# Use WatsonX
settings.llm_provider = "watsonx"
provider = LLMProviderFactory.create_provider("watsonx")
model = provider.create_chat_model(settings)

# Switch to Ollama
settings.llm_provider = "ollama"
provider = LLMProviderFactory.create_provider("ollama")
model = provider.create_chat_model(settings)
```

## Best Practices

### 1. Use Appropriate Temperature

```python
# Deterministic tasks (extraction, classification)
model = provider.create_chat_model(
    settings=settings,
    temperature=0.0
)

# Creative tasks (generation, summarization)
model = provider.create_chat_model(
    settings=settings,
    temperature=0.7
)
```

### 2. Batch When Possible

```python
# ❌ Sequential calls
for prompt in prompts:
    response = model.invoke(prompt)

# ✅ Batch processing
responses = batch_helper.batch_invoke(
    model=model,
    prompts=prompts,
    batch_size=10
)
```

### 3. Handle Errors

```python
try:
    response = model.invoke(prompt)
except Exception as e:
    logger.error(f"LLM call failed: {e}")
    # Fallback logic
    response = default_response
```

### 4. Monitor Token Usage

```python
from langchain.callbacks import get_openai_callback

with get_openai_callback() as cb:
    response = model.invoke(prompt)
    print(f"Tokens used: {cb.total_tokens}")
    print(f"Cost: ${cb.total_cost}")
```

### 5. Use Streaming for Long Responses

```python
# Better UX for long responses
for chunk in streaming_helper.stream_response(model, prompt):
    print(chunk, end="", flush=True)
```

## Performance Considerations

### Latency

| Provider | Model | Latency | Throughput |
|----------|-------|---------|------------|
| WatsonX | Granite-13B | 2-3s | 10 req/s |
| WatsonX | Llama-70B | 5-8s | 5 req/s |
| Ollama | Llama2-7B | 1-2s | 20 req/s |
| Ollama | Mixtral-8x7B | 3-5s | 10 req/s |

### Cost

| Provider | Model | Cost per 1K tokens |
|----------|-------|-------------------|
| WatsonX | Granite-13B | $0.002 |
| WatsonX | Llama-70B | $0.005 |
| Ollama | Any | Free (local) |

## Troubleshooting

### Authentication Errors

**Problem:** WatsonX authentication fails

**Solutions:**
1. Verify API key is correct
2. Check project ID
3. Ensure URL is correct
4. Verify IAM permissions

### Connection Errors

**Problem:** Cannot connect to Ollama

**Solutions:**
1. Check Ollama is running: `ollama serve`
2. Verify base URL
3. Check firewall settings
4. Ensure model is pulled: `ollama pull llama2`

### Slow Responses

**Problem:** LLM calls taking too long

**Solutions:**
1. Use smaller models
2. Reduce max_tokens
3. Enable batch processing
4. Consider caching responses

## See Also

- [Ingestion Agents API](../api/agents/ingestion.md)
- [Retrieval Agents API](../api/agents/retrieval.md)
- [Configuration Guide](../../getting-started/configuration.md)