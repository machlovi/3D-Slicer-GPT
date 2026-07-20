# RadAssistant

An open, agentic natural-language assistant for [3D Slicer](https://slicer.org). Ask for what you
want in plain English; the assistant drives Slicer's tools, **looks at the result with its own
eyes**, and reports back.

> Research and visualization aid. **Not a diagnostic device.** Do not use it to make clinical
> decisions, and do not send identifiable patient data to a cloud API.

---

## Why this exists

Slicer is enormously capable and enormously hard to learn — hundreds of modules, thousands of
parameters. A radiologist who wants "the lungs segmented and measured" should not have to know that
the answer is Segment Editor → Threshold → −1000/−400 HU → Islands → Show 3D → Segment Statistics.
That is what this closes.

## What makes it different

| | Typical LLM-in-Slicer plugin | RadAssistant |
|---|---|---|
| Vision | Model is blind; it fires tools and hopes | **Screenshots come back to the model as images** — it verifies its own work and self-corrects |
| Threading | Busy-wait polling freezes the UI | Agent runs on a worker thread; Qt stays responsive |
| Code execution | Disabled entirely, or wide open | Enabled, but every execution needs **human approval in a dialog** |
| Knowledge | Everything crammed into the prompt | **Progressive disclosure**: skill names in the prompt, bodies loaded on demand |
| Licence | Proprietary, closed core, cloud account | **MIT**, bring your own key |

## Backends — bring your own brain

Pick one in **Setup**. The agent code is identical across all three.

| Backend | For | Vision | Needs |
|---|---|---|---|
| **Ollama** | a local model on your machine or HPC | vision models only | nothing to install in Slicer (pure stdlib) |
| **OpenAI-compatible** | vLLM / TGI / LM Studio | model-dependent | nothing to install in Slicer |
| **Anthropic** | best demo (vision + reasoning) | yes | `pip install anthropic` + a key |

Most strong local **tool-calling** models are **text-only**. When the model can't see, RadAssistant
verifies every action against **structured scene-state** (segment voxel counts, volumes, node
existence) instead of screenshots — often *more* trustworthy for radiology than a pixel impression.
Leave the "vision" box off unless you're running a vision model (Qwen3-VL, Llama 4, Mistral Small 3.2).

## Install (5 minutes)

1. Install **3D Slicer 5.8+** — <https://download.slicer.org>. (Tested on 5.10.)
2. Copy this `RadAssistant` folder anywhere on disk.
3. Slicer → **Edit ▸ Application Settings ▸ Modules** → add the folder to *Additional module paths* → **Restart**.
4. Open **Modules ▸ Utilities ▸ RadAssistant**.
5. In **Setup**, pick a backend and fill in the fields:
   - **Ollama (HPC):** on the HPC run `OLLAMA_HOST=0.0.0.0 ollama serve` and pull a tool-capable model
     (`ollama pull qwen2.5:32b` / `llama3.3` / `gpt-oss:120b`). Set **Server URL** to
     `http://<hpc-address>:11434` and **Model** to that name. No key, no cloud — data stays local.
   - **OpenAI-compatible:** Server URL ending in `/v1`, plus a key if the server needs one.
   - **Anthropic:** click **Install Python packages**, paste a key (or export `ANTHROPIC_API_KEY`).

Optional, for AI auto-segmentation: install **SlicerTotalSegmentator** from the Extensions Manager.
Optional voice: the Install button also offers `sounddevice` + `faster-whisper` (offline dictation).

## The 6-minute demo

Type these one at a time. Nothing is pre-loaded — everything below happens live.

| # | Say this | What the radiologist sees |
|---|---|---|
| 1 | `Load a chest CT and set a lung window` | Data downloads, lung W/L applied. Establishes: it drives the app. |
| 2 | `What am I looking at?` | It screenshots, **looks**, and describes the study in radiology language. This is the moment people sit up. |
| 3 | `Segment the lungs, show them in 3D, and tell me the volumes` | Loads the `lung-segmentation` skill, thresholds at −1000/−400 HU, builds the 3D surface, screenshots to check it, reports volume in mL. One sentence → a five-module workflow. |
| 4 | `Now show me the bones instead` | Volume rendering with a bone preset, camera to anterior, verified by screenshot. |
| 5 | `Run TotalSegmentator on this` *(if installed)* | 100+ labelled organs. Then: `Hide everything except the heart and aorta` → it lists segments and toggles precisely. |
| 6 | `Measure the widest part of the aorta` | It will **decline to diagnose** and offer to measure instead — show the guardrail on purpose. |

Recovery lines if something misbehaves: *"That's the agent self-correcting — watch it screenshot,
see the problem, and retry"* is a feature, not an excuse. It is also true.

## Architecture

```
RadAssistant.py            Slicer module: chat UI, settings, event rendering (Qt main thread)
radassistant_lib/
  agent.py                 Claude Messages API streaming tool-use loop  (worker thread)
  bridge.py                Thread bridge: tool calls → main thread, UI events → main thread
  tools.py                 24 typed tools (JSON schema + implementation)
  context.py               Scene inventory injected into each user turn
  skills.py                SKILL.md discovery + progressive disclosure
  voice.py                 Optional offline dictation (faster-whisper)
skills/*/SKILL.md          Workflow knowledge, loaded on demand by the model
```

The agent loop: user message + scene context → Claude (adaptive thinking) → tool calls → executed on
the Qt main thread → results (text **and images**) → back to Claude → repeat until it answers.

## Tool surface

**See & navigate** `get_scene_overview` · `take_screenshot` · `set_layout` · `center_views` ·
`rotate_3d_view` · `jump_to_position` · `jump_to_segment`
**Load** `load_sample_data` · `load_file` · `import_dicom_folder`
**Display** `set_window_level` (lung/bone/soft-tissue/brain/liver/mediastinum presets) ·
`enable_volume_rendering`
**Segment** `threshold_segmentation` · `filter_segment_islands` · `run_total_segmentator` · `list_segments` ·
`set_segment_visibility` · `set_segment_color` · `highlight_segment` · `show_segmentation_3d`
**Measure** `measure_segment_volumes` · `measure_distance` · `place_point`
**Extend** `read_skill` · `execute_python` *(human approval required)*

## Adding a skill

Create `~/.radassistant/skills/my-workflow/SKILL.md`:

```markdown
---
name: my-workflow
description: One line — this is what the model matches against.
---
Step-by-step instructions for the model, in plain English.
Name the exact tools and parameters. Say what to verify and what to warn the user about.
```

Restart the module. It appears in the system prompt automatically; the body is only loaded when the
model decides it is relevant.

## Privacy

Screenshots and your prompts go to the Anthropic API. Voice, if enabled, is transcribed **locally**
and never leaves the machine. For real patient data you need a BAA and an appropriate deployment —
demo with anonymized or public datasets.

## Licence

MIT.
