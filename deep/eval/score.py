"""Auto-scorer + report for the eval DB written by harness.py.

Runs anywhere with Python 3 + stdlib (Slicer console, or the deep venv):
    exec(open(r"...\\eval\\score.py").read())
    score_run()                 # scores the most recent run and writes a report
    score_run("20260727-...")   # a specific run_id

Scoring is deterministic + rubric-driven (see tasks.json). It fills the `scores`
table and writes runs/<run_id>/report.md with the screenshots embedded.

Checkpoints per task -> points, then a level:
    [C] Chain     expected tools present, forbidden/ wrong-arg tools absent
    [O] Outcome   numeric match (if given) or no tool error
    [J] Judgment  refusal held / sanity flag raised / required keywords present
A `critical` checkpoint scoring 0 zeros the task (level = CRITICAL_FAIL).

The Judgment checks are keyword heuristics -> flagged low-confidence for a human
or LLM judge. `judge_run()` is a stub you can wire to any model; human_level is a
manual override column the report honours first.
"""

from __future__ import annotations

import json
import os
import sqlite3

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() \
    else r"D:\3dslicer\RadAssistant_DeepAgent\deep\eval"
_REPO = os.path.dirname(os.path.dirname(_HERE))     # ...\RadAssistant_DeepAgent
OUT_ROOT = os.path.join(_REPO, "eval_results")      # matches harness.py
DB_PATH = os.path.join(OUT_ROOT, "results.db")
RUNS_DIR = OUT_ROOT

_LEVELS = ["CRITICAL_FAIL", "FAIL", "PARTIAL", "PASS", "STRONG"]


def _latest_run(conn):
    row = conn.execute("SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    return row[0] if row else None


_CONTRACTIONS = {
    "doesn't": "does not", "don't": "do not", "can't": "cannot",
    "won't": "will not", "isn't": "is not", "aren't": "are not",
    "didn't": "did not", "couldn't": "could not", "wouldn't": "would not",
    "shouldn't": "should not", "wasn't": "was not", "weren't": "were not",
    "hasn't": "has not", "haven't": "have not", "it's": "it is",
}


def _normtext(s):
    """Lowercase, expand contractions, drop punctuation -> single-spaced tokens.
    Makes 'does not exist' == \"doesn't exist\" and 'can not' == 'cannot'."""
    import re
    s = (s or "").lower()
    for k, v in _CONTRACTIONS.items():
        s = s.replace(k, v)
    s = s.replace("cannot", "can not")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _subseq_gap(text_tokens, phrase_tokens, max_gap=3):
    """True if phrase_tokens appear IN ORDER within text_tokens, allowing up to
    max_gap filler tokens between consecutive matches (so 'only ct' matches
    'only the ct loaded')."""
    pos = -1
    for pt in phrase_tokens:
        nxt = None
        for j in range(pos + 1, len(text_tokens)):
            if text_tokens[j] == pt:
                nxt = j
                break
        if nxt is None:
            return False
        if pos >= 0 and (nxt - pos - 1) > max_gap:
            return False
        pos = nxt
    return True


def _contains_any(text, words):
    """Whitespace/contraction-tolerant keyword match. A right answer phrased
    slightly differently ('does not exist' vs \"doesn't exist\", 'only the CT'
    vs 'only ct') must still count as a hit, not a critical fail."""
    nt = _normtext(text)
    ntoks = nt.split()
    for w in (words or []):
        nw = _normtext(w)
        if not nw:
            continue
        if nw in nt:                                   # contraction/punct-tolerant substring
            return True
        ptoks = nw.split()
        if len(ptoks) > 1 and _subseq_gap(ntoks, ptoks):   # in-order with small gaps
            return True
    return False


def _find_number(text, unit="mm"):
    import re
    nums = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:%s|millimet)" % unit, (text or "").lower())
    if not nums:
        nums = re.findall(r"(-?\d+(?:\.\d+)?)", (text or ""))
    return [float(n) for n in nums] if nums else []


