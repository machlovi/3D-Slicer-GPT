---
name: study-comparison
description: Compare two things quantitatively — a PRIOR vs CURRENT study (interval change via registration + subtraction), or two SEGMENTATIONS of the same structure (agreement/QA via Dice, Jaccard, Hausdorff). Use for "compare to the prior / baseline", "did it grow/shrink", "how well does the AI segmentation match the manual one", "is auto-seg accurate".
---

# Comparing studies and segmentations

Two distinct jobs — pick the right tool.

## A. Prior vs current study (interval change) → `compare_studies`
For "compare with the prior", "what changed since the baseline", follow-up reading.

1. Make sure BOTH studies are loaded (`get_scene_overview`). If only one is, ask the user to load
   the prior, or load a sample.
2. Call `compare_studies` with `current_volume` (follow-up) and `prior_volume` (baseline). Optional
   `registration`: `rigid` (default, fast) / `affine` / `bspline` (deformable, slow — warn first).
3. It rigidly aligns the prior to the current study and builds a **change map** (current − prior),
   shown side-by-side. Registration + subtraction run OFF the main thread, so the UI stays responsive
   — but a `bspline` run can still take minutes; tell the user before choosing it.
4. **Read the change map descriptively**: bright/dark regions are new or resolved findings. Measure
   them if asked (`measure_distance`, `place_point`, or segment + `measure_segment_volumes`). Never
   diagnose or call change "benign/malignant" — describe and measure only.
5. If registration fails (studies too different, different body regions), say so and offer `affine`.

## B. Two segmentations of the same structure (agreement / QA) → `compare_segments`
For "how well does the AI match the manual outline", "compare the two segmentations", auto-seg QA,
inter-reader agreement, or contour change between two segmentations of the same scan.

1. You need two segments on the same study (e.g. an AI result and a manual/ground-truth one, or a
   TotalSegmentator organ vs a thresholded one). Both are put on the reference volume's grid.
2. Call `compare_segments` with `segment_a`, `segment_b` (and `segmentation_a` / `segmentation_b` if
   they live in different segmentation nodes, `volume_name` for the grid).
3. It reports **Dice** (overlap; 1.0 = identical, >0.9 excellent, 0.8–0.9 good, <0.7 poor),
   **Jaccard/IoU**, and **Hausdorff** boundary distance in mm (worst-case + average gap).
4. Lead with the Dice and its grade, then the Hausdorff. Example: *"Dice 0.91 (excellent overlap);
   worst boundary gap 4.2 mm — the AI segmentation agrees closely with the manual one."*
5. Use this to sanity-check any AI segmentation (TotalSegmentator / MONAI) before trusting its volumes.

## When NOT to use these
- One segmentation, just want its size/HU → `measure_segment_volumes` / `measure_segment_statistics`.
- One study, want to characterize a lesion's texture → `extract_radiomics`.
- Just want to see two volumes side by side without a change map → `set_layout` `side_by_side`.
