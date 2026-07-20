---
name: radiotherapy-dvh
description: Compute radiotherapy dose-volume histograms (DVH) and dose metrics (V-metrics, D-metrics) for organs-at-risk and targets via compute_dvh. Use when the user has an RT dose volume + structure segmentation and asks about dose to a structure, DVH, coverage, or OAR dose. QUANTIFY dose only — never judge whether the plan is acceptable or safe; that is the radiation oncologist's call.
---

# Radiotherapy DVH & dose metrics

`compute_dvh` wraps SlicerRT's `vtkSlicerDoseVolumeHistogramModuleLogic` to build a **dose-volume
histogram** for each segment against an **RT dose volume**, and to compute:

- **V-metrics** — the volume (absolute or %) of a structure receiving **at least** a given dose
  (e.g. "V20Gy of the lung").
- **D-metrics** — the dose received by a given **volume** of a structure (e.g. "D2cc of the cord",
  "D95% of the PTV").

Requires the **SlicerRT** extension. It runs off the main thread; the DVH over an oversampled
labelmap can take a little time.

## Inputs to confirm first
1. **The RT dose volume** (in Gy) — usually loaded from an RTDOSE DICOM object. If it's not obvious
   which loaded volume is the dose, ask.
2. **The structure set** — a segmentation of the OARs / targets (from an RTSTRUCT, TotalSegmentator,
   MONAI, or manual). One structure or all.

## What to report
- The DVH is produced into SlicerRT's results table; report the requested **V/D metrics with units**
  (Gy, cc, %). Lead with the number the user asked for.
- You MAY cite a **published constraint as reference** if asked (e.g. QUANTEC-style values), clearly
  labelled as a guideline reference — but do **NOT** state whether *this* plan passes/fails or is
  "safe". Hand the numbers to the clinician.

## Guardrails
- **Measure, don't judge.** "The cord D2cc is 43 Gy" is fine; "the plan is safe / unsafe / acceptable"
  is not — that determination belongs to the radiation oncologist.
- **Sanity-check units.** A "dose" volume with values in the thousands is likely cGy, not Gy — flag it
  rather than reporting nonsensical Gy numbers.
- **Missing extension** → the tool returns install guidance (Extensions Manager → SlicerRT → restart).
  Never pip-install.
- To build the structures first: `run_total_segmentator` / `run_monai_auto3dseg` for OARs, or
  `import` an RTSTRUCT; add PTV margins with `grow_shrink_segment` (uniform or anisotropic).
