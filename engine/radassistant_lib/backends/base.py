"""Backend abstraction: one small interface, any LLM behind it.

The agent speaks a single neutral message format (Anthropic-style content
blocks — a convenient, well-specified IR) and never imports a vendor SDK.
Each backend translates that IR to its own wire format, runs a streaming
request, and returns a normalized TurnResult.

Neutral message shapes the agent produces:
  {"role": "user", "content": "<text>"}
  {"role": "user", "content": [ {"type":"tool_result", "tool_use_id":..,
                                 "content":[{"type":"text",..},
                                            {"type":"image","source":{...}}],
                                 "is_error": bool} ]}
  {"role": "assistant", "content": [ {"type":"text","text":..},
                                     {"type":"tool_use","id","name","input"} ]}

A backend returns a TurnResult:
  assistant_content : list[block]  — appended to history verbatim as the
                                     assistant turn (may be vendor-native, e.g.
                                     Anthropic thinking blocks)
  stop_reason       : "end" | "tool_use" | "error"
  tool_calls        : list[{"id","name","input"}]  — to execute this round
  usage             : {"input","output","cache_read"}
  error             : str | None
"""

import abc


class Capabilities:
    def __init__(self, vision=False, thinking=False, name=""):
        self.vision = vision        # can the model read images in tool results?
        self.thinking = thinking    # does it emit a separate reasoning stream?
        self.name = name

    def __repr__(self):
        return f"Capabilities(vision={self.vision}, thinking={self.thinking})"


class TurnResult:
    def __init__(self, assistant_content, stop_reason, tool_calls=None,
                 usage=None, error=None):
        self.assistant_content = assistant_content
        self.stop_reason = stop_reason
        self.tool_calls = tool_calls or []
        self.usage = usage or {}
        self.error = error


class Backend(abc.ABC):
    """Implement run_turn; the agent loop calls nothing else."""

    @property
    @abc.abstractmethod
    def capabilities(self):
        ...

    @abc.abstractmethod
    def run_turn(self, system, messages, tools, on_text=None, on_thinking=None):
        """Stream one assistant turn. Return a TurnResult.

        on_text / on_thinking are called with str deltas during streaming
        (from the worker thread — they push to the UI bridge).
        Never raise for API/transport errors: return TurnResult(stop_reason=
        "error", error=<human message>). Raising is reserved for programmer bugs.
        """
        ...


# --- shared IR helpers ------------------------------------------------------

def iter_blocks(content):
    """Yield content blocks whether content is a str or a list."""
    if isinstance(content, str):
        yield {"type": "text", "text": content}
    elif isinstance(content, list):
        for block in content:
            yield block


def block_type(block):
    return block.get("type") if isinstance(block, dict) else getattr(block, "type", None)


def tool_result_to_text(block, include_images):
    """Flatten a neutral tool_result block to (text, [image_b64]).

    Text-only backends pass include_images=False and get just the text — this
    is the structured-state verification channel that lets a local model work
    without vision.
    """
    text_parts, images = [], []
    inner = block.get("content", [])
    if isinstance(inner, str):
        text_parts.append(inner)
    else:
        for piece in inner:
            ptype = piece.get("type")
            if ptype == "text":
                text_parts.append(piece.get("text", ""))
            elif ptype == "image" and include_images:
                source = piece.get("source", {})
                if source.get("type") == "base64":
                    images.append(source.get("data", ""))
    text = "\n".join(t for t in text_parts if t)
    if block.get("is_error"):
        text = "[tool error] " + text
    return text, images
