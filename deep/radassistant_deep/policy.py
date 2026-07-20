"""Deterministic safety policy — a port of RadAssistant's v2 ``policy.py`` + ``approval.py``.

RadAssistant's design doctrine (docs/ARCHITECTURE.md): prompt rules are
probabilistic *guidance*; enforcement lives in code. This module is that code
for the deep-agent port:

* ``classify_tool``   — what kind of action is this? (exact names + keyword
                        patterns so connector-prefixed tools are covered)
* ``approval_tier``   — refinement used by the approval matrix
* ``should_ask``      — the Manual / Accept / Auto matrix
* ``interrupt_config_for_mode`` — compiles the matrix into the ``interrupt_on``
                        mapping consumed by ``create_deep_agent`` (LangChain's
                        HumanInTheLoopMiddleware then owns the pause/resume)
* ``PHIScrubber``     — flags MRNs, dates, paths, accession IDs, scene names
* ``DiagnosisGuard``  — output rail: appends a disclaimer to diagnostic text

Hard rule preserved from RadAssistant: PHI egress is *denied*, never merely
"asked about" — see ``middleware.PolicyMiddleware``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

Tier = Literal["read_only", "reversible", "heavy", "code", "irreversible", "phi_egress"]
ApprovalMode = Literal["manual", "accept", "auto"]

APPROVAL_MODES: tuple[ApprovalMode, ...] = ("manual", "accept", "auto")

# --- classification -----------------------------------------------------------

# Exact names first (native tools), then keyword patterns so namespaced
# connector tools (st_delete_node, idc_download_series, ...) classify correctly
# without enumerating every one.
_PHI_EGRESS_NAMES = {"web_search", "web_fetch"}
_PHI_EGRESS_PATTERNS = ("web_", "search", "fetch", "upload", "send_", "download", "export_report")

_CODE_NAMES = {"execute_python", "execute"}

_IRREVERSIBLE_PATTERNS = ("delete", "remove_node", "clear_scene", "close_scene", "overwrite")

_HEAVY_NAMES = {"run_total_segmentator", "extract_radiomics", "ensure_slicer_extension"}
_HEAVY_PATTERNS = ("segmentator", "radiomics", "train", "register_volumes", "monai", "nninteractive")

_READ_ONLY_NAMES = {
    "get_scene_overview",
    "take_screenshot",
    "list_segments",
    "measure_segment_volumes",
    "segment_statistics",
    "measure_distance",
    "read_skill",
    # deep-agent built-ins
    "ls",
    "read_file",
    "glob",
    "grep",
    "write_todos",
    "task",
    "record_learning",
}


def classify_tool(name: str) -> Literal["phi_egress", "destructive", "heavy", "read_only", "reversible"]:
    """Coarse classification, mirroring RadAssistant ``policy.classify_tool``."""
    n = name.lower()
    if n in _PHI_EGRESS_NAMES or any(p in n for p in _PHI_EGRESS_PATTERNS):
        return "phi_egress"
    if n in _CODE_NAMES or any(p in n for p in _IRREVERSIBLE_PATTERNS):
        return "destructive"
    if n in _HEAVY_NAMES or any(p in n for p in _HEAVY_PATTERNS):
        return "heavy"
    if n in _READ_ONLY_NAMES or n.startswith(("get_", "list_", "measure_", "show_", "read_")):
        return "read_only"
    return "reversible"


def approval_tier(name: str) -> Tier:
    """Refined tier for the approval matrix (RadAssistant ``approval.approval_tier``).

    ``destructive`` splits into ``code`` (execute_python: auditable but
    arbitrary) vs ``irreversible`` (deletes: bounded but permanent).
    """
    coarse = classify_tool(name)
    if coarse == "destructive":
        return "code" if name.lower() in _CODE_NAMES else "irreversible"
    if coarse == "phi_egress":
        return "phi_egress"
    if coarse == "heavy":
        return "heavy"
    if coarse == "read_only":
        return "read_only"
    return "reversible"


def should_ask(mode: ApprovalMode, tier: Tier) -> bool:
    """The Manual / Accept / Auto approval matrix (RadAssistant ``approval.should_ask``).

    read_only and reversible actions never ask; ``auto`` never asks;
    ``accept`` asks only for irreversible actions and PHI egress;
    ``manual`` asks for everything non-trivial.
    """
    if tier in ("read_only", "reversible"):
        return False
    if mode == "auto":
        return False
    if mode == "accept":
        return tier in ("irreversible", "phi_egress")
    return tier in ("heavy", "code", "irreversible", "phi_egress")  # manual


def interrupt_config_for_mode(mode: ApprovalMode, tool_names: Iterable[str]) -> dict[str, dict]:
    """Compile the matrix into ``create_deep_agent(interrupt_on=...)``.

    Only tools whose tier requires asking in this mode get an entry; the
    human may approve or reject (with a message the model then sees).
    """
    config: dict[str, dict] = {}
    for name in tool_names:
        tier = approval_tier(name)
        if should_ask(mode, tier):
            config[name] = {
                "allowed_decisions": ["approve", "reject"],
                "description": f"{tier} action — requires human approval in {mode} mode",
            }
    return config


# --- PHI scrubber ---------------------------------------------------------------

_COMMON_SCENE_WORDS = {
    "volume", "segmentation", "segment", "model", "markups", "transform",
    "mrhead", "ctchest", "cta", "ct", "mri", "lungs", "lung", "bone", "brain",
    "liver", "aorta", "left", "right", "table", "scene", "slicer",
}


@dataclass
class PHIFinding:
    kind: str
    value: str


@dataclass
class PHIScrubber:
    """Flags likely PHI in text destined to leave the machine.

    Port of RadAssistant ``policy.PHIScrubber``: MRN-like digit runs, dates,
    local file paths, accession-style IDs, and distinctive scene node names.
    """

    scene_terms: tuple[str, ...] = ()

    _MRN = re.compile(r"\b\d{6,}\b")
    _DATE = re.compile(
        r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}\.\d{1,2}\.\d{2,4})\b"
    )
    _PATH = re.compile(r"([A-Za-z]:\\[^\s\"']+|/(?:home|Users|data|mnt)/[^\s\"']+)")
    # no trailing \b: accession IDs often end in a check letter (ACC20240105X)
    _ACCESSION = re.compile(r"\b[A-Z]{2,}\d{4,}")

    def findings(self, text: str) -> list[PHIFinding]:
        found: list[PHIFinding] = []
        for kind, rx in (
            ("mrn_like_number", self._MRN),
            ("date", self._DATE),
            ("file_path", self._PATH),
            ("accession_id", self._ACCESSION),
        ):
            for m in rx.finditer(text):
                found.append(PHIFinding(kind, m.group(0)))
        lowered = text.lower()
        for term in self.scene_terms:
            t = term.strip().lower()
            if len(t) >= 4 and t not in _COMMON_SCENE_WORDS and t in lowered:
                found.append(PHIFinding("scene_node_name", term))
        return found

    def is_clean(self, text: str) -> bool:
        return not self.findings(text)


def scene_terms_from(scene_text: str) -> tuple[str, ...]:
    """Extract quoted node names from a scene overview (RadAssistant ``harness.scene_terms_from``)."""
    return tuple(dict.fromkeys(re.findall(r"['\"]([^'\"]{2,64})['\"]", scene_text)))


# --- diagnosis output rail -------------------------------------------------------

DISCLAIMER = (
    "\n\n---\n*RadAssistant is a research and visualization aid, not a medical "
    "device. Nothing above is a diagnosis or treatment recommendation; findings "
    "must be reviewed by a qualified radiologist.*"
)

_DIAGNOSTIC_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bmalignan(t|cy)\b",
        r"\bbenign\b",
        r"\bmetasta(sis|ses|tic)\b",
        r"\bcarcinoma\b",
        r"\bstage\s+(i{1,3}v?|[1-4])\b",
        r"\brecommend(s|ed)?\s+(a\s+)?(biopsy|treatment|chemotherapy|surgery|resection)\b",
        r"\bprognosis\b",
        r"\bdiagnos(is|es|tic of|ed)\b",
        r"\bconsistent with\s+\w+oma\b",
    )
]


@dataclass
class DiagnosisGuard:
    """Scans drafted output for diagnostic assertions; appends (never deletes)."""

    extra_patterns: list[re.Pattern] = field(default_factory=list)

    def flags(self, text: str) -> bool:
        return any(rx.search(text) for rx in (*_DIAGNOSTIC_PATTERNS, *self.extra_patterns))

    def enforce(self, text: str) -> str:
        if self.flags(text) and DISCLAIMER.strip() not in text:
            return text + DISCLAIMER
        return text
