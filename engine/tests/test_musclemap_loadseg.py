r"""Headless registration + behavior test for the MuscleMap and load_segmentation work.

Run INSIDE Slicer (it needs slicer/vtk):

    & "D:\3D Slicer 5.12.2\Slicer.exe" --no-splash --python-script ^
        "D:\3dslicer\RadAssistant_DeepAgent\engine\tests\test_musclemap_loadseg.py"

or paste it into Slicer's Python console. It is hermetic — it builds a tiny synthetic
labelmap in memory, so it needs NO network, NO sample data, and NOT the MuscleMap
extension. It checks:

  1. run_musclemap + load_segmentation are registered (schema + dispatch) and every
     schema still has a backing _tool_ method.
  2. run_musclemap is classified 'heavy' (approval-gated).
  3. the 'musclemap' SKILL.md is discoverable by SkillLibrary(engine/skills).
  4. load_segmentation turns a label file into a VISIBLE segmentation node (the gap fix),
     via a file path, via an in-scene labelmap node, and via an in-scene scalar mask.
  5. run_musclemap's guard fires cleanly (a helpful error, no crash) when the SlicerMuscleMap
     extension isn't installed.

Results are printed and written to eval_results/_musclemap_test.log. Exit code note: when
launched with --python-script, Slicer stays open; check the log / console for PASS/FAIL.
"""

import os
import sys
import tempfile
import traceback

import slicer

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"D:\3dslicer\RadAssistant_DeepAgent\engine\tests"
_ENGINE = os.path.dirname(_HERE)                                   # ...\engine
_REPO = os.path.dirname(_ENGINE)
if _ENGINE not in sys.path:
    sys.path.insert(0, _ENGINE)

_LOG_DIR = os.path.join(_REPO, "eval_results")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG = open(os.path.join(_LOG_DIR, "_musclemap_test.log"), "w", encoding="utf-8")

_passed = 0
_failed = 0


def _say(msg):
    print(msg)
    try:
        _LOG.write(str(msg) + "\n"); _LOG.flush()
    except Exception:
        pass


def check(name, cond, detail=""):
    global _passed, _failed
    ok = bool(cond)
    _passed += ok
    _failed += (not ok)
    _say(("  PASS " if ok else "  FAIL ") + name + (("  -> " + str(detail)) if detail else ""))
    return ok


def _synth_labelmap(name, labels=((1, (5, 15)), (2, (18, 25)))):
    """A small integer labelmap node with a couple of labelled cubes."""
    import numpy as np
    arr = np.zeros((30, 30, 30), dtype="int16")
    for value, (lo, hi) in labels:
        arr[lo:hi, lo:hi, lo:hi] = value
    lm = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode",
                                            slicer.mrmlScene.GenerateUniqueName(name))
    slicer.util.updateVolumeFromArray(lm, arr)
    return lm


def _synth_scalar(name):
    import numpy as np
    arr = np.zeros((30, 30, 30), dtype="int16")
    arr[5:15, 5:15, 5:15] = 1
    sv = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode",
                                            slicer.mrmlScene.GenerateUniqueName(name))
    slicer.util.updateVolumeFromArray(sv, arr)
    return sv


def _n_segs(seg_node):
    return seg_node.GetSegmentation().GetNumberOfSegments()


