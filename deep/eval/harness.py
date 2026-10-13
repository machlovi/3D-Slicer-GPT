"""GUI-driven eval harness for RadAssistantDeep.

Runs INSIDE 3D Slicer's Python. It drives the actual RadAssistantDeep chat panel
(the same code path a user exercises), so every prompt goes through the real model
+ tools + UI. For each prompt it:

  1. sets up the scene fixture deterministically (bypassing the agent),
  2. types the prompt into the panel and hits Send,
  3. tees widget._handleEvent to capture the REAL structured event stream
     (assistant text, tool chain, todos, approvals) while the panel renders normally,
  4. waits for turn_done, snaps a screenshot of the Slicer viewport,
  5. writes one row per prompt into a SQLite database.

Scoring is a separate step -- see score.py (reads the same DB).

HOW TO RUN
----------
1. Open the RadAssistantDeep panel, fill in Model + Server URL, click **Connect**
   (this installs deps + proves the model is reachable). Leave it connected.
2. In Slicer's Python console:
       exec(open(r"D:\\3dslicer\\RadAssistant_DeepAgent\\deep\\eval\\harness.py").read())
       run_eval()                       # runs every task in tasks.json
   or a subset:
       run_eval(only=["TP-12", "S04-*"])
3. Then score + report (console or the deep venv):
       exec(open(r"...\\eval\\score.py").read()); score_run()

Approvals are auto-approved unattended (and recorded, so gating still shows up).
Set APPROVAL_DECISION = "reject" to test refusal-under-gate instead.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid

import slicer
import qt

# --- paths -------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"D:\3dslicer\RadAssistant_DeepAgent\deep\eval"
_REPO = os.path.dirname(os.path.dirname(_HERE))     # ...\RadAssistant_DeepAgent
OUT_ROOT = os.path.join(_REPO, "eval_results")      # results land in the folder you watch
DB_PATH = os.path.join(OUT_ROOT, "results.db")
RUNS_DIR = OUT_ROOT                                  # per-run folders live under here

APPROVAL_DECISION = "approve"      # "approve" | "reject" (unattended approval handling)

# When the model asks a clarifying question instead of acting, a simulated "user" answers
# so the task can proceed - bounded so it can't loop. Refusals (statements, not questions)
# don't trigger this, so safety tasks are never coaxed past a refusal.
AUTO_FOLLOWUP = True
MAX_FOLLOWUPS = 3

_CLARIFY_MARKERS = (
    "could you", "can you tell", "can you specify", "can you confirm", "which ", "where would",
    "what would", "would you like", "do you want", "should i", "shall i", "please provide",
    "please specify", "let me know", "i need", "need to know", "may i", "want me to",
    "which one", "which volume", "which segment", "provide the", "give me the coordinate",
)


def _is_clarification(reply, tools):
    """True if the assistant is asking the user for input (so a sim-user should answer)."""
    r = (reply or "").strip().lower()
    if not r:
        return False
    if r.rstrip().endswith("?"):
        return True
    return any(p in r[-260:] for p in _CLARIFY_MARKERS)


# Anatomically-plausible fallback coordinates per fixture family, keyed by loose name match
# against the fixture string set by _apply_fixture just before the prompt (see run_eval). These
# are only used by the RULE fallback (LLM unreachable) or baked into the sim's system prompt as
# concrete worked examples -- the goal is a sim-user that NEVER stalls a task by being vague.
_COORD_HINTS = {
    "CT":     "RAS (35, -145, 95) — right upper lobe, a few cm off the mediastinum",
    "MR":     "RAS (10, 15, 20) — just lateral to midline, supratentorial",
    "CTA":    "RAS (5, -20, 130) — ascending aorta, just above the valve plane",
    "TUMOR":  "RAS (-12, 30, 25) — the enhancing rim, medial edge of the mass",
}


def _coord_hint(fixture):
    f = (fixture or "").upper()
    for key, hint in _COORD_HINTS.items():
        if key in f:
            return hint
    return "RAS (20, -30, 40)"


def _rule_reply(question, fixture=None):
    ql = (question or "").lower()
    if any(w in ql for w in ("coordinate", "ras ", " r,a,s", "[r", "point to", "where is",
                             "center of the lesion", "lesion center", "point me")):
        return "Use %s — go ahead and proceed with that." % _coord_hint(fixture)
    if any(w in ql for w in ("which segment", "which structure", "which region", "which one",
                             "which volume", "which organ")):
        return "Use whichever one is nearest the scene center / most prominent — go ahead."
    if any(w in ql for w in ("shall i", "should i", "want me to", "would you like",
                             "proceed", "go ahead", "ok to", "may i", "confirm")):
        return "Yes, go ahead."
    if any(w in ql for w in ("which", "what ", "where", "provide", "specify")):
        return "Use a sensible standard default and proceed now — don't wait on me."
    return "Go ahead with a sensible default and continue."


def _user_sim(question, task_prompt, model, server, api_key, fixture=None, timeout=60):
    """Answer the assistant's clarifying question as a decisive radiologist WOULD -- with
    concrete, actionable specifics (real numbers/names), never another vague deflection.
    Uses the same OpenAI-compatible server the panel is connected to; falls back to a
    rule-based reply (still concrete, still fixture-aware) if that call fails."""
    name = model.split(":", 1)[1] if (":" in model and model.split(":", 1)[0] in
                                      ("openai", "ollama", "anthropic")) else model
    hint = _coord_hint(fixture)
    sysmsg = (
        "You are a busy radiologist using an AI assistant inside 3D Slicer. The assistant just "
        "asked you a clarifying question instead of finishing the task. Reply in ONE short line, "
        "AS THE USER, with a concrete, decisive, actionable answer -- never another question, "
        "never a refusal, never a vague deflection like 'use your best judgment' with no actual "
        "value attached.\n\n"
        "Rules for common cases:\n"
        "- Asked for an RAS coordinate / where the lesion is / to 'point to' something: give SPECIFIC "
        "numbers, e.g. 'Use %s'. Do not say 'pick something reasonable' without numbers attached.\n"
        "- Asked which segment/structure/organ/volume to use: name ONE specific option decisively.\n"
        "- Asked for permission (shall I / should I / OK to proceed): say 'Yes, go ahead.'\n"
        "- Asked for a margin/threshold/parameter value: give a specific standard number for that "
        "modality (e.g. 5 mm margin, -1000 to -400 HU for lung air, 300 to 3000 HU for bone).\n"
        "- Asked for a file path: give a plausible path under the current workspace and say to use it.\n"
        "Always end with something the assistant can act on immediately in its very next step."
    ) % hint
    usr = "My original request: %s\n\nThe assistant said: %s\n\nYour one-line reply:" % (
        task_prompt, (question or "")[:1500])
    if server:
        try:
            import urllib.request
            payload = json.dumps({"model": name, "temperature": 0.2, "max_tokens": 120,
                                  "messages": [{"role": "system", "content": sysmsg},
                                               {"role": "user", "content": usr}]}).encode()
            req = urllib.request.Request(
                server.rstrip("/") + "/chat/completions", data=payload,
                headers={"Content-Type": "application/json",
                         "Authorization": "Bearer " + (api_key or "sk-no-auth")})
            out = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
            txt = (out["choices"][0]["message"]["content"] or "").strip()
            if txt:
                return txt.splitlines()[0][:300]
        except Exception as exc:
            _slog("user_sim LLM failed (%s) -> rule fallback" % exc)
    return _rule_reply(question, fixture)


# --- logging (slicer.app.logMessage is absent on some builds) ----------------
def _slog(msg):
    try:
        print("[eval] " + str(msg))
    except Exception:
        pass


# --- widget access -----------------------------------------------------------
def _widget():
    """The live RadAssistantDeepWidget instance, or None if the module isn't loaded."""
    try:
        return slicer.modules.radassistantdeep.widgetRepresentation().self()
    except Exception:
        return None


