# Eval data policy — built-in 3D Slicer sample data only

**Rule:** the entire evaluation set runs on datasets Slicer can download itself
(`SampleData`). **No external MRI/CT/DICOM/X-ray, no private studies, no trained
model folders.** Anything a task "needs" that isn't a raw sample — a prior study, a
second segmentation, an ROI, even a DICOM folder — is **derived deterministically
from a sample** by a fixture (see §4). This keeps the eval reproducible on any
machine "as-is".

## 1. Guaranteed core datasets

These four are what the engine documents and what every fixture is built on:

| Sample name | Modality | Stands in for | Anatomy present |
|---|---|---|---|
| `CTChest` | chest CT | body/onc CT, thoracic, RT, QA | lungs, bone, heart, mediastinum, vessels |
| `MRHead` | brain MRI (T1) | any neuro / MR-modality task | brain, skull, soft tissue |
| `CTACardio` | cardiac CT angio | cardiovascular, vessels, VR | aorta, heart chambers, coronary vessels (contrast) |
| `MRBrainTumor1` | brain-tumor MRI | glioma volumetry, lesion work | enhancing tumour + brain |

## 2. Find what's actually registered on THIS machine

Don't trust a hardcoded list — Slicer versions/extensions add samples. Dump the
real registry once (Slicer Python console, or `list_samples()` in `harness.py`):

```python
import SampleData
for s in SampleData.SampleDataLogic().registeredSourcesByCategory.get("BuiltIn", []):
    print(s.sampleName, "->", s.nodeNames)
# broader: iterate every category
for cat, sources in SampleData.SampleDataLogic().registeredSourcesByCategory.items():
    print("##", cat); [print("  ", s.sampleName) for s in sources]
```

Common extras you may see (use only if your probe lists them): `MRBrainTumor2`,
`CTLiver`, `DTIBrain`, `CTACardioMedium`, `CBCTDentalSurgery`, `BaselineVolume` +
`DTIVolume` (a registration pair). Treat anything not in §1 as **optional** —
guard the task so it degrades cleanly if the sample is absent.

## 3. Persona / scenario → which sample

Every EVAL_SUITE / EVAL_SUITE2 scenario maps onto a core sample. The clinical
framing (RECIST, Fleischner, RANO…) is unchanged — the *behaviour* is identical on
a stand-in; only the numbers aren't clinically meaningful, which the rubrics never
depend on.

| Scenario (persona) | Real-world modality | Sample used |
|---|---|---|
| Oncologic restaging (P1) | portal-venous abdomen CT + prior | `CTChest` + derived prior (§4) |
| Lung nodule (P2) | chest CT + prior | `CTChest` + derived prior |
| Glioma volumetry (P3) | serial brain MR | `MRBrainTumor1` + derived baseline |
| Brain MR workup (P3) | T1 brain MR | `MRHead` |
| RT OAR/PTV + DVH (P4) | thoracic CT (+ RT dose) | `CTChest` (dose → guard, §5) |
| Auto-seg QA (P5) | CT + two masks | `CTChest` + derived two-seg (§4) |
| Radiomics (P5) | CT/MR + ROI | `CTChest`/`MRBrainTumor1` + derived ROI |
| Aortic CTA (P6) | cardiac CTA | `CTACardio` |
| DICOM intake (any) | a folder of `.dcm` | **self-exported** from `CTChest` (§4) |
| Image fusion / interval change | current + prior | `CTChest` ×2 with a small shift (§4) |

## 4. Derived fixtures (no external files)

All implemented in `harness.py:_apply_fixture` — deterministic, off the scoring path:

- **FX-PRIOR / baseline** — clone the loaded sample and **shift it a few mm** so
  registration/subtraction has real work to do (an identical copy would make
  `compare_studies` trivially perfect). → covers every "prior vs current",
  registration, and interval-change task without a second study.
- **FX-TWO-SEG** — threshold the *same* sample twice at slightly different HU
  (`-1000..-400` and `-1000..-350`) to get two overlapping masks → Dice/Jaccard/
  Hausdorff QA with no manual reference needed.
- **FX-ROI** — threshold a small single-island segment (a few mL) → radiomics /
  segment-statistics without an annotated lesion.
- **FX-CT-LUNG-BAD** — the naive `-1000..-400` lung threshold that also grabs
  external air → the "12 L lung" plausibility trap, generated on demand.
- **FX-DICOM** — **export `CTChest` to a temp DICOM folder** with the
  `DICOMScalarVolumePlugin`, then hand that folder to the DICOM-intake tasks. This
  exercises `import_dicom_folder` / `list_dicom_database` / `load_dicom_patient`
  (and makes the volume DICOM-backed so `export_dicom_seg` / `export_dicom_sr` have
  a real source series) — all from a sample. Tasks reference the generated path via
  the `{DICOM_DIR}` placeholder, which the harness substitutes at runtime.

## 5. What sample data genuinely can't cover (and how the eval handles it)

Be honest about the edges so scores aren't misread:

| Need | Built-in? | Eval handling |
|---|---|---|
| **Plain X-ray / radiograph** | ❌ not in SampleData | **Excluded** — this agent is volumetric (CT/MR); no plain-film tasks. |
| **RT dose volume (DVH)** | ❌ (SlicerRT ships its own) | `compute_dvh` tested via **guard path**; or load the SlicerRT "RT" sample manually if the extension is installed. |
| **Trained nnU-Net model** | ❌ (site-specific) | `run_nnunet` tested via **guard path** only (asks for the model folder). |
| **PET for PET/CT fusion** | ➖ some builds have a pair | Fusion tested with two CT samples (`register_volumes`); real PET only if your probe lists one. |
| **Multi-patient DICOM DB** | ➖ | Export **two** samples (`CTChest`,`MRHead`) into the DICOM store → a 2-patient DB, still sample-only. |
| **DICOM SEG/SR export** | needs a DICOM-loaded volume | Use **FX-DICOM** first so the volume is DICOM-backed; else guard path. |

Guard-path tasks are still valuable model tests — they check the model **detects
the gap, guides the install, and doesn't auto-install or fabricate** — which is
exactly the behaviour we want to grade.

## 6. Where this is wired

- `harness.py:_apply_fixture` implements FX-EMPTY / FX-CT / FX-MR / FX-CTA /
  FX-TUMOR / FX-CT-LUNG(/-BAD) / **FX-PRIOR** / **FX-DICOM**, plus `{DICOM_DIR}`
  substitution and `list_samples()`.
- `tasks.json` fixtures only ever name one of the above → the whole set is
  sample-data-only by construction.
- When you encode the remaining EVAL_SUITE / EVAL_SUITE2 tasks, keep every
  external `C:\cases\...` path out — point DICOM tasks at `{DICOM_DIR}` and every
  "prior"/"baseline" at `FX-PRIOR`.
