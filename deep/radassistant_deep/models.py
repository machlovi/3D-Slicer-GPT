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

PROVIDERS = ("ollama", "openai", "anthropic", "gemini", "fake")

# Per-provider default model.
DEFAULTS = {
    "ollama": "qwen2.5:14b",
    "openai": "gpt-4o",
    "anthropic": "claude-3-7-sonnet-20250219",
    "gemini": "gemini-2.0-flash",
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

        class SanitizedChatOpenAI(ChatOpenAI):
            """ChatOpenAI wrapper that flattens list-based system message content blocks into a single string.

            This ensures OpenAI-compatible proxies (such as NYU GPT, LiteLLM, vLLM) that do not support
            Anthropic-style array system messages receive valid plain text system messages.
            """

            def _sanitize_messages(self, messages: list[Any]) -> None:
                from langchain_core.messages import SystemMessage
                for msg in messages:
                    if isinstance(msg, SystemMessage) and isinstance(msg.content, list):
                        text_blocks = []
                        for b in msg.content:
                            if isinstance(b, dict) and b.get("type") == "text":
                                text_blocks.append(b.get("text", ""))
                            elif isinstance(b, str):
                                text_blocks.append(b)
                        msg.content = "\n\n".join(text_blocks)

            def _generate(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> Any:
                self._sanitize_messages(messages)
                return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

            async def _agenerate(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> Any:
                self._sanitize_messages(messages)
                return await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)

            def _stream(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> Any:
                self._sanitize_messages(messages)
                return super()._stream(messages, stop=stop, run_manager=run_manager, **kwargs)

            async def _astream(self, messages: list[Any], stop: list[str] | None = None, run_manager: Any = None, **kwargs: Any) -> Any:
                self._sanitize_messages(messages)
                return await super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs)

        base_url = kwargs.pop("base_url", None) or os.environ.get("OPENAI_BASE_URL")
        if base_url:
            base_url = base_url.rstrip("/")
            if base_url.endswith("/chat/completions"):
                base_url = base_url[:-len("/chat/completions")]
            kwargs["base_url"] = base_url
        if not kwargs.get("api_key"):
            env_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("UV_API_KEY")
            if env_key:
                kwargs["api_key"] = env_key
            elif base_url and not ("api.openai.com" in base_url):
                kwargs["api_key"] = "sk-no-auth"
        kwargs.setdefault("stream_usage", False)
        if kwargs.get("disable_streaming"):
            kwargs["streaming"] = False
            kwargs["disable_streaming"] = True
        return SanitizedChatOpenAI(model=model, **kwargs)

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not kwargs.get("api_key") and os.environ.get("ANTHROPIC_API_KEY"):
            kwargs["api_key"] = os.environ.get("ANTHROPIC_API_KEY")
        return ChatAnthropic(model=model, **kwargs)

    if provider == "gemini":
        from langchain_openai import ChatOpenAI

        base_url = kwargs.pop("base_url", None) or "https://generativelanguage.googleapis.com/v1beta/openai/"
        kwargs["base_url"] = base_url
        if not kwargs.get("api_key"):
            kwargs["api_key"] = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        return SanitizedChatOpenAI(model=model, **kwargs)

    if provider == "fake":
        # Deterministic scripted model for tests and offline demos.
        from .testing import ScriptedChatModel, load_script

        return ScriptedChatModel(script=load_script(model), **kwargs)

    raise ValueError(f"Unknown provider {provider!r}. Expected one of {PROVIDERS}.")
