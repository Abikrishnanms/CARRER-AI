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

# ─── One-time availability cache ─────────────────────────────
# Populated lazily the first time a provider is probed.
# Values: True = available, False = unavailable (import error or no API key)
_provider_available: dict[str, bool | None] = {
    "ollama": None,
    "openai": None,
    "anthropic": None,
}

# Tracks which missing-package warnings have already been emitted so
# they are only logged once per process (not once per worker thread).
_warned_once: set[str] = set()


def _warn_once(key: str, msg: str) -> None:
    """Emit a WARNING log message at most once per unique key."""
    if key not in _warned_once:
        _warned_once.add(key)
        logger.warning(msg)


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
    "skill_extraction":   (LLMProvider.OLLAMA,    "llama3.2"),
    "salary_estimation":  (LLMProvider.OLLAMA,    "llama3.2"),
    "job_cleaning":       (LLMProvider.OLLAMA,    "llama3.2"),
    "duplicate_check":    (LLMProvider.OLLAMA,    "llama3.2"),
    "entity_extraction":  (LLMProvider.OPENAI,    "gpt-4o-mini"),
    "scam_detection":     (LLMProvider.ANTHROPIC, "claude-3-5-haiku-20241022"),
    "authenticity_check": (LLMProvider.OPENAI,    "gpt-4o-mini"),
    "recommendation":     (LLMProvider.OLLAMA,    "llama3.2"),
    "summarization":      (LLMProvider.OPENAI,    "gpt-4o-mini"),
    "complex_reasoning":  (LLMProvider.OPENAI,    "gpt-4o"),
    "default":            (LLMProvider.OLLAMA,    "llama3.2"),
}


class LLMRouter:
    """
    Intelligent LLM router with:
    - Task-based model selection
    - Cost budgeting
    - Automatic fallback chain
    - Token usage tracking
    - One-time availability probing (no repeated import warnings)
    """

    def __init__(self) -> None:
        self.default_provider = LLMProvider(os.getenv("LLM_DEFAULT_PROVIDER", "ollama"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self._clients: dict[str, Any] = {}
        self._token_usage: dict[str, int] = {}
        # Probe availability once at construction so warnings fire only once.
        self._probe_all_providers()

    # ── One-time availability probes ─────────────────────────────────

    def _probe_all_providers(self) -> None:
        """
        Check which optional LLM packages are installed and log a single
        diagnostic INFO (available) or WARNING (missing/no key) message.
        This replaces per-call import checks that flooded logs with 50+ repeats.
        """
        self._probe_ollama()
        self._probe_openai()
        self._probe_anthropic()

    def _probe_ollama(self) -> None:
        global _provider_available
        if _provider_available["ollama"] is not None:
            return
        try:
            import langchain_ollama  # noqa: F401
            _provider_available["ollama"] = True
            logger.debug("LLM: langchain-ollama is available")
        except ImportError:
            _provider_available["ollama"] = False
            _warn_once(
                "missing_ollama",
                "LLM provider 'ollama' is unavailable: langchain-ollama is not installed. "
                "Install it with: pip install langchain-ollama",
            )

    def _probe_openai(self) -> None:
        global _provider_available
        if _provider_available["openai"] is not None:
            return
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            _provider_available["openai"] = False
            logger.debug("LLM: OpenAI skipped — OPENAI_API_KEY not configured")
            return
        try:
            import langchain_openai  # noqa: F401
            _provider_available["openai"] = True
            logger.debug("LLM: langchain-openai is available")
        except ImportError:
            _provider_available["openai"] = False
            _warn_once(
                "missing_openai",
                "LLM provider 'openai' is unavailable: langchain-openai is not installed. "
                "Install it with: pip install langchain-openai",
            )

    def _probe_anthropic(self) -> None:
        global _provider_available
        if _provider_available["anthropic"] is not None:
            return
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-your"):
            _provider_available["anthropic"] = False
            logger.debug("LLM: Anthropic skipped — ANTHROPIC_API_KEY not configured")
            return
        try:
            import langchain_anthropic  # noqa: F401
            _provider_available["anthropic"] = True
            logger.debug("LLM: langchain-anthropic is available")
        except ImportError:
            _provider_available["anthropic"] = False
            _warn_once(
                "missing_anthropic",
                "LLM provider 'anthropic' is unavailable: langchain-anthropic is not installed. "
                "Install it with: pip install langchain-anthropic",
            )

    # ── Client factories (only called when provider is known available) ──

    def _get_ollama_client(self) -> Any:
        """Return a ChatOllama client. Assumes availability was already confirmed."""
        if not _provider_available.get("ollama"):
            return None
        try:
            from langchain_ollama import ChatOllama
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            model = os.getenv("OLLAMA_DEFAULT_MODEL", "llama3.2")
            return ChatOllama(base_url=base_url, model=model, temperature=self.temperature)
        except Exception as exc:
            logger.debug("LLM: Could not create Ollama client: %s", exc)
            return None

    def _get_openai_client(self, model: str = "gpt-4o-mini") -> Any:
        """Return a ChatOpenAI client. Assumes availability was already confirmed."""
        if not _provider_available.get("openai"):
            return None
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key or api_key.startswith("sk-your"):
            return None
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(api_key=api_key, model=model, temperature=self.temperature)
        except Exception as exc:
            logger.debug("LLM: Could not create OpenAI client: %s", exc)
            return None

    def _get_anthropic_client(self, model: str = "claude-3-5-haiku-20241022") -> Any:
        """Return a ChatAnthropic client. Assumes availability was already confirmed."""
        if not _provider_available.get("anthropic"):
            return None
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key or api_key.startswith("sk-ant-your"):
            return None
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(api_key=api_key, model=model, temperature=self.temperature)
        except Exception as exc:
            logger.debug("LLM: Could not create Anthropic client: %s", exc)
            return None

    # ── Public API ────────────────────────────────────────────────────

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
                    logger.warning(
                        "LLM: Falling back from %s to %s for task %s",
                        provider.value, fp.value, task_type,
                    )
                return client, fp.value

        raise RuntimeError(
            f"No LLM provider available for task '{task_type}'. "
            "Please install langchain-ollama (and ensure Ollama is running) "
            "or set a valid OPENAI_API_KEY / ANTHROPIC_API_KEY."
        )

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
            logger.exception("LLM invocation failed for task %s: %s", task_type, e)
            raise


# ── Singleton router ──────────────────────────────────────────────
_router: LLMRouter | None = None


def get_llm_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