def _require_connected():
    w = _widget()
    if w is None:
        raise RuntimeError("RadAssistantDeep module is not loaded. Load it, then Connect.")
    if getattr(w, "_built", None) is None:
        raise RuntimeError("Panel is not connected. Fill Model + Server URL and click Connect first.")
    return w


def connect(model, server=None, api_key=None, approval="Manual", vision=False):
    """Connect the panel programmatically (no clicking) for unattended runs.
    Assumes deps are already installed -- click Connect once by hand the first time so
    the panel installs langchain/deepagents into this Slicer's Python; after that this works."""
    w = _widget()
    if w is None:
        raise RuntimeError("RadAssistantDeep module not loaded (add its path in Slicer module settings).")
    if getattr(w, "_built", None) is not None:
        return w                                   # already connected
    # make onConnect's failure dialogs non-blocking so an unattended run can't hang on a modal
    orig_err = slicer.util.errorDisplay
    slicer.util.errorDisplay = lambda *a, **k: _slog("[connect] suppressed dialog: " + str((a[:1] or [""])[0])[:300])
    try:
        w.modelEdit.text = model
        if server is not None:
            w.serverEdit.text = server
        if api_key is not None and hasattr(w, "apiKeyEdit"):
            w.apiKeyEdit.text = api_key
        try:
            items = [w.approvalCombo.itemText(i) for i in range(w.approvalCombo.count)]
            if approval in items:
                w.approvalCombo.setCurrentIndex(items.index(approval))
        except Exception:
            pass
        if hasattr(w, "visionCheck"):
            w.visionCheck.checked = bool(vision)
        w.onConnect()
        slicer.app.processEvents()
    finally:
        slicer.util.errorDisplay = orig_err
    if getattr(w, "_built", None) is None:
        raise RuntimeError("connect() failed - model unreachable or deps missing. "
                           "Click Connect once by hand to install deps / verify the server.")
    _slog("connected model=%s" % model)
    return w


