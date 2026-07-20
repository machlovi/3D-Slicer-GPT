---
name: radiomics-signature
description: Characterize a lesion or ROI with quantitative radiomics — segment it, verify the segmentation, then extract shape/intensity/texture features (PyRadiomics). Use for "get the radiomic signature / features of this lesion".
---

# Radiomic signature of a lesion (segment → verify → extract)

Goal: turn a region of interest into a reproducible quantitative feature vector a researcher can use. This mirrors the validated segment→radiomics workflow from the mAIstro paper, but with a verification step before extraction — radiomics on a wrong mask is worse than no radiomics.

## Prerequisites
- A scalar volume (the image) is loaded.
- The **SlicerRadiomics** extension is installed (provides the PyRadiomics engine). If `extract_radiomics` reports it's missing, tell the user to install it from the Extensions Manager and restart — do not try to work around it.

## Steps

1. Confirm the image and any existing segmentation with `get_scene_overview`.
2. Get the ROI segmented. In order of preference:
   - If the target is a standard anatomical structure and TotalSegmentator is available → `run_total_segmentator`, then use the relevant segment.
   - Otherwise create it: `threshold_segmentation` for an intensity-defined lesion, or `segment_editor_activate`/hand-off for a lesion the radiologist should draw. **For anything the radiologist cares about clinically, let them draw or correct the boundary** — radiomics is only as good as the contour.
3. **VERIFY before extracting** — this is the step mAIstro skips and we don't:
   - `measure_segment_statistics` on the segment. Sanity-check the volume and mean intensity are physically plausible for what it's supposed to be (e.g. a lung nodule is a few hundred mm³ and low-ish HU, not 5 L).
   - If a screenshot backend is available, `take_screenshot` and look; otherwise rely on the statistics. If the numbers look wrong, fix the segmentation and re-check — do not extract from a bad mask.
4. Extract: `extract_radiomics` with the segment and the reference volume.
   - Default to `feature_classes` = all (shape, firstorder, glcm, glrlm, glszm, gldm, ngtdm) and `image_types` = ["Original"].
   - **Modality matters:** for **MRI** set `normalize: true`; for **CT** leave `normalize: false` (HU are already calibrated). Say which you used.
   - Only add `image_types` like Wavelet/LoG if the user asks — they multiply the feature count and the runtime.
5. Report: lead with the segment's volume and mean intensity (from step 3), then say how many features were extracted and where the CSV was saved. Do NOT read out 100 feature values — summarize (shape + a few first-order), and offer the CSV.

## Reproducibility & honesty
- State the exact settings you used (bin width, normalize, image types) — radiomics is only comparable across cases when these match. The default bin width is 25.
- These are **quantitative descriptors, not a diagnosis.** Never interpret a feature value as benign/malignant. If asked, offer to extract the same signature from a comparison lesion instead.
- If the user is building a cohort (many cases), tell them this tool does one ROI at a time interactively; batch radiomics across a dataset is the job of an offline pipeline (e.g. a mAIstro-style runner), not the in-viewer assistant.
