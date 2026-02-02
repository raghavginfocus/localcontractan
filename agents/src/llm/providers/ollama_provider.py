"""
Ollama LLM Provider

Provider implementation for local Ollama LLM service.
"""

from typing import Any, Dict

import httpx

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from config import Settings
from llm.providers.base import LLMProvider
from logger import get_module_logger

logger = get_module_logger(__name__)


class OllamaProvider(LLMProvider):
    """Provider for Ollama local LLM service."""

    @property
    def name(self) -> str:
        return "ollama"

    def create_chat_model(self, settings: Settings, **kwargs) -> BaseChatModel:
        """
        Create ChatOllama instance.

        Args:
            settings: Application settings
            **kwargs: Additional parameters (temperature, etc.)
        """
        resolved_model = self._resolve_model_name(
            base_url=settings.ollama_base_url,
            preferred_model=settings.ollama_model,
            fallback_model=settings.ollama_fallback_model,
        )

        logger.info(
            "Using Ollama chat model",
            base_url=settings.ollama_base_url,
            model=resolved_model,
            requested_model=settings.ollama_model,
        )

        return ChatOllama(
            model=resolved_model,
            base_url=settings.ollama_base_url,
            temperature=kwargs.get("temperature", 0.1),
        )

    def validate_config(self, settings: Settings) -> bool:
        """
        Validate Ollama configuration.

        Ollama doesn't require API keys, but we check:
        - base_url is set
        - model name is set
        """
        return bool(settings.ollama_base_url and settings.ollama_model)

    def _resolve_model_name(
        self,
        base_url: str,
        preferred_model: str,
        fallback_model: str,
    ) -> str:
        """
        Resolve a usable model name against the configured Ollama server.

        If we can reach Ollama and the preferred model isn't installed, fall back
        to `fallback_model` (if installed) or the first available model.

        This prevents hard failures like:
        "model 'X' not found (status code: 404)".
        """
        available = self._get_available_models(base_url)
        if not available:
            # Can't reach Ollama or no models reported: keep preferred_model.
            return preferred_model

        if preferred_model in available:
            return preferred_model

        if fallback_model in available:
            logger.warning(
                "Preferred Ollama model not available; falling back",
                base_url=base_url,
                preferred_model=preferred_model,
                fallback_model=fallback_model,
                available_models=available[:20],
            )
            return fallback_model

        logger.warning(
            (
                "Preferred/fallback Ollama models not available; "
                "using first available"
            ),
            base_url=base_url,
            preferred_model=preferred_model,
            fallback_model=fallback_model,
            chosen_model=available[0],
            available_models=available[:20],
        )
        return available[0]

    def _get_available_models(self, base_url: str) -> list[str]:
        """Best-effort query to Ollama `/api/tags` to list installed models."""
        url = base_url.rstrip("/") + "/api/tags"
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.warning(
                "Unable to query Ollama for available models",
                base_url=base_url,
                error=str(e),
            )
            return []

        models = data.get("models", [])
        names: list[str] = []
        for m in models:
            name = m.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Ollama provider capabilities."""
        return {
            "supports_streaming": True,
            "supports_function_calling": False,  # Ollama models vary
            "max_tokens": None,  # Model-dependent
            "supported_models": [
                "llama3:8b",
                "llama3:70b",
                "qwen2.5-coder:14b",
                "codellama:7b",
                "mistral",
                "neural-chat",
            ],
        }

    def get_health_check_url(self) -> str | None:
        """Return Ollama health check URL."""
        # Ollama health can be checked via base_url
        return None  # We'll check connectivity differently
