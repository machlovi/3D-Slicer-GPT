"""Persona + session memory — file-based and human-auditable (clinical trust argues for
readable files over an opaque vector store; Anthropic's file-memory pattern gave large
gains on its own).

Three tiers, all plain files under ~/.radassistant/:
  RADASSISTANT.md   persona / safe-operation rules / preferences — loaded every session
                    into the system prompt (analogous to CLAUDE.md / AGENTS.md).
  sessions/<id>.json  a checkpoint of the current goal+plan and a short transcript tail,
                    so a long task survives a crash/restart and can be resumed.
  MEMORY.md         append-only, timestamped learnings distilled from sessions.

Clock is injected so tests are deterministic; stdlib only (tests/test_memory.py).
"""

import json
import os


DEFAULT_PERSONA = """# RadAssistant

Research/visualization aid for 3D Slicer — NOT a diagnostic device. Describe and measure
image features; never diagnose, stage, or recommend treatment. Ask before destructive
actions (deleting nodes, clearing the scene, overwriting files). Never send patient-derived
data off the machine. Prefer dedicated tools over ad-hoc Python.
"""


class Memory:
    def __init__(self, root=None, clock=None):
        self.root = root or os.path.join(os.path.expanduser("~"), ".radassistant")
        self.sessions_dir = os.path.join(self.root, "sessions")
        self._clock = clock or (lambda: "1970-01-01T00:00:00")
        os.makedirs(self.sessions_dir, exist_ok=True)

    # -- persona -------------------------------------------------------------

    @property
    def persona_path(self):
        return os.path.join(self.root, "RADASSISTANT.md")

    def load_persona(self):
        """Return the persona text, creating a default file the first time."""
        if not os.path.isfile(self.persona_path):
            self.write_persona(DEFAULT_PERSONA)
            return DEFAULT_PERSONA
        with open(self.persona_path, encoding="utf-8") as f:
            return f.read()

    def write_persona(self, text):
        with open(self.persona_path, "w", encoding="utf-8") as f:
            f.write(text)

    # -- session checkpoint --------------------------------------------------

    def _session_path(self, session_id):
        safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
        return os.path.join(self.sessions_dir, f"{safe}.json")

    def save_session(self, session_id, plan=None, transcript_tail=None, extra=None):
        """Checkpoint goal+plan and a short transcript tail so a task can resume."""
        data = {
            "session_id": str(session_id),
            "saved_at": self._clock(),
            "plan": plan.to_dict() if plan is not None else None,
            "transcript_tail": list(transcript_tail or [])[-20:],
            "extra": extra or {},
        }
        with open(self._session_path(session_id), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data

    def load_session(self, session_id):
        path = self._session_path(session_id)
        if not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def load_plan(self, session_id):
        """Rehydrate the saved Plan (or None)."""
        data = self.load_session(session_id)
        if not data or not data.get("plan"):
            return None
        from .planning import Plan
        return Plan.from_dict(data["plan"])

    # -- learnings -----------------------------------------------------------

    @property
    def learnings_path(self):
        return os.path.join(self.root, "MEMORY.md")

    def add_learning(self, text, tag=""):
        """Append one timestamped learning line (newest facts supersede older ones)."""
        line = f"- [{self._clock()}]{(' ' + tag) if tag else ''}: {text.strip()}\n"
        header_needed = not os.path.isfile(self.learnings_path)
        with open(self.learnings_path, "a", encoding="utf-8") as f:
            if header_needed:
                f.write("# RadAssistant learnings\n\n")
            f.write(line)
        return line

    def read_learnings(self, limit=50):
        if not os.path.isfile(self.learnings_path):
            return ""
        with open(self.learnings_path, encoding="utf-8") as f:
            lines = [l for l in f if l.startswith("- ")]
        return "".join(lines[-limit:])
