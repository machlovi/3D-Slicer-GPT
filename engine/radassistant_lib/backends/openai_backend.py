"""OpenAI-compatible backend — one adapter for vLLM, TGI, LM Studio, and any
server exposing /v1/chat/completions (including Ollama's shim).

Differences from the native Ollama backend, per the wire spec:
  - tool-call arguments are JSON STRINGS (not objects) — serialize on the way
    out, parse on the way in
  - tool results use role:"tool" + tool_call_id + name
  - images use the image_url data-URI form
  - streamed tool calls arrive as DELTAS accumulated by index

Pure stdlib (urllib) SSE. For Ollama specifically prefer the native backend —
its streaming+tools path is more reliable than the /v1 shim.
"""

import json
import urllib.error
import urllib.request

from .base import Backend, Capabilities, TurnResult, iter_blocks, tool_result_to_text


class OpenAICompatBackend(Backend):
    def __init__(self, base_url="http://localhost:8000/v1", model="",
                 api_key=None, vision=False, timeout=600):
        # Be forgiving: accept a base URL, or one that already includes the
        # /chat/completions endpoint (a common paste), and don't double it.
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[:-len("/chat/completions")]
        self._url = base + "/chat/completions"
        self._model = model
        self._api_key = api_key
        self._vision = bool(vision)
        self._timeout = timeout

    @property
    def capabilities(self):
        return Capabilities(vision=self._vision, thinking=False,
                            name=f"openai-compat:{self._model}")

    def _translate(self, system, messages):
        wire = [{"role": "system", "content": system}]
        id_to_name = {}
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
                        tool_calls.append({
                            "id": block.get("id"), "type": "function",
                            "function": {"name": block.get("name"),
                                         "arguments": json.dumps(block.get("input", {}))}})
                # "" rather than null: strict --jinja templates crash on None content
                entry = {"role": "assistant", "content": "\n".join(text_parts)}
                if tool_calls:
                    entry["tool_calls"] = tool_calls
                wire.append(entry)
                continue

            if isinstance(content, str):
                wire.append({"role": "user", "content": content})
                continue

            image_parts = []
            for block in iter_blocks(content):
                if block.get("type") == "tool_result":
                    text, images = tool_result_to_text(block, self._vision)
                    wire.append({"role": "tool",
                                 "tool_call_id": block.get("tool_use_id"),
                                 "name": id_to_name.get(block.get("tool_use_id"), ""),
                                 "content": text or "(no output)"})
                    for data in images:
                        image_parts.append({"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{data}"}})
                elif block.get("type") == "text":
                    wire.append({"role": "user", "content": block.get("text", "")})
            if image_parts:
                wire.append({"role": "user", "content":
                             [{"type": "text", "text": "(image output from the previous tool)"}]
                             + image_parts})
        return wire

    def run_turn(self, system, messages, tools, on_text=None, on_thinking=None):
        body = {
            "model": self._model,
            "messages": self._translate(system, messages),
            "tools": [{"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"]}} for t in tools],
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        request = urllib.request.Request(self._url, data=json.dumps(body).encode(),
                                         headers=headers, method="POST")

        text_out = []
        thinking_out = []
        calls = {}   # index -> {"id","name","args"}
        usage = {}
        stop_reason = "end"
        try:
            response = urllib.request.urlopen(request, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 404:
                return TurnResult([], "error", error=(
                    f"404 at {self._url}. The Server URL should be the API BASE ending in /v1 "
                    "(e.g. http://localhost:8080/v1) — not the web-UI page. Verify with: "
                    "curl http://localhost:8080/v1/models (should return JSON)."))
            return TurnResult([], "error", error=f"Server HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            return TurnResult([], "error",
                              error=f"Could not reach the OpenAI-compatible server at "
                                    f"{self._url} ({exc.reason}).")
        try:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in chunk:   # llama.cpp/vLLM send errors as a stream event
                    err = chunk["error"]
                    detail = err.get("message") if isinstance(err, dict) else str(err)
                    return TurnResult([], "error", error=f"Server error mid-stream: {detail}")
                if chunk.get("usage"):
                    usage = {"input": chunk["usage"].get("prompt_tokens", 0),
                             "output": chunk["usage"].get("completion_tokens", 0),
                             "cache_read": 0}
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta", {})
                    piece = delta.get("content")
                    if piece:
                        text_out.append(piece)
                        if on_text:
                            on_text(piece)
                    # thinking models (qwen3.x, deepseek-r1, …) stream reasoning
                    # in a separate field — surface it, don't drop it
                    thought = delta.get("reasoning_content") or delta.get("reasoning")
                    if thought:
                        thinking_out.append(thought)
                        if on_thinking:
                            on_thinking(thought)
                    for tc in delta.get("tool_calls", []) or []:
                        index = tc.get("index", 0)
                        slot = calls.setdefault(index, {"id": None, "name": None, "args": ""})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        function = tc.get("function", {})
                        if function.get("name"):
                            slot["name"] = function["name"]
                        if function.get("arguments"):
                            slot["args"] += function["arguments"]
                    if choice.get("finish_reason") == "tool_calls":
                        stop_reason = "tool_use"
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            return TurnResult([], "error", error=f"Stream dropped: {exc}")
        finally:
            response.close()

        if not text_out and not calls and thinking_out:
            return TurnResult([], "error",
                              error="The model produced only internal reasoning and no final "
                                    "answer — re-sending usually fixes it; if it keeps "
                                    "happening on llama.cpp, relaunch the server with "
                                    "--reasoning-format none.")

        tool_calls = []
        for index in sorted(calls):
            slot = calls[index]
            try:
                arguments = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": slot["id"] or f"call_{index}",
                               "name": slot["name"], "input": arguments})

        assistant_content = []
        joined = "".join(text_out)
        if joined.strip():
            assistant_content.append({"type": "text", "text": joined})
        for call in tool_calls:
            assistant_content.append({"type": "tool_use", "id": call["id"],
                                      "name": call["name"], "input": call["input"]})
        if tool_calls:
            stop_reason = "tool_use"
        return TurnResult(assistant_content, stop_reason, tool_calls, usage)


