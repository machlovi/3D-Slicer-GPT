---
name: total-segmentator
description: Run TotalSegmentator AI auto-segmentation (whole-body / many organs / a named organ set) on a CT or MR. Use when the user explicitly asks for TotalSegmentator, "auto-segment", multi-organ, or whole-body anatomy. ALWAYS confirm task + speed and warn about the UI freeze FIRST. NOT for a single lung/bone volume (use thresholding — it's seconds and never freezes).
---

# TotalSegmentator (AI auto-segmentation)

TotalSegmentator runs an nnU-Net model that labels many anatomical structures at once. It is
powerful but **HEAVY: it blocks Slicer's UI until it finishes** (the extension reads the inference
subprocess with a blocking call on the main thread). So you MUST set expectations and get a choice
from the user before starting — never fire `run_total_segmentator` on the first mention.

## STEP 1 — ALWAYS clarify first (do not skip)

Before calling the tool, confirm these with the user in one short message, then wait:

1. **What do they need?** If it's a *single* structure they just want to *see* (lungs, skeleton),
   steer them to the fast path instead (thresholding / volume rendering — seconds, no freeze). Only
   use TotalSegmentator when they want *many* labelled organs, a specific TS task, or clean anatomy
   that thresholding can't isolate.
2. **Task** — must match the image modality (see catalog below). `total` is **CT only**; for MR use
   `total_mr`. Picking a CT task on an MR (or vice-versa) gives garbage.
3. **Speed** — offer the trade-off explicitly:
   - `normal` = full resolution (1.5 mm), best detail. GPU ~30 s; **CPU 5–50 min**.
   - `fast` = 3 mm, a few minutes on CPU, good for orientation/volumes. *(default)*
   - `faster` = 6 mm, quickest, least detail.
4. **Warn about the freeze** based on the machine: *"Slicer will be unresponsive for roughly <estimate>
   while it computes — OK to proceed?"* On GPU it's seconds; on CPU say minutes.

If they only need a few organs, offer **`roi_subset`** — segmenting just those (e.g. liver + spleen)
is much faster and uses less memory. Only valid with `total`/`total_mr`.

## STEP 2 — Run it

Call `run_total_segmentator` with the agreed `task`, `quality`, and optional `roi_subset`
(e.g. `roi_subset: ["liver","spleen","kidney_left","kidney_right"]`).

- On a CPU-only machine the tool **refuses `quality: "normal"`** (the 5–50 min trap) and asks you to
  pick `fast`/`faster`/`roi_subset` or the HPC GPU — relay that choice back to the user, don't retry
  blindly.
- If the tool says the extension or weights aren't installed, tell the user to install/prewarm it
  once via **Modules ▸ Segmentation ▸ TotalSegmentator** (it shows a progress bar and caches the
  ~1.5 GB weights), then retry. Never try to pip-install it yourself.
- If a task reports a **license** is required, tell the user to set a (free academic) license key in
  that module; then retry.

### "I have a GPU but it says CPU / normal is blocked"
Very common: the machine has an NVIDIA GPU but Slicer's **PyTorch is the CPU-only build**
(`torch.version.cuda` is `None`, `torch '+cpu'`), so CUDA can never be used. This is a setup issue,
not a missing GPU. Tell the user to fix it once:
1. Open Slicer's **PyTorch Util** module (it ships with the PyTorch extension).
2. Set **Computation backend** to a CUDA build (e.g. `cu121`), click **Install PyTorch**, restart Slicer.
   (Console equivalent: `import PyTorchUtils; PyTorchUtils.PyTorchUtilsLogic().installTorch(forceComputationBackend='cu121')`)
3. Verify in the Python console: `import torch; torch.cuda.is_available()` → should be `True`.

Then `normal` runs in seconds. **VRAM caveat:** the extension warns below ~7 GB; on a small (e.g.
4 GB) laptop GPU, prefer `fast` for whole-body, or `normal` with `roi_subset` for a targeted
full-resolution run, to avoid out-of-memory.

## STEP 3 — After it finishes

- `list_segments` to show what was produced (often 100+ with `total`).
- `measure_segment_volumes` for volumes; `measure_segment_statistics` for mean HU per organ.
- To view in 3D, **hide most segments first** (or use `roi_subset`), then `show_segmentation_3d` —
  building a closed surface for 100+ organs is very slow. `highlight_segment` to feature one.
- Sanity-check volumes against physiology before reporting (see the measurement guidance).

## Task catalog (installed version)

**CT, free (Apache):** `total` (100+ organs/bones/muscles/vessels), `lung_vessels`, `body`,
`cerebral_bleed`, `hip_implant`, `pleural_pericard_effusion`, `liver_vessels`, `lung_nodules`,
`kidney_cysts`, `breasts`, `oculomotor_muscles`.

**MR, free:** `total_mr`, `body_mr`, `vertebrae_mr`.

**License required (free academic / paid commercial):** `heartchambers_highres`, `coronary_arteries`,
`aortic_sinuses`, `tissue_types`, `vertebrae_body`, `vertebrae_pp`, `appendicular_bones`,
`brain_structures`, `face`, `thigh_shoulder_muscles`, `liver_segments`, `head_glands_cavities`.

Common `roi_subset` names (task `total`): `liver`, `spleen`, `pancreas`, `gallbladder`,
`kidney_left`, `kidney_right`, `stomach`, `aorta`, `inferior_vena_cava`, `heart`, `lung_upper_lobe_left`,
`lung_lower_lobe_left`, `lung_upper_lobe_right`, `lung_middle_lobe_right`, `lung_lower_lobe_right`,
`vertebrae_L1`…`vertebrae_L5`, `rib_left_1`…`rib_right_12`, `femur_left`, `femur_right`.

## When NOT to use TotalSegmentator
- "Show/render the lungs/skeleton" → `enable_volume_rendering` (instant display preset).
- "Segment/measure the lungs" (just lung air volume) → `threshold_segmentation` −1000/−400 HU +
  island cleanup (seconds). TotalSegmentator is overkill and freezes the UI.
