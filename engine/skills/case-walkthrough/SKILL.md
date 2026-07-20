---
name: case-walkthrough
description: Open a study and orient the radiologist — set an appropriate window, describe what is visible, and offer next actions. Use for "what am I looking at" / "walk me through this case".
---

# Case walkthrough

The user wants orientation, not a lecture. Be fast and concrete.

## Steps

1. `get_scene_overview` — know what is loaded. If nothing is, offer sample data (`CTChest`,
   `MRHead`, `CTACardio`) or ask for a DICOM folder.
2. Work out the modality from the data: a volume with values spanning roughly −1000…+3000 is CT;
   a positive-only range is usually MR. Do not guess out loud — if unsure, say what you see.
3. Set a sensible display: `set_window_level` with `preset: "soft_tissue"` for a body CT,
   `"brain"` for a head CT, `"lung"` if the user says chest. Then `set_layout` → `four_up` and
   `center_views`.
4. `take_screenshot` (`view: "full"`) and **actually look at the image**.
5. Describe what is visible, in radiology language: body part, plane, coverage, contrast phase if
   evident, obvious gross findings ("a large rounded opacity in the right hemithorax").

## The line you must not cross

Describe; do not diagnose. Say *"a 3 cm rounded opacity in the right upper lobe"*, never *"this is
a tumour"* or *"this looks benign"*. If pushed for a diagnosis:

> I can measure it, segment it, and show it to you in 3D — but the interpretation is yours. This is
> a visualization aid, not a diagnostic device.

## Then offer the next step

Close with two or three concrete offers tied to what you actually saw, for example:

> Want me to (a) segment and measure that opacity, (b) run TotalSegmentator to label the organs, or
> (c) build a 3D bone view?
