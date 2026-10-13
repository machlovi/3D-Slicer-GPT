# RadAssistant (Deep Agent)

An open, agentic, natural-language assistant for **3D Slicer**, aimed at radiology —
re-implemented as a **LangChain deep agent that runs _inside_ Slicer's own Python**.
Ask in plain English; the agent drives Slicer's *validated* tools (Segment Editor,
TotalSegmentator, PyRadiomics), verifies its own work, keeps **persistent memory**
across restarts, and asks before anything irreversible. Backend-agnostic — a local
model (Ollama / llama.cpp / vLLM), any OpenAI-compatible server, or the Anthropic cloud.

> Research and visualization aid. **Not a diagnostic device.** Don't put PHI in the chat.

## The problem

3D Slicer is one of the most capable open platforms for medical image analysis —
and one of the hardest to actually use. Doing something as simple as "segment the
lungs and tell me their volume" means knowing that the answer is *Segment Editor →
Threshold effect → −1000/−400 HU → Islands effect → Segment Statistics module*,
spread across menus and modules that assume you already know the workflow. Add
AI segmentation (TotalSegmentator, MONAI, nnU-Net), radiomics (PyRadiomics),
registration, DICOM export, and RT dosimetry, and the surface area runs to
hundreds of modules and thousands of parameters. The expertise to use Slicer well
is orthogonal to the expertise to read the images — a radiologist or researcher
loses time to the tool instead of the task.

The obvious fix — "put an LLM in front of it" — creates three new problems of its
own, visible in any naive LLM-in-Slicer plugin:

- **The model is blind and unaccountable.** It fires tool calls and hopes, with no
  way to check its own output against the scene, so mistakes (wrong HU window,
  wrong segment, botched registration) go unnoticed, which matters more in a
  radiology context than in a general coding assistant.
- **It freezes the application.** Long-running operations (AI segmentation,
  registration) called naively on Slicer's Qt main thread block the entire UI —
  TotalSegmentator alone can hang Slicer for minutes on CPU hardware.
- **It has no memory and no restraint.** Every session starts cold, and nothing
  stops the model from reinventing clinical logic in ad hoc Python or deleting
  scene data without asking.

RadAssistant exists to close this gap without introducing new risk: it orchestrates
Slicer's **existing validated tools** instead of reimplementing clinical logic,
**verifies its own work** against screenshots or structured scene-state, runs
heavy operations **off the UI thread**, keeps **persistent memory** across
restarts, and enforces a code-level **approval/PHI/safety policy** — not just a
prompt asking nicely — before anything irreversible or identifiable happens. See
[CAPABILITY_REPORT.md](CAPABILITY_REPORT.md) for a candid, code-grounded read on
how much of that is actually true today versus still in progress.

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
