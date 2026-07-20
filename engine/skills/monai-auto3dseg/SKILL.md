---
name: monai-auto3dseg
description: Run MONAI Auto3DSeg AI auto-segmentation via run_monai_auto3dseg. Use when the user wants automatic organ/lesion segmentation and the case is MR (brain, prostate) or they ask for MONAI, or when TotalSegmentator's CT-focused tasks don't fit. Always pick the model that matches the modality (CT vs MR) and target organs, and warn it runs in the background (can take seconds on GPU, minutes on CPU). Choose the right model BEFORE calling.
---

# MONAI Auto3DSeg (AI auto-segmentation)

`run_monai_auto3dseg` wraps the MONAIAuto3DSeg extension, which ships **dozens of pretrained models**
across **CT** (abdominal organs, bones, vessels, heart, lungs) and **MR** (brain, prostate), plus some
**lesion/tumor** models. It complements the other AI tools:

- **`run_total_segmentator`** — best for whole-body / many-organ **CT**; has its own task catalog.
- **`run_nnunet`** — the user's **own trained** model.
- **`run_monai_auto3dseg`** — broad pretrained coverage, **notably MR**, and lesion models TS lacks.

It runs inference in a **background process** so the Slicer UI stays responsive (GPU: often <1 min;
CPU: several minutes). The tool pumps the event loop until it finishes.

## STEP 1 — pick the right model (do this first)

The model id must match the **modality and anatomy**. Do NOT run a CT model on an MR (or vice-versa).

1. If the user hasn't named a model, call `run_monai_auto3dseg` with **no `model`** — it returns the
   list of available model ids (and the default). Read that list.
2. Match to the case:
   - **CT abdomen / whole-body organs** → a TotalSegmentator-style or abdominal-organs CT model
     (or just use `run_total_segmentator`, which is purpose-built for this).
   - **MR brain** → a brain MR model. **MR prostate** → a prostate MR model.
   - **A lesion/tumor** → a lesion-specific model if one exists for that site+modality.
3. Confirm the chosen model + modality with the user in one line, then call the tool with that `model`.

## STEP 2 — set expectations, then run

- State: which model, GPU vs CPU (CPU is minutes), and that the UI stays usable while it runs.
- Call `run_monai_auto3dseg(model=<id>, volume_name=<vol if ambiguous>)`.
- On a machine with no CUDA it runs on CPU automatically (slower) — mention it; `force_cpu=true` forces CPU.

## If it fails or returns 0 segments
- **0 segments** → almost always a **modality/model mismatch** (CT model on MR, or the volume doesn't
  cover the target anatomy). Re-check the model choice; do not present an empty result as success.
- **Extension missing** → the tool returns install guidance (Extensions Manager → MONAIAuto3DSeg →
  restart). Do NOT pip-install anything yourself.
- **First run of a model** downloads weights (hundreds of MB) — that's a one-time delay, not a hang.

## Safety
This tool produces contours only. RadAssistant **measures and describes** them (volumes, statistics)
— it does **not** diagnose. After segmentation, offer `measure_segment_volumes` / `measure_segment_statistics`
/ `show_segmentation_3d`, and QA against a reference with `compare_segments` (Dice/Hausdorff).
