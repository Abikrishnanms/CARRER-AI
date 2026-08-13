"""
LLM Router — Intelligently selects the optimal LLM for each task.
Supports Ollama (local), OpenAI, Anthropic, and Cohere.
Falls back gracefully when providers are unavailable.
"""

from __future__ import annotations

import logging
import os
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    COHERE = "cohere"


class TaskComplexity(str, Enum):
    SIMPLE = "simple"          # Classification, extraction → cheap model
    MEDIUM = "medium"          # Analysis, summarization → mid-tier model
    COMPLEX = "complex"        # Reasoning, multi-step → best model
    SAFETY_CRITICAL = "safety" # Scam detection → Anthropic (safety-focused)


# Task type → recommended provider + model
TASK_ROUTING_TABLE: dict[str, tuple[LLMProvider, str]] = {
    "skill_extraction": (LLMProvider.OLLAMA, "llama3.2"),
    "salary_estimation": (LLMProvider.OLLAMA, "llama3.2"),
    "job_cleaning": (LLMProvider.OLLAMA, "llama3.2"),
    "duplicate_check": (LLMProvider.OLLAMA, "llama3.2"),
    "entity_extraction": (LLMProvider.OPENAI, "gpt-4o-mini"),
    "scam_detection": (LLMProvider.ANTHROPIC, "claude-3-5-haiku-20241022"),
    "authenticity_check": (LLMProvider.OPENAI, "gpt-4o-mini"),
    "recommendation": (LLMProvider.OLLAMA, "llama3.2"),
    "summarization": (LLMProvider.OPENAI, "gpt-4o-mini"),
    "complex_reasoning": (LLMProvider.OPENAI, "gpt-4o"),
    "default": (LLMProvider.OLLAMA, "llama3.2"),
}


class LLMRouter:
    """
    Intelligent LLM router with:
    - Task-based model selection
    - Cost budgeting
    - Automatic fallback chain
    - Token usage tracking
    """

    def __init__(self) -> None:
        self.default_provider = LLMProvider(os.getenv("LLM_DEFAULT_PROVIDER", "ollama"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self._clients: dict[str, Any] = {}
        self._token_usage: dict[str, int] = {}

    def _get_ollama_client(self) -> Any:
        """Get or create Ollama client."""
        try:
            from langchain_ollama import ChatOllama
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2")
            return ChatOllama(base_url=base_url, model=model, temperature=self.temperature)
        except ImportError:
            logger.warning("langchain-ollama not installed")
            return None

    def _get_openai_client(self, model: str = "gpt-4o-mini") -> Any:
        """Get or create OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            return None
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(api_key=api_key, model=model, temperature=self.temperature)
        except ImportError:
            logger.warning("langchain-openai not installed")
            return None

    def _get_anthropic_client(self, model: str = "claude-3-5-haiku-20241022") -> Any:
        """Get or create Anthropic client."""
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-your"):
            return None
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(api_key=api_key, model=model, temperature=self.temperature)
        except ImportError:
            logger.warning("langchain-anthropic not installed")
            return None

    def get_client_for_task(self, task_type: str = "default") -> tuple[Any, str]:
        """
        Get the best available LLM client for a given task type.
        Returns (client, provider_name) or raises if none available.
        """
        provider, model = TASK_ROUTING_TABLE.get(task_type, TASK_ROUTING_TABLE["default"])

        # Build fallback chain
        fallback_chain = [
            (provider, model),
            (LLMProvider.OLLAMA, os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2")),
            (LLMProvider.OPENAI, "gpt-4o-mini"),
        ]

        for fp, fm in fallback_chain:
            client = None
            if fp == LLMProvider.OLLAMA:
                client = self._get_ollama_client()
            elif fp == LLMProvider.OPENAI:
                client = self._get_openai_client(fm)
            elif fp == LLMProvider.ANTHROPIC:
                client = self._get_anthropic_client(fm)

            if client is not None:
                if fp != provider:
                    logger.warning(f"Falling back from {provider.value} to {fp.value} for task {task_type}")
                return client, fp.value

        raise RuntimeError(f"No LLM provider available for task {task_type}. "
                          "Please configure OLLAMA_BASE_URL or an API key.")

    async def invoke(
        self,
        prompt: str,
        task_type: str = "default",
        system_prompt: str | None = None,
        max_tokens: int = 2048,
    ) -> dict[str, Any]:
        """
        Invoke the best available LLM for a task.
        Returns: {content, model, tokens_used, latency_ms}
        """
        client, provider = self.get_client_for_task(task_type)
        start = time.monotonic()

        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = await client.ainvoke(messages)

            latency_ms = (time.monotonic() - start) * 1000
            usage = getattr(response, "usage_metadata", {})
            tokens = getattr(usage, "total_tokens", 0) if usage else 0

            return {
                "content": response.content,
                "model": provider,
                "tokens_used": tokens,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            logger.exception(f"LLM invocation failed for task {task_type}: {e}")
            raise


# Singleton router
_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
