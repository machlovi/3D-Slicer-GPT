---
name: dicom-rt-export
description: Export segmentations/contours as DICOM so they can go to a treatment-planning system or PACS. Use for "export these contours as DICOM-RT", "hand them to the planning system", "save as RTSTRUCT/DICOM SEG". Pick a sensible default output folder and export — don't stall asking for a folder.
---

# Exporting contours as DICOM (SEG / RT)

When the user asks to export contours for a planning system or PACS, **complete the export** with
sensible defaults rather than round-tripping on trivia.

## Defaults (don't stall on these)
- **Output folder**: default to `/tmp/dicom_rt` (or the run's working dir). Announce where you wrote
  it; only ask if the user explicitly wants a specific location.
- **Format**: "DICOM-RT / for the planning system" → **DICOM RTSTRUCT** semantics via the DICOM SEG
  export path; for PACS interchange a **DICOM SEG** object. If the user just says "DICOM-RT", pick the
  planning-system-appropriate export and state which you used — don't block on the SEG-vs-RTSTRUCT
  distinction unless they ask.

## Workflow
1. `get_scene_overview` / `list_segments` to confirm the segmentation and which segments to export.
2. `export_dicom_seg(segmentation=<node>, output_dir="/tmp/dicom_rt")` (or the RT export tool).
3. Report the output path, the number of structures written, and the format.

## Guardrails
- One clarifying question at most, and only if genuinely ambiguous — otherwise export with defaults
  and tell the user what you chose (they can redirect).
- Use the native export tool; don't hand-write DICOM with `execute_python`.
- Don't assert the contours are clinically acceptable — you export them; QA is the planner's job.
