---
name: bone-3d-view
description: Produce a 3D bone/skeleton view from a CT — either fast volume rendering or a real bone segmentation for measurement and 3D printing.
---

# 3D bone visualization (CT)

Two routes. Pick by what the user actually wants.

## Route A — "just show me the bones in 3D" (fast, a few seconds)

Use volume rendering. Nothing is segmented; it is a display effect.

1. `enable_volume_rendering` with `preset: "CT-Bone"` (for a contrast CT chest, `CT-Chest-Contrast-Enhanced`
   also reads well).
2. `set_layout` to `3d_only`, then `rotate_3d_view` to `anterior`.
3. `take_screenshot` with `view: "3d"` and look. If the render is a grey fog, the preset does not
   match the data (e.g. it is an MRI, not a CT) — say so instead of insisting it worked.

## Route B — "I want to measure it / print it / segment it"

Threshold-based segmentation produces a real surface mesh.

1. `set_window_level` with `preset: "bone"` so the user sees what you are thresholding.
2. `threshold_segmentation`: cortical bone is roughly **+300 to +3000 HU**. Name the segment
   `"Bone"`, colour it bone-white (`red: 0.95, green: 0.93, blue: 0.87`), and set
   `keep_largest_island: true` **only** if the user wants a single connected structure (e.g. one
   femur). For a whole skeleton leave it off — islands would delete every bone but the largest.
3. `show_segmentation_3d`, `rotate_3d_view` → `anterior`, `take_screenshot` (`view: "3d"`).
4. If asked for size: `measure_segment_volumes`, or `measure_distance` between two RAS points.

## Caveats to state, not hide

- Metal implants and contrast in vessels both exceed 300 HU and will appear as "bone".
- Thin trabecular bone and the skull base are often under-segmented at a 300 HU floor. If the user
  cares about those, suggest lowering to ~150 HU and re-running, and show the difference.
