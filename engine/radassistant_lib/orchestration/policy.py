"""Deterministic policy gate — enforceable safety, not prose.

Research is unanimous: prompt rules are probabilistic guidance, not enforcement
(models have been observed silently dropping medical disclaimers). So domain policy
lives in CODE, as a gate outside the token stream, belt-and-suspenders with the
system prompt. Two enforcement points:

  1. authorize(tool, args)  — pre-action gate: allow / approve (human) / deny.
       · read-only ops           -> allow
       · destructive/irreversible -> approve  (reuse the existing modal dialog)
       · off-machine egress w/ PHI -> deny     (breaks the "lethal trifecta")
  2. DiagnosisGuard.scan(text) — output rail: flag diagnostic/treatment language so
       the executor can rewrite to descriptive + append the scope disclaimer.

Plus PHIScrubber, used to guard arguments to any tool that leaves the machine.

Pure stdlib (re only) → unit-testable outside Slicer (see tests/test_policy.py).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# --- tool risk classification ----------------------------------------------
# Names are matched exactly OR by the keyword patterns below, so connector tools
# (which we prefix-namespace) are covered without enumerating all ~84.

_DESTRUCTIVE_EXACT = {
    "execute_python", "clear_scene", "delete_node", "save_file", "save_scene",
    "remove_node", "convert_labelmap_to_segmentation",
}
_DESTRUCTIVE_PATTERNS = (
    "delete", "clear_", "remove_", "_remove", "save_", "export_", "write_",
    "overwrite", "apply_transform", "segment_clear",
)
# Tools that send data OFF the machine — the egress leg of the lethal trifecta.
_PHI_EGRESS_EXACT = {"web_search", "web_fetch", "search_web", "fetch_url"}
_PHI_EGRESS_PATTERNS = ("web_", "http_", "upload", "_egress", "cloud_")
# Heavy compute — candidates for HPC offload (not a safety risk, an advisory tier).
_HEAVY_EXACT = {"run_total_segmentator", "extract_radiomics"}
_HEAVY_PATTERNS = ("nninteractive", "medgemma", "totalsegmentator", "radiomics")


def _match(name, exact, patterns):
    n = (name or "").lower()
    if n in exact:
        return True
    return any(p in n for p in patterns)


def classify_tool(name) -> str:
    """Return a risk tier: 'phi_egress' | 'destructive' | 'heavy' | 'read_only'."""
    if _match(name, _PHI_EGRESS_EXACT, _PHI_EGRESS_PATTERNS):
        return "phi_egress"
    if _match(name, _DESTRUCTIVE_EXACT, _DESTRUCTIVE_PATTERNS):
        return "destructive"
    if _match(name, _HEAVY_EXACT, _HEAVY_PATTERNS):
        return "heavy"
    return "read_only"


@dataclass
class PolicyDecision:
    action: str            # "allow" | "approve" | "deny"
    risk: str
    reason: str = ""
    phi_matches: List[str] = field(default_factory=list)

    @property
    def allowed(self):
        return self.action == "allow"


def authorize(tool_name, args=None, *, scene_terms=None) -> PolicyDecision:
    """Pre-action gate. `scene_terms` = current scene node names, so we can detect
    PHI being funneled into an off-machine tool argument."""
    risk = classify_tool(tool_name)
    args = args or {}

    if risk == "phi_egress":
        blob = " ".join(str(v) for v in _flatten(args))
        safe, matches = PHIScrubber(scene_terms).scan(blob)
        if not safe:
            return PolicyDecision(
                "deny", risk,
                reason=("refusing to send possible PHI/local identifiers off the "
                        "machine (" + ", ".join(matches[:5]) + "). Strip patient "
                        "identifiers and retry."),
                phi_matches=matches)
        return PolicyDecision(
            "approve", risk,
            reason="first off-machine request this session — confirm before sending.")

    if risk == "destructive":
        return PolicyDecision(
            "approve", risk,
            reason=f"'{tool_name}' modifies or deletes scene/disk state — needs approval.")

    return PolicyDecision("allow", risk)


def _flatten(obj):
    """Yield scalar values from nested dict/list args."""
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _flatten(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _flatten(v)
    else:
        yield obj


# --- diagnosis / treatment output rail --------------------------------------

_DIAGNOSIS_PATTERNS = [
    r"\bmalignant\b", r"\bbenign\b", r"\bcancer(ous)?\b", r"\bcarcinoma\b",
    r"\bmetasta(sis|tic|ses)\b", r"\bdiagnos(is|es|e|ed|tic)\b",
    r"\bthis (is|appears to be|looks like) (a )?(tumou?r|cancer|malignan)",
    r"\bconsistent with (a )?(malignan|cancer|carcinoma|metasta)",
    r"\bsuggestive of (malignan|cancer|carcinoma)",
    r"\bstage\s+(0|i{1,3}v?|iv)\b",
    r"\b(you|the patient) (have|has|likely has)\b",
    r"\b(recommend|prescrib|advise)\w*\s+(a\s+)?(biopsy|surgery|chemo|radiation|treatment)",
    r"\bprognosis\b",
]
_DIAGNOSIS_RE = [re.compile(p, re.IGNORECASE) for p in _DIAGNOSIS_PATTERNS]

DISCLAIMER = ("_RadAssistant is a research/visualization aid, not a diagnostic device. "
              "The above describes and measures image features only; interpretation is "
              "the physician's._")


class DiagnosisGuard:
    """Flags diagnostic / interpretive / treatment language in drafted output.

    Deliberately targets strong ASSERTIONS ('this is malignant', 'stage III',
    'recommend a biopsy'), not neutral anatomy words ('tumor segment', 'lesion
    volume'), to avoid false positives on legitimate descriptive text.
    """

    def scan(self, text):
        if not text:
            return True, []
        matches = []
        for rx in _DIAGNOSIS_RE:
            m = rx.search(text)
            if m:
                matches.append(m.group(0))
        return (len(matches) == 0), matches

    def enforce(self, text):
        """Return (clean_text, was_flagged). If flagged, append the disclaimer
        rather than deleting content (the model's description may still be useful)."""
        ok, matches = self.scan(text)
        if ok:
            return text, False
        return text.rstrip() + "\n\n" + DISCLAIMER, True


# --- PHI scrubber (guards off-machine tool arguments) -----------------------

class PHIScrubber:
    """Heuristic detector for likely PHI / local identifiers in a string.

    Not a certified de-identifier — it is a defense-in-depth guard so that scene
    node names, patient IDs, dates, and local file paths do not get funneled into
    a web search/fetch. `scene_terms` are the current scene's node names, passed
    in by the caller so patient-derived names are caught explicitly.
    """

    _MRN = re.compile(r"\b\d{6,}\b")                              # long digit runs
    _DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
    _PATH = re.compile(r"([A-Za-z]:\\[^\s]+|/(?:home|Users|data|gpfs|mnt)/[^\s]+)")
    _ACCESSION = re.compile(r"\b[A-Z]{2,}\d{4,}\b")              # e.g. UPENN00123

    def __init__(self, scene_terms=None):
        # keep only distinctive scene names (skip trivial/common tokens)
        self.scene_terms = [t for t in (scene_terms or [])
                            if t and len(t) >= 4 and t.lower() not in _COMMON_NODE_NAMES]

    def scan(self, text):
        """Return (is_safe, matches)."""
        if not text:
            return True, []
        matches = []
        for rx in (self._PATH, self._DATE, self._ACCESSION, self._MRN):
            matches += rx.findall(text)
        low = text.lower()
        for term in self.scene_terms:
            if term.lower() in low:
                matches.append(term)
        # flatten any tuple groups from findall
        flat = []
        for m in matches:
            flat.append(m if isinstance(m, str) else next((x for x in m if x), ""))
        flat = [m for m in flat if m]
        return (len(flat) == 0), flat


_COMMON_NODE_NAMES = {"mrhead", "ctchest", "volume", "segmentation", "model",
                      "scene", "red", "green", "yellow", "none"}
