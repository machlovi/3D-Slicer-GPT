"""Persistent plan / todo-list / goal state — RadAssistant v2.

Why this exists (research-backed): production agents (Claude Code, Cursor, Cline)
stay on-track over long, multi-step tasks by maintaining an EXPLICIT plan that is
re-emitted into context every turn. It is the single strongest anti-drift ("context
rot") mechanism and it needs no framework. This module is the plain-data core:

  - Goal      : what "done" means, with acceptance criteria + status.
  - TodoItem  : one step, with a status, an activeForm label shown while running,
                and a `verify` string naming the DETERMINISTIC check that proves it
                (research is blunt: LLM self-judging degrades; verification must be
                an external/tool check — node exists? volume in range?).
  - Plan      : goal + ordered items, with the "exactly one in_progress" invariant,
                markdown rendering for the chat panel, and JSON (de)serialization so
                it can be persisted per session and re-injected each turn.

Pure stdlib, Slicer-free → unit-testable outside Slicer (see tests/test_planning.py).
The executor loop (Phase 4) drives this; the planner agent (Phase 2) fills it in.
"""

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional

from .router import extract_json_object   # shared robust JSON extractor


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


_MARK = {
    TodoStatus.PENDING: "[ ]",
    TodoStatus.IN_PROGRESS: "[⟳]",
    TodoStatus.COMPLETED: "[x]",
    TodoStatus.BLOCKED: "[⊘]",
}


@dataclass
class TodoItem:
    id: int
    content: str                       # imperative: "Segment the liver"
    active_form: str = ""              # present-continuous: "Segmenting the liver"
    status: TodoStatus = TodoStatus.PENDING
    verify: str = ""                  # deterministic check that proves this step
    evidence: str = ""                # what the check actually observed
    blocked_by: Optional[int] = None  # id of the item this waits on

    def __post_init__(self):
        # accept plain strings from JSON / the model and coerce to the enum
        if not isinstance(self.status, TodoStatus):
            self.status = TodoStatus(self.status)
        if not self.active_form:
            self.active_form = self.content

    def to_dict(self):
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=int(d["id"]),
            content=d["content"],
            active_form=d.get("active_form", d.get("activeForm", "")),
            status=d.get("status", TodoStatus.PENDING),
            verify=d.get("verify", ""),
            evidence=d.get("evidence", ""),
            blocked_by=d.get("blocked_by"),
        )


@dataclass
class Goal:
    statement: str = ""
    acceptance: List[str] = field(default_factory=list)   # criteria that define "done"
    status: TodoStatus = TodoStatus.PENDING

    def __post_init__(self):
        if not isinstance(self.status, TodoStatus):
            self.status = TodoStatus(self.status)

    def to_dict(self):
        return {"statement": self.statement,
                "acceptance": list(self.acceptance),
                "status": self.status.value}

    @classmethod
    def from_dict(cls, d):
        if not d:
            return cls()
        return cls(statement=d.get("statement", ""),
                   acceptance=list(d.get("acceptance", [])),
                   status=d.get("status", TodoStatus.PENDING))