class GeminiBackend(OpenAICompatBackend):
    """Google Gemini via its OpenAI-compatible endpoint (free tier works).

    Uses a NON-streaming request: for reliable tool calling on Gemini's compat
    layer, one complete response beats streamed tool-call deltas. The turn's
    text is delivered in one go rather than token-by-token.
    """

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, api_key, model="gemini-2.0-flash", vision=False, timeout=300):
        super().__init__(base_url=self.ENDPOINT, model=model,
                         api_key=api_key, vision=vision, timeout=timeout)

    def run_turn(self, system, messages, tools, on_text=None, on_thinking=None):
        body = {
            "model": self._model,
            "messages": self._translate(system, messages),
            "tools": [{"type": "function", "function": {
                "name": t["name"], "description": t["description"],
                "parameters": t["input_schema"]}} for t in tools],
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        request = urllib.request.Request(self._url, data=json.dumps(body).encode(),
                                         headers=headers, method="POST")
        try:
            response = urllib.request.urlopen(request, timeout=self._timeout)
            raw = response.read().decode("utf-8", "replace")
            response.close()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            if exc.code in (401, 403):
                return TurnResult([], "error", error="Gemini rejected the API key (401/403). "
                                                     "Check the key in Setup.")
            if exc.code == 429:
                return TurnResult([], "error", error="Gemini free-tier rate limit hit (429). "
                                                     "Wait a minute and retry.")
            return TurnResult([], "error", error=f"Gemini HTTP {exc.code}: {detail}")
        except urllib.error.URLError as exc:
            return TurnResult([], "error", error=f"Could not reach Gemini ({exc.reason}). "
                                                 "Check your internet connection.")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return TurnResult([], "error", error="Gemini returned a non-JSON response.")
        if isinstance(data.get("error"), dict):
            return TurnResult([], "error", error="Gemini: " + str(data["error"].get("message", data["error"])))

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message", {})
        text = message.get("content") or ""
        if text and on_text:
            on_text(text)

        tool_calls = []
        for tc in message.get("tool_calls") or []:
            function = tc.get("function", {})
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append({"id": tc.get("id") or f"call_{len(tool_calls)}",
                               "name": function.get("name"), "input": arguments})

        assistant_content = []
        if text.strip():
            assistant_content.append({"type": "text", "text": text})
        for call in tool_calls:
            assistant_content.append({"type": "tool_use", "id": call["id"],
                                      "name": call["name"], "input": call["input"]})
        usage = {}
        if isinstance(data.get("usage"), dict):
            usage = {"input": data["usage"].get("prompt_tokens", 0),
                     "output": data["usage"].get("completion_tokens", 0), "cache_read": 0}
        return TurnResult(assistant_content, "tool_use" if tool_calls else "end", tool_calls, usage)
