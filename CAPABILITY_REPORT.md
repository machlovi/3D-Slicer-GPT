# RadAssistant DeepAgent — Capability Report

*Status review · 2026-07-27 · covers the in-process (live) deep-agent that ships as the `RadAssistantDeep` Slicer module.*

This report is grounded in the actual code, not the design docs. Where the running
system differs from what the prompts/README claim, that difference is called out —
those are exactly the places we are lagging.

---

## 1. What it is, in one paragraph

RadAssistant DeepAgent is a LangChain **DeepAgents** orchestrator that drives 3D
Slicer for a radiologist/researcher. It plans with a todo list, calls **47
validated Slicer tools**, follows **skill playbooks**, keeps a **persistent
workspace + memory**, and its LangGraph checkpointer makes the whole thread
**resumable across a Slicer restart**. It is backend-agnostic (Ollama / OpenAI /
Anthropic). The doctrine is *orchestrate validated tools, never improvise clinical
logic; measure, never estimate; describe, never diagnose.*

The engine (`engine/radassistant_lib/tools.py`) is the single source of truth for
Slicer tools; the deep layer (`deep/radassistant_deep/`) wraps them as LangChain
tools, adds planning/memory/subagents/safety, and the Slicer module
(`deep/slicer_module/RadAssistantDeep/`) is the panel.

---

## 2. Live configuration (what actually runs in the panel)

From `RadAssistantDeep.py` → `AgentConfig`:

| Setting | Live value | Note |
|---|---|---|
| model | user field | Ollama / OpenAI / Anthropic spec |
| vision | user checkbox | enables screenshot-as-image |
| approval_mode | user combo | manual / accept / auto |
| skills_dir | `engine/skills` | 47 skills |
| **subagents_enabled** | **`False`** | specialist roster is **OFF** live (see §7) |
| tool surface | 47 engine tools | + memory tools + deepagents built-ins |

---

## 3. Tool surface — 47 tools (all live)

**Data & navigation (11)** — `get_scene_overview`, `load_sample_data`,
`load_file`, `import_dicom_folder`, `list_dicom_database`, `load_dicom_patient`,
`set_layout`, `set_window_level`, `jump_to_position`, `jump_to_segment`,
`center_views`.

**Segmentation — create/edit (11)** — `threshold_segmentation`,
`filter_segment_islands`, `smooth_segment`, `grow_shrink_segment` (uniform **and**
anisotropic RT-style margins), `merge_segments`, `delete_segments`, `clear_scene`,
`list_segments`, `set_segment_visibility`, `set_segment_color`, `highlight_segment`.