class Plan:
    """A goal plus an ordered todo list, with the single-in_progress invariant."""

    def __init__(self, goal: Optional[Goal] = None, items: Optional[List[TodoItem]] = None):
        self.goal = goal or Goal()
        self.items: List[TodoItem] = list(items or [])

    # -- construction --------------------------------------------------------

    @classmethod
    def from_todos(cls, contents, goal=None):
        """Build a fresh plan from a list of step descriptions.

        Each entry may be a plain string ("Load the CT") or a dict
        {"content":..., "active_form":..., "verify":...}. IDs are assigned 1..N.
        """
        items = []
        for i, entry in enumerate(contents, start=1):
            if isinstance(entry, str):
                items.append(TodoItem(id=i, content=entry))
            else:
                items.append(TodoItem(
                    id=i,
                    content=entry["content"],
                    active_form=entry.get("active_form", entry.get("activeForm", "")),
                    verify=entry.get("verify", ""),
                ))
        g = goal if isinstance(goal, Goal) else Goal(statement=goal or "")
        return cls(goal=g, items=items)

    # -- lookup --------------------------------------------------------------

    def get(self, item_id) -> Optional[TodoItem]:
        return next((it for it in self.items if it.id == item_id), None)

    @property
    def in_progress(self) -> Optional[TodoItem]:
        return next((it for it in self.items if it.status is TodoStatus.IN_PROGRESS), None)

    def next_pending(self) -> Optional[TodoItem]:
        return next((it for it in self.items if it.status is TodoStatus.PENDING), None)

    def is_complete(self) -> bool:
        return bool(self.items) and all(
            it.status is TodoStatus.COMPLETED for it in self.items)

    # -- transitions (enforce exactly-one in_progress) -----------------------

    def start(self, item_id) -> TodoItem:
        """Mark an item in_progress; demote any other in_progress back to pending."""
        item = self._require(item_id)
        for it in self.items:
            if it.status is TodoStatus.IN_PROGRESS and it.id != item_id:
                it.status = TodoStatus.PENDING
        item.status = TodoStatus.IN_PROGRESS
        return item

    def complete(self, item_id, evidence="") -> TodoItem:
        item = self._require(item_id)
        item.status = TodoStatus.COMPLETED
        if evidence:
            item.evidence = evidence
        return item

    def block(self, item_id, blocked_by=None) -> TodoItem:
        item = self._require(item_id)
        item.status = TodoStatus.BLOCKED
        item.blocked_by = blocked_by
        return item

    def advance(self, evidence="") -> Optional[TodoItem]:
        """Complete the current in_progress item and start the next pending one.

        Returns the newly-started item, or None if nothing is left to do.
        """
        current = self.in_progress
        if current is not None:
            self.complete(current.id, evidence)
        nxt = self.next_pending()
        if nxt is not None:
            self.start(nxt.id)
        return nxt

    def _require(self, item_id) -> TodoItem:
        item = self.get(item_id)
        if item is None:
            raise KeyError(f"no todo item with id {item_id}")
        return item

    # -- validation ----------------------------------------------------------

    def validate(self) -> List[str]:
        """Return a list of invariant violations (empty == healthy)."""
        problems = []
        active = [it for it in self.items if it.status is TodoStatus.IN_PROGRESS]
        if len(active) > 1:
            problems.append(
                f"{len(active)} items are in_progress; exactly one is allowed "
                f"(ids {[it.id for it in active]})")
        ids = [it.id for it in self.items]
        if len(ids) != len(set(ids)):
            problems.append("duplicate todo ids")
        for it in self.items:
            if it.blocked_by is not None and self.get(it.blocked_by) is None:
                problems.append(f"item {it.id} blocked_by unknown id {it.blocked_by}")
        return problems

    # -- rendering / persistence --------------------------------------------

    def render_markdown(self) -> str:
        """Human-facing checklist for the Slicer chat panel."""
        lines = []
        if self.goal.statement:
            lines.append(f"**Goal:** {self.goal.statement}")
            for crit in self.goal.acceptance:
                lines.append(f"  - _accept:_ {crit}")
            lines.append("")
        for it in self.items:
            label = it.active_form if it.status is TodoStatus.IN_PROGRESS else it.content
            line = f"{_MARK[it.status]} {label}"
            if it.status is TodoStatus.COMPLETED and it.evidence:
                line += f"  — {it.evidence}"
            if it.status is TodoStatus.BLOCKED and it.blocked_by is not None:
                line += f"  (needs #{it.blocked_by})"
            lines.append(line)
        return "\n".join(lines) if lines else "_(no plan yet)_"

    def as_context(self) -> str:
        """Compact form re-injected into the model's context each turn."""
        done = sum(1 for it in self.items if it.status is TodoStatus.COMPLETED)
        header = f"PLAN ({done}/{len(self.items)} done)"
        if self.goal.statement:
            header += f" — goal: {self.goal.statement}"
        rows = []
        for it in self.items:
            row = f"  {it.status.value:11} #{it.id} {it.content}"
            if it.verify and it.status is not TodoStatus.COMPLETED:
                row += f"  [verify: {it.verify}]"
            rows.append(row)
        return header + "\n" + "\n".join(rows)

    def to_dict(self):
        return {"goal": self.goal.to_dict(),
                "items": [it.to_dict() for it in self.items]}

    def to_json(self, **kw):
        return json.dumps(self.to_dict(), **kw)

    @classmethod
    def from_dict(cls, d):
        return cls(goal=Goal.from_dict(d.get("goal")),
                   items=[TodoItem.from_dict(x) for x in d.get("items", [])])

    @classmethod
    def from_json(cls, s):
        return cls.from_dict(json.loads(s))


# --- planner prompt + parsing (used by the executor when needs_plan) --------

_PLANNER = """You are the PLANNER for RadAssistant inside 3D Slicer (medical imaging).
Break the user's request into a short ordered todo list. Reply with ONE JSON object only:

{{"goal": {{"statement": "<what done means>", "acceptance": ["<checkable criterion>", ...]}},
 "todos": [{{"content": "<imperative step>", "active_form": "<present-continuous>",
             "verify": "<a DETERMINISTIC check that proves this step from a tool result or scene
                        fact, e.g. 'segmentation Lungs exists and volume_ml in [1000,8000]'>"}}]}}

Rules: 3-8 steps; each step one Slicer action; prefer dedicated tools over code; every todo needs
a concrete verify (never 'looks right'); never include diagnosis.

CURRENT SCENE:
{scene}
"""


def build_planner_prompt(request, scene_summary=""):
    return (_PLANNER.format(scene=scene_summary or "(empty scene)"),
            f"Request: {request}\n\nReturn only the JSON plan.")


def parse_plan_response(text, fallback_goal="") -> Optional[Plan]:
    """Parse a planner reply into a Plan, or None if there's no usable plan."""
    obj = extract_json_object(text)
    if not obj:
        return None
    todos = obj.get("todos") or []
    if not todos:
        return None
    goal_raw = obj.get("goal")
    if isinstance(goal_raw, str):
        goal = Goal(statement=goal_raw)
    elif isinstance(goal_raw, dict):
        goal = Goal(statement=goal_raw.get("statement", fallback_goal),
                    acceptance=list(goal_raw.get("acceptance", [])))
    else:
        goal = Goal(statement=fallback_goal)
    try:
        return Plan.from_todos(todos, goal=goal)
    except (KeyError, TypeError):
        return None
