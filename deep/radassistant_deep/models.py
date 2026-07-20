"""Backend-agnostic chat-model factory.

RadAssistant is backend-agnostic (Ollama for HPC/local, OpenAI-compatible
endpoints, Anthropic). This module keeps that property for the deep-agent
re-implementation: everything downstream receives a LangChain ``BaseChatModel``
and never cares which provider produced it.

Model selection precedence:
    1. explicit ``spec`` argument            e.g. "ollama:qwen3:14b"
    2. ``RADASSISTANT_MODEL`` env var        same syntax
    3. provider default (see DEFAULTS)

Spec syntax is ``provider:model_name`` where model_name may itself contain
colons (Ollama tags). A bare spec with no known provider prefix is treated as
an Ollama model name, which matches how RadAssistant treats bare names.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models import BaseChatModel

PROVIDERS = ("ollama", "openai", "anthropic", "fake")

# Per-provider default model. The Anthropic default follows current Anthropic
# guidance (Opus 4.8 unless the user asks for something else).
DEFAULTS = {
    "ollama": "qwen3:14b",
    "openai": "gpt-5.2",
    "anthropic": "claude-opus-4-8",
}

ENV_MODEL = "RADASSISTANT_MODEL"
ENV_OLLAMA_HOST = "OLLAMA_HOST"


def parse_model_spec(spec: str) -> tuple[str, str]:
    """Split ``provider:model`` into its parts.

    Ollama tags contain colons ("qwen3:14b"), so only the first segment is
    considered a provider, and only when it is a known provider name.
    """
    head, sep, tail = spec.partition(":")
    if sep and head.lower() in PROVIDERS:
        provider = head.lower()
        model = tail or DEFAULTS.get(provider, "")
        return provider, model
    return "ollama", spec


def create_model(spec: str | None = None, /, **kwargs: Any) -> BaseChatModel:
    """Create a chat model for any supported backend.

    kwargs are forwarded to the provider class (temperature, base_url, ...).
    """
    spec = spec or os.environ.get(ENV_MODEL) or f"ollama:{DEFAULTS['ollama']}"
    provider, model = parse_model_spec(spec)

    # Convenience: a bare model name (no explicit provider) plus an
    # OpenAI-style Server URL (ending in /v1) almost always means an
    # OpenAI-compatible server (llama.cpp / vLLM), not Ollama. Route it there
    # so users don't have to remember the "openai:" prefix. An explicit
    # "ollama:..." spec is respected as-is.
    _explicit = spec.partition(":")[0].lower() in PROVIDERS
    _base = kwargs.get("base_url") or os.environ.get("OPENAI_BASE_URL")
    if provider == "ollama" and not _explicit and _base and _base.rstrip("/").endswith("/v1"):
        provider = "openai"

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        host = kwargs.pop("base_url", None) or os.environ.get(ENV_OLLAMA_HOST)
        if host:
            kwargs["base_url"] = host
        return ChatOllama(model=model, **kwargs)

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        # OPENAI_BASE_URL / OPENAI_API_KEY env vars are honoured by the class
        # itself, which is how RadAssistant points this at vLLM/llama.cpp
        # OpenAI-compatible servers on the HPC. A base_url passed explicitly
        # (the Server URL field) wins over the env var.
        base_url = kwargs.pop("base_url", None) or os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        # Local HPC servers (llama.cpp/vLLM) usually ignore the key but the
        # client still requires *some* value — supply a placeholder if none.
        if not kwargs.get("api_key") and not os.environ.get("OPENAI_API_KEY"):
            kwargs["api_key"] = "sk-no-auth"
        return ChatOpenAI(model=model, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, **kwargs)

    if provider == "fake":
        # Deterministic scripted model for tests and offline demos.
        from .testing import ScriptedChatModel, load_script

        return ScriptedChatModel(script=load_script(model), **kwargs)

    raise ValueError(f"Unknown provider {provider!r}. Expected one of {PROVIDERS}.")
