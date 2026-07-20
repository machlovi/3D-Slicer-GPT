"""Deterministic fake chat model for tests and offline demos.

The deep agent is a loop around a chat model; to test the loop, the tools,
the approval gate and the subagent plumbing *rigorously* we need a model
whose behaviour is exact and repeatable. ``ScriptedChatModel`` plays back a
pre-written sequence of assistant turns (optionally with tool calls) and
records every prompt it receives so tests can assert on what the harness
actually sent to the model.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterable, Sequence

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


def ai(text: str = "", tool_calls: Iterable[dict[str, Any]] | None = None) -> AIMessage:
    """Build one scripted assistant turn.

    ``tool_calls`` items are ``{"name": ..., "args": {...}}``; ids are filled in.
    """
    calls = [
        {
            "name": c["name"],
            "args": c.get("args", {}),
            "id": c.get("id") or f"call_{uuid.uuid4().hex[:12]}",
            "type": "tool_call",
        }
        for c in (tool_calls or [])
    ]
    return AIMessage(content=text, tool_calls=calls)


class ScriptedChatModel(BaseChatModel):
    """Chat model that replays a fixed script of assistant turns.

    * Each ``_generate`` call returns the next scripted turn.
    * When the script is exhausted it returns ``exhausted_reply`` with no tool
      calls, so agent loops always terminate.
    * Every prompt received is appended to ``self.calls`` for assertions.
    * ``bind_tools`` records the bound tool names (``self.bound_tools``) and
      returns the model unchanged, which is all the agent harness needs.
    """

    script: list[AIMessage] = Field(default_factory=list)
    exhausted_reply: str = "Done."
    _i: int = PrivateAttr(default=0)
    _calls: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _bound_tools: list[list[str]] = PrivateAttr(default_factory=list)
    _bound_tool_objects: list[list[Any]] = PrivateAttr(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-chat-model"

    # -- introspection helpers -------------------------------------------------
    @property
    def calls(self) -> list[list[BaseMessage]]:
        return self._calls

    @property
    def bound_tools(self) -> list[list[str]]:
        return self._bound_tools

    @property
    def bound_tool_objects(self) -> list[list[Any]]:
        return self._bound_tool_objects

    @property
    def steps_consumed(self) -> int:
        return self._i

    # -- BaseChatModel interface ----------------------------------------------
    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        names = []
        for t in tools:
            name = getattr(t, "name", None) or getattr(t, "__name__", None)
            if name is None and isinstance(t, dict):
                name = t.get("name") or t.get("function", {}).get("name")
            names.append(str(name))
        self._bound_tools.append(names)
        self._bound_tool_objects.append(list(tools))
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._calls.append(list(messages))
        if self._i < len(self.script):
            message = self.script[self._i]
            self._i += 1
        else:
            message = AIMessage(content=self.exhausted_reply)
        return ChatResult(generations=[ChatGeneration(message=message)])


# ---------------------------------------------------------------------------
# Canned scripts, used by ``create_model("fake:<name>")`` for offline demos.
# ---------------------------------------------------------------------------

def demo_lung_script() -> list[AIMessage]:
    """A miniature RadAssistant session: plan, inspect, segment, measure, report."""
    return [
        ai(
            "I'll plan this lung segmentation first.",
            tool_calls=[
                {
                    "name": "write_todos",
                    "args": {
                        "todos": [
                            {"content": "Check what is loaded in the scene", "status": "in_progress"},
                            {"content": "Threshold lung parenchyma (-1000..-400 HU)", "status": "pending"},
                            {"content": "Report lung volume", "status": "pending"},
                        ]
                    },
                }
            ],
        ),
        ai(tool_calls=[{"name": "get_scene_overview", "args": {}}]),
        ai(
            "A chest CT is loaded. Thresholding the lungs now.",
            tool_calls=[
                {
                    "name": "threshold_segmentation",
                    "args": {
                        "volume_name": "CTChest",
                        "segment_name": "Lungs",
                        "lower_threshold": -1000,
                        "upper_threshold": -400,
                    },
                }
            ],
        ),
        ai(tool_calls=[{"name": "segment_statistics", "args": {"segment_name": "Lungs"}}]),
        ai(
            "Segmented both lungs by HU threshold (-1000 to -400) and rendered them. "
            "Total air-filled lung volume is about 4.6 L. Note this HU band also "
            "includes trachea and main bronchi."
        ),
    ]


_SCRIPTS = {
    "demo": demo_lung_script,
    "": demo_lung_script,
}


def load_script(name: str) -> list[AIMessage]:
    try:
        return _SCRIPTS[name]()
    except KeyError:
        raise ValueError(
            f"Unknown fake script {name!r}. Available: {sorted(k for k in _SCRIPTS if k)}"
        ) from None


def last_human_text(messages: list[BaseMessage]) -> str:
    """Convenience for assertions: text of the most recent human message."""
    for m in reversed(messages):
        if m.type == "human":
            return m.content if isinstance(m.content, str) else json.dumps(m.content)
    return ""
