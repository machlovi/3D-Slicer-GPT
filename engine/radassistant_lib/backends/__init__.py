"""Backend factory. build_backend(config) -> Backend.

config keys:
  provider : "ollama" | "openai" | "anthropic"
  model    : model name/id
  host     : Ollama base URL (ollama)
  base_url : OpenAI-compatible base URL ending in /v1 (openai)
  api_key  : key for anthropic / an authenticated OpenAI-compatible server
  effort   : anthropic reasoning effort
  vision   : override vision capability (bool); None = auto-detect
  num_ctx  : ollama context length
"""

import re

from .base import Backend, Capabilities, TurnResult  # noqa: F401

# Models known to handle long multi-step agent chains well despite a modest or
# MoE parameter count (from mAIstro's Table 1 and general reputation).
_STRONG_NAMES = ("llama3.3", "llama-3.3", "llama4", "llama-4", "gpt-oss:120b",
                 "deepseek-v3", "deepseek-r1", "command-r-plus", "mixtral-8x22b",
                 "qwq", "gpt-4", "gpt-5", "o1", "o3")


def capability_warning(provider, model):
    """Empirical guardrail: small local models reliably do only single tool calls.

    mAIstro benchmarked 12 LLMs — frontier/≥70B ≈100% task success, but 24B≈36%,
    14B≈55%, 8B≈18%, 7B≈10%. A single TotalSegmentator run works even on 7B; long
    'segment → radiomics → report' chains need a strong model. Returns "" or a note.
    """
    m = (model or "").lower()
    if provider == "anthropic" or any(s in m for s in _STRONG_NAMES):
        return ""
    sizes = [int(n) for n in re.findall(r"(\d+)\s*b\b", m)]
    if not sizes:
        return ""  # unknown size — don't nag
    biggest = max(sizes)
    if biggest >= 65:
        return ""
    if biggest >= 27:
        return (f"Note: a ~{biggest}B model does single operations well but may struggle "
                "with long multi-step workflows. For chained playbooks, prefer a 70B+ or "
                "frontier model.")
    return (f"⚠ Small model (~{biggest}B): reliable for single operations (e.g. one "
            "TotalSegmentator run) but multi-step chains often fail. Use a 70B+/frontier "
            "model for those.")


def build_backend(config):
    provider = (config.get("provider") or "ollama").lower()

    if provider == "ollama":
        from .ollama_backend import OllamaBackend
        return OllamaBackend(
            host=config.get("host", "http://localhost:11434"),
            model=config.get("model", "qwen2.5:14b"),
            num_ctx=config.get("num_ctx", 16384),
            vision=config.get("vision"),
        )
    if provider == "openai":
        from .openai_backend import OpenAICompatBackend
        return OpenAICompatBackend(
            base_url=config.get("base_url", "http://localhost:8000/v1"),
            model=config.get("model", ""),
            api_key=config.get("api_key") or None,
            vision=bool(config.get("vision")),
        )
    if provider == "gemini":
        from .openai_backend import GeminiBackend
        return GeminiBackend(
            api_key=config.get("api_key") or None,
            model=config.get("model", "gemini-2.0-flash"),
            vision=bool(config.get("vision")),
        )
    if provider == "anthropic":
        from .anthropic_backend import AnthropicBackend
        return AnthropicBackend(
            api_key=config.get("api_key") or None,
            model=config.get("model", "claude-opus-4-8"),
            effort=config.get("effort", "high"),
        )
    raise ValueError(f"unknown backend provider '{provider}'")
