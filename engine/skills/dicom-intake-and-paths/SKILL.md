---
name: dicom-intake-and-paths
description: Import and sort DICOM from a real folder on the host machine. Use for "I have a pile of loose DICOMs at <path>", "sort out what's what", "import this folder", "load the study from D:\... or /data/...". Clarifies that HOST paths are valid arguments to the Slicer-side data tools — do NOT refuse a Windows/Unix path because of the agent's own virtual filesystem.
---

# DICOM intake from a host folder — paths are real

Slicer's data tools run **inside Slicer** and take **real host paths**. A path like `D:\scans\ct`
or `/home/user/study` is a valid argument to `import_dicom_folder`, `load_file`, and
`load_dicom_patient`. Do **not** tell the user "the D: drive isn't accessible / I work on a virtual
filesystem" — that virtual `/` scratch space is only for files *you* write (reports, notes); it is
not where the imaging tools operate.

## Workflow for "loose DICOMs, sort out what's what"
1. `import_dicom_folder(<the host path exactly as given>)` — this recurses, parses headers, and
   populates Slicer's DICOM database, grouping by Patient → Study → Series.
2. `list_dicom_database` — report the hierarchy: how many patients/studies/series, modality, series
   descriptions, and (when mixed scanners) the differing `Manufacturer`/`StationName` per series.
3. Summarize "what's what": e.g. "3 studies from 2 scanners — CT chest (GE), MR brain T1+T2 (Siemens)…".
4. Load only what the user asked for (e.g. one series) with `load_dicom_patient` / the series loader.

## Guardrails
- Pass the path through verbatim; don't rewrite `D:\` to `/`. If the folder truly can't be read, the
  tool returns an error — surface *that*, don't pre-emptively refuse.
- Sorting/organizing is a database operation (import + list); you do not need `execute_python` for it.
- Keep Slicer's DICOM database as the source of truth; don't hand-parse files yourself.
