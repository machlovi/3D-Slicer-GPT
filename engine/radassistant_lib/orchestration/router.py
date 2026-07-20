"""Router / Decider — the cheap "decision agent" that runs first each turn.

Research-backed: a small, cheap classifier that emits a STRUCTURED decision is the
highest-leverage orchestration move — it controls latency, and (critically) it lets
us expose only the ~5-10 relevant tools per turn instead of all ~84, which is what
keeps a local model accurate. The decision only ever references enums + the real
tool/skill registry, so hallucinated routes are dropped, not executed.

This module is the pure, testable core: the decision type, a robust parser for messy
local-model output, and the prompt builder. The actual LLM call is made by the
executor through the existing Backend; nothing here imports Slicer or a model, so it
unit-tests outside Slicer (see tests/test_router.py).
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional


INTENTS = {"answer", "load", "describe", "measure", "segment", "visualize",
           "edit_scene", "qa_docs", "register", "other"}
RISKS = {"read_only", "reversible", "destructive", "phi_egress"}
COMPUTE = {"local", "hpc"}
TIERS = {"small_local", "large_local", "cloud"}

CONFIDENCE_ABSTAIN = 0.4   # below this, ask the user instead of guessing


@dataclass
class RouterDecision:
    intent: str = "other"
    route: str = ""                       # a skill id, or "" for none
    tools: List[str] = field(default_factory=list)   # subset to expose this turn
    needs_plan: bool = False
    ask_user: bool = False
    clarifying_question: str = ""
    risk: str = "reversible"
    compute: str = "local"
    model_tier: str = "large_local"
    confidence: float = 0.0
    rationale: str = ""
    parse_failed: bool = False          # True = the model gave no usable JSON (not a real ask)

    def to_dict(self):
        return asdict(self)

    def is_confident(self, threshold=CONFIDENCE_ABSTAIN) -> bool:
        return self.confidence >= threshold and not self.ask_user

    @classmethod
    def abstain(cls, question="Could you clarify what you'd like me to do?"):
        return cls(intent="other", ask_user=True, clarifying_question=question,
                   risk="read_only", confidence=0.0, parse_failed=True,
                   rationale="router could not parse a confident decision")

    @classmethod
    def from_raw(cls, raw, known_tools=None, known_skills=None):
        """Coerce an arbitrary dict (from the model) into a valid decision.

        Enforces enums, filters `tools` to the real registry (drops hallucinations),
        drops an unknown `route`, clamps confidence, and coerces booleans.
        """
        if not isinstance(raw, dict):
            return cls.abstain()

        def _enum(value, allowed, default):
            v = str(value).strip().lower() if value is not None else ""
            return v if v in allowed else default

        def _bool(value):
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("true", "1", "yes", "y")

        tools = raw.get("tools") or []
        if isinstance(tools, str):
            tools = [t.strip() for t in re.split(r"[,\s]+", tools) if t.strip()]
        tools = [str(t) for t in tools]
        if known_tools is not None:
            known = set(known_tools)
            tools = [t for t in tools if t in known]

        route = str(raw.get("route") or "").strip()
        if known_skills is not None and route and route not in set(known_skills):
            route = ""

        try:
            confidence = max(0.0, min(1.0, float(raw.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0

        decision = cls(
            intent=_enum(raw.get("intent"), INTENTS, "other"),
            route=route,
            tools=tools,
            needs_plan=_bool(raw.get("needs_plan")),
            ask_user=_bool(raw.get("ask_user")),
            clarifying_question=str(raw.get("clarifying_question") or "").strip(),
            risk=_enum(raw.get("risk"), RISKS, "reversible"),
            compute=_enum(raw.get("compute"), COMPUTE, "local"),
            model_tier=_enum(raw.get("model_tier"), TIERS, "large_local"),
            confidence=confidence,
            rationale=str(raw.get("rationale") or "").strip(),
        )
        # low confidence with no explicit question → abstain-to-ask
        if decision.confidence < CONFIDENCE_ABSTAIN and not decision.ask_user:
            decision.ask_user = True
            if not decision.clarifying_question:
                decision.clarifying_question = (
                    "I'm not sure what you'd like — could you say a bit more?")
        return decision


# --- robust JSON extraction from messy model output -------------------------

def _balanced_objects(text):
    """Yield every top-level {...} substring, respecting quoted strings."""
    out, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                out.append(text[start:i + 1])
                start = None
    return out


_SCHEMA_KEYS = ("intent", "tools", "confidence", "needs_plan", "risk", "goal", "todos")


def extract_json_object(text) -> Optional[dict]:
    """Best-effort: pull the schema-shaped JSON object out of a model reply.

    Handles ```json fenced blocks, <think> reasoning that itself contains braces,
    and trailing prose. Among all parseable objects it returns the one that looks
    most like our decision/plan schema (most known keys), so a stray `{}` inside a
    thinking model's chain-of-thought doesn't win over the real answer.
    """
    if not text:
        return None
    # a thinking model may wrap reasoning in <think>…</think>; ignore that span
    stripped = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = []
    for src in (stripped, text):
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", src, re.DOTALL)
        if fence:
            candidates.append(fence.group(1))
        candidates.extend(_balanced_objects(src))

    best, best_score = None, -1
    for c in candidates:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        score = sum(1 for k in _SCHEMA_KEYS if k in obj)
        if score > best_score:
            best, best_score = obj, score
    return best


def parse_router_response(text, known_tools=None, known_skills=None) -> RouterDecision:
    """Parse a model's router reply into a validated RouterDecision (never raises)."""
    raw = extract_json_object(text)
    if raw is None:
        return RouterDecision.abstain()
    return RouterDecision.from_raw(raw, known_tools=known_tools, known_skills=known_skills)


# --- prompt construction ----------------------------------------------------

_ROUTER_INSTRUCTIONS = """You are the ROUTER for RadAssistant, an assistant inside 3D Slicer (medical imaging).
Decide how to handle the user's request. Reply with ONE JSON object and nothing else.

Schema (all keys required):
{{
  "intent": one of {intents},
  "route": a skill id from the list below, or "" if none applies,
  "tools": array of tool names to use this turn — pick the FEWEST that suffice (usually 1-5); [] if none,
  "needs_plan": true only for multi-step tasks (3+ dependent steps),
  "ask_user": true if the request is ambiguous or unsafe to guess,
  "clarifying_question": the question to ask if ask_user is true, else "",
  "risk": one of {risks}  (phi_egress = would send data off the machine, e.g. web tools),
  "compute": one of {compute}  (hpc only for heavy jobs like TotalSegmentator on a GPU),
  "model_tier": one of {tiers},
  "confidence": a number 0.0-1.0,
  "rationale": one short sentence
}}

Rules: never diagnose; describing and measuring are fine. Prefer a dedicated tool over code.
Only choose tools that actually exist in the list. If unsure, set ask_user true with low confidence.

Output ONLY the JSON object — no markdown, no commentary, no <think> tags. Start with {{ and end with }}.
Example: {{"intent":"segment","route":"lung-segmentation","tools":["threshold_segmentation","measure_segment_volumes"],"needs_plan":true,"ask_user":false,"clarifying_question":"","risk":"reversible","compute":"local","model_tier":"large_local","confidence":0.9,"rationale":"multi-step lung segmentation and volumetry"}}

CURRENT SCENE:
{scene}

AVAILABLE SKILLS:
{skills}

AVAILABLE TOOLS:
{tools}
"""


def build_router_prompt(request, scene_summary="", tools=None, skills=None,
                        backends_note=""):
    """Assemble the router system prompt. `tools`/`skills` are lists of
    (name, one-line description) pairs."""
    def _fmt(pairs):
        if not pairs:
            return "(none)"
        return "\n".join(f"- {name}: {desc}" for name, desc in pairs)

    system = _ROUTER_INSTRUCTIONS.format(
        intents=sorted(INTENTS), risks=sorted(RISKS),
        compute=sorted(COMPUTE), tiers=sorted(TIERS),
        scene=scene_summary or "(empty scene)",
        skills=_fmt(skills), tools=_fmt(tools))
    if backends_note:
        system += f"\nBACKENDS: {backends_note}\n"
    user = f"User request: {request}\n\nReturn only the JSON decision."
    return system, user
