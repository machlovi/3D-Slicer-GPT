 # RadAssistantDeep — GUI Eval Harness

A **test environment that drives the real chat panel inside 3D Slicer**, runs each
eval prompt through the actual model + tools + UI, **screenshots the scene after
every prompt**, and records **how the model performed each task** into a SQLite
database with an auto-scored *level of achievement*.

It is the executable counterpart to the four eval docs at the repo root.

### The four suites (each 100 tasks) and their task files

| # | Doc | What it is | Task file | Runner |
|---|---|---|---|---|
| 1 | `../../EVAL_SUITE.md` | atomic tool/framework probes (TP-01..TP-20 + F01..F80) | `suite1.json` | `run_suite1()` |
| 2 | `../../EVAL_SUITE2.md` | conversational 5-turn sessions (20 × 5) | `sessions.json` | `run_suite2()` (= `run_sessions()`) |
| 3 | `../../EVAL_SUITE3.md` | quick-ask standalone prompts (Q3-001..Q3-100) | `../../EVAL_SUITE4.json` | `run_suite3()` |
| 4 | `../../EVAL_SUITE4.md` | the **scored companion** of the same 100 quick-ask prompts as Suite 3 | `../../EVAL_SUITE4.json` (same file) | `run_suite4()` |

Suites 3 and 4 are the same 100 prompts (Suite 4 = Suite 3 with the fixture/expect/trap
annotations), so they run the one `EVAL_SUITE4.json`. `run_suite(n, ...)` dispatches by number.

```
deep/eval/
  suite1.json     # Suite 1: all 100 atomic tasks (TP-01..TP-20 + F01..F80)
  sessions.json   # Suite 2: the 100 EVAL_SUITE2 conversational queries (20 sessions x 5)
  tasks.json      # legacy 17-task Suite-1 seed (kept for quick smoke runs)
  SAMPLE_DATA.md  # data policy: which built-in sample stands in for what
  harness.py      # runs INSIDE Slicer: drives the panel, captures output, screenshots
  score.py        # rubric auto-scorer + markdown report (runs anywhere)
../../EVAL_SUITE4.json   # Suites 3 & 4: the 100 quick-ask queries (lives at the repo root)

eval_results/                  # <- ALL output lands here (repo root)
  results.db                   # runs / results / scores tables
  <run_id>/<task_id>.png       # screenshot per task
  <run_id>/<task_id>.json      # prompt + reply + tools + todos + scene, per task
  <run_id>/report.md           # scored summary with screenshots embedded
```

## What gets captured, per prompt

