"""Shared fixtures: a scripted model, a mock Slicer scene, and an agent factory.

Mirrors RadAssistant's own testing strategy — every suite runs without a live
LLM or Slicer, via dependency injection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from radassistant_deep import AgentConfig, MockSlicerSession, build_agent
from radassistant_deep.testing import ScriptedChatModel

SKILL_MD = """---
name: lung-segmentation
description: Segment both lungs from a chest CT by HU thresholding and report volumes.
---

# Lung segmentation

1. get_scene_overview
2. threshold_segmentation lower -1000 upper -400
3. measure_segment_volumes
"""


@pytest.fixture
def home(tmp_path: Path) -> Path:
    return tmp_path / "home"


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    d = tmp_path / "skills" / "lung-segmentation"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return tmp_path / "skills"


@pytest.fixture
def session() -> MockSlicerSession:
    s = MockSlicerSession()
    s.load_sample_data("CTChest")
    s.calls.clear()
    return s


@pytest.fixture
def make_agent(home: Path, skills_dir: Path, session: MockSlicerSession):
    """Factory: build the deep agent around a scripted model."""

    def _make(script, *, approval_mode="accept", vision=False, extra_tools=(), subagents=True):
        model = ScriptedChatModel(script=list(script))
        built = build_agent(
            AgentConfig(
                model=model,
                approval_mode=approval_mode,
                vision=vision,
                home=home,
                skills_dir=skills_dir,
                session=session,
                subagents_enabled=subagents,
                extra_tools=list(extra_tools),
            )
        )
        return built, model

    return _make


def run(built, text: str, thread: str = "t1") -> dict:
    return built.agent.invoke(
        {"messages": [{"role": "user", "content": text}]},
        config={"configurable": {"thread_id": thread}},
    )


def tool_messages(result: dict, name: str | None = None) -> list:
    out = [m for m in result["messages"] if getattr(m, "type", "") == "tool"]
    if name:
        out = [m for m in out if getattr(m, "name", "") == name]
    return out
