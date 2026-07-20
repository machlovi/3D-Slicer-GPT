---
name: slicer-extensions
description: Detect and load Slicer extensions (TotalSegmentator, PyRadiomics/SlicerRadiomics, VMTK, MONAI, nnInteractive) before using tools that need them. Use whenever a task needs an AI segmentation or radiomics tool, or a tool reports an extension is missing/not detected.
---

# Using Slicer extensions

Several validated tools depend on a Slicer **extension** being loaded:

| Task the user asks for | Tool to use | Extension it needs |
| --- | --- | --- |
| Auto-segment anatomy (organs, brain, lungs, etc.) | `run_total_segmentator` | `TotalSegmentator` |
| Radiomics feature extraction | `extract_radiomics` | `SlicerRadiomics` |
| Vessel / aorta segmentation helpers | (VMTK tools) | `SlicerVMTK` |
| MONAI auto-segmentation | (MONAI tools) | `MONAIAuto3DSeg` |
| Interactive AI segmentation | (nnInteractive tools) | `NNInteractive` |

## The rule

**Before calling an extension-dependent tool, call `ensure_slicer_extension` with the
extension name.** It checks whether the extension is already loaded and, if not,
loads or installs it. This is also how you resolve an "extension not found" or
"module not detected" error — the extension may be installed but you just need
to confirm it is loaded.

**NEVER hand-write `execute_python` to `import` a package or install an
extension.** That is fragile, trips the execute_python safety circuit breaker,
and bypasses the validated path. Use `ensure_slicer_extension`, then the
dedicated tool.

## Workflow

1. The user asks for something that needs an extension (e.g. "segment the brain
   structures", "run TotalSegmentator", "extract radiomics features").
2. Call `ensure_slicer_extension` with the matching extension name from the
   table above (e.g. `ensure_slicer_extension("TotalSegmentator")`).
3. Read its result:
   - **"is loaded" / "is available"** → proceed to the dedicated tool
     (e.g. `run_total_segmentator`).
   - **"Installed ... RESTART Slicer"** → the extension was just installed but a
     Slicer restart is required before its module loads. Tell the user plainly:
     "I installed the *TotalSegmentator* extension — please restart 3D Slicer,
     then ask me again." Do **not** try to proceed this session.
   - **"Could not auto-install" / "Install it manually"** → tell the user how to
     install it (View ▸ Extensions Manager, search for the extension, install,
     restart), and offer an alternative if one exists (e.g. threshold-based
     segmentation instead of TotalSegmentator).
4. Only after the extension is confirmed loaded, run the dedicated tool and then
   verify the result with `measure_segment_volumes` / `list_segments`.

## Do not

- Do not repeatedly retry `execute_python` when a tool reports a missing
  extension — call `ensure_slicer_extension` instead.
- Do not claim a segmentation succeeded until you have verified it with a
  measurement tool.
- Do not pretend an extension is present if `ensure_slicer_extension` said a
  restart or manual install is needed — relay that honestly to the user.
