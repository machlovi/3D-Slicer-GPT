# Packaging RadAssistant as a 3D Slicer extension

RadAssistant is structured as a **proper Slicer extension**, not just a loose scripted module:

```
RadAssistant/                     <- extension root (this git repo) = D:\3dslicer\RadAssistant
├── CMakeLists.txt                <- extension-level CMake (defines EXTENSION_* meta; add_subdirectory)
├── RadAssistant.s4ext            <- extension description (for the Extensions Index / build factory)
├── RadAssistant.png              <- extension icon
└── RadAssistant/                 <- the MODULE folder = D:\3dslicer\RadAssistant\RadAssistant
    ├── CMakeLists.txt            <- module CMake (builds the scripted module + ships the support trees)
    ├── RadAssistant.py           <- the module
    ├── Resources/Icons/RadAssistant.png
    ├── radassistant_lib/         <- support package  (shipped via install(DIRECTORY))
    ├── skills/                   <- skill library     (shipped)
    └── connectors/               <- connector adapters (shipped)
```

⚠️ **Two folders, don't mix them up:**
- **Extension root** = `D:\3dslicer\RadAssistant` — pick this for **Extension Wizard ▸ Select Extension**.
- **Module folder** = `D:\3dslicer\RadAssistant\RadAssistant` — pick this for **Additional module paths**.

Three ways to get it into Slicer. **Pick by what you need.**

---

## Method A — Dev install (recommended now; no build required)

The practical way to make RadAssistant permanent for you and collaborators today (the standard Slicer
*installer* does not include the CMake SDK needed to compile an extension — see Method B).

**A1 — Additional module paths (most foolproof):**
1. Edit ▸ Application Settings ▸ Modules.
2. Additional module paths ▸ Add ▸ `D:\3dslicer\RadAssistant\RadAssistant` (the folder with RadAssistant.py).
3. OK ▸ restart. RadAssistant appears under Modules ▸ Utilities, and its chat auto-docks on the right.

**A2 — Extension Wizard (loads it "as an extension"):**
1. Open the Extension Wizard (module search 🔍 ▸ type "Extension Wizard").
2. Select Extension ▸ choose the extension root `D:\3dslicer\RadAssistant` (NOT the inner folder).
3. Add to paths + restart.

A collaborator does the same after `git clone`. No compilation.

---

## Method B — Build an installable package (`Install from file`)

Produces the `.tar.gz`/`.zip` that **Extensions Manager ▸ Install from file** accepts.
**Requires a Slicer build tree** — the binary installer at
`C:\Users\munee\AppData\Local\slicer.org\3D Slicer 5.10.0` does **not** contain `SlicerConfig.cmake`,
so you cannot build against the installed app alone. You need either a Slicer built from source
(`.../Slicer-SuperBuild/Slicer-build`) or an official Slicer developer/SDK package for the version.

> NOTE: A hand-made zip of the module folder (e.g. `RadAssistant.zip`) is **not** an installable
> package — "Install from file" expects the CPack layout produced below, not a raw folder zip.

```bash
cmake -DSlicer_DIR:PATH=/path/to/Slicer-SuperBuild/Slicer-build ^
      -DCMAKE_BUILD_TYPE:STRING=Release ^
      D:/3dslicer/RadAssistant
cmake --build . --config Release
cpack                      # emits RadAssistant-<ver>-<platform>.tar.gz
```

Then in Slicer: Extensions Manager ▸ Install from file ▸ pick the generated archive ▸ restart.
Because RadAssistant is pure Python, the build only *copies* files — no C++ compilation of our code.

---

## Method C — The public marketplace (Level 2)

For one-click install by every Slicer user via the in-app Extensions Manager:
1. Push this repo public and replace the `REPLACE-ME` URLs in `CMakeLists.txt` and `RadAssistant.s4ext`.
2. Submit a PR adding RadAssistant to the [Slicer/ExtensionsIndex](https://github.com/Slicer/ExtensionsIndex).
3. Slicer's build **factory** compiles it on all platforms and a maintainer reviews/merges it.

RadAssistant already meets the key prerequisites: MIT licensed, pure-Python, public-repo-ready.

---

## Before you publish
- Replace `REPLACE-ME` URLs in `CMakeLists.txt`, `RadAssistant.s4ext`.
- Swap the placeholder `RadAssistant.png` / `RadAssistant/Resources/Icons/RadAssistant.png` for a final icon.
- Add a `.gitignore` for dev clutter (`radassistant-deep/`, `*.log`, `__pycache__/`, `ctkDICOM*.sql`,
  `RadAssistant.zip`) so it stays out of the published extension.
- Heavy deps (LLM backends) should `pip_install` lazily at runtime (TotalSegmentator/MONAI convention),
  not be bundled; API keys come from settings/env and must never be committed.
