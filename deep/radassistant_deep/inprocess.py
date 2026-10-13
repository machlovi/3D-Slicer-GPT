"""Run the deep agent IN-PROCESS, inside Slicer's own Python.

This is the shippable-extension path: no external venv and no Web Server exec
bridge. Instead of the out-of-process ``SlicerSession`` (which re-implements each
tool as an exec snippet), this wraps the **native RadAssistant ToolRegistry**
(~45 already-validated tools) directly as LangChain tools and feeds them to the
same deepagents harness — reusing the identical memory, skills, policy middleware
and approval matrix as the out-of-process build.

Requires the LangChain stack to be importable in Slicer's Python (install once with
``slicer.util.pip_install`` on first run — see the Slicer module).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

from .agent import (
    AgentConfig,
    BuiltAgent,
    VIRTUAL_MEMORY_ROOT,
    VIRTUAL_SKILLS_ROOT,
    _default_checkpointer,
    default_home,
)
from .memory import LearningStore, ensure_persona, PERSONA_FILENAME
from .middleware import DiagnosisGuardMiddleware, PolicyMiddleware, SceneContextMiddleware
from .models import create_model
from .policy import interrupt_config_for_mode
from .prompts import build_system_prompt
from .sessions import ToolOutcome
from .subagents import build_subagents
from .memory_tools import build_memory_tools


def build_langchain_tools_from_registry(registry: Any, *, vision: bool = False,
                                        executor: Any = None) -> list:
    """Wrap every native ToolRegistry tool as a LangChain StructuredTool.

    The native registry exposes ``definitions`` (name/description/input_schema) and
    ``execute(name, args) -> {text, image_b64, media_type, is_error}`` and never
    raises — exactly the contract a LangChain tool wants.

    ``executor`` is an optional ``fn(name, args) -> dict`` used instead of calling
    ``registry.execute`` directly. In the live Slicer module this is
    ``MainThreadBridge.run_tool_blocking``, so tool calls made from the agent's
    worker thread hop back to the Qt main thread (native tools touch Slicer/MRML).
    """
    run = executor or registry.execute
    tools = []
    for definition in registry.definitions:
        name = definition["name"]
        description = definition.get("description", "")
        schema = definition.get("input_schema") or {"type": "object", "properties": {}}

        def _make(tool_name: str):
            def _call(**kwargs):
                out = run(tool_name, kwargs) or {}
                text = out.get("text", "")
                if out.get("is_error") and not str(text).lower().startswith("error"):
                    text = "Error: " + str(text)
                if vision and out.get("image_b64") and not out.get("is_error"):
                    return [
                        {"type": "text", "text": text},
                        {"type": "image", "source_type": "base64",
                         "data": out["image_b64"], "mime_type": out.get("media_type", "image/png")},
                    ]
                return text
            return _call

        tools.append(StructuredTool.from_function(
            func=_make(name), name=name, description=description, args_schema=schema))
    return tools


class _SceneProxy:
    """Session-shaped adapter so the scene/policy middleware work unchanged in-process."""

    def __init__(self, registry: Any):
        self._registry = registry

    def scene_overview(self) -> ToolOutcome:
        out = self._registry.execute("get_scene_overview", {}) or {}
        return ToolOutcome(text=out.get("text", ""), is_error=bool(out.get("is_error")))


def build_inprocess_agent(config: AgentConfig, registry: Any, *, executor: Any = None) -> BuiltAgent:
    """Assemble the deep agent bound to the native in-process ToolRegistry.

    ``executor`` (fn(name, args) -> dict) marshals tool calls; pass
    ``MainThreadBridge.run_tool_blocking`` in the live Slicer module.
    """
    if isinstance(config.model, BaseChatModel):
        model = config.model
    else:
        model_kwargs: dict[str, Any] = {}
        if config.base_url:
            model_kwargs["base_url"] = config.base_url
        if config.api_key:
            model_kwargs["api_key"] = config.api_key
        model = create_model(config.model, **model_kwargs)

    # deepagents interrupts own the approval flow; the native registry must not also
    # pop its own confirm dialogs, so force it to auto.
    registry.approval_mode = "auto"
    registry.vision_available = config.vision

    home = Path(config.home or default_home())
    persona_path = ensure_persona(home)
    learning_store = LearningStore(workspace=home)

    skills_dir = config.skills_dir
    routes: dict[str, Any] = {
        f"{VIRTUAL_MEMORY_ROOT}/": FilesystemBackend(root_dir=home, virtual_mode=True),
    }
    skills_sources: list[str] | None = None
    if skills_dir is not None and Path(skills_dir).is_dir():
        routes[f"{VIRTUAL_SKILLS_ROOT}/"] = FilesystemBackend(root_dir=Path(skills_dir), virtual_mode=True)
        skills_sources = [f"{VIRTUAL_SKILLS_ROOT}/"]
    backend = CompositeBackend(default=StateBackend(), routes=routes)

    slicer_tools = build_langchain_tools_from_registry(registry, vision=config.vision, executor=executor)
    tools = [*slicer_tools, *build_memory_tools(learning_store), *config.extra_tools]

    proxy = _SceneProxy(registry)
    tool_names = [t.name for t in tools]
    interrupt_on = interrupt_config_for_mode(config.approval_mode, tool_names) or None
    policy = PolicyMiddleware(session=proxy)
    middleware = [SceneContextMiddleware(proxy), policy, DiagnosisGuardMiddleware()]
    subagents = build_subagents(slicer_tools, skills=skills_sources) if config.subagents_enabled else None

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=build_system_prompt(vision=config.vision),
        middleware=middleware,
        subagents=subagents,
        skills=skills_sources,
        memory=[f"{VIRTUAL_MEMORY_ROOT}/{PERSONA_FILENAME}"],
        backend=backend,
        interrupt_on=interrupt_on,
        checkpointer=config.checkpointer or _default_checkpointer(home),
        name="radassistant-deep-inprocess",
    )

    return BuiltAgent(
        agent=agent,
        session=proxy,
        config=config,
        learning_store=learning_store,
        policy=policy,
        tools=tools,
        skills_dir=Path(skills_dir) if skills_dir else None,
        persona_path=persona_path,
    )


# ---------------------------------------------------------------------------
# In-process turn machinery — adapted from serve.py, but callback-based instead
# of stdin/stdout JSON. It emits the SAME event dicts the Slicer panel already
# renders (thinking_delta / assistant_delta / tool / todos / approval / ...).
# Runs on the agent WORKER thread; emit() and ask() marshal to the main thread.
# ---------------------------------------------------------------------------

import json as _json

_OPEN_TAG, _CLOSE_TAG = "<think>", "</think>"
_TAG_KEEP = max(len(_OPEN_TAG), len(_CLOSE_TAG)) - 1


def _reasoning_of(chunk: Any) -> str:
    ak = getattr(chunk, "additional_kwargs", None) or {}
    for key in ("reasoning_content", "reasoning"):
        v = ak.get(key)
        if v:
            return v if isinstance(v, str) else str(v)
    return ""


class _ThinkSplitter:
    def __init__(self):
        self.in_think = False
        self.buf = ""

    def feed(self, text):
        out = []
        self.buf += text
        while True:
            tag = _CLOSE_TAG if self.in_think else _OPEN_TAG
            idx = self.buf.find(tag)
            if idx == -1:
                break
            before = self.buf[:idx]
            if before:
                out.append(("thinking" if self.in_think else "answer", before))
            self.buf = self.buf[idx + len(tag):]
            self.in_think = not self.in_think
        if len(self.buf) > _TAG_KEEP:
            piece, self.buf = self.buf[:-_TAG_KEEP], self.buf[-_TAG_KEEP:]
            if piece:
                out.append(("thinking" if self.in_think else "answer", piece))
        return out

    def flush(self):
        if not self.buf:
            return []
        out = [("thinking" if self.in_think else "answer", self.buf)]
        self.buf = ""
        return out


def _consume_stream(stream, emit, streamed, should_stop):
    from langchain_core.messages import AIMessage, ToolMessage
    splitters = {}

    def _answer(mid, piece):
        emit({"type": "assistant_delta", "id": mid, "text": piece})
        streamed[mid] = streamed.get(mid, "") + piece

    stopped = False
    for chunk, meta in stream:
        if should_stop and should_stop():
            stopped = True
            try:
                stream.close()
            except Exception:
                pass
            break
        node = meta.get("langgraph_node")
        is_ai = isinstance(chunk, AIMessage) or type(chunk).__name__ == "AIMessageChunk"
        if is_ai and node == "model":
            mid = getattr(chunk, "id", None) or "cur"
            reasoning = _reasoning_of(chunk)
            if reasoning:
                emit({"type": "thinking_delta", "id": mid, "text": reasoning})
            content = chunk.content if isinstance(chunk.content, str) else ""
            if content:
                splitter = splitters.setdefault(mid, _ThinkSplitter())
                for kind, piece in splitter.feed(content):
                    if kind == "thinking":
                        emit({"type": "thinking_delta", "id": mid, "text": piece})
                    else:
                        _answer(mid, piece)
        elif isinstance(chunk, ToolMessage) and node == "tools":
            content = chunk.content
            text = content if isinstance(content, str) else _json.dumps(content, default=str)
            emit({"type": "tool", "name": getattr(chunk, "name", "tool"),
                  "text": text, "error": getattr(chunk, "status", None) == "error"})
    for mid, splitter in splitters.items():
        for kind, piece in splitter.flush():
            if kind == "thinking":
                emit({"type": "thinking_delta", "id": mid, "text": piece})
            else:
                _answer(mid, piece)
    return stopped


def _pending_interrupt(built, run_config):
    state = built.agent.get_state(run_config)
    if getattr(state, "interrupts", None):
        return state.interrupts[0].value
    return None


def _current_todos(built, run_config):
    """The plan (write_todos state) currently stored in the thread, or None."""
    try:
        return built.agent.get_state(run_config).values.get("todos")
    except Exception:
        return None


# def _reconcile_final(built, run_config, streamed, emit, todos_before=None):
#     from langchain_core.messages import AIMessage
#     try: 
#     values = built.agent.get_state(run_config).values
#     todos = values.get("todos")
#     # Only surface a plan the model actually wrote/updated THIS turn. The thread is
#     # resumed across restarts, so a plan left over from an earlier turn (e.g. an old
#     # TotalSegmentator plan) would otherwise redisplay on every unrelated request
#     # like a plain "load a CT" — misaligned with what the turn actually did.
#     if todos and todos != todos_before:
#         emit({"type": "todos", "todos": todos})
#     for msg in reversed(values.get("messages", [])):
#         if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
#             full = msg.content if isinstance(msg.content, str) else ""
#             mid = getattr(msg, "id", None) or "cur"
#             already = streamed.get(mid, "")
#             if full and full != already and full.startswith(already):
#                 emit({"type": "assistant_delta", "id": mid, "text": full[len(already):]})
#             break

def run_turn(built, text, run_config, emit, ask, should_stop=None, interrupts_possible=False):
    from langgraph.types import Command
    from langchain_core.messages import AIMessage
    streamed = {}
    try:
        try:
            stream = built.agent.stream(
                {"messages": [{"role": "user", "content": text}]},
                config=run_config, stream_mode="messages")
            stopped = _consume_stream(stream, emit, streamed, should_stop)
        except Exception as exc:
            err_str = str(exc)
            if "No generations found in stream" in err_str or "stream" in err_str.lower():
                result = built.agent.invoke(
                    {"messages": [{"role": "user", "content": text}]},
                    config=run_config
                )
                stopped = False
                for msg in reversed(result.get("messages", [])):
                    if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                        content = msg.content if isinstance(msg.content, str) else ""
                        if content:
                            emit({"type": "assistant_delta", "id": getattr(msg, "id", "final"), "text": content})
                        break
            else:
                raise exc

        while not stopped and interrupts_possible:
            request = _pending_interrupt(built, run_config)
            if request is None:
                break
            actions = (request or {}).get("action_requests", [])
            decisions = ask([{"name": a.get("name"), "args": a.get("args", {}),
                              "description": a.get("description", "")} for a in actions])
            if decisions is None:
                decisions = [{"type": "reject", "message": "Cancelled."} for _ in actions]
            try:
                stream = built.agent.stream(Command(resume={"decisions": decisions}),
                                            config=run_config, stream_mode="messages")
                stopped = _consume_stream(stream, emit, streamed, should_stop)
            except Exception as exc:
                err_str = str(exc)
                if "No generations found in stream" in err_str or "stream" in err_str.lower():
                    result = built.agent.invoke(Command(resume={"decisions": decisions}), config=run_config)
                    stopped = False
                    for msg in reversed(result.get("messages", [])):
                        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
                            content = msg.content if isinstance(msg.content, str) else ""
                            if content:
                                emit({"type": "assistant_delta", "id": getattr(msg, "id", "final"), "text": content})
                            break
                else:
                    raise exc

        if stopped:
            emit({"type": "stopped"})
    except Exception as exc:
        err_str = str(exc)
        if "model_dump" in err_str or "NoneType" in err_str and "model_dump" in err_str:
            emit({"type": "error", "text": "Turn failed: The NYU GPT proxy returned an empty (null) response body. "
                                          "As noted in your config, NYU GPT does not support tool calling loops. "
                                          "Please use Ollama (local) or OpenAI Cloud for tool operations."})
        else:
            emit({"type": "error", "text": "Turn failed: %s" % exc})
    emit({"type": "turn_done"})
    




# def run_turn(built, text, run_config, emit, ask, should_stop=None):
#     from langgraph.types import Command
#     streamed = {}
#     todos_before = _current_todos(built, run_config)
#     try:
#         stream = built.agent.stream(
#             {"messages": [{"role": "user", "content": text}]},
#             config=run_config, stream_mode="messages")
#         stopped = _consume_stream(stream, emit, streamed, should_stop)
#         while not stopped:
#             request = _pending_interrupt(built, run_config)
#             if request is None:
#                 break
#             actions = (request or {}).get("action_requests", [])
#             decisions = ask([...])
#             if decisions is None:
#                 decisions = [{"type": "reject", "message": "Cancelled."} for _ in actions]
#             stream = built.agent.stream(Command(resume={"decisions": decisions}),
#                                         config=run_config, stream_mode="messages")
#             stopped = _consume_stream(stream, emit, streamed, should_stop)

#         # ── KEY FIX: re-enable input NOW, before the slow reconciliation ──
#         emit({"type": "turn_done"})   # ← input responsive immediately

#         if stopped:
#             emit({"type": "stopped"})
#         # else:
#         #     _reconcile_final(built, run_config, streamed, emit, todos_before)
#         return   # ← don't emit turn_done again at the bottom
#     except Exception as exc:
#         emit({"type": "error", "text": "Turn failed: %s" % exc})
#     emit({"type": "turn_done"})