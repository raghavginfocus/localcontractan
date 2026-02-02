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
        """
        temperature = kwargs.get("temperature", 0.1)

        return ChatWatsonx(
            model_id=settings.watsonx_model_id,
            project_id=settings.watsonx_project_id,
            url=settings.watsonx_url,
            apikey=settings.watsonx_api_key,
            temperature=temperature,
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
