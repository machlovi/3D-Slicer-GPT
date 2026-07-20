"""The append-only learnings channel (RadAssistant MEMORY.md) as a LangChain tool.

This is the ONLY tool builder the LIVE in-process agent uses from the deep layer.
The actual Slicer tools come from the native engine registry
(engine/radassistant_lib/tools.py), wrapped directly in inprocess.py.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

from .memory import LearningStore


def build_memory_tools(store: LearningStore) -> list[BaseTool]:
    """The append-only learnings channel (RadAssistant MEMORY.md)."""

    @tool
    def record_learning(text: str, tag: str = "general") -> str:
        """Append one durable learning to the assistant's MEMORY.md (e.g. a
        user preference, a workflow correction, a dataset quirk). Use sparingly
        for facts that should survive this session; do not record routine
        results."""
        return store.record(text, tag)

    return [record_learning]
