---
name: musclemap
description: Run MuscleMap (SlicerMuscleMap) whole-body muscle + bone AI segmentation for musculoskeletal MUSCLE analysis — muscle volume and intramuscular fat / composition on T1 / T2 / Dixon / fat-fraction MRI or CT. Use when the user wants MUSCLE quantification specifically. Confirm modality + warn about the wait FIRST, and make sure the extension's dependencies are installed once. NOT for general multi-organ CT anatomy (use total-segmentator) or a single structure (use thresholding).
---

# MuscleMap (whole-body muscle segmentation)

MuscleMap is a community/consortium tool that runs a deep-learning model to label the whole body's
**muscles and bones** (~99 structures) so you can quantify **muscle volume** and **intramuscular fat /
composition**. It is the right tool when the question is about *muscle* — sarcopenia/atrophy research,
fat infiltration, muscle volumetry across visits — on **quantitative MRI (T1, T2, Dixon, fat-fraction)
or CT**. It is delivered here through the `run_musclemap` tool, which drives the SlicerMuscleMap
`WholeBodyMuscleSegmentation` module (it shells out to the `mm_segment` model).

Like TotalSegmentator it is **HEAVY and blocks Slicer's UI** while the model runs (the segmentation
runs as a subprocess the module waits on). So set expectations before you start — don't fire
`run_musclemap` on first mention.

## STEP 1 — clarify + check readiness first (don't skip)

1. **Is muscle really the target?** If they want general CT organs → `total-segmentator`/`run_total_segmentator`.
   If they just want to *see* one structure → thresholding / volume rendering (seconds, no freeze).
   Use MuscleMap when they want **muscle volume or fat/composition**.
2. **Modality** — MuscleMap handles T1 / T2 / **Dixon** / **fat-fraction** MRI and CT. The Slicer
   module segments **whole-body** (there's no region picker in the module — it does the whole field of
   view). Confirm the loaded image is one of those and covers the muscles of interest.
3. **Warn about the wait.** The model blocks the UI while it runs — seconds-to-minutes on a GPU,
   longer on CPU. Say roughly how long based on the machine, and get an OK.
4. **Dependencies installed?** The first time, MuscleMap needs **PyTorch** (Slicer's *PyTorch Util*
   module) **and** the **MuscleMap package** (the `mm_segment` CLI). If `run_musclemap` reports they're
   missing, tell the user to install them **once** via **Modules ▸ Segmentation ▸ MuscleMap
   (WholeBodyMuscleSegmentation) ▸ "Install MuscleMap dependencies"** — that button pins numpy/torch so
   it can't break Slicer's Python. **Never pip-install it by hand.**

## STEP 2 — run it

Call `run_musclemap` with the image (`volume_name`; omit if only one is loaded).
- `force_cpu: true` to force CPU if the GPU is unavailable/unwanted.
- `lower_overlap: true` uses a lower sliding-window overlap (75% vs 90%) — less VRAM and faster, a
  little coarser. **Try this first on a CUDA out-of-memory error** (common on small laptop GPUs), or
  fall back to `force_cpu: true`.

## STEP 3 — after it finishes

The result loads as a segmentation node ("MuscleMap…") with per-muscle labels and colors.
- `list_segments` to see the muscles/bones produced.
- `measure_segment_volumes` → **muscle volume** (report in mL/cc).
- `measure_segment_statistics` → **mean intensity per muscle**. On a **Dixon fat-fraction** map the
  mean value *is* the fat fraction (%); on T1/T2 higher signal in muscle suggests fat infiltration but
  is scanner-relative — say so, don't over-claim.
- `show_segmentation_3d` to render — **hide most segments first** (many structures) or it's slow.
- Sanity-check the numbers before reporting (a muscle "volume" that's implausibly large usually means
  the mask leaked into other tissue).

**Measure and quantify — never diagnose.** Report muscle volume, fat fraction, and interval change;
leave sarcopenia/atrophy/clinical calls to the clinician. For change across visits, register/compare
the studies and report the delta, not a verdict.

## When NOT to use MuscleMap
- General multi-organ CT anatomy (liver, lungs, bones, vessels) → `run_total_segmentator` (task `total`).
- MR organs / lesions → `run_monai_auto3dseg`.
- A single muscle/structure you only need to *see* → thresholding + `show_segmentation_3d`.
