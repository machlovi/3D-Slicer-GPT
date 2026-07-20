"""Ollama backend — your HPC local model as the brain.

Pure stdlib (urllib) so the local path needs ZERO pip installs inside Slicer.
Talks to Ollama's native /api/chat: NDJSON streaming, native tool calling,
optional image input for vision models.

Because most strong local tool-callers are text-only, this backend defaults to
the structured-state verification channel (images in tool results are dropped
unless the model is declared vision-capable). See docs/ARCHITECTURE.md.
"""

import json
import urllib.error
import urllib.request

from .base import Backend, Capabilities, TurnResult, iter_blocks, tool_result_to_text

# Name-based fallback only — the Setup checkbox always overrides via config["vision"].
_VISION_HINTS = ("llava", "vision", "-vl", "moondream", "gemma3", "gemma4", "minicpm-v",
                 "llama3.2-vision", "llama4", "qwen3.5", "qwen3.6", "medgemma")


def _looks_like_vision(model):
    m = (model or "").lower()
    return any(h in m for h in _VISION_HINTS)


class OllamaBackend(Backend):
    def __init__(self, host="http://localhost:11434", model="qwen2.5:14b",
                 num_ctx=16384, keep_alive="30m", vision=None, timeout=600):
        self._host = host.rstrip("/")
        self._model = model
        self._num_ctx = int(num_ctx)
        self._keep_alive = keep_alive
        self._timeout = timeout
        self._vision = _looks_like_vision(model) if vision is None else bool(vision)

    @property
    def capabilities(self):
        return Capabilities(vision=self._vision, thinking=False,
                            name=f"ollama:{self._model}")

    # -- IR -> Ollama wire format -------------------------------------------

    def _translate(self, system, messages):
        wire = [{"role": "system", "content": system}]
        id_to_name = {}   # tool_use_id -> tool name, so tool results can be tagged
        for message in messages:
            role = message.get("role")
            content = message.get("content")

            if role == "assistant":
                text_parts, tool_calls = [], []
                for block in iter_blocks(content):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        id_to_name[block.get("id")] = block.get("name")
                        tool_calls.append({"function": {
                            "name": block.get("name"),
                            "arguments": block.get("input", {})}})
                entry = {"role": "assistant", "content": "\n".join(text_parts)}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                wire.append(entry)
                continue

            # user turn: plain string, or a list of tool_result blocks
            if isinstance(content, str):
                wire.append({"role": "user", "content": content})
                continue

            pending_images = []
            for block in iter_blocks(content):
                if block.get("type") == "tool_result":
                    text, images = tool_result_to_text(block, self._vision)
                    # Ollama matches results to calls by name (no tool_call_id).
                    entry = {"role": "tool", "content": text or "(no output)"}
                    name = id_to_name.get(block.get("tool_use_id"))
                    if name:
                        entry["tool_name"] = name
                    wire.append(entry)
                    pending_images.extend(images)
                elif block.get("type") == "text":
                    wire.append({"role": "user", "content": block.get("text", "")})
                elif block.get("type") == "image" and self._vision:
                    source = block.get("source", {})
                    if source.get("type") == "base64":
                        pending_images.append(source.get("data", ""))
            if pending_images:
                wire.append({"role": "user",
                             "content": "(image output from the previous tool)",
                             "images": pending_images})
        return wire

    # -- run one turn --------------------------------------------------------

    def run_turn(self, system, messages, tools, on_text=None, on_thinking=None):
        body = {
            "model": self._model,
            "messages": self._translate(system, messages),
            "tools": [{"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"]}} for t in tools],
            "stream": True,
            "options": {"num_ctx": self._num_ctx},
            "keep_alive": self._keep_alive,
        }
        request = urllib.request.Request(
            self._host + "/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST")

        text_out = []
        tool_calls = []
        usage = {}
        try:
            response = urllib.request.urlopen(request, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if "does not support tools" in detail:
                return TurnResult([], "error",
                                  error=f"Model '{self._model}' does not support tool "
                                        "calling. Pick a tool-capable model (e.g. "
                                        "qwen2.5, llama3.1/3.3, mistral-nemo).")
            return TurnResult([], "error", error=f"Ollama HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            return TurnResult([], "error",
                              error=f"Could not reach Ollama at {self._host} "
                                    f"({exc.reason}). Is the server running and reachable "
                                    "from this machine? For a remote HPC host set "
                                    "OLLAMA_HOST=0.0.0.0 there and use its address here.")

        try:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:
                    return TurnResult([], "error", error=f"Ollama: {chunk['error']}")
                message = chunk.get("message", {})
                delta = message.get("content", "")
                if delta:
                    text_out.append(delta)
                    if on_text:
                        on_text(delta)
                for call in message.get("tool_calls", []) or []:
                    function = call.get("function", {})
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except json.JSONDecodeError:
                            arguments = {}
                    tool_calls.append({"id": f"call_{len(tool_calls)}",
                                       "name": function.get("name"),
                                       "input": arguments})
                if chunk.get("done"):
                    usage = {"input": chunk.get("prompt_eval_count", 0),
                             "output": chunk.get("eval_count", 0),
                             "cache_read": 0}
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            return TurnResult([], "error", error=f"Ollama stream dropped: {exc}")
        finally:
            response.close()

        assistant_content = []
        joined = "".join(text_out)
        if joined.strip():
            assistant_content.append({"type": "text", "text": joined})
        for call in tool_calls:
            assistant_content.append({"type": "tool_use", "id": call["id"],
                                      "name": call["name"], "input": call["input"]})
        stop = "tool_use" if tool_calls else "end"
        return TurnResult(assistant_content, stop, tool_calls, usage)