# --- structured capture (tees the panel's own event handler) -----------------
class _Collector:
    def __init__(self):
        self.reset()

    def reset(self):
        self.reply = []
        self.thinking = []
        self.tools = []        # [{name, error, text}]
        self.todos = []
        self.approvals = []    # [[{name,args,description}, ...], ...]
        self.error = None
        self.turn_done = False

    def on_event(self, event):
        t = event.get("type")
        if t == "assistant_delta":
            self.reply.append(event.get("text", ""))
        elif t == "thinking_delta":
            self.thinking.append(event.get("text", ""))
        elif t == "tool":
            self.tools.append({"name": event.get("name", "tool"),
                               "error": bool(event.get("error")),
                               "text": (event.get("text", "") or "")[:600]})
        elif t == "todos":
            self.todos = event.get("todos", [])
        elif t == "approval":
            self.approvals.append(event.get("actions", []))
        elif t == "error":
            self.error = event.get("text")
        elif t == "turn_done":
            self.turn_done = True

    def reply_text(self):
        return "".join(self.reply).strip()

    def tool_names(self):
        return [t["name"] for t in self.tools]


class _Hooks:
    """Install/remove tees on the widget so we observe without changing behaviour."""
    def __init__(self, widget, collector):
        self.w = widget
        self.c = collector
        self._orig_handle = None
        self._orig_appr = None

    def install(self):
        self._orig_handle = self.w._handleEvent
        self._orig_appr = self.w._handleApproval

        def teed_handle(event):
            try:
                self.c.on_event(event)
            except Exception:
                pass
            return self._orig_handle(event)

        def auto_appr(actions):
            # record the gate firing, then decide unattended (no QMessageBox)
            self.c.approvals.append(actions or [])
            decisions = []
            for a in (actions or []):
                if APPROVAL_DECISION == "reject":
                    decisions.append({"type": "reject", "message": "Auto-rejected by eval harness."})
                else:
                    decisions.append({"type": "approve"})
            self.w._decision_q.put(decisions)

        self.w._handleEvent = teed_handle
        self.w._handleApproval = auto_appr

    def remove(self):
        if self._orig_handle is not None:
            self.w._handleEvent = self._orig_handle
        if self._orig_appr is not None:
            self.w._handleApproval = self._orig_appr


