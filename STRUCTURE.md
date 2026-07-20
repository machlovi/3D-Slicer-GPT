# RadAssistant_DeepAgent — structure

RadAssistant re-implemented as a **LangChain deep agent that runs _inside_ 3D
Slicer's own Python** — no external venv, no web bridge. Three top-level parts:

```
RadAssistant_DeepAgent/
├─ engine/       ← the RadAssistant "engine": the native Slicer tools + skills
├─ deep/         ← the LangChain deep-agent layer + the Slicer module you load
└─ packaging/    ← Slicer-extension packaging (CMake, .s4ext, icon)
```

> The one rule that removes all the confusion:
> **Slicer tools live in exactly ONE place — `engine/radassistant_lib/tools.py`.**
> The live agent wraps those directly. Nothing in `deep/` defines the real Slicer tools.

---

## engine/ — what actually touches Slicer
The validated native framework. **All 47 Slicer tools are here** (load, segment,
measure, `clear_scene`, `run_total_segmentator`, …) — the single source of truth.

```
engine/
  radassistant_lib/
    tools.py        ← THE 47 Slicer tools (the file you edit to add/change a tool)
    bridge.py       ← MainThreadBridge: marshals tool calls to Slicer's Qt main thread
    context.py      ← get_scene_overview text
    orchestration/  ← policy (approval tiers), router, connectors, hpc
    backends/       ← Ollama / OpenAI / Anthropic backends (native standalone path)
    agent.py  skills.py  logbook.py  voice.py  __init__.py
  skills/           ← SKILL.md playbooks (shared by both layers)
  connectors/       ← Talk2View-format extension connectors
  Resources/  CMakeLists.txt
  RadAssistant.py   ← the NATIVE standalone Slicer module (non-LangChain fallback)
```

## deep/ — the LangChain layer (what you run)
Wraps the engine's `ToolRegistry` as LangChain tools and adds persistent memory,
the approval policy, subagents, and a resumable thread.

```
deep/
  radassistant_deep/
    inprocess.py    ← ★ LIVE path: build_inprocess_agent() + run_turn()
    agent.py        ← offline/test assembly (build_agent) + AgentConfig / BuiltAgent
    memory.py       ← LearningStore + persona  (persistent memory)
    memory_tools.py ← record_learning — the ONLY deep-layer tool used live
    sessions.py     ← ToolOutcome + SlicerSession + MockSlicerSession (offline tests)
    slicer_tools.py ← LangChain-native Slicer tools for OFFLINE/mock tests only
    policy.py       ← approval matrix (gates irreversible/destructive tools)
    middleware.py  prompts.py  models.py  subagents.py  testing.py
  slicer_module/RadAssistantDeep/
    RadAssistantDeep.py  ← ★ the Slicer module you load (docks the chat panel)
  tests/  pyproject.toml  README.md
```

### Live vs. offline — why there are two "Slicer tool" files
| File | Runs in Slicer? | Purpose |
|------|-----------------|---------|
| `engine/radassistant_lib/tools.py` | ✅ yes (via `inprocess.py`) | the real 47 tools |
| `deep/…/slicer_tools.py` | ❌ no | a mirror driving `MockSlicerSession` in offline tests; also supplies the READ_ONLY / SEGMENTATION tool-name groups used by `subagents.py` |
| `deep/…/memory_tools.py` | ✅ yes | `record_learning` (persistent memory) |

The out-of-process path (a web server + external venv: `serve.py`, `cli.py`,
`WebServerSlicerSession`) was **removed** — it can't ship as an extension.

---

## Load it in Slicer
Edit ▸ Application Settings ▸ Modules ▸ **Additional module paths**, add:
```
…\RadAssistant_DeepAgent\deep\slicer_module\RadAssistantDeep
```
Restart Slicer. First launch pip-installs the LangChain stack into Slicer's Python.

## One turn, end to end
1. `RadAssistantDeep.py` builds the native `ToolRegistry` (engine) + `MainThreadBridge`.
2. `build_inprocess_agent()` wraps the 47 tools as LangChain tools + `record_learning`.
3. A worker thread runs the turn; each tool call hops to Slicer's main thread via the bridge.
4. Irreversible tools surface an approval in the panel; memory + thread persist to disk
   (so the agent remembers across restarts).

---

## Housekeeping
- A full pre-cleanup backup is in the session scratchpad: `RadAssistant_DeepAgent_BACKUP.zip`.
- The former sibling folders `D:\3dslicer\RadAssistant` and `D:\3dslicer\radassistant-deep`
  are the **originals this project superseded** — safe to archive/delete once you've
  confirmed the repackaged extension works (the good code now lives here).