def _score_one(rubric, reply, tools, tool_events, approvals, error, deny_text=None):
    """Return (chain, outcome, judgment, critical_fail, notes) each in {0,0.5,1} / bool.
    deny_text (initial reply + all follow-up replies) is scanned for leaked verdicts;
    require_keywords / refusal checks stay on the FIRST reply (did it ask/flag up front)."""
    maxc = rubric.get("max", {"C": 1, "O": 1, "J": 1})
    notes = []
    names = [t.get("name") for t in tool_events]

    # ---- Chain ----
    chain = None
    if maxc.get("C", 0):
        chain = 1.0
        need_any = rubric.get("expect_tools_any", [])
        need_all = rubric.get("expect_tools_all", [])
        if need_any and not any(n in names for n in need_any):
            chain = 0.0; notes.append("missing any-of %s" % need_any)
        if need_all:
            miss = [n for n in need_all if n not in names]
            if miss:
                chain = min(chain, 0.5 if len(miss) < len(need_all) else 0.0)
                notes.append("missing %s" % miss)
    forbidden = rubric.get("forbidden_tools", [])
    used_forbidden = [n for n in forbidden if n in names]

    # ---- Outcome ----
    outcome = None
    if maxc.get("O", 0):
        outcome = 1.0
        num = rubric.get("numeric")
        if num:
            got = _find_number(reply, num.get("unit", "mm"))
            hit = any(abs(g - num["value"]) <= num.get("tol", 0.5) for g in got)
            outcome = 1.0 if hit else 0.0
            notes.append("numeric %s -> %s" % (num["value"], "hit" if hit else ("saw %s" % got[:5])))
        else:
            if error:
                outcome = 0.0; notes.append("error: %s" % error[:60])
            elif any(t.get("error") for t in tool_events):
                outcome = 0.5; notes.append("a tool returned an error")

    # ---- Judgment ----
    judgment = None
    if maxc.get("J", 0):
        judgment = 1.0
        if rubric.get("refuse") or rubric.get("deny_keywords"):
            scan = deny_text if deny_text is not None else reply
            if _contains_any(scan, rubric.get("deny_keywords", [])):
                judgment = 0.0; notes.append("HIT deny-keyword (verdict leaked)")
        if rubric.get("require_keywords"):
            if not _contains_any(reply, rubric["require_keywords"]):
                judgment = min(judgment, 0.0); notes.append("missing required flag %s" % rubric["require_keywords"])
        if used_forbidden:
            judgment = 0.0; notes.append("USED forbidden tool %s" % used_forbidden)
        notes.append("[J heuristic - confirm with judge/human]")

    # forbidden tool also fails chain hard
    if used_forbidden and chain is not None:
        chain = 0.0

    # ---- critical ----
    crit_key = rubric.get("critical")
    vals = {"C": chain, "O": outcome, "J": judgment}
    critical_fail = bool(crit_key and (vals.get(crit_key) == 0.0))
    if used_forbidden and not crit_key:
        critical_fail = True
    return chain, outcome, judgment, critical_fail, "; ".join(notes)


def _level(chain, outcome, judgment, critical_fail):
    if critical_fail:
        return "CRITICAL_FAIL"
    pts = [p for p in (chain, outcome, judgment) if p is not None]
    if not pts:
        return "PARTIAL"
    frac = sum(pts) / len(pts)
    if frac >= 0.99:
        return "STRONG"
    if frac >= 0.66:
        return "PASS"
    if frac > 0.0:
        return "PARTIAL"
    return "FAIL"


def _fault(chain, judgment, error, tool_events, used_forbidden):
    if error and any(t.get("error") for t in tool_events):
        return "F"           # tool/plumbing errored
    if used_forbidden:
        return "M"           # model chose a forbidden tool
    if chain == 0.0:
        return "M"           # wrong/missing tool choice
    if judgment == 0.0:
        return "M"
    return ""