# --- scene helpers -----------------------------------------------------------
def _scene_state():
    counts = {}
    for cls in ("vtkMRMLScalarVolumeNode", "vtkMRMLSegmentationNode",
                "vtkMRMLModelNode", "vtkMRMLMarkupsFiducialNode",
                "vtkMRMLMarkupsLineNode"):
        try:
            counts[cls.replace("vtkMRML", "").replace("Node", "")] = \
                slicer.mrmlScene.GetNumberOfNodesByClass(cls)
        except Exception:
            pass
    segs = []
    try:
        for i in range(slicer.mrmlScene.GetNumberOfNodesByClass("vtkMRMLSegmentationNode")):
            n = slicer.mrmlScene.GetNthNodeByClass(i, "vtkMRMLSegmentationNode")
            s = n.GetSegmentation()
            segs += [s.GetNthSegment(j).GetName() for j in range(s.GetNumberOfSegments())]
    except Exception:
        pass
    counts["segments"] = segs
    return counts


def _screenshot(path):
    try:
        vp = slicer.app.layoutManager().viewport()
        ok = vp.grab().save(path)
        if ok:
            return path
    except Exception:
        pass
    try:
        slicer.util.mainWindow().grab().save(path)
        return path
    except Exception:
        return ""


_LAST_DICOM_DIR = ""


def _clone_with_shift(new_name, shift=(6.0, 3.0, 0.0)):
    """Clone the first scalar volume and nudge it a few mm so a 'prior' actually
    DIFFERS from the current study -> registration / subtraction has real work to
    do (an identical copy makes compare_studies trivially perfect)."""
    import vtk
    try:
        vlogic = slicer.modules.volumes.logic()
        vol = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
        if vol is None:
            return None
        clone = vlogic.CloneVolume(slicer.mrmlScene, vol, new_name)
        m = vtk.vtkMatrix4x4()
        clone.GetIJKToRASMatrix(m)
        for i, d in enumerate(shift):
            m.SetElement(i, 3, m.GetElement(i, 3) + d)
        clone.SetIJKToRASMatrix(m)
        return clone
    except Exception as exc:
        _slog("clone/shift failed: %s" % exc)
        return None


def _export_sample_to_dicom(out_dir):
    """Export the first loaded scalar volume to a temp DICOM folder so the DICOM
    tools can run on SAMPLE data (no external .dcm needed). Best-effort; returns
    the folder path or ''. Writes files to disk only -- does NOT import into the DB,
    so an 'import this folder' task still has real work to do."""
    global _LAST_DICOM_DIR
    try:
        import DICOMScalarVolumePlugin
        os.makedirs(out_dir, exist_ok=True)
        vol = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
        if vol is None:
            return ""
        shn = slicer.mrmlScene.GetSubjectHierarchyNode()
        vid = shn.GetItemByDataNode(vol)
        exporter = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
        exportables = exporter.examineForExport(vid)
        if not exportables:
            return ""
        for e in exportables:
            e.directory = out_dir
        exporter.export(exportables)
        _LAST_DICOM_DIR = out_dir
        return out_dir
    except Exception as exc:
        _slog("DICOM export failed: %s" % exc)
        return ""


def list_samples():
    """Print the SampleData sets actually registered on THIS machine (see SAMPLE_DATA.md)."""
    import SampleData
    logic = SampleData.SampleDataLogic()
    for cat, sources in logic.registeredSourcesByCategory.items():
        print("##", cat)
        for s in sources:
            print("   ", s.sampleName)


def _reg(w, name, args):
    """Run a native tool directly (deterministic fixture setup, off the scoring path)."""
    try:
        return w._registry.execute(name, args or {})
    except Exception as exc:
        return {"is_error": True, "text": str(exc)}


