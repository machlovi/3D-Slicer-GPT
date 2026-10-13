"""LangChain-native Slicer tool surface over a SlicerSession (offline / mock path).

NOTE: the LIVE in-process agent does NOT use these tools — it wraps the native
engine registry (engine/radassistant_lib/tools.py) directly in inprocess.py.
This module exists to (1) drive MockSlicerSession in offline tests and (2) supply
the READ_ONLY / SEGMENTATION tool-name groups that subagents.py consumes.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import BaseTool, tool

from .sessions import SlicerSession, ToolOutcome


def _text(outcome: ToolOutcome) -> str:
    prefix = "Error: " if outcome.is_error and not outcome.text.lower().startswith("error") else ""
    return prefix + outcome.text


def _image_block(outcome: ToolOutcome) -> dict:
    return {
        "type": "image",
        "source_type": "base64",
        "data": outcome.image_b64,
        "mime_type": outcome.media_type,
    }


def build_slicer_tools(session: SlicerSession, *, vision: bool = False) -> list[BaseTool]:
    """Build the Slicer tool set bound to one session."""

    @tool
    def get_scene_overview() -> str:
        """List everything loaded in the Slicer scene: volumes (with dimensions,
        spacing, window/level), segmentations and their segments, and what the 3D
        view shows. Call this first in a task and again whenever you need to
        verify the current state — it is the ground truth for what exists."""
        return _text(session.scene_overview())

    @tool
    def load_sample_data(name: str) -> str:
        """Download and load a built-in anonymized sample dataset by name
        (e.g. 'CTChest', 'MRHead', 'CTACardio'). Use when the user asks to try
        a workflow but no data is loaded."""
        return _text(session.load_sample_data(name))

    @tool
    def set_window_level(
        volume_name: str,
        preset: str | None = None,
        window: float | None = None,
        level: float | None = None,
    ) -> str:
        """Set a volume's display window/level. Prefer a radiology preset
        ('lung', 'bone', 'soft_tissue', 'abdomen', 'brain'); pass explicit
        window+level only for unusual cases. Use before showing anatomy so the
        user can see what you are working on."""
        return _text(session.set_window_level(volume_name, preset, window, level))

    @tool
    def take_screenshot(view: str = "full"):
        """Capture the current Slicer view ('full', 'red', 'yellow', 'green' or
        '3d'). With a vision-capable model the image is attached so you can
        LOOK at it; with a text-only model you get a confirmation string and
        should verify with get_scene_overview / measurements instead."""
        outcome = session.take_screenshot(view)
        if vision and outcome.image_b64 and not outcome.is_error:
            return [{"type": "text", "text": outcome.text}, _image_block(outcome)]
        return _text(outcome)

    @tool
    def list_segments(segmentation_name: str | None = None) -> str:
        """List segments (name, visibility, colour) in one segmentation, or in
        all segmentations when no name is given. Use to check what a
        segmentation step actually produced."""
        return _text(session.list_segments(segmentation_name))

    @tool
    def threshold_segmentation(
        volume_name: str,
        segment_name: str,
        lower_threshold: float,
        upper_threshold: float,
    ) -> str:
        """Create a new segment by intensity thresholding a volume (HU band for
        CT), using Slicer's validated Segment Editor Threshold effect. Use for
        well-characterised bands (air-filled lung: -1000..-400 HU; bone:
        300..3000 HU). Do NOT invent thresholds for tissue you are unsure
        about — say so instead."""
        return _text(
            session.threshold_segmentation(volume_name, segment_name, lower_threshold, upper_threshold)
        )

    @tool
    def filter_segment_islands(
        segment_name: str,
        operation: str,
        min_size_ml: float = 5.0,
    ) -> str:
        """Clean up a segment with the Segment Editor Islands effect. operation
        is 'remove_small' (speckle removal, uses min_size_ml), 'keep_largest'
        (WARNING: deletes all but one connected component — wrong for paired
        organs like lungs) or 'split_to_segments'. Use dedicated cleanup tools;
        never hand-write voxel code for this."""
        return _text(session.filter_segment_islands(segment_name, operation, min_size_ml))

    @tool
    def show_segmentation_3d(segmentation_name: str | None = None) -> str:
        """Build the closed-surface representation and show a segmentation in
        the 3D view. Call after creating or editing segments so the user can
        see the result."""
        return _text(session.show_segmentation_3d(segmentation_name))

    @tool
    def measure_segment_volumes(segmentation_name: str | None = None) -> str:
        """Compute per-segment volumes in mL (cm3) with Slicer's
        SegmentStatistics module. This is the ONLY acceptable source for any
        volume number you report — never estimate."""
        return _text(session.measure_segment_volumes(segmentation_name))

    @tool
    def segment_statistics(segment_name: str) -> str:
        """Volume plus intensity statistics (mean/median/min/max/std HU) for
        one segment. Use when the user asks about density or intensity, or to
        sanity-check that a segment contains the tissue you intended."""
        return _text(session.segment_statistics(segment_name))

    @tool
    def run_total_segmentator(volume_name: str, task: str = "total") -> str:
        """Run the TotalSegmentator AI model to auto-segment 100+ anatomical
        structures on a CT volume. This is the clean validated path for
        anatomical segmentation — prefer it over thresholding when the user
        wants real anatomy. Requires the TotalSegmentator extension: if this
        reports the extension is not loaded, call ensure_slicer_extension
        first. Heavy: takes minutes."""
        return _text(session.run_total_segmentator(volume_name, task))

    @tool
    def ensure_slicer_extension(extension_name: str) -> str:
        """Detect and, if needed, load/install a Slicer extension so its module
        and tools become usable. Call this BEFORE a tool that depends on an
        extension (e.g. 'TotalSegmentator' before run_total_segmentator,
        'SlicerRadiomics' before extract_radiomics). It first checks whether the
        extension is already loaded — use it to resolve "extension not found /
        not detected" situations. NEVER hand-write execute_python to import or
        install an extension; use this tool."""
        return _text(session.ensure_extension(extension_name))

    @tool
    def set_layout(layout: str) -> str:
        """Switch the viewport layout. Options: 'four_up', 'conventional',
        '3d_only', 'red_only' (axial), 'yellow_only' (sagittal), 'green_only'
        (coronal), 'side_by_side'. Use to give the user the right view for the
        task (e.g. 'side_by_side' to compare two studies)."""
        return _text(session.set_layout(layout))

    @tool
    def center_views() -> str:
        """Recenter and fit all slice views to the data and reset the 3D camera.
        Use after loading data, or when the user says the view is panned/zoomed
        off and wants it back to normal."""
        return _text(session.center_views())

    @tool
    def enable_volume_rendering(volume_name: str, preset: str | None = None) -> str:
        """Show a volume in 3D via GPU volume rendering — a DISPLAY, not a
        segmentation. Optional preset e.g. 'CT-Bone', 'CT-Lung',
        'CT-Chest-Contrast-Enhanced', 'MR-Default'. Use for a fast 3D picture
        (tumour board, orientation); do NOT use it when the user needs a
        measurable object — create a segmentation for that."""
        return _text(session.enable_volume_rendering(volume_name, preset))

    @tool
    def load_file(path: str) -> str:
        """Load a single image or model from a file path (NRRD/NIfTI/NHDR volume,
        or VTK/STL/OBJ model). For a FOLDER of DICOM slices use
        import_dicom_folder instead. Reports the node that loaded, or a clean
        not-found / unsupported-format message."""
        return _text(session.load_file(path))

    @tool
    def import_dicom_folder(path: str) -> str:
        """Index and load a DIRECTORY of DICOM files. Use when the user points at
        a folder of .dcm slices (not a single file). Verify what actually came in
        with get_scene_overview — a folder can hold several series."""
        return _text(session.import_dicom_folder(path))

    @tool
    def jump_to_position(r: float, a: float, s: float) -> str:
        """Center all slice views on an RAS coordinate (millimetres). Use to
        navigate to coordinates the user gives, or ones you got from a tool. Do
        NOT invent a coordinate — if you don't have one, place/measure first or ask."""
        return _text(session.jump_to_position(r, a, s))

    @tool
    def jump_to_segment(segment_name: str) -> str:
        """Center all slice views on a named segment (matched loosely, e.g.
        'right kidney' -> 'kidney_right'). Use to take the user to a structure
        that has been segmented; errors clearly if there is no such segment."""
        return _text(session.jump_to_segment(segment_name))

    @tool
    def rotate_3d_view(direction: str) -> str:
        """Aim the 3D camera along an anatomical axis: 'anterior', 'posterior',
        'left', 'right', 'superior', 'inferior'. Needs a layout with a 3D view —
        if there isn't one, switch to 'four_up' or '3d_only' via set_layout first."""
        return _text(session.rotate_3d_view(direction))

    @tool
    def place_point(r: float, a: float, s: float, name: str | None = None) -> str:
        """Place a markup point (fiducial) at an RAS coordinate (mm), optionally
        named. Use to mark a location the user indicates, e.g. before measuring."""
        return _text(session.place_point(r, a, s, name))

    @tool
    def measure_distance(r1: float, a1: float, s1: float, r2: float, a2: float, s2: float) -> str:
        """Measure the straight-line distance (mm) between two RAS points, drawing
        a line markup. Use for a lesion long-axis / diameter once you have both
        endpoints. Report the returned number — never estimate a size by eye."""
        return _text(session.measure_distance(r1, a1, s1, r2, a2, s2))

    @tool
    def set_segment_visibility(segment_name: str, visible: bool) -> str:
        """Show or hide a segment in the views. Hiding is NOT deleting — a hidden
        segment still counts toward totals and the 3D build; use delete_segments
        to actually remove one."""
        return _text(session.set_segment_visibility(segment_name, visible))

    @tool
    def set_segment_color(segment_name: str, color: str) -> str:
        """Recolour a segment. color is a name: red, green, blue, yellow, cyan,
        magenta, orange, white, gray, purple, pink. Use for figures or to
        distinguish structures."""
        return _text(session.set_segment_color(segment_name, color))

    @tool
    def highlight_segment(segment_name: str) -> str:
        """Emphasise one segment (fully opaque) while dimming the rest. Use to
        draw attention to a structure without hiding or deleting the others."""
        return _text(session.highlight_segment(segment_name))

    @tool
    def smooth_segment(segment_name: str, method: str = "median", kernel_mm: float = 3.0) -> str:
        """Smooth a blocky/staircased segment with the Segment Editor Smoothing
        effect. method: 'median' (default), 'gaussian' (soft rounding), 'opening'
        (removes thin spurs), 'closing' (fills small pits/holes). Changes volume
        slightly — re-measure after. Never hand-write VTK smoothing."""
        return _text(session.smooth_segment(segment_name, method, kernel_mm))

    @tool
    def grow_shrink_segment(segment_name: str, margin_mm: float | None = None,
                            margin_axial_mm: float | None = None,
                            margin_si_mm: float | None = None) -> str:
        """Grow (dilate, +) or shrink (erode, -) a segment by a margin in mm.
        UNIFORM: give margin_mm. ANISOTROPIC (e.g. an RT PTV of 10 mm sup-inf and
        5 mm axial): give margin_axial_mm (in-plane) AND margin_si_mm. All
        supplied axis margins must share one sign. Uses the validated Margin
        effect / SimpleITK morphology — do NOT hand-write Python for margins."""
        return _text(session.grow_shrink_segment(segment_name, margin_mm, margin_axial_mm, margin_si_mm))

    @tool
    def merge_segments(segment_names: list[str], new_name: str | None = None) -> str:
        """Union two or more segments (within ONE segmentation) into the first,
        optionally renaming it; the others are removed. E.g. combine left+right
        lung islands into 'Lungs'. Give at least two names."""
        return _text(session.merge_segments(segment_names, new_name))

    @tool
    def delete_segments(segment_names: list[str]) -> str:
        """Permanently remove one or more segments — DESTRUCTIVE and irreversible,
        so it requires human approval (except in auto mode). Name exactly which to
        delete, and verify first (e.g. a huge 'lung' may actually be external air)."""
        return _text(session.delete_segments(segment_names))

    @tool
    def execute_python(code: Annotated[str, "Python source to run inside Slicer"]) -> str:
        """LAST RESORT: run arbitrary Python inside Slicer (slicer, vtk, qt,
        numpy available). Requires human approval. Use ONLY when no dedicated
        tool can do the job, keep it short and read-only where possible, and
        never re-implement segmentation/measurement logic that a validated
        tool provides."""
        return _text(session.exec_python(code))

    @tool
    def start_segmentation_recording(output_filename: str = "slicer_cleanup_log.json") -> str:
        """Start recording user segmentation actions (paint, erase, clicks, brush sizes) in 3D Slicer."""
        return _text(session.start_segmentation_recording(output_filename))

    @tool
    def stop_segmentation_recording() -> str:
        """Stop recording user segmentation actions and save the recorded log to disk."""
        return _text(session.stop_segmentation_recording())

    @tool
    def get_segmentation_recording_status() -> str:
        """Get current status of the segmentation action recording."""
        return _text(session.get_segmentation_recording_status())

    @tool
    def mimic_segmentation_cleanup(trajectory_path: str, target_segmentation: str, source_volume: str = "", target_volume: str = "") -> str:
        """Replay recorded segmentation edits on a new target volume, using optional image registration to map coordinate systems."""
        return _text(session.mimic_segmentation_cleanup(trajectory_path, target_segmentation, source_volume, target_volume))

    return [
        get_scene_overview,
        load_sample_data,
        set_window_level,
        take_screenshot,
        list_segments,
        threshold_segmentation,
        filter_segment_islands,
        show_segmentation_3d,
        measure_segment_volumes,
        segment_statistics,
        run_total_segmentator,
        ensure_slicer_extension,
        set_layout,
        center_views,
        enable_volume_rendering,
        load_file,
        import_dicom_folder,
        jump_to_position,
        jump_to_segment,
        rotate_3d_view,
        place_point,
        measure_distance,
        set_segment_visibility,
        set_segment_color,
        highlight_segment,
        smooth_segment,
        grow_shrink_segment,
        merge_segments,
        delete_segments,
        execute_python,
        start_segmentation_recording,
        stop_segmentation_recording,
        get_segmentation_recording_status,
        mimic_segmentation_cleanup,
    ]




READ_ONLY_TOOL_NAMES = (
    "get_scene_overview",
    "take_screenshot",
    "list_segments",
    "measure_segment_volumes",
    "segment_statistics",
)

SEGMENTATION_TOOL_NAMES = (
    "get_scene_overview",
    "list_segments",
    "threshold_segmentation",
    "filter_segment_islands",
    "show_segmentation_3d",
    "measure_segment_volumes",
    "segment_statistics",
    "run_total_segmentator",
    "set_window_level",
    "start_segmentation_recording",
    "stop_segmentation_recording",
    "get_segmentation_recording_status",
    "mimic_segmentation_cleanup",
)