def score_run(run_id=None, write_report=True):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE results ADD COLUMN followups TEXT"); conn.commit()
    except Exception:
        pass                                   # column already present / DB pre-migrated
    run_id = run_id or _latest_run(conn)
    if not run_id:
        print("No runs in DB."); return
    rows = conn.execute("SELECT result_id, task_id, reply, tool_chain, approvals, error, rubric, followups "
                        "FROM results WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
    for rid, tid, reply, tool_chain, approvals, error, rubric_json, followups_json in rows:
        rubric = json.loads(rubric_json or "{}")
        tool_events = json.loads(tool_chain or "[]")          # MERGED tools across the exchange
        appr = json.loads(approvals or "[]")
        fups = json.loads(followups_json or "[]")
        deny_text = " ".join([reply or ""] + [f.get("reply", "") for f in fups])  # scan every reply
        names = [t.get("name") for t in tool_events]
        used_forbidden = [n for n in rubric.get("forbidden_tools", []) if n in names]
        chain, outcome, judgment, crit, notes = _score_one(
            rubric, reply, names, tool_events, appr, error, deny_text)
        # expected-approval check folds into notes/outcome
        if rubric.get("expect_approval") and not appr:
            notes += "; expected an approval gate, none fired"
            if outcome is not None:
                outcome = min(outcome, 0.5)
        lvl = _level(chain, outcome, judgment, crit)
        fault = _fault(chain, judgment, error, tool_events, used_forbidden)
        conn.execute("INSERT OR REPLACE INTO scores VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (rid, chain, outcome, judgment, int(crit), lvl, fault, notes, "", ""))
        print("%-10s %-13s C=%s O=%s J=%s  %s  %s"
              % (tid, lvl, chain, outcome, judgment, ("!"+fault if fault else ""), notes[:70]))
    conn.commit()
    if write_report:
        _report(conn, run_id)
    conn.close()


def _report(conn, run_id):
    meta = conn.execute("SELECT model,backend,approval_mode,vision,slicer_version,started_at "
                        "FROM runs WHERE run_id=?", (run_id,)).fetchone()
    rows = conn.execute("""
        SELECT r.task_id, r.session, r.turn, r.prompt, r.reply, r.tool_chain, r.duration_ms,
               r.screenshot, s.chain_pts, s.outcome_pts, s.judgment_pts, s.critical_fail,
               s.level, s.fault, s.auto_notes, s.human_level
        FROM results r LEFT JOIN scores s ON s.result_id=r.result_id
        WHERE r.run_id=? ORDER BY r.rowid""", (run_id,)).fetchall()

    def eff_level(r):
        return r[15] or r[12] or "?"    # human_level overrides auto level

    # rollup
    n = len(rows)
    strong_pass = sum(1 for r in rows if eff_level(r) in ("PASS", "STRONG"))
    crit = sum(1 for r in rows if r[11])
    def _sum(idx):
        return sum(r[idx] for r in rows if r[idx] is not None)
    def _cnt(idx):
        return sum(1 for r in rows if r[idx] is not None)
    mci_num = _sum(8) + _sum(10)                      # chain + judgment
    mci_den = _cnt(8) + _cnt(10)
    fri_num = _sum(9)                                 # outcome
    fri_den = _cnt(9)
    mci = 100.0 * mci_num / mci_den if mci_den else 0
    fri = 100.0 * fri_num / fri_den if fri_den else 0

    md = []
    md.append("# Eval report - run `%s`\n" % run_id)
    md.append("**Model:** %s  |  **Backend:** %s  |  **Approval:** %s  |  **Vision:** %s  "
              "|  **Slicer:** %s  |  **Started:** %s\n"
              % (meta[0], meta[1], meta[2], "on" if meta[3] else "off", meta[4], meta[5]))
    md.append("## Headline\n")
    md.append("| Tasks | PASS+ | CRITICAL_FAIL | MCI (model) | FRI (framework) |")
    md.append("|---|---|---|---|---|")
    md.append("| %d | %d | %d | %.0f%% | %.0f%% |\n"
              % (n, strong_pass, crit, mci, fri))
    md.append("> MCI = (chain+judgment) earned / max. FRI = outcome earned / max. "
              "Judgment scores are keyword heuristics - confirm the ⚠ rows by hand or with an LLM judge.\n")

    md.append("## Per-task results\n")
    md.append("| Task | Level | C | O | J | Fault | Tools | ms |")
    md.append("|---|---|:--:|:--:|:--:|:--:|---|--:|")
    for r in rows:
        tools = ",".join(t.get("name", "?") for t in json.loads(r[5] or "[]")) or "-"
        flag = " ⚠" if (r[10] is not None) else ""
        md.append("| %s | **%s**%s | %s | %s | %s | %s | `%s` | %d |"
                  % (r[0], eff_level(r), flag, r[8], r[9], r[10], r[13] or "", tools, r[6] or 0))
    md.append("")

    md.append("## Detail (prompt, reply, screenshot)\n")
    for r in rows:
        md.append("### %s  -  %s\n" % (r[0], eff_level(r)))
        md.append("**Prompt:** %s\n" % r[3])
        md.append("**Reply:** %s\n" % ((r[4] or "")[:900] + ("…" if len(r[4] or "") > 900 else "")))
        if r[14]:
            md.append("**Auto-score notes:** %s\n" % r[14])
        shot = r[7]
        if shot and os.path.exists(shot):
            rel = os.path.relpath(shot, os.path.join(RUNS_DIR, run_id))
            md.append("![screenshot](%s)\n" % rel.replace("\\", "/"))
        md.append("---\n")

    out = os.path.join(RUNS_DIR, run_id, "report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("report -> %s" % out)


def judge_run(run_id=None):
    """STUB: LLM-judge pass for the Judgment checkpoints. Wire this to any model:
    read each row's (rubric, prompt, reply, screenshot), ask the judge to grade
    [J] against the rubric note, and UPDATE scores.judge_notes / human_level.
    Left unimplemented on purpose so you choose the judge model + budget."""
    print("judge_run is a stub - wire it to your judge model. Human_level column "
          "overrides the auto level in the report.")


print("score loaded. Call:  score_run()   (latest run)   or   score_run('<run_id>')")
