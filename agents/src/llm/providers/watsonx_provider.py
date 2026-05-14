"""
WatsonX LLM Provider

Provider implementation for IBM watsonx.ai using LangChain.
"""

from typing import Any, Dict

from langchain_core.language_models import BaseChatModel
from langchain_ibm import ChatWatsonx

from config import Settings
from llm.providers.base import LLMProvider


class WatsonXProvider(LLMProvider):
    """Provider for IBM watsonx.ai LLM service."""

    @property
    def name(self) -> str:
        return "watsonx"

    def create_chat_model(
        self,
        settings: Settings,
        **kwargs: Any,
    ) -> BaseChatModel:
        """
        Create a ChatWatsonx instance configured from Settings.

        Required settings (environment variables in parentheses):
        - watsonx_api_key (WATSONX_API_KEY)
        - watsonx_project_id (WATSONX_PROJECT_ID)
        - watsonx_model_id (WATSONX_MODEL_ID)
        - watsonx_url (WATSONX_URL)
        - watsonx_decoding_method (WATSONX_DECODING_METHOD)
        - watsonx_max_new_tokens (WATSONX_MAX_NEW_TOKENS)
        - watsonx_temperature (WATSONX_TEMPERATURE)
        """
        # Allow override from kwargs, otherwise use settings
        # Handle both dict and direct value for temperature
        if isinstance(kwargs.get("temperature"), dict):
            temperature = settings.watsonx_temperature
        else:
            temperature = kwargs.get("temperature", settings.watsonx_temperature)
        
        # Handle max_new_tokens similarly
        if isinstance(kwargs.get("max_new_tokens"), dict):
            max_new_tokens = settings.watsonx_max_new_tokens
        else:
            max_new_tokens = kwargs.get("max_new_tokens", settings.watsonx_max_new_tokens)
        
        # Build parameters dict for WatsonX
        params = {
            "decoding_method": settings.watsonx_decoding_method,
            "max_new_tokens": int(max_new_tokens),
            "temperature": float(temperature),
        }
        
        # Add response format for JSON output (if supported by model)
        # This helps ensure the model returns valid JSON
        model_id_lower = settings.watsonx_model_id.lower()
        if any(model in model_id_lower for model in ["llama-3", "llama-4", "gpt", "openai"]):
            # Llama 3, Llama 4, and OpenAI-based models support response_format
            params["response_format"] = {"type": "json_object"}

        return ChatWatsonx(
            model_id=settings.watsonx_model_id,
            project_id=settings.watsonx_project_id,
            url=settings.watsonx_url,
            apikey=settings.watsonx_api_key,
            params=params,
        )

    def validate_config(self, settings: Settings) -> bool:
        """
        Validate WatsonX configuration.

        We require all core fields to be non-empty.
        """
        return bool(
            settings.watsonx_api_key
            and settings.watsonx_project_id
            and settings.watsonx_model_id
            and settings.watsonx_url
        )

    def get_capabilities(self) -> Dict[str, Any]:
        """Return WatsonX provider capabilities."""
        return {
            "supports_streaming": True,
            "supports_function_calling": True,  # Depends on model
            "max_tokens": 4096,  # Model-dependent
            "supported_models": [
                "meta-llama/llama-3-70b-instruct",
                "meta-llama/llama-3-8b-instruct",
                "ibm/granite-13b-instruct-v2",
                "mistralai/mixtral-8x7b-instruct-v01",
            ],
        }
