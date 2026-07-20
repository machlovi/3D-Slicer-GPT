"""Anthropic backend — best-in-class vision + tool use + adaptive thinking.

The neutral IR is already Anthropic's content-block format, so translation is
close to the identity. Used for the demo and whenever a cloud vision model is
acceptable for the data at hand.
"""

from .base import Backend, Capabilities, TurnResult

DEFAULT_MODEL = "claude-opus-4-8"
MAX_TOKENS = 64000


class AnthropicBackend(Backend):
    def __init__(self, api_key=None, model=DEFAULT_MODEL, effort="high"):
        self._api_key = api_key
        self._model = model
        self._effort = effort
        self._client = None

    @property
    def capabilities(self):
        return Capabilities(vision=True, thinking=True, name=f"anthropic:{self._model}")

    def _ensure_client(self):
        if self._client is not None:
            return None
        try:
            import anthropic
        except ImportError:
            return ("The 'anthropic' package is not installed. Use the Install "
                    "button in Setup, or switch to the Ollama backend.")
        try:
            self._client = anthropic.Anthropic(api_key=self._api_key or None)
        except Exception as exc:
            return f"Could not create Anthropic client: {exc}"
        return None

    def run_turn(self, system, messages, tools, on_text=None, on_thinking=None):
        import anthropic
        error = self._ensure_client()
        if error:
            return TurnResult([], "error", error=error)

        system_blocks = [{"type": "text", "text": system,
                          "cache_control": {"type": "ephemeral"}}]
        try:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": self._effort},
                system=system_blocks,
                tools=[{"name": t["name"], "description": t["description"],
                        "input_schema": t["input_schema"]} for t in tools],
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta" and on_text:
                            on_text(event.delta.text)
                        elif event.delta.type == "thinking_delta" and on_thinking:
                            on_thinking(event.delta.thinking)
                response = stream.get_final_message()
        except anthropic.AuthenticationError:
            return TurnResult([], "error", error="Invalid or missing Anthropic API key.")
        except anthropic.NotFoundError:
            return TurnResult([], "error", error=f"Model '{self._model}' not found.")
        except anthropic.RateLimitError:
            return TurnResult([], "error", error="Rate limited — wait and retry.")
        except anthropic.APIStatusError as exc:
            return TurnResult([], "error", error=f"API error {exc.status_code}: {exc.message}")
        except anthropic.APIConnectionError:
            return TurnResult([], "error", error="Network error reaching the Anthropic API.")

        tool_calls = [{"id": b.id, "name": b.name, "input": dict(b.input or {})}
                      for b in response.content if b.type == "tool_use"]
        stop = {"tool_use": "tool_use", "end_turn": "end", "pause_turn": "tool_use",
                "max_tokens": "end", "refusal": "error"}.get(response.stop_reason, "end")
        error = None
        if response.stop_reason == "refusal":
            error = "The model declined this request for safety reasons."
        usage = {}
        try:
            usage = {"input": response.usage.input_tokens,
                     "output": response.usage.output_tokens,
                     "cache_read": response.usage.cache_read_input_tokens}
        except Exception:
            pass
        # assistant_content is the native block list (thinking blocks preserved).
        return TurnResult(response.content, stop, tool_calls, usage, error)
