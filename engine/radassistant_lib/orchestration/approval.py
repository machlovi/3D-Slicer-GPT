"""Approval modes — Manual / Accept / Auto, like Claude Code's permission modes.

Today every action that needs approval pops a modal the user must click. That's right
for a first run, but painful when you're driving a long task. This adds a session mode
the user picks with a button, and the modal only appears when the mode + the action's
risk actually call for it:

  Manual  ask before every non-trivial action (execute_python, heavy jobs, deletes,
          off-machine egress). Safe default.
  Accept  auto-run the routine heavy work (code, long compute) once you've opted in,
          but STILL confirm the irreversible stuff (delete/clear/overwrite) and any
          off-machine egress.
  Auto    run everything without asking — EXCEPT sending patient data off the machine,
          which the policy layer hard-denies regardless of mode (medical safety is not
          a togglable convenience).

Read-only and reversible actions (screenshots, measurements, segmentation edits) never
prompt in any mode. Pure stdlib, unit-tested (tests/test_approval.py).
"""

MODES = ("manual", "accept", "auto")
DEFAULT_MODE = "manual"

_CODE_TOOLS = {"execute_python"}


def approval_tier(tool_name, base_risk=None):
    """Refine policy.classify_tool() into the tiers the mode matrix uses:
    read_only | reversible | heavy | code | irreversible | phi_egress."""
    from .policy import classify_tool
    base = base_risk or classify_tool(tool_name)
    if base in ("phi_egress", "read_only", "heavy"):
        return base
    if base != "destructive":
        return "reversible"
    # destructive splits into arbitrary code vs. irreversible data loss
    return "code" if (tool_name or "").lower() in _CODE_TOOLS else "irreversible"


def should_ask(mode, tier):
    """Given the session mode and a tool's tier, does this action need a human prompt?

    (PHI-egress-with-data is denied earlier by policy.authorize; here phi_egress means a
    clean off-machine request that is merely gated, not blocked.)
    """
    if tier in ("read_only", "reversible"):
        return False
    if mode == "auto":
        return False
    if mode == "accept":
        return tier in ("irreversible", "phi_egress")
    # manual: confirm everything non-trivial
    return True


def normalize(mode):
    m = (mode or "").strip().lower()
    return m if m in MODES else DEFAULT_MODE


def describe(mode):
    return {
        "manual": "Manual — confirm each action",
        "accept": "Accept — auto-run code/compute, confirm deletes & web",
        "auto": "Auto — run everything (PHI never leaves the machine)",
    }.get(normalize(mode), "")
