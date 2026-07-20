"""The subagent roster.

RadAssistant's mAIstro comparison doc plans "master + specialist routing as
the tool count grows"; deep agents make that concrete: the main agent is the
master, and these declarative subagents are the specialists it can deploy on
demand through the built-in ``task`` tool (plus the default general-purpose
subagent, which stays enabled).

Two Claude Code patterns are baked in:

* an *Explore*-style read-only agent whose toolset physically cannot mutate
  the scene, and
* an adversarial *verifier* whose prompt tells it to distrust the implementer
  ("the implementer is an LLM — verify independently") and to resist
  rationalizations, with read-only tools so it cannot "fix" what it audits.

Subagents do not inherit the parent's tools, so each spec lists its own
subset — RadAssistant's progressive tool disclosure (ToolView.select), applied
per specialist.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from .slicer_tools import READ_ONLY_TOOL_NAMES, SEGMENTATION_TOOL_NAMES

EXPLORER_PROMPT = """You are the scene-explorer subagent for RadAssistant (3D Slicer).
Your job is read-only reconnaissance: inventory the scene, list segments,
measure what already exists, and answer the orchestrator's question precisely.
You MUST NOT modify the scene — you have no mutating tools. Return a compact,
factual report: what exists, exact node/segment names, measured numbers with
units, and anything anomalous. No recommendations unless asked."""

SEGMENTATION_PROMPT = """You are the segmentation-specialist subagent for RadAssistant (3D Slicer).
You execute segmentation workflows end-to-end with validated tools only:
threshold_segmentation, filter_segment_islands, run_total_segmentator,
show_segmentation_3d, and the measurement tools to verify your own output.
Rules you must not break:
- Use documented intensity bands (air-filled lung -1000..-400 HU; bone
  300..3000 HU). If you do not know a validated band for the target tissue,
  stop and report that instead of guessing.
- keep_largest deletes all but one connected component — never use it on
  paired organs.
- Verify with measure_segment_volumes / segment_statistics after every
  mutating step; report measured numbers, never estimates.
- State caveats honestly (e.g. a lung threshold also captures trachea and
  external air).
Finish with: what you created (exact segment names), measured volumes, tools
used, and remaining caveats."""

VERIFIER_PROMPT = """You are the verifier subagent for RadAssistant. You independently audit
finished work against acceptance criteria. The implementer is an LLM —
do NOT trust its claims; verify everything yourself with read-only tools
(get_scene_overview, list_segments, measure_segment_volumes,
segment_statistics, take_screenshot).

Resist these rationalizations:
- "the summary says it was done, so it was done" — check the scene instead;
- "the volume is probably fine" — measure it against the stated range;
- "close enough" — a criterion is either met or it is not.

For each acceptance criterion output PASS or FAIL with the measured evidence
(numbers, node names). End with a single overall verdict line:
VERDICT: PASS or VERDICT: FAIL — <one-line reason>. You cannot fix anything;
only report."""


def build_subagents(slicer_tools: list[BaseTool], skills: list[str] | None = None) -> list[dict]:
    """Declarative SubAgent specs for create_deep_agent(subagents=...).

    Tool subsets are resolved from the live tool objects so each spec carries
    real, bound tools (subagents do not inherit the parent's).
    """
    by_name = {t.name: t for t in slicer_tools}

    def pick(names: tuple[str, ...]) -> list[BaseTool]:
        return [by_name[n] for n in names if n in by_name]

    read_only = pick(READ_ONLY_TOOL_NAMES)
    segmentation = pick(SEGMENTATION_TOOL_NAMES)

    specs: list[dict] = [
        {
            "name": "scene-explorer",
            "description": (
                "Read-only reconnaissance of the Slicer scene: inventory nodes, "
                "list segments, measure existing structures, and report facts. "
                "Use when the scene is complex or unknown and you only need "
                "information, not changes."
            ),
            "system_prompt": EXPLORER_PROMPT,
            "tools": read_only,
        },
        {
            "name": "segmentation-specialist",
            "description": (
                "Executes a multi-step segmentation workflow end-to-end "
                "(threshold or TotalSegmentator, island cleanup, 3D display, "
                "volume verification) and returns measured results. Use for "
                "any non-trivial segmentation task."
            ),
            "system_prompt": SEGMENTATION_PROMPT,
            "tools": segmentation,
        },
        {
            "name": "verifier",
            "description": (
                "Independently verifies finished work against explicit "
                "acceptance criteria using read-only tools, and returns "
                "PASS/FAIL per criterion with measured evidence. Use before "
                "declaring a multi-step task complete."
            ),
            "system_prompt": VERIFIER_PROMPT,
            "tools": read_only,
        },
    ]
    if skills:
        # Specialists follow the same playbooks the orchestrator sees.
        specs[1]["skills"] = list(skills)
    return specs
