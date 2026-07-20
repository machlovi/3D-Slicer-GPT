"""The v2 Orchestrator — one turn = route → (plan) → disclose → execute → verify.

This is the "Claude Code-like" master loop, assembled from the tested primitives:

  route     a cheap structured decision (router.py): intent, tool subset, needs_plan,
            ask_user, risk. Abstain-to-ask on low confidence.
  plan      if multi-step, a persistent todo list + goal (planning.py), re-injected
            into context every round and updated by the model via `update_plan`.
  disclose  expose ONLY the router-selected tools + a small always-on core
            (ToolView) — never all ~84, which is what keeps a local model accurate.
  execute   single-threaded tool loop with the deterministic policy gate (policy.py)
            in front of every call, and vision/structured verification behind it.
  verify    check the goal's acceptance criteria before declaring done; run the
            diagnosis output-rail over the final text.

Slicer-free by dependency injection: every side-effecting capability (calling the
model, running a tool, prompting for approval, reading the scene, emitting UI events)
is passed in as a callable, so the whole turn is unit-testable with fakes
(tests/test_executor.py). agent.py wires these callables to the real backend + bridge.
"""

from .router import build_router_prompt, parse_router_response
from .planning import build_planner_prompt, parse_plan_response
from .policy import authorize, DiagnosisGuard
from .connectors import ToolView


UPDATE_PLAN_TOOL = {
    "name": "update_plan",
    "description": ("Update your todo list as you work: mark the step you are starting "
                    "and the steps you have finished (with the evidence that proves each). "
                    "Call this right after a step's result comes back."),
    "input_schema": {"type": "object", "properties": {
        "start": {"type": "integer", "description": "id of the step you are now starting"},
        "complete": {"type": "array", "items": {"type": "integer"},
                     "description": "ids of steps just finished"},
        "evidence": {"type": "string",
                     "description": "what proves the finished step(s), e.g. a volume or node name"}}}}


