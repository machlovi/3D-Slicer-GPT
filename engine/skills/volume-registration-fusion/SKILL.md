---
name: volume-registration-fusion
description: Align/co-register/fuse two loaded volumes so they overlay in the same space. Use for "fuse the PET onto the CT", "co-register the ultrasound with the CT", "align the prior to the current", "overlay MR on CT", "they weren't acquired on the same table". Actually RUN register_volumes — don't just describe it.
---

# Registering & fusing two volumes

When two volumes are in the scene and the user wants them aligned/overlaid, **perform the
registration** — do not describe the concept and stop.

## Workflow
1. `get_scene_overview` to confirm BOTH volumes are present (see scene-inventory-first). Name the
   **fixed** (reference — usually the CT / current study) and the **moving** volume (PET / US / prior).
2. `register_volumes(fixed=<ref>, moving=<other>)` — start **rigid** for cross-modality PET/CT or
   MR/CT fusion and different-table acquisitions; escalate to affine/deformable only if asked or if
   rigid clearly under-aligns.
3. Show the result as a fusion: set a layout that overlays foreground on background (foreground =
   moving, with opacity ~0.5) so the user sees both on the same lesion.
4. Report what you aligned to what and the transform type used.

## Modality notes
- **PET → CT**: rigid, CT fixed. Fusion colour map (e.g. PET-Heat) on the foreground.
- **US → CT/MR**: rigid first; ultrasound geometry is awkward, so state the limitation rather than
  forcing a deformable fit.
- **Prior → current** (same modality, interval change): register, then subtract — this overlaps with
  the study-comparison skill; prefer `compare_studies` when the ask is "did it grow/shrink".

## Guardrails
- If only ONE volume is loaded, say precisely which one is missing and how to load it — do not clear
  the scene or reload samples to "start over".
- Registration is a native tool (`register_volumes`); don't script it with `execute_python`.