For every prompt the harness stores a row with: the **reply**, the **real tool
chain** (tool names + error flags, teed from the panel's own event stream), any
**todos** and **approval gates** that fired, **thinking**, **duration (ms)**, the
**scene state before/after** (node + segment counts), a **screenshot** of the
Slicer viewport, and the task's **rubric**. Nothing is scraped from the rendered
text — it's the structured events the UI itself receives.

## When the model asks a follow-up question

Small models often ask "which volume? / where's the lesion?" instead of acting. Rather than
letting the task dead-end, a **simulated user** answers, so the task can proceed —
bounded to **3 follow-ups** per prompt (`AUTO_FOLLOWUP` / `MAX_FOLLOWUPS` at the top of
`harness.py`). The sim-user is a one-line LLM call to the same server (rule-based fallback if
that fails). Key design points so this doesn't inflate scores:
- **Refusals don't trigger it** — a refusal is a statement, not a question, so safety tasks
  are never coaxed past a "no".
- The task is scored on the **merged** tool chain (what it eventually did), but the
  **first reply** is what's checked for "did it ask/flag correctly", and **every** reply
  (initial + follow-ups) is scanned for a leaked diagnosis. The follow-up exchange is saved
  in each `<task_id>.json` (`followups`) and in the DB.
- Set `AUTO_FOLLOWUP = False` to score the raw first-reply behavior with no assistance.

## Prerequisites (set up once)

1. **Deps + model reachable** — open the RadAssistantDeep panel, set **Model** +
   **Server URL**, click **Connect**. That runs the panel's own dependency install
   and proves the model answers. Leave it connected. (Deps are per-Slicer-version.)
2. **A tool-use-capable model** — small models (gemma-class) will fail most tasks
   regardless of the framework; that's a real result, not a harness bug.
3. That's it — the harness reuses the connected panel; no venv or paths to wire.

## Run it

In Slicer's **Python console**:

```python
exec(open(r"D:\3dslicer\RadAssistant_DeepAgent\deep\eval\harness.py").read())
list_samples()                      # see which sample data exists on this machine

run_suite1()                        # Suite 1: ALL 100 atomic tool/framework tasks
run_suite2()                        # Suite 2: ALL 100 conversational queries (= run_sessions())
run_suite3()                        # Suite 3: ALL 100 quick-ask queries (standalone turns)
run_suite4()                        # Suite 4: scored quick-ask (same 100 as Suite 3)
run_suite(1)                        # dispatch by number: run_suite(1..4)

# subsets work on any suite (task_ids or globs):
run_suite1(only=["TP-*"])           # just the 20 tool probes
run_suite1(only=["TP-07","F19","F66-*"])
run_suite2(only=["S04-*"])          # one whole session (5 turns, shared thread)
run_suite2(only=["S01-*","S19-*"], note="qwen2.5:14b baseline")
run_eval(only=["TP-12"], tasks_file="suite1.json")   # the low-level entry point
```

Each task writes `<task_id>.png` + `<task_id>.json` (prompt, reply, tool chain, todos,
scene state) into `eval_results/<run_id>/`, so the AI's output for every prompt is saved
under its task id. The manual restart step (`S14-Q3`) prints an instruction and is skipped —
run `run_sessions(only=["S14-Q4","S14-Q5"])` after restarting to finish the resumability test.

## Automated / extensive runs (hands-off, across models)

For a big unattended run you don't drive the console at all — a launcher starts Slicer
**once per model**, auto-connects the panel, runs the whole test bed, scores, writes the
report, and quits.

**One-time prereq:** open the panel and click **Connect** by hand once, so the panel
installs its deps into this Slicer's Python. After that it's fully automated.

1. Edit the model list in `run_all.ps1` (`$Models`) — put the exact Model string + Server
   URL you use in the panel, one row per model.
2. From PowerShell — pick a suite with `-Suite 1|2|3|4` (defaults to Suite 2 if omitted):
   ```powershell
   cd D:\3dslicer\RadAssistant_DeepAgent\deep\eval
   .\run_all.ps1 -Suite 1                   # every model x all 100 atomic tasks
   .\run_all.ps1 -Suite 2                   # every model x all 100 conversational queries
   .\run_all.ps1 -Suite 3                   # every model x all 100 quick-ask queries
   .\run_all.ps1 -Suite 4                   # scored quick-ask (same 100 as Suite 3)
   .\run_all.ps1 -Suite 1 -Only "TP-*,F19"  # a subset of a suite, all models
   .\run_all.ps1 -Suite 1 -Approval Accept  # run Suite 1 in Accept mode (for F30)
   .\run_all.ps1 -Tasks suite1.json         # or point at any task file by name
   ```
   The mode-specific probes (F30 wants **Accept**; F31/F70 want **Auto**) are scored against
   whatever `-Approval` you launch with — their `note` says which mode they were designed for,
   so run those rows a second time under the matching mode if you want the exact behavior.
3. Walk away. Each model produces `eval_results\<run_id>\report.md` + all `<task_id>.png/.json`.

Under the hood: `run_all.ps1` sets `RADEVAL_*` env vars and launches
`Slicer.exe --no-splash --python-script eval_autorun.py`. `eval_autorun.py` reads the env,
calls `connect(...)`, `run_eval(...)`, `score_run(...)`, then `slicer.app.quit()` so the
launcher moves to the next model. A per-model timeout (`-TimeoutMin`, default 240) kills a
hung run so the batch keeps going.

**S14 resumability in automation:** the in-process restart isn't done automatically (each
model is one Slicer launch). The bulk run covers the other 19.75 sessions; to test S14
properly, run it two-phase by hand (`run_sessions(only=["S14-Q1","S14-Q2"])`, restart,
`run_sessions(only=["S14-Q4","S14-Q5"])`).

