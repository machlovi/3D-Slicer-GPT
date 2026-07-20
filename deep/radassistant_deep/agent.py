"""Assembly: RadAssistant's workflow on the deepagents harness.

One call — :func:`build_agent` — produces a single deep agent that:

* plans with the built-in ``write_todos`` tool (v2 planning),
* grounds every turn in the live scene via a system reminder (v1/v2 scene
  context),
* uses the RadAssistant Slicer tool set over an injectable
  :class:`SlicerSession` (mock, or a live Slicer Web Server),
* loads the *existing* RadAssistant ``skills/`` library with progressive
  disclosure (v2 read_skill → deepagents SkillsMiddleware),
* can deploy specialist subagents on demand through the ``task`` tool
  (scene-explorer / segmentation-specialist / verifier / general-purpose),
* enforces the Manual/Accept/Auto approval matrix through human-in-the-loop
  interrupts, PHI-egress denial, an execute_python circuit breaker and the
  diagnosis output rail (v2 policy/approval),
* persists a persona file and append-only learnings under
  ``~/.radassistant-deep`` (v2 memory), and keeps multi-turn state on a
  LangGraph checkpointer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

from .memory import LearningStore, ensure_persona, PERSONA_FILENAME
from .middleware import DiagnosisGuardMiddleware, PolicyMiddleware, SceneContextMiddleware
from .models import create_model
from .policy import ApprovalMode, interrupt_config_for_mode
from .prompts import build_system_prompt
from .sessions import MockSlicerSession, SlicerSession
from .subagents import build_subagents
from .memory_tools import build_memory_tools
from .slicer_tools import build_slicer_tools

ENV_HOME = "RADASSISTANT_DEEP_HOME"
ENV_SKILLS = "RADASSISTANT_SKILLS_DIR"

VIRTUAL_SKILLS_ROOT = "/skills"
VIRTUAL_MEMORY_ROOT = "/memory"


def default_home() -> Path:
    return Path(os.environ.get(ENV_HOME) or (Path.home() / ".radassistant-deep"))


def default_skills_dir() -> Path | None:
    """The original RadAssistant skills library, when running from the repo."""
    env = os.environ.get(ENV_SKILLS)
    if env:
        return Path(env)
    repo_skills = Path(__file__).resolve().parents[2] / "RadAssistant" / "skills"
    return repo_skills if repo_skills.is_dir() else None


def _default_checkpointer(home: Path) -> BaseCheckpointSaver:
    """Persist conversation threads to disk so chat history survives a restart —
    the piece the original loop lacked (a shut-down chat lost all context).

    Defensive: falls back to the in-memory saver if the sqlite checkpointer
    package isn't installed, so this never breaks the build. Pairs with a
    resumable thread_id in serve.py to actually resume the last conversation.
    """
    try:
        import sqlite3
        from langgraph.checkpoint.sqlite import SqliteSaver

        home.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(home / "threads.sqlite"), check_same_thread=False)
        saver = SqliteSaver(conn)
        try:
            saver.setup()  # create tables on first use (no-op if they exist)
        except Exception:
            pass
        return saver
    except Exception:
        return InMemorySaver()


@dataclass
class AgentConfig:
    model: str | BaseChatModel | None = None
    base_url: str | None = None              # HPC / OpenAI-compatible server address
    api_key: str | None = None               # optional; local servers usually ignore it
    approval_mode: ApprovalMode = "accept"
    vision: bool = False
    home: Path | None = None                 # persona + MEMORY.md live here
    skills_dir: Path | None = None           # SKILL.md library (RadAssistant's by default)
    live_url: str | None = None              # http://host:2016 -> real Slicer
    session: SlicerSession | None = None     # explicit injection (tests) wins
    checkpointer: BaseCheckpointSaver | None = None
    # False removes the specialist roster (scene-explorer/segmentation-
    # specialist/verifier); deepagents' built-in general-purpose subagent and
    # the task tool remain — that is core harness behaviour.
    subagents_enabled: bool = True
    extra_tools: list[Any] = field(default_factory=list)


@dataclass
class BuiltAgent:
    agent: Any
    session: SlicerSession
    config: AgentConfig
    learning_store: LearningStore
    policy: PolicyMiddleware
    tools: list[Any]
    skills_dir: Path | None
    persona_path: Path


def _make_session(config: AgentConfig) -> SlicerSession:
    if config.session is not None:
        return config.session
    if config.live_url:
        raise ValueError(
            "out-of-process web mode (live_url) was removed — run the agent "
            "in-process via the Slicer module (build_inprocess_agent).")
    return MockSlicerSession()


def build_agent(config: AgentConfig | None = None) -> BuiltAgent:
    config = config or AgentConfig()

    # --- model + session ------------------------------------------------------
    if isinstance(config.model, BaseChatModel):
        model = config.model
    else:
        model_kwargs: dict[str, Any] = {}
        if config.base_url:
            model_kwargs["base_url"] = config.base_url
        if config.api_key:
            model_kwargs["api_key"] = config.api_key
        model = create_model(config.model, **model_kwargs)
    session = _make_session(config)

    # --- memory (persona + learnings) on disk ---------------------------------
    home = Path(config.home or default_home())
    persona_path = ensure_persona(home)
    learning_store = LearningStore(workspace=home)

    # --- backend: virtual scratch space + real skills/memory directories ------
    # Agent-written files (reports, notes) land in the safe virtual StateBackend;
    # the skills library and persona are real directories mounted read-through
    # at /skills and /memory. This reuses RadAssistant's skills folder in place.
    skills_dir = config.skills_dir or default_skills_dir()
    # NB: CompositeBackend route keys must carry a trailing slash — the path
    # remapping assumes it and mangles paths otherwise.
    routes: dict[str, Any] = {
        f"{VIRTUAL_MEMORY_ROOT}/": FilesystemBackend(root_dir=home, virtual_mode=True),
    }
    skills_sources: list[str] | None = None
    if skills_dir is not None and Path(skills_dir).is_dir():
        routes[f"{VIRTUAL_SKILLS_ROOT}/"] = FilesystemBackend(root_dir=Path(skills_dir), virtual_mode=True)
        skills_sources = [f"{VIRTUAL_SKILLS_ROOT}/"]
    backend = CompositeBackend(default=StateBackend(), routes=routes)

    # --- tools -----------------------------------------------------------------
    slicer_tools = build_slicer_tools(session, vision=config.vision)
    tools = [*slicer_tools, *build_memory_tools(learning_store), *config.extra_tools]

    # --- safety: approval matrix -> interrupts; policy + output rail ----------
    tool_names = [t.name for t in tools]
    interrupt_on = interrupt_config_for_mode(config.approval_mode, tool_names) or None
    policy = PolicyMiddleware(session=session)
    middleware = [
        SceneContextMiddleware(session),
        policy,
        DiagnosisGuardMiddleware(),
    ]

    # --- subagents ---------------------------------------------------------------
    subagents = build_subagents(slicer_tools, skills=skills_sources) if config.subagents_enabled else None

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=build_system_prompt(vision=config.vision),
        middleware=middleware,
        subagents=subagents,
        skills=skills_sources,
        memory=[f"{VIRTUAL_MEMORY_ROOT}/{PERSONA_FILENAME}"],
        backend=backend,
        interrupt_on=interrupt_on,
        checkpointer=config.checkpointer or _default_checkpointer(home),
        name="radassistant-deep",
    )

    return BuiltAgent(
        agent=agent,
        session=session,
        config=config,
        learning_store=learning_store,
        policy=policy,
        tools=tools,
        skills_dir=Path(skills_dir) if skills_dir else None,
        persona_path=persona_path,
    )
