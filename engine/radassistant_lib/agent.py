"""Backend-agnostic agent worker: a streaming tool-use loop on a background thread.

The agent depends only on a Backend (Ollama / OpenAI-compatible / Anthropic) and
the bridge. The LLM call streams on this thread; every tool call is marshaled to
the Qt main thread and its result (text, and an image only if the backend can
see) is returned to the model. Multiple tool calls in one turn run in order and
return in a single user message.

UI events emitted through the bridge:
  status(str), thinking_delta(str), assistant_delta(str),
  tool_start({name, input}), tool_end({name, ok, summary}),
  turn_done({usage}), error(str)
"""

import queue
import threading
import time

from . import logbook

MAX_HISTORY_MESSAGES = 60
KEEP_IMAGES_IN_LAST_N = 6
MAX_TOOL_ROUNDS = 25   # hard stop on a runaway tool loop

# Server phrasings for "you sent an image but no vision is loaded" — llama.cpp
# without --mmproj, Ollama with a text-only model, vLLM/TGI template errors.
_IMAGE_REJECT_SIGNATURES = ("image input", "mmproj", "does not support image",
                            "missing data required for image", "image_url")


def _rejects_images(error):
    e = (error or "").lower()
    return any(s in e for s in _IMAGE_REJECT_SIGNATURES)


_STOP = object()


class _Interrupted(Exception):
    """Raised inside a streaming callback to abort the current turn on user request."""


