"""Custom agent middleware — the RadAssistant workflow rails on the deepagents harness.

Three pieces, each mirroring a mechanism from RadAssistant (and, where noted,
a pattern Claude Code uses):

* ``SceneContextMiddleware``  — grounds every user turn in the live Slicer
  scene by appending a ``<system-reminder>`` message at turn start (RadAssistant
  v1 prepends ``<scene_context>`` to each user message; Claude Code injects
  system reminders the same way). Kept out of the system prompt so the static
  prompt prefix stays byte-stable for prompt caching.
* ``PolicyMiddleware``        — the deterministic gate on every tool call:
  PHI egress is hard-DENIED (not merely confirmed), and ``execute_python``
  gets a consecutive-failure circuit breaker (3 strikes, then it is blocked
  with an instruction to use dedicated tools — RadAssistant's exact rule).
* ``DiagnosisGuardMiddleware`` — output rail: if the final assistant text makes
  diagnostic assertions, append the research-use disclaimer (never deletes).

Approval prompting itself is NOT re-implemented here: the Manual/Accept/Auto
matrix is compiled by ``policy.interrupt_config_for_mode`` into deepagents'
``interrupt_on``, and LangChain's HumanInTheLoopMiddleware owns pause/resume.
"""

from __future__ import annotations

from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from .policy import DiagnosisGuard, PHIScrubber, classify_tool, scene_terms_from
from .sessions import SlicerSession

MAX_CONSECUTIVE_EXEC_FAILURES = 3

CIRCUIT_BREAKER_MESSAGE = (
    "execute_python is blocked: it failed "
    f"{MAX_CONSECUTIVE_EXEC_FAILURES} times in a row. Stop writing code and "
    "use the dedicated tools instead (threshold_segmentation, "
    "filter_segment_islands, measure_segment_volumes, run_total_segmentator, "
    "...). If you were trying to import or install a Slicer extension, call "
    "ensure_slicer_extension instead. If no dedicated tool fits, explain the "
    "limitation to the user."
)


class SceneContextMiddleware(AgentMiddleware):
    """Append the live scene inventory as a system reminder at turn start.

    ``before_agent`` runs once per ``invoke``/turn (not once per model call),
    so the reminder lands right after the user's message — exactly where
    RadAssistant v1 injects ``<scene_context>`` — and is persisted in history,
    which keeps the growing message prefix stable for prompt caching.
    """

    def __init__(self, session: SlicerSession) -> None:
        super().__init__()
        self.session = session

    def before_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if getattr(last, "type", None) != "human":
            return None  # resumed turns (e.g. after an approval) keep their context
        overview = self.session.scene_overview()
        reminder = HumanMessage(
            content=(
                "<system-reminder>\n<scene_context>\n"
                f"{overview.text}\n"
                "</scene_context>\n"
                "This is the current Slicer scene state, injected automatically. "
                "Treat it as ground truth; re-check with get_scene_overview after "
                "mutating the scene.\n</system-reminder>"
            )
        )
        return {"messages": [reminder]}


class PolicyMiddleware(AgentMiddleware):
    """Deterministic per-call enforcement (deny beats ask; code has a breaker)."""

    def __init__(self, session: SlicerSession | None = None) -> None:
        super().__init__()
        self.session = session
        self.exec_fail_streak = 0
        self.denials: list[tuple[str, str]] = []

    # -- helpers ---------------------------------------------------------------
    def _scene_terms(self) -> tuple[str, ...]:
        if self.session is None:
            return ()
        try:
            return scene_terms_from(self.session.scene_overview().text)
        except Exception:
            return ()

    @staticmethod
    def _flatten(args: Any) -> str:
        if isinstance(args, dict):
            return " ".join(f"{k}={PolicyMiddleware._flatten(v)}" for k, v in args.items())
        if isinstance(args, (list, tuple)):
            return " ".join(PolicyMiddleware._flatten(v) for v in args)
        return str(args)

    def _deny(self, request: ToolCallRequest, reason: str) -> ToolMessage:
        name = request.tool_call["name"]
        self.denials.append((name, reason))
        return ToolMessage(
            content=f"Error: {reason}",
            tool_call_id=request.tool_call["id"],
            name=name,
            status="error",
        )

    # -- hook --------------------------------------------------------------------
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Any],
    ) -> ToolMessage | Any:
        name = request.tool_call["name"]
        args = request.tool_call.get("args") or {}

        # 1. PHI egress: hard deny, regardless of approval mode.
        if classify_tool(name) == "phi_egress":
            scrubber = PHIScrubber(scene_terms=self._scene_terms())
            findings = scrubber.findings(self._flatten(args))
            if findings:
                kinds = ", ".join(sorted({f.kind for f in findings}))
                return self._deny(
                    request,
                    f"blocked {name}: arguments look like they contain PHI ({kinds}). "
                    "Patient data must not leave this machine. Rephrase without "
                    "identifiers, or keep the work local.",
                )

        # 2. execute_python circuit breaker (RadAssistant: 3 consecutive failures).
        if name == "execute_python":
            if self.exec_fail_streak >= MAX_CONSECUTIVE_EXEC_FAILURES:
                return self._deny(request, CIRCUIT_BREAKER_MESSAGE)
            result = handler(request)
            if isinstance(result, ToolMessage):
                failed = result.status == "error" or str(result.content).lstrip().lower().startswith(
                    ("error", "traceback")
                )
                self.exec_fail_streak = self.exec_fail_streak + 1 if failed else 0
            return result

        # 3. Any successful dedicated tool resets the streak (RadAssistant rule).
        result = handler(request)
        if isinstance(result, ToolMessage) and result.status != "error":
            self.exec_fail_streak = 0
        return result


class DiagnosisGuardMiddleware(AgentMiddleware):
    """Append the disclaimer when the final answer reads as diagnostic."""

    def __init__(self, guard: DiagnosisGuard | None = None) -> None:
        super().__init__()
        self.guard = guard or DiagnosisGuard()

    def after_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if not messages:
            return None
        last = messages[-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        text = last.content if isinstance(last.content, str) else ""
        if not text:
            return None
        enforced = self.guard.enforce(text)
        if enforced == text:
            return None
        patched = AIMessage(content=enforced, id=last.id)  # same id -> in-place replace
        return {"messages": [patched]}


class OpenAIProxySanitizerMiddleware(AgentMiddleware):
    """Sanitizes model requests for OpenAI-compatible proxies (e.g. NYU GPT / LiteLLM / vLLM).

    Converts list-based `system_message.content` (Anthropic block format with prompt caching)
    into a plain text string so OpenAI-compatible proxy gateways do not reject the request.
    """

    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        system_message = getattr(request, "system_message", None)
        if system_message is not None and isinstance(system_message.content, list):
            text_blocks = []
            for b in system_message.content:
                if isinstance(b, dict) and b.get("type") == "text":
                    text_blocks.append(b.get("text", ""))
                elif isinstance(b, str):
                    text_blocks.append(b)
            clean_text = "\n\n".join(text_blocks)
            from langchain_core.messages import SystemMessage
            clean_sys = SystemMessage(content=clean_text)
            request = request.override(system_message=clean_sys)
        return handler(request)