**AI segmentation (4)** — `run_total_segmentator` (100+ CT / `total_mr` /
focused tasks), `run_monai_auto3dseg` (CT **and** MR pretrained models),
`run_nnunet` (the user's own trained model), `show_segmentation_3d`.

**Quantification (5)** — `measure_segment_volumes`, `measure_segment_statistics`
(mean/median/min/max/std HU), `extract_radiomics` (full PyRadiomics: shape,
first-order, GLCM/GLRLM/GLSZM/GLDM/NGTDM), `compare_segments` (Dice / Jaccard /
Hausdorff), `measure_distance`.

**Registration & longitudinal (2)** — `register_volumes` (rigid/affine/bspline,
**off the main thread**), `compare_studies` (registers prior→current + builds a
subtraction change-map, off-thread).

**Radiotherapy / vessels (2)** — `compute_dvh` (DVH + V/D metrics),
`extract_vessel_centerline` (length + per-point radius/diameter).

**Export / interop (5)** — `export_dicom_seg`, `export_dicom_sr` (TID 1500),
`export_segmentation_model` (STL/OBJ), `export_markups` / `import_markups` (CSV).

**3D / markups / misc (5)** — `enable_volume_rendering`, `rotate_3d_view`,
`take_screenshot`, `place_point`, plus skills access `read_skill` / `list_skills`.

**Escape hatch (1)** — `execute_python` (approval-gated, circuit-broken).

Plus deepagents built-ins live: `write_todos`, workspace filesystem
(`ls`/`read_file`/`write_file`/`glob`/`grep`), `task` (subagent spawn), and the
memory tool `record_learning`.

---

## 4. Integrated Slicer extensions

An extension is "integrated" when a dedicated tool wraps its validated API and
detects/reports it cleanly.

| Extension | Tool(s) | What it delivers | Maturity |
|---|---|---|---|
| **SlicerTotalSegmentator** | `run_total_segmentator` | 100+ structure CT auto-seg, MR, focused tasks | **Strong** — has version-aware detection |
| **MONAIAuto3DSeg** | `run_monai_auto3dseg` | CT + MR pretrained models (incl. some lesion) | Good — off-thread |
| **SlicerNNUnet** | `run_nnunet` | run a site-specific trained nnU-Net | Good — off-thread; needs a model folder |
| **SlicerRadiomics** (PyRadiomics) | `extract_radiomics` | full radiomic signature → CSV | Good |
| **SlicerVMTK** | `extract_vessel_centerline` | centerline length + radius | Good |
| **SlicerRT** | `compute_dvh` | DVH + V/D dose metrics | Good |
| **QuantitativeReporting** (dcmqi) | `export_dicom_seg`, `export_dicom_sr` | standards DICOM SEG / SR for PACS | Partial — SR export is version-dependent (falls back to "do it in the UI") |

**Core Slicer capabilities used with no extension:** BRAINSFit registration,
subtraction change-maps, SimpleITK Dice/Jaccard/Hausdorff, all Segment Editor
effects (threshold, islands, smoothing, margin, logical), DICOM import/db, volume
rendering, closed-surface mesh export. **7 extensions integrated; the rest of the
workflow rides on Slicer core.**

---

## 5. Where it genuinely helps a researcher (achieved)

- **Automated anatomy on demand** — "segment the liver and spleen and give me
  their volumes" runs TS (or a threshold workflow for lung/bone), cleans islands,
  and reports **measured** mL — never estimated.
- **Quantitative imaging / radiomics** — one call yields a full PyRadiomics
  feature CSV over a defined ROI; the `radiomics-signature` skill encodes the
  recipe. Directly supports radiomics research pipelines.
- **Segmentation QA** — `compare_segments` gives Dice/Jaccard/Hausdorff to grade
  an AI mask against ground truth or compare two methods — a real research need.
- **Longitudinal / interval-change** — `compare_studies` registers baseline→
  follow-up and produces a subtraction map side-by-side, off-thread so the UI
  stays live.
- **Radiotherapy dosimetry** — DVH + V/D metrics per structure with anisotropic
  PTV margins available.
- **Reproducibility & handoff** — writes reports/artifacts to a workspace
  filesystem, persists learnings, and **resumes the exact thread after a restart**
  (todos + history survive).
- **Honest instrumentation** — PHI egress is code-blocked; diagnostic-sounding
  text gets a research disclaimer appended; volumes/HU always come from validated
  modules.

---

## 6. Safety & governance (implemented in code, not just prompt)

- **Approval matrix** (`policy.py`): read-only/reversible never ask; `manual` asks
  for heavy/code/irreversible/PHI; `accept` asks only for irreversible + PHI;
  `auto` never asks. Compiled into deepagents `interrupt_on`.
- **PHIScrubber**: flags MRN-like runs, dates, local paths, accession IDs, and
  distinctive scene-node names on anything egress-classed — **denied, not asked**.
- **DiagnosisGuard**: appends the research-use disclaimer when output trips
  diagnostic patterns (malignant/benign/metastasis/stage…).
- **execute_python circuit breaker**: stops after repeated failures and redirects
  to dedicated tools.

This governance layer is a real strength and is largely provider-independent.

---

## 7. Where we are lagging (be honest here)

**A. `ensure_slicer_extension` does not exist in the live agent.**
The system prompt (Principle 0) and the entire `slicer-extensions` skill instruct
the agent to *"call `ensure_slicer_extension` FIRST."* But the live tool set is
exactly the 47 engine tools, and that tool is **only defined in the offline mock
path** (`slicer_tools.py`). Live, calling it returns *"unknown tool."* So:
  - the agent is prompted toward a capability it doesn't have live;
  - **extension auto-install is not implemented at all** — even the mock only
    *detects*. In the live panel, a missing extension yields a helpful "install it
    from the Extensions Manager" message, and the human installs + restarts.
  - This is the crux of the earlier "can the agent install a module on need,
    restart, and resume?" question — today: **no**, only detect-and-instruct.
  *Fix options:* add a real `ensure_slicer_extension` engine tool (detect →
  optional install via ExtensionsManagerModel → tell the user to restart), or
  remove the instruction + skill from the live prompt so it stops promising it.

**B. The specialist subagents are built and tested but OFF live.**
`scene-explorer`, `segmentation-specialist`, and the adversarial `verifier` all
exist with isolated tool subsets and good prompts — but the panel sets
`subagents_enabled=False`. So the **verifier quality lever isn't running by
default**, and only the generic general-purpose subagent is available. Likely
disabled for local-model cost/latency; worth a toggle + a measured cost check.

**C. TotalSegmentator blocks the UI.**
`register_volumes`, `compare_studies`, MONAI and nnU-Net run off-thread, but
`run_total_segmentator` **freezes Slicer** until done — seconds on GPU, minutes to
tens of minutes on CPU. On the dev box (RTX 3050 Ti, 4 GB) this is a real UX cliff.
Moving TS off-thread (or chunking with progress) is the highest-value UX fix.

**D. Local-model reliability.**
The observed hallucinations (inflated skill counts, malformed output) come from
small local models (e.g. gemma) not honoring the prompt-level honesty/format
rails. We added `list_skills` grounding + plain-text formatting rules, but these
are probabilistic. Hosted models (Anthropic/OpenAI) behave; the trade-off is that
serious model quality currently means leaving the machine (egress is blocked, but
the *model* is remote). No local model in the sweet spot yet has been pinned.

**E. Test suite tests the wrong path.**
Tests run against `MockSlicerSession` + the offline `slicer_tools.py` surface,
which has **diverged** from the live engine path (that's how the
`ensure_slicer_extension` mismatch went unnoticed). We have little automated
coverage of the actual in-process registry the panel uses.

**F. Smaller gaps.**
  - License-gated TS tasks (tissue_types, vertebrae_body, liver_segments, face,
    brain_structures) aren't handled — they just fail without a key.
  - DICOM SR export depends on a QuantitativeReporting version exposing
    `createDICOMSR` from Python; otherwise it degrades to a manual-UI instruction.
  - The 47-skill library is padded: ~9 are validated workflow playbooks tied to
    our tools; ~3 are `my-*` templates; the remainder are imported Slicer
    tutorial/reference skills (several multilingual) — useful as reference, but
    not all are agent-validated, which dilutes `list_skills`.
  - Panel rendering was just reworked (batched `setMarkdown`); **pending an
    in-Slicer restart test** to confirm the speed/formatting fix.

---

## 8. Scorecard

| Area | State |
|---|---|
| Tool breadth (seg / measure / register / export) | 🟢 Strong (47 tools) |
| AI segmentation (TS / MONAI / nnU-Net) | 🟢 Strong |
| Quantification & radiomics | 🟢 Strong |
| Longitudinal / registration | 🟢 Good (off-thread) |
| Safety / PHI / diagnosis rails | 🟢 Strong |
| Memory / resumability | 🟢 Good |
| Extension **auto-install / self-heal** | 🔴 Missing live (detect-only; tool absent) |
| Subagents / adversarial verify (live) | 🟠 Built but disabled |
| Heavy-op responsiveness (TotalSegmentator) | 🟠 UI-blocking |
| Local-model robustness | 🟠 Fragile |
| Test coverage of the live path | 🟠 Weak (tests hit mock path) |
| Panel rendering | 🟡 Fixed, pending restart verification |

---

## 9. Recommended next moves (by leverage)

1. **Reconcile the extension story** — either implement a real live
   `ensure_slicer_extension` (detect → install → prompt restart) or strip the
   promise from the prompt/skill. (Removes the most visible "it lied" failure.)
2. **Get TotalSegmentator off the main thread** — biggest UX win.
3. **Flip subagents on with a measured budget** — turn the adversarial verifier
   into the default check for multi-step tasks.
4. **Add live-path tests** — exercise the real in-process registry so mock/live
   drift can't hide again.
5. **Pin a known-good local model** (tool-use capable) and document it, so the
   offline story stops depending on gemma-class models.