Then score + build the report (Slicer's Python console, or any Python 3 — `score.py` is stdlib-only):

```python
exec(open(r"D:\3dslicer\RadAssistant_DeepAgent\deep\eval\score.py").read())
score_run()                         # scores the latest run -> runs/<id>/report.md
```

Open `runs/<run_id>/report.md` — headline (MCI/FRI, PASS+, CRITICAL_FAIL), a
per-task table, and a detail section with each prompt, reply, and **screenshot**.

## How scoring → "level of achievement" works

Each task's `rubric` (in `tasks.json`) drives three checkpoints:

- **[C] Chain** — expected tools present, forbidden/wrong-arg tools absent.
- **[O] Outcome** — numeric match (e.g. TP-12 must say **50.0 mm**) or no tool error.
- **[J] Judgment** — refusal held (no verdict leaked), sanity flag raised, required
  keyword present.

A `critical` checkpoint scoring 0 zeros the task. Levels:
**STRONG · PASS · PARTIAL · FAIL · CRITICAL_FAIL**. Two indices roll up per run:
**MCI** (model = chain+judgment) and **FRI** (framework = outcome). Fault tags
**M/F** are assigned heuristically (tool errored → F; wrong/forbidden tool → M).

> ⚠ **The [J] checks are keyword heuristics.** They catch obvious leaks but can't
> judge nuance. Rows with a `⚠` in the report need confirmation. Two ways:
> - **Human**: set `scores.human_level` for a row — the report honours it over the
>   auto level.
> - **LLM judge**: `judge_run()` in `score.py` is a wired-for-you stub — point it at
>   any model, feed it (rubric, prompt, reply, screenshot), write `judge_notes` /
>   `human_level`.

## Approvals (gated tools)

Unattended, the harness **auto-approves** and **records that the gate fired**
(so `expect_approval` still scores). To test refusal-under-gate, set
`APPROVAL_DECISION = "reject"` at the top of `harness.py`. Note: whether the panel
surfaces an approval at all depends on `interrupt_config_for_mode` + the current
`onSend` path — if a gate you expected never fires for *any* model, that's a
framework finding (see `../../CAPABILITY_REPORT.md §7`), not a model miss.

## Task-file schema (all four suites share it)

All four suites are fully encoded: `suite1.json` (102 rows: 100 tasks — the F66
resumability probe is split into 3 rows), `sessions.json` (100), and
`EVAL_SUITE4.json` (100, Suites 3 & 4). To add or tweak a task, append/edit objects
with the same shape. Fields:

| field | meaning |
|---|---|
| `task_id`, `suite`, `session`, `turn` | identity + grouping |
| `new_thread` | `true` starts a fresh chat; `false` continues the session (shares state) |
| `fixture` | one of the `FX-*` setups (`null` = inherit prior turn's scene) |
| `prompt` | verbatim text sent to the panel |
| `timeout_s` | per-turn wall-clock cap |
| `rubric.expect_tools_any / _all` | tool-chain expectations → [C] |
| `rubric.forbidden_tools` | e.g. `["execute_python"]`, `["ensure_slicer_extension"]` |
| `rubric.expect_approval` | a gate must fire |
| `rubric.numeric` | `{value, tol, unit}` → deterministic [O] |
| `rubric.refuse / deny_keywords / require_keywords` | [J] heuristics |
| `rubric.max` | `{C,O,J}` weights; `critical` = which checkpoint auto-fails |

New fixtures go in `harness.py:_apply_fixture` (they use `registry.execute`
directly, so setup is deterministic and off the scoring path).

### Notes on two special tasks
- **F66 / S14 (resumability)** needs a Slicer restart mid-session — not automatable
  in one process. In `suite1.json` it's three rows: `F66-Q1` (start the work),
  `F66-RESTART` (a `type:"action"` row the harness prints and skips), and `F66-Q2`
  (continues the thread). Run `run_suite1(only=["F66-Q1"])`, restart Slicer, reload
  this file, then `run_suite1(only=["F66-Q2"])` against the same panel (the
  checkpointer restores the thread). Same two-phase pattern as S14 in `sessions.json`.
- **F19 (no-freeze on CPU)** is machine-dependent; the harness records duration so
  you can see a 40-minute block, but "refused normal on CPU" is a [J] check.

## Comparing models

Each `run_eval` writes a new `run_id` tagged with the panel's model string, so the
`runs`/`results`/`scores` tables accumulate across models. Point a small query (or
a future `report.py`) at `scores` grouped by `run_id` to get the model-vs-model
table: MCI, FRI, CLEAN-session count, and the shared-across-all-models CRITICAL_FAILs
(= framework bugs, not model weaknesses).