class Orchestrator:
    ALWAYS_ON = ["get_scene_overview", "take_screenshot", "list_segments",
                 "measure_segment_volumes", "read_skill"]
    SELF_GATED = {"execute_python"}     # tools that already prompt for approval themselves
    MAX_ROUNDS = 20

    def __init__(self, *, system, tool_defs, skills, decide_fn, agent_fn, tool_fn,
                 emit, scene_fn, approve_fn=None, scene_terms_fn=None, vision=False,
                 tool_limit=12, default_tools=None):
        self.system = system
        self.tool_defs = list(tool_defs)
        self.skills = list(skills or [])
        # tools to expose when the router can't produce a usable decision (weak local
        # model): degrade to a broad native toolset + planning rather than refusing.
        self.default_tools = list(default_tools) if default_tools else None
        self.decide_fn = decide_fn          # (system, user) -> raw text  (one-shot, no tools)
        self.agent_fn = agent_fn            # (system, messages, tools) -> TurnResult-like
        self.tool_fn = tool_fn              # (name, args) -> {text, is_error, image_b64?}
        self.emit = emit                    # (kind, payload) -> None
        self.scene_fn = scene_fn            # () -> str  (compact scene summary)
        self.approve_fn = approve_fn        # (title, body) -> bool
        self.scene_terms_fn = scene_terms_fn or (lambda: [])
        self.vision = vision
        self.tool_limit = tool_limit
        self.approval_mode = "manual"   # manual | accept | auto (set by the UI)
        self._view = ToolView(self.tool_defs, always_on=self.ALWAYS_ON)
        self._by_name = {d["name"]: d for d in self.tool_defs}
        self.plan = None

    # -- one turn ------------------------------------------------------------

    def run_turn(self, user_text):
        self.plan = None
        scene = self.scene_fn()

        # 1. ROUTE
        self.emit("status", "deciding…")
        decision = self._route(user_text, scene)
        self.emit("route", decision.to_dict())
        if decision.parse_failed:
            # the model couldn't emit a usable decision — don't refuse a clear request;
            # fall back to a broad native toolset and let the loop/plan handle it.
            self.emit("status", "router unclear — proceeding with the default toolset")
            decision = self._fallback_decision(user_text)
        elif decision.ask_user:
            self.emit("assistant", decision.clarifying_question)
            self.emit("turn_done", {})
            return {"decision": decision, "asked": True}

        # 2. PLAN (multi-step only)
        if decision.needs_plan:
            self.emit("status", "planning…")
            self._make_plan(user_text, scene)

        # 3. DISCLOSE — only the relevant tools this turn (broader on fallback)
        limit = 24 if decision.rationale.startswith("router unparsed") else self.tool_limit
        exposed = self._expose(decision.tools, limit=limit)

        # 4. EXECUTE
        final_text = self._run_tool_loop(user_text, scene, exposed)

        # 5. OUTPUT RAIL + VERIFY
        guarded, flagged = DiagnosisGuard().enforce(final_text)
        if guarded.strip():
            self.emit("assistant", guarded)
        verified = None
        if self.plan is not None:
            verified = self.plan.is_complete()
            self.emit("goal", {"complete": verified, "plan": self.plan.render_markdown()})
        self.emit("turn_done", {})
        return {"decision": decision, "plan": self.plan, "final": guarded,
                "diagnosis_flagged": flagged, "verified": verified}

    # -- steps ---------------------------------------------------------------

    def _route(self, user_text, scene):
        system, user = build_router_prompt(
            user_text, scene_summary=scene, tools=self._view.catalog(), skills=self.skills)
        raw = self.decide_fn(system, user)
        return parse_router_response(raw, known_tools=list(self._by_name),
                                     known_skills=[s[0] for s in self.skills])

    def _make_plan(self, user_text, scene):
        system, user = build_planner_prompt(user_text, scene)
        self.plan = parse_plan_response(self.decide_fn(system, user), fallback_goal=user_text)
        if self.plan and self.plan.items:
            self.plan.start(self.plan.items[0].id)
            self.emit("plan", self.plan.render_markdown())

    def _fallback_decision(self, user_text):
        from .router import RouterDecision
        low = user_text.lower()
        hits = sum(1 for kw in ("segment", "measure", "show", "load", "threshold",
                                "render", "report", "volume", " and ", "then", "3d")
                   if kw in low)
        tools = self.default_tools or list(self._by_name)[:15]
        return RouterDecision(intent="other", tools=tools, needs_plan=hits >= 3,
                              risk="reversible", confidence=0.5,
                              rationale="router unparsed; default toolset")

    def _expose(self, names, limit=None):
        defs = self._view.select(names, limit=limit or self.tool_limit)
        if self.plan is not None:
            defs = defs + [UPDATE_PLAN_TOOL]
        return defs

    def _run_tool_loop(self, user_text, scene, exposed):
        messages = [{"role": "user", "content": self._turn_context(scene, user_text)}]
        final_text = ""
        for _ in range(self.MAX_ROUNDS):
            result = self.agent_fn(self.system, messages, exposed)
            content = getattr(result, "assistant_content", None) or []
            if not content:
                self.emit("error", getattr(result, "error", None) or "the model returned nothing")
                break
            messages.append({"role": "assistant", "content": content})
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    final_text += b.get("text", "")
            if getattr(result, "stop_reason", "end") != "tool_use":
                break

            tool_results = []
            for call in getattr(result, "tool_calls", []):
                tool_results.append(self._handle_call(call))
            messages.append({"role": "user", "content": tool_results})
        return final_text

    def _handle_call(self, call):
        name = call["name"]
        args = dict(call.get("input") or {})
        cid = call.get("id", "call")

        if name == "update_plan":
            return self._apply_plan_update(cid, args)

        pol = authorize(name, args, scene_terms=self.scene_terms_fn())
        if pol.action == "deny":
            self.emit("tool_end", {"name": name, "ok": False, "summary": pol.reason})
            return self._tr(cid, pol.reason, is_error=True)
        if pol.action == "approve" and name not in self.SELF_GATED:
            from .approval import approval_tier, should_ask
            if should_ask(self.approval_mode, approval_tier(name, base_risk=pol.risk)):
                # Safe default: with no approval UI wired, refuse rather than silently run.
                if self.approve_fn is None:
                    self.emit("tool_end", {"name": name, "ok": False,
                                           "summary": "needs approval; none available"})
                    return self._tr(cid, f"'{name}' requires human approval but no approver "
                                         "is wired; refused.", is_error=True)
                if not self.approve_fn(f"Approve '{name}'?", pol.reason):
                    return self._tr(cid, "the user rejected this action.", is_error=True)
            # else: Accept/Auto mode auto-approved this tier — run without prompting.

        self.emit("tool_start", {"name": name, "input": args})
        outcome = self.tool_fn(name, args)
        self.emit("tool_end", {"name": name, "ok": not outcome.get("is_error"),
                               "summary": (outcome.get("text", "") or "")[:200]})
        return self._tr_outcome(cid, outcome)

    def _apply_plan_update(self, cid, args):
        if self.plan is None:
            return self._tr(cid, "no active plan to update.", is_error=True)
        ev = str(args.get("evidence", "") or "")
        for i in args.get("complete", []) or []:
            try:
                self.plan.complete(int(i), ev)
            except (KeyError, ValueError):
                pass
        if args.get("start") is not None:
            try:
                self.plan.start(int(args["start"]))
            except (KeyError, ValueError):
                pass
        self.emit("plan", self.plan.render_markdown())
        return self._tr(cid, "plan updated:\n" + self.plan.as_context())

    # -- helpers -------------------------------------------------------------

    def _turn_context(self, scene, user_text):
        parts = [f"<scene>\n{scene}\n</scene>"]
        if self.plan is not None:
            parts.append(f"<plan>\n{self.plan.as_context()}\n</plan>")
        parts.append(user_text)
        return "\n\n".join(parts)

    def _tr(self, cid, text, is_error=False):
        return {"type": "tool_result", "tool_use_id": cid,
                "content": [{"type": "text", "text": text}], "is_error": is_error}

    def _tr_outcome(self, cid, outcome):
        content = []
        if self.vision and outcome.get("image_b64"):
            content.append({"type": "image", "source": {
                "type": "base64", "media_type": outcome.get("media_type", "image/png"),
                "data": outcome["image_b64"]}})
        content.append({"type": "text", "text": outcome.get("text", "")})
        return {"type": "tool_result", "tool_use_id": cid, "content": content,
                "is_error": bool(outcome.get("is_error"))}
