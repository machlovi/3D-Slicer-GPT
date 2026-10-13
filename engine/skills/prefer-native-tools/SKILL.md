---
name: prefer-native-tools
description: Reach for the 47 native Slicer tools before execute_python. Use whenever tempted to script something — camera moves, thresholds, measurements, exports, layout. execute_python is a gated last resort (a circuit breaker blocks it); a native tool almost always exists and scores better.
---

# Prefer native tools over execute_python

There are 47 first-class tools. `execute_python` is heavy, approval-gated, and trips a circuit
breaker when overused — it is a **last resort**, not the default.

## Before scripting, map the intent to a native tool
| You want to… | Native tool (not Python) |
|---|---|
| See what's loaded | `get_scene_overview`, `list_segments` |
| Window/level, layout, center | `set_window_level`, `set_layout`, `center_views` |
| Rotate / snapshot the 3D view | `rotate_3d_view`, `take_screenshot` |
| Threshold / clean a segment | `threshold_segmentation`, `filter_segment_islands`, `smooth_segment` |
| Grow/shrink (margins) | `grow_shrink_segment` |
| Measure | `measure_segment_volumes`, `measure_segment_statistics`, `measure_distance` |
| AI segment | `run_total_segmentator`, `run_monai_auto3dseg` |
| Register / fuse | `register_volumes` |
| DVH | `compute_dvh` |
| Export | `export_segmentation_model`, `export_dicom_seg` |
| Load / import | `load_file`, `import_dicom_folder`, `load_dicom_patient`, `load_sample_data` |

## When Python is genuinely the only path
- `rotate_3d_view` covers cardinal directions only. For an **arbitrary angle** (e.g. "rotate 30°"),
  that is a real gap — state it, offer the nearest cardinal view via `rotate_3d_view`, and only fall
  back to a single minimal `execute_python` call if the user insists on the exact angle. (Known tool
  gap: `rotate_3d_view` could take an explicit `angle`.)
- Never use `execute_python` to do something a listed tool already does — it fails the rubric and may
  be blocked mid-run.
