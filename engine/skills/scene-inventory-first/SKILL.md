---
name: scene-inventory-first
description: ALWAYS check what is already loaded before asking the user for data or saying the scene is empty. Use for any request that names data implicitly — "what's loaded", "what am I looking at", "segment the lung", "measure the aorta", "fuse the PET onto the CT", "grab the T2 series" — where a volume/segmentation may already be in the scene. Prevents asking the user to supply data that is already present.
---

# Look before you ask — inventory the scene first

The most common failure is declaring "nothing is loaded" or asking the user to provide data that is
**already in the scene**. The scene the user is looking at is your working data.

## The rule
1. On any task that references data (a volume, a series, a structure, "this", "that", "the CT"),
   your FIRST action is `get_scene_overview`.
2. Treat whatever it returns — volumes, segmentations, models, markups — as the data to work on.
3. Only ask for a path / import if the overview is **genuinely empty** for the thing you need.
4. Never answer "what's loaded?" from memory — read the scene, then answer with the actual node names.

## Worked patterns
- *"What's loaded / what am I looking at?"* → `get_scene_overview`, then name the volumes, their
  modality/dimensions, and any segmentations. Do not say "nothing is loaded" without checking.
- *"Segment the lung / measure the aorta"* → the CT is almost certainly the loaded volume; use it.
  Don't ask "which volume?" when exactly one scalar volume is present.
- *"Grab the T2 series and load it"* → if a study is in the DICOM database, list series and load the
  T2; if a matching volume is already in the scene, use it. Empty database is the only reason to ask
  for a path.
- *"Fuse the PET onto the CT" / "co-register the US with the CT"* → check for BOTH volumes first
  (see the volume-registration-fusion skill). If only one is present, say precisely which one is
  missing — don't clear or reload the scene.

## Guardrails
- Do NOT `clear_scene` / reload sample data to "reset" — that destroys the user's state (this caused a
  lost-scene failure). Work with what's there.
- If exactly one candidate volume exists, proceed with it instead of asking a disambiguating question.