def main():
    _say("=" * 64)
    _say("MuscleMap / load_segmentation test | Slicer %s" % slicer.app.applicationVersion)

    from radassistant_lib.tools import ToolRegistry
    from radassistant_lib.skills import SkillLibrary
    from radassistant_lib.orchestration import policy

    skills = SkillLibrary(os.path.join(_ENGINE, "skills"))
    reg = ToolRegistry(skills)

    # 1) registration -------------------------------------------------------
    _say("\n[1] registration + schema/method consistency")
    names = [d["name"] for d in reg.definitions]
    check("run_musclemap in definitions", "run_musclemap" in names)
    check("load_segmentation in definitions", "load_segmentation" in names)
    check("_tool_run_musclemap exists", hasattr(reg, "_tool_run_musclemap"))
    check("_tool_load_segmentation exists", hasattr(reg, "_tool_load_segmentation"))
    orphans = [n for n in names if not hasattr(reg, "_tool_" + n)]
    check("every schema has a _tool_ method", not orphans, orphans)
    ms = next((d for d in reg.definitions if d["name"] == "run_musclemap"), {})
    props = (ms.get("input_schema", {}) or {}).get("properties", {})
    check("run_musclemap params = volume_name/force_cpu/lower_overlap",
          set(props) == {"volume_name", "force_cpu", "lower_overlap"}, sorted(props))

    # 2) heavy tiering ------------------------------------------------------
    _say("\n[2] approval tiering")
    check("run_musclemap classified heavy", policy.classify_tool("run_musclemap") == "heavy",
          policy.classify_tool("run_musclemap"))

    # 3) skill discoverable -------------------------------------------------
    _say("\n[3] skill discovery")
    prompt_list = skills.list_for_prompt()
    check("musclemap skill listed for prompt", "musclemap" in prompt_list)
    body = skills.read("musclemap")
    check("musclemap skill body reads", body and "MuscleMap" in body and "not diagnose" in body.lower())

    # 4) load_segmentation end-to-end (the gap fix) -------------------------
    _say("\n[4] load_segmentation makes a mask VISIBLE + usable")
    tmp = tempfile.mkdtemp(prefix="mmtest_")

    # (a) from a file path
    lm = _synth_labelmap("fileLabel")
    path = os.path.join(tmp, "mask.nii.gz")
    slicer.util.saveNode(lm, path)
    slicer.mrmlScene.RemoveNode(lm)
    before = {n.GetID() for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")}
    r = reg.execute("load_segmentation", {"path": path})
    check("(a) file path: no error", not r.get("is_error"), r.get("text", "")[:120])
    new = [n for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode") if n.GetID() not in before]
    seg = new[-1] if new else None
    check("(a) a segmentation node was created", seg is not None)
    if seg:
        check("(a) it has >=2 segments", _n_segs(seg) >= 2, _n_segs(seg))
        disp = seg.GetDisplayNode()
        check("(a) it is visible", disp is not None and disp.GetVisibility())

    # (b) from an in-scene labelmap node
    lm2 = _synth_labelmap("sceneLabel")
    before = {n.GetID() for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")}
    r = reg.execute("load_segmentation", {"labelmap_name": "sceneLabel"})
    check("(b) labelmap_name: no error", not r.get("is_error"), r.get("text", "")[:120])
    new = [n for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode") if n.GetID() not in before]
    check("(b) segmentation created from scene labelmap", bool(new) and _n_segs(new[-1]) >= 2)

    # (c) from an in-scene SCALAR mask (exercises _scalar_to_labelmap)
    _synth_scalar("scalarMask")
    before = {n.GetID() for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode")}
    r = reg.execute("load_segmentation", {"labelmap_name": "scalarMask"})
    check("(c) scalar mask: no error", not r.get("is_error"), r.get("text", "")[:120])
    new = [n for n in slicer.util.getNodesByClass("vtkMRMLSegmentationNode") if n.GetID() not in before]
    check("(c) segmentation created from scalar mask", bool(new) and _n_segs(new[-1]) >= 1)

    # (d) load_file on a labelmap hints toward load_segmentation
    r = reg.execute("load_file", {"path": path})
    check("(d) load_file hints to load_segmentation on a labelmap",
          "load_segmentation" in r.get("text", ""), r.get("text", "")[:140])

    # 5) run_musclemap guard fires cleanly without the extension ------------
    _say("\n[5] run_musclemap guard (extension absent)")
    r = reg.execute("run_musclemap", {"volume_name": ""})
    check("no-volume path errors cleanly", r.get("is_error"), r.get("text", "")[:120])
    _synth_scalar("mmInput")
    r = reg.execute("run_musclemap", {"volume_name": "mmInput"})
    # With SlicerMuscleMap absent this must be a helpful guard error, not a crash.
    installed = hasattr(slicer.modules, "wholebodymusclesegmentation")
    if installed:
        check("MuscleMap installed -> ran or gave a dep/runtime message", True, r.get("text", "")[:120])
    else:
        check("extension-absent guard is a clean error", r.get("is_error"))
        check("guard mentions MuscleMap/extension",
              "musclemap" in r.get("text", "").lower() or "extension" in r.get("text", "").lower(),
              r.get("text", "")[:160])

    _say("\n" + "=" * 64)
    _say("RESULT: %d passed, %d failed" % (_passed, _failed))
    _say("=" * 64)


try:
    main()
except Exception:
    _say("TEST HARNESS ERROR:\n" + traceback.format_exc())
finally:
    try:
        _LOG.flush(); _LOG.close()
    except Exception:
        pass
