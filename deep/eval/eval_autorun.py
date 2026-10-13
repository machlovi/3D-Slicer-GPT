"""Unattended eval entry point - launched by Slicer, runs the whole test bed, quits.

    Slicer.exe --no-splash --python-script eval_autorun.py

Config comes from environment variables (set by run_all.ps1, or export them yourself):
    RADEVAL_MODEL     model string, exactly as you'd type in the panel's Model field  (required)
    RADEVAL_SERVER    server URL, as in the panel's Server field                       (optional)
    RADEVAL_APIKEY    API key for hosted models                                        (optional)
    RADEVAL_APPROVAL  Manual | Accept | Auto      (default Manual)
    RADEVAL_TASKS     sessions.json | tasks.json  (default sessions.json)
    RADEVAL_ONLY      comma globs e.g. S01-*,S19-*   (default: everything)
    RADEVAL_NOTE      free label recorded with the run

It writes a full log to  eval_results/_autorun.log  (so a fast open/close is diagnosable),
auto-connects the panel, runs the tasks, scores, then quits Slicer.

PREREQ (once): open the panel and click Connect by hand so deps install into this Slicer.
"""

import os
import time
import traceback

import slicer

_EVAL = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"D:\3dslicer\RadAssistant_DeepAgent\deep\eval"
_OUT = os.path.join(os.path.dirname(os.path.dirname(_EVAL)), "eval_results")
os.makedirs(_OUT, exist_ok=True)
_LOG_PATH = os.path.join(_OUT, "_autorun.log")
_LOG = open(_LOG_PATH, "a", encoding="utf-8")


def log(msg):
    line = "[autorun %s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        _LOG.write(line + "\n"); _LOG.flush()
    except Exception:
        pass
    print(line)


def _wait_for_module(timeout_s=45):
    """Scripted modules can lag app startup; wait for the panel widget to exist."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            w = slicer.modules.radassistantdeep.widgetRepresentation().self()
            if w is not None:
                return w
        except Exception:
            pass
        slicer.app.processEvents()
        time.sleep(0.5)
    return None


def _main():
    log("=" * 60)
    log("start | Slicer %s | py %s" % (slicer.app.applicationVersion, os.sys.version.split()[0]))
    model = os.environ.get("RADEVAL_MODEL", "").strip()
    server = os.environ.get("RADEVAL_SERVER", "").strip() or None
    apikey = os.environ.get("RADEVAL_APIKEY", "").strip() or None
    approval = os.environ.get("RADEVAL_APPROVAL", "Manual").strip() or "Manual"
    tasks = os.environ.get("RADEVAL_TASKS", "sessions.json").strip() or "sessions.json"
    note = os.environ.get("RADEVAL_NOTE", model)
    only = os.environ.get("RADEVAL_ONLY", "").strip()
    only_list = [s for s in (x.strip() for x in only.split(",")) if s] or None
    log("config: model=%r server=%r approval=%s tasks=%s only=%s" % (model, server, approval, tasks, only_list))
    if not model:
        raise RuntimeError("RADEVAL_MODEL is not set (edit run_all.ps1 $Models, or set the env var).")

    log("waiting for RadAssistantDeep module...")
    w = _wait_for_module()
    if w is None:
        raise RuntimeError("RadAssistantDeep module never appeared. Is its path added in "
                           "Slicer > Application Settings > Modules? Launch it once in the GUI.")
    log("module ready: %s" % type(w).__name__)

    # load the harness AFTER we know slicer is up (defines connect/run_eval into globals)
    exec(open(os.path.join(_EVAL, "harness.py"), encoding="utf-8").read(), globals())
    log("harness loaded")

    log("connecting model=%s ..." % model)
    connect(model, server=server, api_key=apikey, approval=approval)          # noqa: F821
    log("connected OK")

    log("running tasks...")
    run_id = run_eval(only=only_list, note=note, tasks_file=tasks)             # noqa: F821
    log("run finished: run_id=%s" % run_id)

    exec(open(os.path.join(_EVAL, "score.py"), encoding="utf-8").read(), globals())
    score_run(run_id)                                                         # noqa: F821
    log("scored + report written for run_id=%s" % run_id)
    log("DONE. report: %s" % os.path.join(_OUT, run_id, "report.md"))


try:
    _main()
except Exception:
    log("FAILED:\n" + traceback.format_exc())
finally:
    try:
        _LOG.flush(); _LOG.close()
    except Exception:
        pass
    slicer.app.quit()