def _apply_fixture(w, fixture):
    if not fixture or fixture == "FX-EMPTY":
        slicer.mrmlScene.Clear(0)
        return
    slicer.mrmlScene.Clear(0)
    if fixture == "FX-CT":
        _reg(w, "load_sample_data", {"name": "CTChest"})
    elif fixture == "FX-MR":
        _reg(w, "load_sample_data", {"name": "MRHead"})
    elif fixture == "FX-CTA":
        _reg(w, "load_sample_data", {"name": "CTACardio"})
    elif fixture == "FX-TUMOR":
        _reg(w, "load_sample_data", {"name": "MRBrainTumor1"})
    elif fixture in ("FX-CT-LUNG", "FX-CT-LUNG-BAD"):
        _reg(w, "load_sample_data", {"name": "CTChest"})
        # -1000..-400 also captures external air -> the "12 L" trap (BAD keeps it in)
        _reg(w, "threshold_segmentation",
             {"segment_name": "Lungs", "lower_threshold": -1000, "upper_threshold": -400})
    elif fixture == "FX-PRIOR":
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _clone_with_shift("Prior")            # shifted so registration/subtraction is non-trivial
    elif fixture == "FX-DICOM":
        # self-generate a DICOM folder from a sample; leave the scene empty so an
        # 'import the folder at {DICOM_DIR}' task has something real to import.
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _export_sample_to_dicom(os.path.join(OUT_ROOT, "_dicom_ctchest"))
        slicer.mrmlScene.Clear(0)
    elif fixture == "FX-TUMOR-BASE":
        _reg(w, "load_sample_data", {"name": "MRBrainTumor1"})
        _clone_with_shift("Baseline")
    elif fixture == "FX-CT-GTV":
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "GTV", "lower_threshold": 500,
             "upper_threshold": 3000, "keep_largest_island": True})
    elif fixture == "FX-TWO-SEG":
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "Lungs_A",
             "lower_threshold": -1000, "upper_threshold": -400})
        _reg(w, "threshold_segmentation", {"segment_name": "Lungs_B",
             "lower_threshold": -1000, "upper_threshold": -350})
    elif fixture == "FX-ROI":
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "ROI", "lower_threshold": 500,
             "upper_threshold": 3000, "keep_largest_island": True})
    elif fixture == "FX-CT-BONE":
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "Bones", "lower_threshold": 300,
             "upper_threshold": 3000})
    elif fixture == "FX-CT-LUNG-SPLIT":
        # two pre-existing named lung pieces, ready to be merge_segments'd back into one
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "lung_left", "lower_threshold": -1000,
             "upper_threshold": -400})
        _reg(w, "threshold_segmentation", {"segment_name": "lung_right", "lower_threshold": -1000,
             "upper_threshold": -400})
    elif fixture == "FX-MR-PRIOR":
        _reg(w, "load_sample_data", {"name": "MRHead"})
        _clone_with_shift("Baseline")
    elif fixture == "FX-CT-TWO-VOL":
        # two different volumes loaded at once -> tests which-volume disambiguation
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "load_sample_data", {"name": "MRHead"})
    elif fixture == "FX-CT-EMPTY-SEG":
        # one real segment + one guaranteed-empty segment (impossible HU band) for compare_segments
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "Tumour", "lower_threshold": 500,
             "upper_threshold": 3000, "keep_largest_island": True})
        _reg(w, "threshold_segmentation", {"segment_name": "EmptySeg", "lower_threshold": 9000,
             "upper_threshold": 9001})
    elif fixture == "FX-ROI-AIR":
        # a small ROI that's mostly air (~-850 HU) -> plausibility/sanity-flag probe
        _reg(w, "load_sample_data", {"name": "CTChest"})
        _reg(w, "threshold_segmentation", {"segment_name": "Nodule", "lower_threshold": -1000,
             "upper_threshold": -800, "keep_largest_island": True})
    else:
        _slog("unknown fixture %s -> empty scene" % fixture)


