"""RadAssistant v2 orchestration layer.

Research-backed agent machinery, added ALONGSIDE the existing streaming loop so
nothing breaks. Pure-stdlib and Slicer-free wherever possible, so each piece is
unit-testable outside Slicer.

Modules (built incrementally):
  planning.py   Todo list + Goal state — the persistent, re-emitted plan that
                keeps a long task on-track (Claude Code's anti-drift mechanism).
  router.py     (Phase 2) cheap structured decision: intent, tool subset, risk…
  policy.py     (Phase 2) deterministic medical-safety / permission gate.
"""

from .planning import Goal, Plan, TodoItem, TodoStatus  # noqa: F401
