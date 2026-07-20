---
name: lung-segmentation
description: SEGMENT or MEASURE lung volume from a chest CT (HU thresholding + island cleanup). Use ONLY for "segment the lungs" or "measure/quantify lung volume" — NOT for "show/render/visualize the lungs", which is enable_volume_rendering (a fast display preset, no segmentation).
---

# Lung segmentation and volumetry (CT)

Goal: from a chest CT, produce a lung segmentation the radiologist can see in 3D, plus volumes in mL.

## Physiology sanity bounds — use these to catch contamination
- One lung ≈ **1.5–3 L**; both lungs together ≈ **4–6 L** (up to ~7 L in large/hyperinflated patients).
- If a segment you are calling "lung" is **> ~7 L, it is contaminated with EXTERNAL AIR** — do not
  report it as a lung volume. Clean it or switch to TotalSegmentator.

## Steps

1. Confirm a chest CT is loaded (`get_scene_overview`); if not, offer to load `CTChest`.
2. Lung window so the user sees your work: `set_window_level` preset `"lung"`.
3. Threshold air-filled lung at **−1000 to −400 HU**: `threshold_segmentation` lower −1000, upper −400,
   `segment_name: "Lungs"`, `keep_largest_island: false`. This also catches trachea/bronchi **and air
   OUTSIDE the patient** — say so.
4. Separate the lungs from external air with dedicated tools — **never write Python for this**:
   - `filter_segment_islands` `operation: "split_to_segments"` to break the threshold into islands,
     then `measure_segment_volumes` to size them.
   - **CRITICAL — the LARGEST island is almost always EXTERNAL AIR, not a lung.** It surrounds the
     patient and fills the scanner bore and is typically **> 8 L**. **Do NOT "merge the two largest
     islands"** — that merges external air with one lung and yields a nonsense ~15–25 L. The real
     lungs are the largest islands whose size is *physiologically plausible* (~1.5–3 L each).
     **DELETE the > ~7 L blob (external air) with `delete_segments` — do not just hide it.** Hiding
     leaves it in the volume total AND it still slows the 3D mesh build; deleting fixes both. Then
     `merge_segments` the two lung-sized islands if a single "Lungs" segment is wanted, and
     `filter_segment_islands` `"remove_small"` (min_size_ml 5) for speckle.
   - If you cannot cleanly separate them this way, **STOP and offer `run_total_segmentator`** (below).
     Do not hand-roll external-air removal in `execute_python`.
5. Show it (only if the user wants 3D): `show_segmentation_3d`, then `rotate_3d_view` `anterior`.
6. Verify with `measure_segment_volumes` and check against the sanity bounds above. If you can see,
   also `take_screenshot` the 3d view. **If the 3D looks like a box, or you appear to be INSIDE it,
   the segment still contains external air (a box around the patient) — this is a DATA problem, not a
   rendering bug. Do NOT reposition the camera or rebuild the surface with `execute_python`.** Clean
   the segment (remove the external-air island) or use TotalSegmentator, and tell the user.

## Reporting
Lead with the number, then the caveat — and sanity-check it:

> Both lungs ≈ **4,180 mL** total (left 1,980 / right 2,200). Threshold −1000/−400 HU, so airways are
> included; this is a rough total lung volume, not a lobar analysis. Want lobes via TotalSegmentator?

If your number is **> ~7 L**, say so plainly: *"that figure includes air outside the patient — it is
not a valid lung volume,"* and offer the TotalSegmentator path.

## If TotalSegmentator is installed
`run_total_segmentator` `task: "total"` gives anatomically clean, labelled lungs (lobes) and avoids
the external-air problem entirely. It takes a few minutes — warn about the wait. This is the
recommended path whenever thresholding can't cleanly isolate the lungs.