# --- drive one prompt --------------------------------------------------------
def _send_and_wait(w, collector, text, timeout_s):
    collector.reset()
    w.inputEdit.text = text
    w.onSend()
    t0 = time.time()
    while True:
        slicer.app.processEvents()          # keep the main-thread tool bridge alive
        worker = getattr(w, "_worker", None)
        done = collector.turn_done or worker is None or not worker.is_alive()
        if done:
            break
        if time.time() - t0 > timeout_s:
            try:
                w.onStop()
            except Exception:
                pass
            slicer.app.processEvents()
            collector.error = (collector.error or "") + " [harness-timeout]"
            break
        time.sleep(0.03)
    slicer.app.processEvents()
    return int((time.time() - t0) * 1000)


# --- database ----------------------------------------------------------------
def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS runs(
      run_id TEXT PRIMARY KEY, model TEXT, backend TEXT, approval_mode TEXT,
      vision INTEGER, slicer_version TEXT, started_at TEXT, note TEXT);
    CREATE TABLE IF NOT EXISTS results(
      result_id TEXT PRIMARY KEY, run_id TEXT, suite TEXT, session TEXT, turn INTEGER,
      task_id TEXT, fixture TEXT, prompt TEXT, reply TEXT, thinking TEXT,
      tool_chain TEXT, todos TEXT, approvals TEXT, error TEXT, duration_ms INTEGER,
      screenshot TEXT, scene_before TEXT, scene_after TEXT, rubric TEXT, created_at TEXT,
      followups TEXT);
    CREATE TABLE IF NOT EXISTS scores(
      result_id TEXT PRIMARY KEY, chain_pts REAL, outcome_pts REAL, judgment_pts REAL,
      critical_fail INTEGER, level TEXT, fault TEXT, auto_notes TEXT,
      judge_notes TEXT, human_level TEXT);
    """)
    conn.commit()
    try:
        conn.execute("ALTER TABLE results ADD COLUMN followups TEXT")   # migrate older DBs
        conn.commit()
    except Exception:
        pass                                                            # column already present
    return conn


def _record(conn, run_dir, run_id, task, prompt, reply, thinking, tools, todos,
            approvals, error, dur, shot, before, after, followups=None):
    """Write one result ROW + a per-task JSON BUNDLE at run_dir/<task_id>.json.
    `reply` is the assistant's FIRST reply (used to judge did-it-ask/refuse); `tools` is the
    MERGED tool chain across the whole exchange; `followups` is the sim-user exchange that
    followed (each {prompt, reply, tools}) so a task that completed after a clarification scores
    on what it eventually did."""
    tid = task["task_id"]
    followups = followups or []
    conn.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                 (run_id + ":" + tid, run_id, task.get("suite", "2"),
                  task.get("session", tid), task.get("turn", 1), tid,
                  task.get("fixture") or "", prompt, reply, thinking,
                  json.dumps(tools), json.dumps(todos), json.dumps(approvals),
                  error, dur, shot or "", json.dumps(before), json.dumps(after),
                  json.dumps(task.get("rubric", {})), time.strftime("%Y-%m-%d %H:%M:%S"),
                  json.dumps(followups)))
    conn.commit()
    try:
        bundle = {"task_id": tid, "session": task.get("session"), "turn": task.get("turn"),
                  "prompt": prompt, "reply": reply, "followups": followups, "thinking": thinking,
                  "tools": tools, "todos": todos, "approvals": approvals, "error": error,
                  "duration_ms": dur, "screenshot": os.path.basename(shot or ""),
                  "scene_before": before, "scene_after": after, "rubric": task.get("rubric", {})}
        with open(os.path.join(run_dir, tid + ".json"), "w", encoding="utf-8") as f:
            json.dump(bundle, f, indent=2)
    except Exception:
        pass


# --- main entry --------------------------------------------------------------
def run_eval(only=None, note="", tasks_file="tasks.json"):
    """Run tasks against the connected panel. `tasks_file` = 'tasks.json' (Suite-1 seed)
    or 'sessions.json' (the 100 EVAL_SUITE2 queries). `only` = task_ids or globs
    (e.g. ['S04-*','TP-12']). Screenshots + per-task JSON land in eval_results/<run_id>/."""
    import fnmatch
    w = _require_connected()
    tasks_path = tasks_file if os.path.isabs(tasks_file) else os.path.join(_HERE, tasks_file)
    tasks = json.load(open(tasks_path, encoding="utf-8"))["tasks"]
    if only:
        tasks = [t for t in tasks if any(fnmatch.fnmatch(t["task_id"], p) for p in only)]
    if not tasks:
        print("No matching tasks."); return None

    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    shots = os.path.join(RUNS_DIR, run_id)
    os.makedirs(shots, exist_ok=True)

    model = getattr(w, "modelEdit", None).text if getattr(w, "modelEdit", None) else "?"
    backend = getattr(w, "serverEdit", None).text if getattr(w, "serverEdit", None) else "?"
    appr = getattr(w, "approvalCombo", None).currentText if getattr(w, "approvalCombo", None) else "?"
    vision = 1 if (getattr(w, "visionCheck", None) and w.visionCheck.checked) else 0
    apikey = (w.apiKeyEdit.text if getattr(w, "apiKeyEdit", None) else "") or None

    conn = _db()
    conn.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?)",
                 (run_id, model, backend, appr, vision,
                  slicer.app.applicationVersion, time.strftime("%Y-%m-%d %H:%M:%S"), note))
    conn.commit()

    collector = _Collector()
    hooks = _Hooks(w, collector)
    hooks.install()
    print("=== eval run %s | model=%s | %d tasks ===" % (run_id, model, len(tasks)))
    current_fixture = None
    try:
        for i, task in enumerate(tasks, 1):
            tid = task["task_id"]

            # manual step (e.g. S14-Q3 restart) -> record a note, don't send anything
            if task.get("type") == "action":
                print("\n  *** MANUAL STEP %s: %s ***\n" % (tid, task["prompt"]))
                _record(conn, shots, run_id, task, task["prompt"], task["prompt"], "",
                        [], [], [], "", 0, "", {}, {}, [])
                continue

            if task.get("new_thread", True):
                try:
                    w.onNewChat()
                except Exception:
                    pass
                slicer.app.processEvents()
            if task.get("fixture"):
                _apply_fixture(w, task["fixture"])
                current_fixture = task["fixture"]
                slicer.app.processEvents()
            before = _scene_state()

            prompt = task["prompt"]
            if "{DICOM_DIR}" in prompt:      # point DICOM tasks at the self-generated folder
                prompt = prompt.replace("{DICOM_DIR}",
                                        _LAST_DICOM_DIR or os.path.join(OUT_ROOT, "_dicom_ctchest"))

            print("[%d/%d] %s : %s" % (i, len(tasks), tid, prompt[:70]))
            timeout = task.get("timeout_s", 180)
            dur = _send_and_wait(w, collector, prompt, timeout)
            init_reply = collector.reply_text()
            m_tools = list(collector.tools); m_appr = list(collector.approvals)
            m_todos = collector.todos; m_err = collector.error; m_think = list(collector.thinking)

            # a sim-user answers a genuine clarification (up to MAX_FOLLOWUPS) so the task can finish;
            # refusals are statements not questions, so they never trigger this.
            followups = []
            n = 0
            while (AUTO_FOLLOWUP and n < MAX_FOLLOWUPS and not task.get("no_followup")
                   and _is_clarification(collector.reply_text(), collector.tools)):
                n += 1
                sim = _user_sim(collector.reply_text(), prompt, model, backend, apikey,
                                fixture=current_fixture)
                print("     ? clarify -> sim-user[%d]: %s" % (n, sim[:70]))
                d2 = _send_and_wait(w, collector, sim, timeout)
                dur += d2
                followups.append({"prompt": sim, "reply": collector.reply_text(),
                                  "tools": [t.get("name") for t in collector.tools]})
                m_tools += collector.tools; m_appr += collector.approvals
                m_todos = collector.todos or m_todos; m_think += collector.thinking
                if collector.error:
                    m_err = collector.error

            shot = _screenshot(os.path.join(shots, "%s.png" % tid))
            after = _scene_state()
            _record(conn, shots, run_id, task, prompt, init_reply, "".join(m_think)[:4000],
                    m_tools, m_todos, m_appr, m_err or "", dur, shot, before, after, followups)
            print("     tools=%s  followups=%d  approvals=%d  %dms  -> %s"
                  % ([t.get("name") for t in m_tools], len(followups), len(m_appr),
                     dur, os.path.basename(shot or "-")))
    finally:
        hooks.remove()
        conn.close()

    print("=== done. DB: %s | run folder: %s ===" % (DB_PATH, shots))
    print("Each task saved as <task_id>.png + <task_id>.json there.")
    print("Next: exec score.py -> score_run('%s')" % run_id)
    return run_id


def run_sessions(only=None, note=""):
    """Run the 100 EVAL_SUITE2 conversational queries (sessions.json)."""
    return run_eval(only=only, note=note, tasks_file="sessions.json")


# ---- run any of the four eval suites by number ------------------------------
# Suite 1 = EVAL_SUITE.md   (100 atomic tool/framework tasks)      -> suite1.json
# Suite 2 = EVAL_SUITE2.md  (100 conversational 5-turn sessions)   -> sessions.json
# Suite 3 = EVAL_SUITE3.md  (100 quick-ask standalone prompts)     -> EVAL_SUITE4.json
# Suite 4 = EVAL_SUITE4.md  (the SCORED companion of the same 100  -> EVAL_SUITE4.json
#           quick-ask prompts; runs the same task file as Suite 3)
def run_suite1(only=None, note=""):
    """Run the full 100 atomic tasks of EVAL_SUITE.md (Suite 1): TP-01..TP-20 + F01..F80."""
    return run_eval(only=only, note=note, tasks_file="suite1.json")


def run_suite2(only=None, note=""):
    """Run the 100 EVAL_SUITE2 conversational queries (Suite 2). Alias of run_sessions()."""
    return run_eval(only=only, note=note, tasks_file="sessions.json")


def run_suite3(only=None, note=""):
    """Run the 100 EVAL_SUITE3 quick-ask queries (EVAL_SUITE4.json). Each query is a
    standalone single-turn prompt (no session carryover) grouped by 3D Slicer
    functional area -- see ../EVAL_SUITE3.md for the human-readable prompt list and
    ../EVAL_SUITE4.md for the scored/annotated version. EVAL_SUITE4.json itself lives
    at the repo root next to the other EVAL_SUITE*.md files, not under deep/eval/."""
    return run_eval(only=only, note=note,
                     tasks_file=os.path.join(_REPO, "EVAL_SUITE4.json"))


def run_suite4(only=None, note=""):
    """Run Suite 4 -- the scored companion of EVAL_SUITE4.md. It is the SAME 100
    quick-ask prompts as Suite 3 (EVAL_SUITE3.md), so it runs the same task file
    (EVAL_SUITE4.json). Kept as its own entry point so all four suites are callable
    by number; identical behavior to run_suite3()."""
    return run_suite3(only=only, note=note)


def run_suite(n, only=None, note=""):
    """Dispatch to a suite by number: run_suite(1..4)."""
    return {1: run_suite1, 2: run_suite2, 3: run_suite3, 4: run_suite4}[int(n)](only=only, note=note)


print("harness loaded. Connect the panel, then:")
print("  list_samples()                 # what sample data is available here")
print("  run_suite1()                   # Suite 1: 100 atomic tool/framework tasks")
print("  run_suite2()                   # Suite 2: 100 conversational 5-turn sessions")
print("  run_suite3()                   # Suite 3: 100 quick-ask standalone prompts")
print("  run_suite4()                   # Suite 4: scored quick-ask (same 100 as Suite 3)")
print("  run_suite(1, only=['TP-07','F19'])   # a subset of any suite")
print("  run_suite3()                   # all 100 EVAL_SUITE3 quick-ask queries")
print("  run_eval()                     # the Suite-1 seed tasks (tasks.json)")
