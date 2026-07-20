"""File-based, human-auditable memory — a port of RadAssistant's ``orchestration/memory.py``.

Three tiers, all plain files in the agent workspace:

* ``RADASSISTANT.md``  — persona / safe-operation rules. Loaded into the system
  prompt at startup via deepagents' ``memory=`` parameter (the AGENTS.md
  mechanism). Created with a default persona on first run.
* ``MEMORY.md``        — append-only timestamped learnings
  (``- [<ts>] <tag>: <text>``), written through the ``record_learning`` tool.
* Session persistence  — unlike v2's hand-rolled ``sessions/<id>.json``,
  the deep agent gets durable sessions from a LangGraph checkpointer, so no
  custom code is needed here.

The clock is injectable for deterministic tests, exactly like the original.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PERSONA_FILENAME = "RADASSISTANT.md"
LEARNINGS_FILENAME = "MEMORY.md"

DEFAULT_PERSONA = """# RadAssistant operating rules

- You are RadAssistant, an agentic assistant for 3D Slicer (radiology).
- Orchestrate validated tools; never improvise clinical logic in code.
- Prefer dedicated tools over execute_python. The human owns the pixels;
  you own the plumbing.
- Never state a number you did not measure with a tool.
- You do not diagnose. Describe what was measured and rendered.
- Ask before destructive or irreversible actions.
"""


def _default_clock() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def ensure_persona(workspace: Path) -> Path:
    """Create the default persona file if missing; return its path."""
    workspace.mkdir(parents=True, exist_ok=True)
    path = workspace / PERSONA_FILENAME
    if not path.exists():
        path.write_text(DEFAULT_PERSONA, encoding="utf-8")
    return path


@dataclass
class LearningStore:
    """Append-only learnings file (``- [<ts>] <tag>: <text>``)."""

    workspace: Path
    clock: Callable[[], str] = field(default=_default_clock)

    @property
    def path(self) -> Path:
        return Path(self.workspace) / LEARNINGS_FILENAME

    def record(self, text: str, tag: str = "general") -> str:
        text = " ".join(str(text).split())
        if not text:
            return "Nothing to record: empty learning."
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = f"- [{self.clock()}] {tag}: {text}\n"
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line)
        return f"Recorded learning under tag '{tag}'."

    def read_all(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")