class AssistantAgent(threading.Thread):
    def __init__(self, bridge, tool_definitions, system_prompt, backend):
        super().__init__(daemon=True, name="RadAssistantAgent")
        self._bridge = bridge
        self._tools = tool_definitions
        self._system = system_prompt
        self._backend = backend
        self._vision = bool(backend.capabilities.vision)
        self._inbox = queue.Queue()
        self._messages = []
        self._interrupt = threading.Event()   # set from the main thread by the Stop button

    # -- called from the main thread ------------------------------------

    def send_user_message(self, text):
        self._inbox.put(text)

    def reset_conversation(self):
        self._inbox.put(("__reset__", None))

    def request_stop(self):
        self._inbox.put(_STOP)

    def interrupt(self):
        """Ask the running turn to stop at the next safe point (streaming chunk or
        tool-round boundary). Safe to call from the main thread."""
        self._interrupt.set()

    # -- worker thread ----------------------------------------------------

    def run(self):
        while True:
            item = self._inbox.get()
            if item is _STOP:
                return
            if isinstance(item, tuple) and item[0] == "__reset__":
                self._messages = []
                continue
            try:
                self._process_turn(item)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                self._bridge.emit("error", f"Unexpected agent error: {exc}")
                self._bridge.emit("turn_done", {})

    def _process_turn(self, user_text):
        self._interrupt.clear()            # fresh turn — drop any stale stop request
        checkpoint = len(self._messages)   # roll back to here on a fatal error

        logbook.turn(user_text)
        scene = self._bridge.run_tool_blocking("get_scene_overview", {})
        self._messages.append({
            "role": "user",
            "content": f"<scene_context>\n{scene.get('text', '')}\n</scene_context>\n\n{user_text}",
        })
        self._prune_history()

        def _guard(kind):
            # a streaming callback that aborts the turn if Stop was pressed
            def cb(t):
                if self._interrupt.is_set():
                    raise _Interrupted()
                self._bridge.emit(kind, t)
            return cb

        usage = {}
        retried_empty = False
        stopped = False
        for _ in range(MAX_TOOL_ROUNDS):
            if self._interrupt.is_set():
                stopped = True
                break
            self._bridge.emit("status", "thinking…")
            _m0 = time.time()
            try:
                result = self._backend.run_turn(
                    self._system, self._messages, self._tools,
                    on_text=_guard("assistant_delta"),
                    on_thinking=_guard("thinking_delta"))
            except _Interrupted:
                stopped = True
                logbook.event("MODEL  interrupted by user after %dms",
                              int((time.time() - _m0) * 1000))
                break
            logbook.model(int((time.time() - _m0) * 1000), result.stop_reason,
                          result.error, result.usage)
            usage = result.usage or usage

            if not result.assistant_content:
                if self._vision and _rejects_images(result.error):
                    # The server can't accept the screenshot we attached (e.g.
                    # llama.cpp without --mmproj): scrub images, drop to the
                    # structured-state channel, and retry instead of dying.
                    self._disable_vision(result.error)
                    continue
                if not retried_empty and (not result.error or
                                          "only internal reasoning" in result.error):
                    # Thinking models occasionally end a turn with reasoning but
                    # no answer — one silent retry usually recovers it.
                    retried_empty = True
                    self._bridge.emit("status", "empty response — retrying…")
                    continue
                # Nothing usable came back (transport/auth error) — undo the turn.
                del self._messages[checkpoint:]
                self._bridge.emit("error", result.error or "The model returned nothing.")
                self._bridge.emit("turn_done", {})
                return

            self._messages.append({"role": "assistant", "content": result.assistant_content})

            if result.error:
                self._bridge.emit("error", result.error)
                break
            if result.stop_reason != "tool_use":
                break

            tool_results = []
            for call in result.tool_calls:
                if self._interrupt.is_set():
                    # pair every remaining tool_use with a result so history stays valid
                    tool_results.append({"type": "tool_result", "tool_use_id": call["id"],
                                         "content": [{"type": "text",
                                                      "text": "[interrupted by user]"}],
                                         "is_error": True})
                    stopped = True
                    continue
                self._bridge.emit("tool_start", {"name": call["name"],
                                                 "input": dict(call.get("input") or {})})
                _c0 = time.time()
                outcome = self._bridge.run_tool_blocking(call["name"], dict(call.get("input") or {}))
                _dur = int((time.time() - _c0) * 1000)
                content = []
                if self._vision and outcome.get("image_b64"):
                    content.append({"type": "image", "source": {
                        "type": "base64",
                        "media_type": outcome.get("media_type", "image/png"),
                        "data": outcome["image_b64"]}})
                content.append({"type": "text", "text": outcome.get("text", "")})
                tool_results.append({"type": "tool_result",
                                     "tool_use_id": call["id"],
                                     "content": content,
                                     "is_error": bool(outcome.get("is_error"))})
                self._bridge.emit("tool_end", {"name": call["name"],
                                               "ok": not outcome.get("is_error"),
                                               "summary": outcome.get("text", "")[:200],
                                               "duration_ms": _dur})
            self._messages.append({"role": "user", "content": tool_results})
            if stopped:
                break
        else:
            self._bridge.emit("error",
                              f"Stopped after {MAX_TOOL_ROUNDS} tool rounds to avoid a loop.")

        if stopped:
            self._bridge.emit("interrupted", None)
        self._bridge.emit("turn_done", usage)
        self._interrupt.clear()

    def _disable_vision(self, server_error):
        """The server rejected an image mid-conversation. Go text-only: scrub
        every image from history, steer the model to structured verification,
        and tell the user — the turn then retries instead of failing."""
        self._vision = False
        for message in self._messages:
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            message["content"] = [
                b for b in content
                if not (isinstance(b, dict) and b.get("type") == "image")]
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        block["content"] = [
                            b for b in inner
                            if not (isinstance(b, dict) and b.get("type") == "image")
                        ] or [{"type": "text",
                               "text": "[screenshot removed — this server cannot read images]"}]
        self._system += (
            "\n\nIMPORTANT UPDATE: the server rejected image input — YOU CANNOT SEE IMAGES "
            "in this session. Verify every change with structured tools instead: "
            "get_scene_overview, list_segments, measure_segment_volumes.")
        self._bridge.emit("vision_failed",
                          "The server rejected image input (no vision projector loaded), so "
                          "vision is off for this session — verifying via scene state instead. "
                          "Fix: uncheck 'This model can see images' in Setup, or serve the "
                          "model with its mmproj file. Server said: "
                          + str(server_error or "")[:200])

    # -- history management ----------------------------------------------

    def _prune_history(self):
        cutoff = max(0, len(self._messages) - KEEP_IMAGES_IN_LAST_N)
        for message in self._messages[:cutoff]:
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    inner = block.get("content")
                    if isinstance(inner, list):
                        block["content"] = [
                            b for b in inner
                            if not (isinstance(b, dict) and b.get("type") == "image")
                        ] or [{"type": "text", "text": "[earlier screenshot removed]"}]

        while len(self._messages) > MAX_HISTORY_MESSAGES:
            drop_until = None
            for index in range(1, len(self._messages)):
                message = self._messages[index]
                if (isinstance(message, dict) and message.get("role") == "user"
                        and isinstance(message.get("content"), str)):
                    drop_until = index
                    break
            if drop_until is None:
                break
            del self._messages[:drop_until]
