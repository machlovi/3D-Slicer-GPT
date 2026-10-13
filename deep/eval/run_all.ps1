<#
  Extensive automated eval across models. Launches Slicer ONCE PER MODEL, unattended:
  each launch auto-connects the panel, runs the whole test bed, scores, writes
  eval_results\<run_id>\report.md, and quits. You start it and walk away.

  PREREQ (once): open the RadAssistantDeep panel and click Connect by hand, so the panel
  installs its Python deps into this Slicer. After that, this script is hands-off.

  Usage (from PowerShell):
      cd D:\3dslicer\RadAssistant_DeepAgent\deep\eval
      .\run_all.ps1                              # default: Suite 2 (sessions.json)
      .\run_all.ps1 -Suite 1                     # Suite 1: 100 atomic tasks (suite1.json)
      .\run_all.ps1 -Suite 3                     # Suite 3: 100 quick-ask (EVAL_SUITE4.json)
      .\run_all.ps1 -Suite 4                     # Suite 4: scored quick-ask (same 100 as Suite 3)
      .\run_all.ps1 -Suite 1 -Only "TP-*,F19"    # a subset of a suite, all models
      .\run_all.ps1 -Tasks tasks.json            # or point at any task file by name

  The four suites (see the EVAL_SUITE*.md docs at the repo root):
      1 -> suite1.json      100 atomic tool/framework tasks   (EVAL_SUITE.md)
      2 -> sessions.json    100 conversational 5-turn sessions (EVAL_SUITE2.md)
      3 -> EVAL_SUITE4.json 100 quick-ask standalone prompts   (EVAL_SUITE3.md)
      4 -> EVAL_SUITE4.json scored quick-ask, SAME 100 as #3   (EVAL_SUITE4.md)
#>
param(
  [string]$SlicerExe  = "D:\3D Slicer 5.12.2\Slicer.exe",
  [int]   $Suite      = 0,             # 1|2|3|4 -> picks the task file; 0 = use -Tasks
  [string]$Tasks      = "sessions.json",
  [string]$Only       = "",
  [string]$Approval   = "Manual",
  [int]   $TimeoutMin = 240
)

$RepoRoot = "D:\3dslicer\RadAssistant_DeepAgent"
$Autorun  = Join-Path $RepoRoot "deep\eval\eval_autorun.py"
$OutDir   = Join-Path $RepoRoot "eval_results"

# -Suite N maps to the right task file (absolute for the repo-root quick-ask file);
# if -Suite isn't given, fall back to -Tasks (default sessions.json) for back-compat.
if ($Suite -ne 0) {
  switch ($Suite) {
    1 { $Tasks = "suite1.json" }
    2 { $Tasks = "sessions.json" }
    3 { $Tasks = Join-Path $RepoRoot "EVAL_SUITE4.json" }
    4 { $Tasks = Join-Path $RepoRoot "EVAL_SUITE4.json" }
    default { Write-Error "Unknown -Suite $Suite (use 1, 2, 3 or 4)"; exit 1 }
  }
  Write-Host "Suite $Suite -> tasks: $Tasks" -ForegroundColor Cyan
}
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
# Slicer drops a ctkDICOM database + other scratch in its working dir -> corral it here
# (keeps the source folder deep\eval clean).
$CwdScratch = Join-Path $OutDir "_slicer_cwd"
if (-not (Test-Path $CwdScratch)) { New-Item -ItemType Directory -Path $CwdScratch | Out-Null }

# ---- MODELS TO TEST -------------------------------------------------------------
# Put the EXACT model string + Server URL you use in the panel's Model / Server fields.
# Add or remove rows freely; each row = one full run.
$Models = @(
  @{ model = "openai:qwen-vision"; server = "http://127.0.0.1:11445/v1"; key = "sk-no-auth" }
  # add rows once other servers/models are up (use a /v1 URL for OpenAI-compatible servers):
  # @{ model = "openai:some-other";     server = "http://127.0.0.1:11445/v1"; key = "sk-no-auth" }
  # @{ model = "anthropic:claude-...";  server = "";                          key = "sk-ant-..." }
)
# ---------------------------------------------------------------------------------

if (-not (Test-Path $SlicerExe)) { Write-Error "Slicer not found: $SlicerExe"; exit 1 }

foreach ($m in $Models) {
  Write-Host "===== $($m.model) =====" -ForegroundColor Cyan
  $env:RADEVAL_MODEL    = $m.model
  $env:RADEVAL_SERVER   = $m.server
  $env:RADEVAL_APIKEY   = $m.key
  $env:RADEVAL_APPROVAL = $Approval
  $env:RADEVAL_TASKS    = $Tasks
  $env:RADEVAL_ONLY     = $Only
  $env:RADEVAL_NOTE     = $m.model

  $p = Start-Process -FilePath $SlicerExe `
        -ArgumentList @("--no-splash", "--python-script", $Autorun) -PassThru `
        -WorkingDirectory $CwdScratch `
        -RedirectStandardOutput (Join-Path $OutDir "_slicer_stdout.log") `
        -RedirectStandardError  (Join-Path $OutDir "_slicer_stderr.log")
  if (-not $p.WaitForExit($TimeoutMin * 60 * 1000)) {
    Write-Host "  timeout after $TimeoutMin min -> killing Slicer" -ForegroundColor Yellow
    try { $p.Kill() } catch {}
    Start-Sleep -Seconds 5
  }
  Write-Host "----- tail of _autorun.log -----" -ForegroundColor DarkGray
  $alog = Join-Path $OutDir "_autorun.log"
  if (Test-Path $alog) { Get-Content $alog -Tail 20 } else { Write-Host "(no _autorun.log written - script may not have started)" -ForegroundColor Yellow }
  Write-Host "===== $($m.model) done (exit $($p.ExitCode)) =====" -ForegroundColor Green
}

Write-Host "All models finished. Reports: D:\3dslicer\RadAssistant_DeepAgent\eval_results\<run_id>\report.md"
