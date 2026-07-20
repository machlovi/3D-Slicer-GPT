"""Wire the v2 Orchestrator to RadAssistant's real backend + tool registry.

This is the seam between the tested-in-isolation orchestration layer and the live app.
It is deliberately UI-free: give it a backend, a ToolRegistry, and an emit callback and
it returns a ready Orchestrator. That lets the exact same wiring be driven two ways:

  · from the Slicer Python Console (single-threaded, tool_fn = registry.execute directly) —
    the safe way to exercise the full route→plan→execute→verify pipeline against the real
    model and real Slicer before any Qt UI changes;
  · later, from agent.py on the worker thread (tool_fn = bridge.run_tool_blocking), behind
    the Setup feature flag.

Slicer-free itself (no `import slicer`), so it still imports fine outside Slicer.
"""

from .executor import Orchestrator


V2_SYSTEM = """You are RadAssistant, an AI colleague operating inside 3D Slicer for radiology.
You drive Slicer's validated tools; you are not a segmentation algorithm and never diagnose —
you describe and measure, and interpretation belongs to the physician. Prefer a dedicated tool
over writing Python. If no tool supports what was asked, say so plainly and offer the closest
supported option — do NOT improvise with execute_python, guess at the Slicer API, edit segments
by trial and error, or invent a compromise (e.g. an "averaged" margin) the user did not ask for.
A <scene> block and (when present) a <plan> block are provided each turn:
keep the plan current with update_plan, and verify each step from a tool result before marking
it done. Ask before destructive actions. Lead with the outcome, then the caveat."""


def oneshot_text(backend, system, user):
    """One-shot completion with no tools — used for the router/planner decisions."""
    result = backend.run_turn(system, [{"role": "user", "content": user}], [])
    parts = [b.get("text", "") for b in (result.assistant_content or [])
             if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(parts)
    if not text and getattr(result, "error", None):
        # surface transport errors as empty so the router safely abstains
        return ""
    return text


def scene_terms_from(scene_text):
    """Pull quoted node names out of the scene summary, for the PHI-egress guard."""
    import re
    return re.findall(r'"([^"]{2,64})"', scene_text or "")


def build_orchestrator(*, backend, tools, skills=None, emit=None, tool_fn=None,
                       approve_fn=None, system=V2_SYSTEM, debug=False,
                       approval_mode="manual"):
    """Assemble an Orchestrator bound to the real backend + ToolRegistry.

    tools    : radassistant_lib.tools.ToolRegistry (native + any registered connectors)
    skills   : list of (name, description) pairs for the router; if None, derived below
    emit     : (kind, payload) -> None
    tool_fn  : (name, args) -> {text,is_error,image_b64?}; default = tools.execute (main-thread)
    approve_fn: (title, body) -> bool  (e.g. slicer.util.confirmYesNoDisplay)
    """
    emit = emit or (lambda k, p=None: None)
    run_tool = tool_fn or (lambda name, args: tools.execute(name, args))

    def scene_fn():
        out = run_tool("get_scene_overview", {})
        return out.get("text", "") if isinstance(out, dict) else str(out)

    def decide_fn(sys_prompt, user):
        raw = oneshot_text(backend, sys_prompt, user)
        if debug:
            print("\n[decide raw] " + repr(raw)[:900])
        return raw

    def agent_fn(sys_prompt, messages, tool_subset):
        return backend.run_turn(sys_prompt, messages, tool_subset)

    orch = Orchestrator(
        system=system,
        tool_defs=tools.all_definitions(),
        skills=skills or [],
        decide_fn=decide_fn,
        agent_fn=agent_fn,
        tool_fn=run_tool,
        emit=emit,
        scene_fn=scene_fn,
        approve_fn=approve_fn,
        scene_terms_fn=lambda: scene_terms_from(scene_fn()),
        vision=bool(getattr(backend.capabilities, "vision", False)),
        default_tools=[d["name"] for d in tools.definitions],   # native tools for fallback
    )
    orch.approval_mode = approval_mode
    return orch
