# radassistant-deep (the `deep/` layer)

RadAssistant's agentic workflow, re-implemented as a **LangChain deep agent**
([`deepagents`](https://docs.langchain.com/oss/python/deepagents/overview)):
one orchestrator that plans, drives validated 3D Slicer tools, and **deploys
specialist subagents on demand** when a task gets hard — while keeping every
safety rail from the original in deterministic code.

> **It runs _in-process_ inside Slicer's own Python.** The live agent
> (`inprocess.py`) wraps the native engine `ToolRegistry` directly. See
> [../STRUCTURE.md](../STRUCTURE.md) for the whole picture.

```
user ──► deep agent (orchestrator)
           │  write_todos ............ plan with verifiable steps
           │  <system-reminder> ...... live scene context every turn
           │  skills (reused) ........ progressive-disclosure playbooks
           │  Slicer tools ........... native engine ToolRegistry, wrapped in-process
           │  task ─────────────────► subagents, spawned as needed:
           │                            · scene-explorer (read-only recon)
           │                            · segmentation-specialist
           │                            · verifier (adversarial audit)
           ▼
        policy rails (code, not prompts): approval interrupts · PHI denial
        · execute_python circuit breaker · diagnosis disclaimer
```

## How the original maps onto the deep-agent harness

| RadAssistant (v1/v2)                          | radassistant-deep                                              |
| --------------------------------------------- | -------------------------------------------------------------- |
| v2 planner + `update_plan` tool               | built-in `write_todos` planning (todo list in agent state)     |
| v2 router / ToolView progressive disclosure   | curated toolset + per-subagent tool subsets                    |
| `<scene_context>` injected per turn           | `SceneContextMiddleware` system-reminder at turn start         |
| `skills/` + `read_skill` on demand            | the **same** `SKILL.md` library via SkillsMiddleware           |
| `policy.authorize` PHI hard-deny              | `PolicyMiddleware.wrap_tool_call` denial (any approval mode)   |
| Manual/Accept/Auto × tier approval matrix     | compiled to `interrupt_on` → human-in-the-loop interrupts      |
| `execute_python` 3-strike circuit breaker     | `PolicyMiddleware` streak counter (reset by dedicated tools)   |
| `DiagnosisGuard` output rail                  | `DiagnosisGuardMiddleware.after_model` disclaimer              |
| `RADASSISTANT.md` persona / `MEMORY.md`       | `memory=` (AGENTS.md mechanism) / `record_learning` tool       |
| backends: Ollama / OpenAI / Anthropic         | `create_model("provider:model")` — same three, plus `fake:`    |
| `MainThreadBridge` into Slicer                | **in-process**: native `ToolRegistry` wrapped in `inprocess.py`|
| history pruning / context limits              | built-in summarization middleware + prompt caching             |
| v2 executor round limit, tool-result IR       | LangGraph runtime, checkpointer-backed (resumable) threads     |

Claude Code patterns adopted: static-first system prompt with session data
injected after the cacheable prefix, `<system-reminder>` scene grounding,
prescriptive *when-to-use* tool descriptions, an Explore-style read-only agent,
an adversarial verifier, consecutive-failure circuit breaking, and "when in
doubt, ask the human" approval defaults.

## Run — live in 3D Slicer (the only runtime)

Add `slicer_module/RadAssistantDeep` to Slicer's **Additional module paths**,
restart, and the chat panel docks on the right. Point Setup at your model server
and Connect. Full load steps + one-turn flow: [../STRUCTURE.md](../STRUCTURE.md).

> The out-of-process CLI + Web Server path (`radassistant-deep …`, `--live`,
> `serve.py`, `WebServerSlicerSession`) was **removed** — it can't ship as an
> extension. The agent now runs in-process inside Slicer.

## Approval matrix (enforced as LangGraph interrupts)

| tier / mode              | manual | accept | auto |
| ------------------------ | :----: | :----: | :--: |
| read-only / reversible   |   —    |   —    |  —   |
| heavy (TotalSegmentator) |  ask   |   —    |  —   |
| code (`execute_python`)  |  ask   |   —    |  —   |
| irreversible (deletes, `clear_scene`) | ask | ask |  —   |
| PHI egress               | **denied in code when identifiers are detected — every mode**; otherwise ask per matrix |

## Offline tests / dev (optional venv)

The extension needs no venv (it installs into Slicer's Python on first launch).
A venv is only for the offline test suite, which runs without an LLM or Slicer via
a `ScriptedChatModel` + deterministic `MockSlicerSession`:

```bash
cd deep
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -e .[all,dev]
pytest        # policy matrix · tools · memory · agent loop · subagents · safety
```

```python
# offline/mock assembly (build_agent); the LIVE module calls build_inprocess_agent()
from radassistant_deep import AgentConfig, build_agent
built = build_agent(AgentConfig(model="fake:demo", approval_mode="manual"))
```

## Layout (see [../STRUCTURE.md](../STRUCTURE.md) for detail)

```
radassistant_deep/
  inprocess.py     LIVE: build_inprocess_agent() + run_turn()
  agent.py         offline/test assembly (build_agent) + AgentConfig/BuiltAgent
  memory.py        persona (RADASSISTANT.md) + learnings (MEMORY.md)
  memory_tools.py  record_learning — the only deep-layer tool used live
  sessions.py      ToolOutcome + SlicerSession + MockSlicerSession (offline tests)
  slicer_tools.py  LangChain Slicer tools for OFFLINE/mock tests + tool-name groups
  policy.py middleware.py prompts.py models.py subagents.py testing.py
slicer_module/RadAssistantDeep/RadAssistantDeep.py   the Slicer module you load
tests/               deterministic tests (no LLM, no Slicer)
```

Persona + learnings live under `~/.radassistant-deep/` (`RADASSISTANT_DEEP_HOME`
to relocate; `RADASSISTANT_SKILLS_DIR` to point at a different skills library).
`take_screenshot` attaches image content only for vision models; text-only models
use the structured-state verification channel.
