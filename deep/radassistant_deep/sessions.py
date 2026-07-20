"""The Slicer execution seam.

RadAssistant runs *inside* Slicer and marshals every tool call onto the Qt
main thread through a ``MainThreadBridge``. The deep-agent port runs *outside*
Slicer, so the equivalent seam is a ``SlicerSession``: a typed object with one
method per scene operation.

Two implementations:

* ``MockSlicerSession``  — an in-memory scene with realistic, deterministic
  behaviour. This is what makes the whole agent rigorously testable (the same
  dependency-injection trick RadAssistant's own v2 test-suite uses), and what
  powers the offline demo.
* (the live path is the in-process Slicer module, not a session here)  # 
  built-in **Web Server** module's ``/slicer/exec`` endpoint. Every method
  sends a small Python snippet that uses the same validated Slicer APIs the
  in-process RadAssistant tools use, and prints one JSON object as its result.
  The HTTP transport is injectable so the wire protocol is unit-testable
  without Slicer.

Both honour the RadAssistant tool-outcome convention: **never raise** — return
``ToolOutcome(is_error=True, text=...)`` with a recovery hint instead.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Protocol

# 1x1 grey PNG — a stand-in screenshot for the mock session.
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNoaGj4DwAF"
    "hAK1eF9NIQAAAABJRU5ErkJggg=="
)

WINDOW_PRESETS = {
    "lung": (1500, -600),
    "bone": (1800, 400),
    "soft_tissue": (400, 50),
    "abdomen": (400, 50),
    "brain": (80, 40),
}

SAMPLE_DATASETS = {
    "CTChest": {"modality": "CT", "dims": (512, 512, 139), "spacing": (0.77, 0.77, 2.5)},
    "MRHead": {"modality": "MR", "dims": (256, 256, 130), "spacing": (1.0, 1.0, 1.3)},
    "CTACardio": {"modality": "CT", "dims": (512, 512, 321), "spacing": (0.68, 0.68, 0.8)},
}

# Viewport layouts: friendly name -> vtkMRMLLayoutNode constant attribute.
LAYOUTS = {
    "four_up": "SlicerLayoutFourUpView",
    "conventional": "SlicerLayoutConventionalView",
    "3d_only": "SlicerLayoutOneUp3DView",
    "red_only": "SlicerLayoutOneUpRedSliceView",       # axial
    "yellow_only": "SlicerLayoutOneUpYellowSliceView",  # sagittal
    "green_only": "SlicerLayoutOneUpGreenSliceView",    # coronal
    "side_by_side": "SlicerLayoutSideBySideView",
}

# Named colours for segments -> RGB in 0..1.
COLORS = {
    "red": (1.0, 0.0, 0.0), "green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0),
    "yellow": (1.0, 1.0, 0.0), "cyan": (0.0, 1.0, 1.0), "magenta": (1.0, 0.0, 1.0),
    "orange": (1.0, 0.5, 0.0), "white": (1.0, 1.0, 1.0), "gray": (0.5, 0.5, 0.5),
    "purple": (0.5, 0.0, 0.5), "pink": (1.0, 0.75, 0.8),
}

_VIEW_AXES = ("anterior", "posterior", "left", "right", "superior", "inferior")


@dataclass
class ToolOutcome:
    text: str
    image_b64: str | None = None
    media_type: str = "image/png"
    is_error: bool = False


def ok(text: str, image_b64: str | None = None) -> ToolOutcome:
    return ToolOutcome(text=text, image_b64=image_b64)


def err(text: str) -> ToolOutcome:
    return ToolOutcome(text=text, is_error=True)


class SlicerSession(Protocol):
    """One method per scene operation; every method returns a ToolOutcome."""

    def scene_overview(self) -> ToolOutcome: ...
    def load_sample_data(self, name: str) -> ToolOutcome: ...
    def set_window_level(self, volume_name: str, preset: str | None, window: float | None, level: float | None) -> ToolOutcome: ...
    def take_screenshot(self, view: str) -> ToolOutcome: ...
    def list_segments(self, segmentation_name: str | None) -> ToolOutcome: ...
    def threshold_segmentation(self, volume_name: str, segment_name: str, lower: float, upper: float) -> ToolOutcome: ...
    def filter_segment_islands(self, segment_name: str, operation: str, min_size_ml: float) -> ToolOutcome: ...
    def show_segmentation_3d(self, segmentation_name: str | None) -> ToolOutcome: ...
    def measure_segment_volumes(self, segmentation_name: str | None) -> ToolOutcome: ...
    def segment_statistics(self, segment_name: str) -> ToolOutcome: ...
    def run_total_segmentator(self, volume_name: str, task: str) -> ToolOutcome: ...
    def ensure_extension(self, extension_name: str) -> ToolOutcome: ...
    def set_layout(self, layout: str) -> ToolOutcome: ...
    def center_views(self) -> ToolOutcome: ...
    def enable_volume_rendering(self, volume_name: str, preset: str | None) -> ToolOutcome: ...
    def load_file(self, path: str) -> ToolOutcome: ...
    def import_dicom_folder(self, path: str) -> ToolOutcome: ...
    def jump_to_position(self, r: float, a: float, s: float) -> ToolOutcome: ...
    def jump_to_segment(self, segment_name: str) -> ToolOutcome: ...
    def rotate_3d_view(self, direction: str) -> ToolOutcome: ...
    def place_point(self, r: float, a: float, s: float, name: str | None) -> ToolOutcome: ...
    def measure_distance(self, r1: float, a1: float, s1: float, r2: float, a2: float, s2: float) -> ToolOutcome: ...
    def set_segment_visibility(self, segment_name: str, visible: bool) -> ToolOutcome: ...
    def set_segment_color(self, segment_name: str, color: str) -> ToolOutcome: ...
    def highlight_segment(self, segment_name: str) -> ToolOutcome: ...
    def smooth_segment(self, segment_name: str, method: str, kernel_mm: float) -> ToolOutcome: ...
    def grow_shrink_segment(self, segment_name: str, margin_mm: float | None, margin_axial_mm: float | None, margin_si_mm: float | None) -> ToolOutcome: ...
    def merge_segments(self, segment_names: list[str], new_name: str | None) -> ToolOutcome: ...
    def delete_segments(self, segment_names: list[str]) -> ToolOutcome: ...
    def exec_python(self, code: str) -> ToolOutcome: ...


# Slicer extensions the deep agent knows how to require, keyed by the exact
# EXTENSION name in the Extensions Manager (as it appears in
# ``extensionsManagerModel().installedExtensions``). ``modules`` are the Slicer
# scripted-module names that prove it is loaded and usable *this session*.
#
# Detection deliberately does NOT trust an importable pip package: e.g.
# ``import totalsegmentator`` succeeds from a bundled dependency even when the
# TotalSegmentator *extension* is not installed, which is a false positive.
KNOWN_EXTENSIONS = {
    "TotalSegmentator": {"modules": ["TotalSegmentator"]},
    "SlicerRadiomics": {"modules": ["SlicerRadiomics", "SlicerRadiomicsCLI"]},
    "SlicerVMTK": {"modules": ["VesselnessFiltering", "LevelSetSegmentation"]},
    "MONAIAuto3DSeg": {"modules": ["MONAIAuto3DSeg"]},
    "NNUNet": {"modules": ["nnUNet", "NNUNet"]},
    "NNInteractive": {"modules": ["nnInteractive"]},
}


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------

@dataclass
class _Segment:
    volume_ml: float
    color: tuple[float, float, float] = (0.9, 0.6, 0.65)
    visible: bool = True


@dataclass
class MockSlicerSession:
    """Deterministic in-memory Slicer scene.

    Numbers are computed from inputs by fixed formulas, so tests can assert
    exact values and the demo behaves identically on every run.
    """

    volumes: dict[str, dict] = field(default_factory=dict)
    segmentations: dict[str, dict[str, _Segment]] = field(default_factory=dict)
    shown_3d: list[str] = field(default_factory=list)
    screenshots: int = 0
    exec_log: list[str] = field(default_factory=list)
    calls: list[tuple[str, dict]] = field(default_factory=list)

    def _record(self, op: str, **args: object) -> None:
        self.calls.append((op, dict(args)))

    # -- helpers ---------------------------------------------------------------
    def _find_volume(self, name: str) -> str | None:
        if name in self.volumes:
            return name
        low = name.lower()
        for k in self.volumes:
            if low in k.lower():
                return k
        return None

    def _find_segment(self, name: str) -> tuple[str, str] | None:
        low = name.lower()
        for seg_node, segments in self.segmentations.items():
            for s in segments:
                if s.lower() == low:
                    return seg_node, s
        for seg_node, segments in self.segmentations.items():
            for s in segments:
                if low in s.lower():
                    return seg_node, s
        return None

    # -- protocol --------------------------------------------------------------
    def scene_overview(self) -> ToolOutcome:
        self._record("scene_overview")
        if not self.volumes and not self.segmentations:
            return ok("The Slicer scene is currently empty. No volumes, segmentations, models or markups are loaded.")
        lines = []
        for name, v in self.volumes.items():
            d, s = v["dims"], v["spacing"]
            lines.append(
                f"Volume '{name}': {v['modality']}, dims {d[0]}x{d[1]}x{d[2]}, "
                f"spacing {s[0]:.2f}/{s[1]:.2f}/{s[2]:.2f} mm, W/L {v.get('window', 400)}/{v.get('level', 40)}"
            )
        for name, segments in self.segmentations.items():
            seg_list = ", ".join(f"'{s}'" for s in segments)
            lines.append(f"Segmentation '{name}': segments [{seg_list}]")
        if self.shown_3d:
            lines.append(f"3D view shows: {', '.join(self.shown_3d)}")
        return ok("\n".join(lines))

    def load_sample_data(self, name: str) -> ToolOutcome:
        self._record("load_sample_data", name=name)
        meta = SAMPLE_DATASETS.get(name)
        if meta is None:
            return err(f"Unknown sample dataset '{name}'. Valid options: {', '.join(sorted(SAMPLE_DATASETS))}.")
        self.volumes[name] = dict(meta)
        return ok(f"Loaded sample dataset '{name}' ({meta['modality']}, dims {meta['dims']}).")

    def set_window_level(self, volume_name, preset, window, level) -> ToolOutcome:
        self._record("set_window_level", volume_name=volume_name, preset=preset, window=window, level=level)
        vol = self._find_volume(volume_name)
        if vol is None:
            return err(f"No volume matching '{volume_name}'. Loaded volumes: {', '.join(self.volumes) or 'none'}.")
        if preset:
            if preset not in WINDOW_PRESETS:
                return err(f"Unknown preset '{preset}'. Valid presets: {', '.join(sorted(WINDOW_PRESETS))}.")
            window, level = WINDOW_PRESETS[preset]
        if window is None or level is None:
            return err("Provide either a preset or both window and level values.")
        self.volumes[vol]["window"], self.volumes[vol]["level"] = window, level
        return ok(f"Set '{vol}' display to window {window} / level {level}.")

    def take_screenshot(self, view: str) -> ToolOutcome:
        self._record("take_screenshot", view=view)
        self.screenshots += 1
        return ok(f"Screenshot of '{view}' view captured.", image_b64=_TINY_PNG_B64)

    def list_segments(self, segmentation_name) -> ToolOutcome:
        self._record("list_segments", segmentation_name=segmentation_name)
        if not self.segmentations:
            return ok("No segmentations in the scene.")
        lines = []
        for node, segments in self.segmentations.items():
            if segmentation_name and segmentation_name.lower() not in node.lower():
                continue
            for sname, seg in segments.items():
                vis = "visible" if seg.visible else "hidden"
                lines.append(f"'{node}' / '{sname}': {vis}, color rgb{seg.color}")
        return ok("\n".join(lines) if lines else f"No segmentation matching '{segmentation_name}'.")

    def threshold_segmentation(self, volume_name, segment_name, lower, upper) -> ToolOutcome:
        self._record("threshold_segmentation", volume_name=volume_name, segment_name=segment_name, lower=lower, upper=upper)
        vol = self._find_volume(volume_name)
        if vol is None:
            return err(f"No volume matching '{volume_name}'. Loaded volumes: {', '.join(self.volumes) or 'none'}.")
        if upper <= lower:
            return err(f"upper_threshold ({upper}) must be greater than lower_threshold ({lower}).")
        # Deterministic fake volume: the canonical lung band on a chest CT
        # lands near physiology; anything else scales with band width.
        if vol == "CTChest" and lower <= -900 and -500 <= upper <= -300:
            volume_ml = 4600.0
        else:
            volume_ml = round(abs(upper - lower) * 2.5, 1)
        node = "Segmentation"
        self.segmentations.setdefault(node, {})[segment_name] = _Segment(volume_ml=volume_ml)
        return ok(
            f"Created segment '{segment_name}' in '{node}' by thresholding '{vol}' "
            f"[{lower}, {upper}] HU. Approximate volume: {volume_ml:.0f} mL."
        )

    def filter_segment_islands(self, segment_name, operation, min_size_ml) -> ToolOutcome:
        self._record("filter_segment_islands", segment_name=segment_name, operation=operation, min_size_ml=min_size_ml)
        found = self._find_segment(segment_name)
        if found is None:
            return err(f"No segment matching '{segment_name}'. Use list_segments to see what exists.")
        if operation not in ("remove_small", "keep_largest", "split_to_segments"):
            return err("operation must be one of remove_small, keep_largest, split_to_segments.")
        node, sname = found
        seg = self.segmentations[node][sname]
        if operation == "remove_small":
            seg.volume_ml = round(seg.volume_ml * 0.97, 1)
            return ok(f"Removed islands smaller than {min_size_ml} mL from '{sname}'. New volume ~{seg.volume_ml:.0f} mL.")
        if operation == "keep_largest":
            seg.volume_ml = round(seg.volume_ml * 0.55, 1)
            return ok(f"Kept only the largest island of '{sname}'. New volume ~{seg.volume_ml:.0f} mL.")
        return ok(f"Split '{sname}' into per-island segments.")

    def show_segmentation_3d(self, segmentation_name) -> ToolOutcome:
        self._record("show_segmentation_3d", segmentation_name=segmentation_name)
        if not self.segmentations:
            return err("No segmentation to show. Create one first (e.g. threshold_segmentation).")
        node = segmentation_name or next(iter(self.segmentations))
        if node not in self.segmentations:
            return err(f"No segmentation named '{node}'. Existing: {', '.join(self.segmentations)}.")
        if node not in self.shown_3d:
            self.shown_3d.append(node)
        return ok(f"Created closed-surface representation and enabled 3D display for '{node}'.")

    def measure_segment_volumes(self, segmentation_name) -> ToolOutcome:
        self._record("measure_segment_volumes", segmentation_name=segmentation_name)
        if not self.segmentations:
            return err("No segmentations to measure.")
        lines = ["segment | volume_ml"]
        for node, segments in self.segmentations.items():
            if segmentation_name and segmentation_name.lower() not in node.lower():
                continue
            for sname, seg in segments.items():
                lines.append(f"{sname} | {seg.volume_ml:.1f}")
        return ok("\n".join(lines))

    def segment_statistics(self, segment_name) -> ToolOutcome:
        self._record("segment_statistics", segment_name=segment_name)
        found = self._find_segment(segment_name)
        if found is None:
            return err(f"No segment matching '{segment_name}'. Use list_segments to see what exists.")
        node, sname = found
        seg = self.segmentations[node][sname]
        # Deterministic fake HU stats derived from the volume value.
        mean = round(-700 + seg.volume_ml % 100, 1)
        return ok(
            f"Statistics for '{sname}' ({node}): volume {seg.volume_ml:.1f} mL, "
            f"mean {mean} HU, median {mean + 12} HU, min -1000 HU, max -350 HU, std 96 HU."
        )

    def run_total_segmentator(self, volume_name, task) -> ToolOutcome:
        self._record("run_total_segmentator", volume_name=volume_name, task=task)
        vol = self._find_volume(volume_name)
        if vol is None:
            return err(f"No volume matching '{volume_name}'.")
        node = "TotalSegmentator"
        produced = {
            "lung_left": _Segment(volume_ml=2100.0),
            "lung_right": _Segment(volume_ml=2400.0),
            "trachea": _Segment(volume_ml=38.0),
            "heart": _Segment(volume_ml=640.0),
        }
        self.segmentations.setdefault(node, {}).update(produced)
        return ok(
            f"TotalSegmentator ({task}) finished on '{vol}': created {len(produced)} segments "
            f"in '{node}' ({', '.join(produced)})."
        )

    def ensure_extension(self, extension_name: str) -> ToolOutcome:
        self._record("ensure_extension", extension_name=extension_name)
        self.extensions_installed = getattr(self, "extensions_installed", set())
        if extension_name not in KNOWN_EXTENSIONS:
            return err(
                f"Unknown extension '{extension_name}'. Known: {', '.join(sorted(KNOWN_EXTENSIONS))}."
            )
        self.extensions_installed.add(extension_name)
        return ok(f"Extension '{extension_name}' is available. (mock)")

    def exec_python(self, code: str) -> ToolOutcome:
        self._record("exec_python", code=code)
        self.exec_log.append(code)
        if "boom" in code:
            return err("Traceback (most recent call last): RuntimeError: boom")
        return ok("Code executed. (mock: no-op)")

    def set_layout(self, layout: str) -> ToolOutcome:
        self._record("set_layout", layout=layout)
        if layout not in LAYOUTS:
            return err(f"Unknown layout '{layout}'. Options: {', '.join(sorted(LAYOUTS))}.")
        self.layout = layout
        return ok(f"Layout set to '{layout}'. (mock)")

    def center_views(self) -> ToolOutcome:
        self._record("center_views")
        return ok("Recentered all slice views and reset the 3D camera. (mock)")

    def enable_volume_rendering(self, volume_name: str, preset: str | None) -> ToolOutcome:
        self._record("enable_volume_rendering", volume_name=volume_name, preset=preset)
        v = self._find_volume(volume_name)
        if v is None:
            return err(f"No volume matching '{volume_name}'.")
        if v not in self.shown_3d:
            self.shown_3d.append(v)
        extra = f" (preset {preset})" if preset else ""
        return ok(f"Volume rendering enabled for '{v}'{extra}. (mock)")

    def load_file(self, path: str) -> ToolOutcome:
        self._record("load_file", path=path)
        name = path.replace("\\", "/").rstrip("/").split("/")[-1].split(".")[0] or "loaded"
        self.volumes[name] = {"modality": "?", "dims": (256, 256, 100), "spacing": (1.0, 1.0, 1.0)}
        return ok(f"Loaded '{name}' from {path}. (mock)")

    def import_dicom_folder(self, path: str) -> ToolOutcome:
        self._record("import_dicom_folder", path=path)
        self.volumes["DICOMSeries"] = {"modality": "CT", "dims": (512, 512, 120), "spacing": (0.7, 0.7, 2.0)}
        return ok(f"Imported DICOM from {path}: 1 series loaded. (mock)")

    def jump_to_position(self, r: float, a: float, s: float) -> ToolOutcome:
        self._record("jump_to_position", r=r, a=a, s=s)
        return ok(f"Jumped slice views to RAS ({r}, {a}, {s}). (mock)")

    def jump_to_segment(self, segment_name: str) -> ToolOutcome:
        self._record("jump_to_segment", segment_name=segment_name)
        hit = self._find_segment(segment_name)
        if hit is None:
            return err(f"No segment matching '{segment_name}'.")
        return ok(f"Centered views on segment '{hit[1]}'. (mock)")

    def rotate_3d_view(self, direction: str) -> ToolOutcome:
        self._record("rotate_3d_view", direction=direction)
        if direction not in _VIEW_AXES:
            return err(f"Unknown direction '{direction}'. Options: {', '.join(_VIEW_AXES)}.")
        return ok(f"Rotated 3D view to face {direction}. (mock)")

    def place_point(self, r: float, a: float, s: float, name: str | None) -> ToolOutcome:
        self._record("place_point", r=r, a=a, s=s, name=name)
        label = f" '{name}'" if name else ""
        return ok(f"Placed point{label} at RAS ({r}, {a}, {s}). (mock)")

    def measure_distance(self, r1, a1, s1, r2, a2, s2) -> ToolOutcome:
        self._record("measure_distance", r1=r1, a1=a1, s1=s1, r2=r2, a2=a2, s2=s2)
        d = ((r1 - r2) ** 2 + (a1 - a2) ** 2 + (s1 - s2) ** 2) ** 0.5
        return ok(f"Distance between the two points: {d:.1f} mm. (mock)")

    def _seg_obj(self, name):
        hit = self._find_segment(name)
        if hit is None:
            return None, None, None
        node, sname = hit
        return self.segmentations[node][sname], node, sname

    def set_segment_visibility(self, segment_name, visible) -> ToolOutcome:
        self._record("set_segment_visibility", segment_name=segment_name, visible=visible)
        seg, _, sname = self._seg_obj(segment_name)
        if seg is None:
            return err(f"No segment matching '{segment_name}'.")
        seg.visible = bool(visible)
        return ok(f"Set '{sname}' visibility to {bool(visible)}. (mock)")

    def set_segment_color(self, segment_name, color) -> ToolOutcome:
        self._record("set_segment_color", segment_name=segment_name, color=color)
        if color not in COLORS:
            return err(f"Unknown colour '{color}'. Options: {', '.join(sorted(COLORS))}.")
        seg, _, sname = self._seg_obj(segment_name)
        if seg is None:
            return err(f"No segment matching '{segment_name}'.")
        seg.color = COLORS[color]
        return ok(f"Set '{sname}' colour to {color}. (mock)")

    def highlight_segment(self, segment_name) -> ToolOutcome:
        self._record("highlight_segment", segment_name=segment_name)
        seg, _, sname = self._seg_obj(segment_name)
        if seg is None:
            return err(f"No segment matching '{segment_name}'.")
        return ok(f"Highlighted '{sname}' (others dimmed). (mock)")

    def smooth_segment(self, segment_name, method, kernel_mm) -> ToolOutcome:
        self._record("smooth_segment", segment_name=segment_name, method=method, kernel_mm=kernel_mm)
        if method not in ("median", "gaussian", "opening", "closing"):
            return err(f"Unknown method '{method}'. Options: median, gaussian, opening, closing.")
        seg, _, sname = self._seg_obj(segment_name)
        if seg is None:
            return err(f"No segment matching '{segment_name}'.")
        return ok(f"Smoothed '{sname}' ({method}, {kernel_mm} mm). (mock)")

    def grow_shrink_segment(self, segment_name, margin_mm, margin_axial_mm, margin_si_mm) -> ToolOutcome:
        self._record("grow_shrink_segment", segment_name=segment_name, margin_mm=margin_mm,
                     margin_axial_mm=margin_axial_mm, margin_si_mm=margin_si_mm)
        seg, _, sname = self._seg_obj(segment_name)
        if seg is None:
            return err(f"No segment matching '{segment_name}'.")
        if margin_axial_mm is not None or margin_si_mm is not None:
            ax = margin_axial_mm if margin_axial_mm is not None else (margin_mm or 0.0)
            si = margin_si_mm if margin_si_mm is not None else (margin_mm or 0.0)
            if ax == 0 and si == 0:
                return err("both margins are 0 - give a nonzero axial or superior-inferior margin")
            if (ax > 0 or si > 0) and (ax < 0 or si < 0):
                return err("mixed grow/shrink per axis isn't supported - use all-grow or all-shrink")
            verb = "Grew" if (ax > 0 or si > 0) else "Shrank"
            return ok(f"{verb} '{sname}' anisotropically ({abs(ax)} mm axial, {abs(si)} mm sup-inf). (mock)")
        if not margin_mm:
            return err("give margin_mm (uniform) or margin_axial_mm + margin_si_mm; 0 does nothing")
        verb = "Grew" if margin_mm > 0 else "Shrank"
        seg.volume_ml *= 1.1 if margin_mm > 0 else 0.9
        return ok(f"{verb} '{sname}' by {abs(margin_mm)} mm. (mock)")

    def merge_segments(self, segment_names, new_name) -> ToolOutcome:
        self._record("merge_segments", segment_names=segment_names, new_name=new_name)
        if not segment_names or len(segment_names) < 2:
            return err("give at least two segment names to merge")
        if self._find_segment(segment_names[0]) is None:
            return err(f"No segment matching '{segment_names[0]}'.")
        return ok(f"Merged {len(segment_names)} segments into '{new_name or segment_names[0]}'. (mock)")

    def delete_segments(self, segment_names) -> ToolOutcome:
        self._record("delete_segments", segment_names=segment_names)
        removed = []
        for nm in list(segment_names or []):
            hit = self._find_segment(nm)
            if hit:
                node, sname = hit
                self.segmentations[node].pop(sname, None)
                removed.append(sname)
        if not removed:
            return err(f"No segments matched: {segment_names}.")
        return ok(f"Deleted {len(removed)} segment(s): {', '.join(removed)}. (mock)")
