# RadAssistant (Deep Agent)

An open, agentic, natural-language assistant for **3D Slicer**, aimed at radiology —
re-implemented as a **LangChain deep agent that runs _inside_ Slicer's own Python**.
Ask in plain English; the agent drives Slicer's *validated* tools (Segment Editor,
TotalSegmentator, PyRadiomics), verifies its own work, keeps **persistent memory**
across restarts, and asks before anything irreversible. Backend-agnostic — a local
model (Ollama / llama.cpp / vLLM), any OpenAI-compatible server, or the Anthropic cloud.

> Research and visualization aid. **Not a diagnostic device.** Don't put PHI in the chat.

## Layout

| Path | What |
|---|---|
| [`engine/`](engine/) | The RadAssistant engine: the **47 native Slicer tools** + skills (the single source of truth for scene actions). |
| [`deep/`](deep/) | The LangChain deep-agent layer **and the Slicer module you load**. |
| [`packaging/`](packaging/) | Slicer-extension packaging (CMake, `.s4ext`, icon). |

**Full map + the runtime flow: [STRUCTURE.md](STRUCTURE.md).**

## Load it in Slicer

1. Edit ▸ Application Settings ▸ Modules ▸ **Additional module paths** → add
   `…\RadAssistant_DeepAgent\deep\slicer_module\RadAssistantDeep` → restart Slicer.
2. First launch pip-installs the LangChain stack into Slicer's Python (one time).
3. The chat panel docks on the right automatically. Point Setup at your model server,
   Connect, and try *"Load the CTChest sample and tell me what's loaded."*

## Design principle

Orchestrate Slicer's validated tools; **never reimplement clinical logic**. When no
tool supports what was asked, the agent says so plainly instead of improvising with
raw Python. Slicer tools live in exactly one file — `engine/radassistant_lib/tools.py`.

MIT licensed.
