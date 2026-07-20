"""Tool registry: JSON-schema definitions sent to Claude + implementations.

Every implementation runs on the Qt main thread (dispatched by the bridge) and
returns a dict:

    {"text": str,                      # what the model reads
     "image_b64": str | None,          # optional PNG for the model to SEE
     "media_type": "image/png",
     "is_error": bool}

Design rules learned from the Talk2View analysis:
  - never raise out of a tool; return an error string with recovery hints
    (e.g. list the valid node names) so the model can self-correct
  - resolve names forgivingly (exact -> case-insensitive substring)
  - destructive or arbitrary actions (execute_python, clear_scene) require a
    human approval dialog before running
"""

import base64
import contextlib
import io
import math
import os
import tempfile

import ctk
import qt
import slicer
import vtk

WINDOW_LEVEL_PRESETS = {
    "lung":        (1500, -600),
    "bone":        (2000, 300),
    "soft_tissue": (400, 50),
    "brain":       (80, 40),
    "liver":       (150, 30),
    "mediastinum": (350, 50),
    "abdomen":     (350, 40),   # adopted from Talk2View SlicerTools presets
    "mri_t1":      (500, 250),
    "mri_t2":      (400, 200),
}

LAYOUTS = {
    "four_up": "SlicerLayoutFourUpView",
    "conventional": "SlicerLayoutConventionalView",
    "3d_only": "SlicerLayoutOneUp3DView",
    "red_only": "SlicerLayoutOneUpRedSliceView",
    "yellow_only": "SlicerLayoutOneUpYellowSliceView",
    "green_only": "SlicerLayoutOneUpGreenSliceView",
    "side_by_side": "SlicerLayoutSideBySideView",
    "3d_and_red": "SlicerLayoutOneUp3DView",  # closest single-view fallback
}

VIEW_AXES = {"left": 0, "right": 1, "posterior": 2, "anterior": 3,
             "inferior": 4, "superior": 5}


def _ok(text, image_b64=None):
    return {"text": text, "image_b64": image_b64,
            "media_type": "image/png", "is_error": False}


def _err(text):
    return {"text": "Error: " + text, "image_b64": None,
            "media_type": "image/png", "is_error": True}


def _module_present(module_name):
    """True if a scripted/loadable module is registered in THIS Slicer.

    ``slicer.modules`` keys are the lowercased module name, but rely on a
    case-insensitive scan of moduleNames() too so a naming quirk can't produce a
    false negative (the bug that made TotalSegmentator look 'not installed')."""
    if hasattr(slicer.modules, module_name.lower()):
        return True
    try:
        return any(n.lower() == module_name.lower() for n in slicer.util.moduleNames())
    except Exception:
        return False


def _extension_status(module_name, package_name):
    """Version-aware view of an optional extension in the RUNNING Slicer.

    Extensions are per-Slicer-version: installing one in Slicer 5.10 does NOT make
    it available in 5.8. This returns what THIS process can actually see so the
    error message can be honest about *where* it's looking instead of a flat
    'not installed' that contradicts what the user sees in the Extensions Manager.
    """
    import importlib.util
    status = {"module_name": module_name, "package_name": package_name}
    for key, getter in (("version", lambda: slicer.app.applicationVersion),
                        ("revision", lambda: slicer.app.revision)):
        try:
            status[key] = str(getter())
        except Exception:
            status[key] = "?"
    status["module_loaded"] = _module_present(module_name)
    try:
        status["package"] = importlib.util.find_spec(package_name) is not None
    except Exception:
        status["package"] = False
    on_disk = False
    try:
        install_path = slicer.app.extensionsInstallPath
        if install_path and os.path.isdir(os.path.join(install_path, module_name)):
            on_disk = True
    except Exception:
        pass
    status["on_disk_here"] = on_disk
    return status


# ---------------------------------------------------------------------------
# forgiving node / segment resolution
# ---------------------------------------------------------------------------

def _find_node(name, classes):
    nodes = []
    for cls in classes:
        nodes.extend(slicer.util.getNodesByClass(cls))
    for node in nodes:
        if node.GetName() == name:
            return node, None
    lowered = (name or "").lower()
    matches = [n for n in nodes if lowered and lowered in n.GetName().lower()]
    if len(matches) == 1:
        return matches[0], None
    available = ", ".join(f'"{n.GetName()}"' for n in nodes) or "(none)"
    return None, f"no node matching '{name}'. Available: {available}"


def _active_volume():
    """The volume currently shown as slice-view background, if any."""
    selection = slicer.app.applicationLogic().GetSelectionNode()
    volume_id = selection.GetActiveVolumeID() if selection else None
    node = slicer.mrmlScene.GetNodeByID(volume_id) if volume_id else None
    if node is not None and node.IsA("vtkMRMLScalarVolumeNode"):
        return node
    return None


def _find_volume(name):
    if not name:  # default: the displayed background volume, else the only one
        active = _active_volume()
        if active is not None:
            return active, None
        volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
        if len(volumes) == 1:
            return volumes[0], None
        if not volumes:
            return None, "no volumes are loaded"
        names = ", ".join(f'"{n.GetName()}"' for n in volumes)
        return None, f"several volumes are loaded and none is displayed — name one of: {names}"
    return _find_node(name, ["vtkMRMLScalarVolumeNode"])


def _find_segmentation(name):
    if not name:  # default: the most recently added segmentation (the one being worked on)
        segs = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
        if segs:
            return segs[-1], None
        return None, "no segmentations are loaded"
    return _find_node(name, ["vtkMRMLSegmentationNode"])


def _find_segment_id(segmentation_node, segment_name):
    segmentation = segmentation_node.GetSegmentation()
    names = []
    for i in range(segmentation.GetNumberOfSegments()):
        seg_id = segmentation.GetNthSegmentID(i)
        seg = segmentation.GetSegment(seg_id)
        names.append(seg.GetName())
        if seg.GetName() == segment_name:
            return seg_id, None
    lowered = segment_name.lower()
    hits = []
    for i in range(segmentation.GetNumberOfSegments()):
        seg_id = segmentation.GetNthSegmentID(i)
        if lowered in segmentation.GetSegment(seg_id).GetName().lower():
            hits.append(seg_id)
    if len(hits) == 1:
        return hits[0], None
    shown = ", ".join(f'"{n}"' for n in names[:30]) or "(none)"
    return None, f"no segment matching '{segment_name}'. Segments: {shown}"


def _confirm(title, body, code=None):
    """Modal approval dialog. Returns True if the human approves."""
    dialog = qt.QDialog(slicer.util.mainWindow())
    dialog.setWindowTitle(title)
    layout = qt.QVBoxLayout(dialog)
    layout.addWidget(qt.QLabel(body))
    if code:
        view = qt.QPlainTextEdit(code)
        view.setReadOnly(True)
        view.setMinimumSize(560, 260)
        layout.addWidget(view)
    buttons = qt.QDialogButtonBox()
    approve = buttons.addButton("Approve && Run", qt.QDialogButtonBox.AcceptRole)
    buttons.addButton("Reject", qt.QDialogButtonBox.RejectRole)
    approve.setStyleSheet("font-weight: bold")
    buttons.connect("accepted()", dialog.accept)
    buttons.connect("rejected()", dialog.reject)
    layout.addWidget(buttons)
    return bool(dialog.exec_())


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    def __init__(self, skill_library):
        self._skills = skill_library
        self.vision_available = True   # set by the widget from the backend's capabilities
        self._exec_fail_streak = 0     # consecutive execute_python errors → circuit breaker
        self._exec_fails_total = 0     # TOTAL execute_python errors this turn → hard cap
        self._external = {}            # name -> LoadedTool from connectors (v2, opt-in)
        self.approval_mode = "manual"  # manual | accept | auto — set by the UI buttons

    def begin_turn(self):
        """Reset per-turn safety counters. Called by the widget on each new user
        message so the total-failure cap can't leak across turns."""
        self._exec_fail_streak = 0
        self._exec_fails_total = 0

    def _needs_approval(self, tool_name):
        """Consult the session approval mode + the tool's risk tier."""
        try:
            from radassistant_lib.orchestration.approval import approval_tier, should_ask
            return should_ask(self.approval_mode, approval_tier(tool_name))
        except Exception:
            return True   # fail safe: if anything is off, ask

    @staticmethod
    def _pump():
        """Let Qt repaint / process input during a long main-thread op so the UI
        doesn't look frozen. Cheap and safe; a no-op outside a running app."""
        try:
            slicer.app.processEvents()
        except Exception:
            pass

    @staticmethod
    def _reset_views():
        """Fit slice views to the data — but never let a display convenience turn a
        successful load into an error (e.g. no slice views in a headless/3D-only layout)."""
        try:
            slicer.util.resetSliceViews()
        except Exception:
            pass

    # -- external (connector) tools -----------------------------------------

    def register_external(self, loaded_tools):
        """Register connector-adapter tools (v2). Native tools always win on a
        name clash, so this can never shadow a built-in."""
        for lt in loaded_tools:
            if not hasattr(self, "_tool_" + lt.name) and lt.name not in self._external:
                self._external[lt.name] = lt

    def external_definitions(self):
        return [{"name": lt.name, "description": lt.description,
                 "input_schema": lt.input_schema} for lt in self._external.values()]

    def all_definitions(self):
        """Native + connector tool definitions (used by the v2 router/ToolView)."""
        return self.definitions + self.external_definitions()

    # -- schemas sent to Claude (order is stable for prompt caching) --------

    @property
    def definitions(self):
        return [
            {"name": "get_scene_overview",
             "description": "List everything loaded in the Slicer scene (volumes, segmentations, models, markups). Call this first when unsure what data exists.",
             "input_schema": {"type": "object", "properties": {}}},

            {"name": "take_screenshot",
             "description": "Capture what is currently displayed and SEE it yourself. Call this after visual changes to verify the result, or when the user asks about what is on screen. view: 'full' = whole layout, 'red'/'yellow'/'green' = that slice view, '3d' = the 3D view.",
             "input_schema": {"type": "object", "properties": {
                 "view": {"type": "string", "enum": ["full", "red", "yellow", "green", "3d"],
                          "description": "Which view to capture (default full)"}},
              }},

            {"name": "load_sample_data",
             "description": "Download and load a built-in anonymized sample dataset. Good options: 'CTChest' (chest CT), 'MRHead' (brain MRI), 'CTACardio' (cardiac CT angio), 'MRBrainTumor1' (brain tumor MRI).",
             "input_schema": {"type": "object", "properties": {
                 "name": {"type": "string", "description": "Sample dataset name"}},
              "required": ["name"]}},

            {"name": "load_file",
             "description": "Load a medical image or model file from disk (NIfTI, NRRD, STL, OBJ, VTK, etc.).",
             "input_schema": {"type": "object", "properties": {
                 "path": {"type": "string", "description": "Absolute file path"}},
              "required": ["path"]}},

            {"name": "import_dicom_folder",
             "description": "Import a folder of DICOM files into Slicer's DICOM database and load the images into the scene.",
             "input_schema": {"type": "object", "properties": {
                 "path": {"type": "string", "description": "Absolute folder path containing DICOM files"}},
              "required": ["path"]}},

            {"name": "list_dicom_database",
             "description": ("List the patients / studies / series already in Slicer's DICOM database "
                             "WITHOUT loading anything. Use to see what studies are available to load — "
                             "e.g. to find a prior/baseline study to compare against."),
             "input_schema": {"type": "object", "properties": {}}},

            {"name": "load_dicom_patient",
             "description": ("Load a specific patient's images from Slicer's DICOM database into the scene "
                             "(the folder must have been imported first with import_dicom_folder). Use to "
                             "load a chosen prior study without re-importing. Omit patient_name if only one "
                             "patient is in the database."),
             "input_schema": {"type": "object", "properties": {
                 "patient_name": {"type": "string", "description": "patient name or ID to match; omit if only one patient"}}}},

            {"name": "set_layout",
             "description": "Switch the view layout.",
             "input_schema": {"type": "object", "properties": {
                 "layout": {"type": "string", "enum": sorted(LAYOUTS.keys())}},
              "required": ["layout"]}},

            {"name": "set_window_level",
             "description": "Set display window/level of a volume. Either give a radiology preset (lung, bone, soft_tissue, brain, liver, mediastinum, abdomen, mri_t1, mri_t2) or explicit window+level values.",
             "input_schema": {"type": "object", "properties": {
                 "volume_name": {"type": "string", "description": "Volume name; omit if only one volume is loaded"},
                 "preset": {"type": "string", "enum": sorted(WINDOW_LEVEL_PRESETS.keys())},
                 "window": {"type": "number"},
                 "level": {"type": "number"}}}},

            {"name": "jump_to_position",
             "description": "Center all slice views on an RAS coordinate (mm).",
             "input_schema": {"type": "object", "properties": {
                 "r": {"type": "number"}, "a": {"type": "number"}, "s": {"type": "number"}},
              "required": ["r", "a", "s"]}},

            {"name": "jump_to_segment",
             "description": "Center the slice views on a named segment of a segmentation.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"}},
              "required": ["segment_name"]}},

            {"name": "list_segments",
             "description": "List all segments of a segmentation with their colors and visibility.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string", "description": "Omit if only one segmentation exists"}}}},

            {"name": "set_segment_visibility",
             "description": "Show or hide segments. Pass specific segment names, or omit segment_names to affect ALL segments.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_names": {"type": "array", "items": {"type": "string"}},
                 "visible": {"type": "boolean"}},
              "required": ["visible"]}},

            {"name": "set_segment_color",
             "description": "Set the RGB color of one segment (components 0-1).",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"},
                 "red": {"type": "number"}, "green": {"type": "number"}, "blue": {"type": "number"}},
              "required": ["segment_name", "red", "green", "blue"]}},

            {"name": "highlight_segment",
             "description": "Make one segment fully opaque and fade all other segments to a low 3D opacity so it stands out.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"},
                 "background_opacity": {"type": "number", "description": "0-1, default 0.15"}},
              "required": ["segment_name"]}},

            {"name": "show_segmentation_3d",
             "description": "Build the 3D surface of a segmentation and show it in the 3D view.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"}}}},

            {"name": "measure_segment_volumes",
             "description": "Compute the volume in cm3 (and mL) of each segment. Returns a table.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_names": {"type": "array", "items": {"type": "string"},
                                   "description": "Omit for all segments"}}}},

            {"name": "measure_segment_statistics",
             "description": "Report volume (cm3) AND intensity statistics (mean/median/min/max/std — e.g. mean HU on CT) for each segment against a scalar volume, using Slicer's validated SegmentStatistics. Use for 'what is the mean HU / density of the lesion' questions.",
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "volume_name": {"type": "string", "description": "Scalar volume providing intensities; omit if only one is loaded"},
                 "segment_names": {"type": "array", "items": {"type": "string"}, "description": "Omit for all"}}}},

            {"name": "extract_radiomics",
             "description": "Extract quantitative radiomic features (shape, first-order intensity, and GLCM/GLRLM/GLSZM/GLDM/NGTDM texture) from one segment using the validated PyRadiomics engine. Requires the SlicerRadiomics extension. Use after segmenting a lesion/ROI to compute its radiomic signature; writes a full-feature CSV and returns a summary.",
             "input_schema": {"type": "object", "properties": {
                 "segment_name": {"type": "string", "description": "The segment (ROI) to characterize"},
                 "segmentation_name": {"type": "string", "description": "Omit if only one segmentation exists"},
                 "volume_name": {"type": "string", "description": "Reference scalar volume (the image); omit if only one is loaded"},
                 "feature_classes": {"type": "array", "items": {"type": "string"},
                                     "description": "Subset of firstorder, shape, glcm, glrlm, glszm, gldm, ngtdm. Default: all."},
                 "image_types": {"type": "array", "items": {"type": "string"},
                                 "description": "Preprocessing filters, e.g. Original, Wavelet, LoG. Default: Original."},
                 "bin_width": {"type": "number", "description": "Intensity discretization bin width. Default 25."},
                 "normalize": {"type": "boolean", "description": "Normalize intensities (usually True for MRI, False for CT). Default False."}},
              "required": ["segment_name"]}},

            {"name": "compare_segments",
             "description": ("Quantify how much two segments AGREE — Dice coefficient, Jaccard/IoU, "
                             "and Hausdorff boundary distance (mm) — computed with SimpleITK (no extra "
                             "extension needed). Use to QA an AI segmentation against a manual/ground-"
                             "truth one, compare two methods, or measure contour change between two "
                             "segmentations of the same study. Both segments are rasterized onto the "
                             "reference volume's grid. Dice 1.0 = identical; >0.9 excellent."),
             "input_schema": {"type": "object", "properties": {
                 "segment_a": {"type": "string", "description": "first segment name"},
                 "segment_b": {"type": "string", "description": "second segment name"},
                 "segmentation_a": {"type": "string", "description": "segmentation holding segment_a; omit if only one"},
                 "segmentation_b": {"type": "string", "description": "segmentation holding segment_b; omit to use the same as segment_a"},
                 "volume_name": {"type": "string", "description": "reference volume providing the common grid; omit if only one is loaded"}},
              "required": ["segment_a", "segment_b"]}},

            {"name": "compare_studies",
             "description": ("Prior-vs-current comparison: rigidly REGISTER a prior study to the current "
                             "one and build a SUBTRACTION change-map, then show them side by side. Uses "
                             "Slicer core (BRAINSFit + SubtractScalarVolumes) run OFF the main thread so "
                             "the UI stays responsive. Use for interval-change reading (follow-up vs "
                             "baseline). You must have BOTH studies loaded. Describe the change; never "
                             "diagnose."),
             "input_schema": {"type": "object", "properties": {
                 "current_volume": {"type": "string", "description": "the current/follow-up study; omit if only two volumes are loaded"},
                 "prior_volume": {"type": "string", "description": "the prior/baseline study to align to the current one"},
                 "registration": {"type": "string", "enum": ["rigid", "affine", "bspline"],
                                  "description": "alignment type; default rigid (fast). bspline is deformable and slow."}}}},

            {"name": "register_volumes",
             "description": ("Align (register) one volume ONTO another so they share the same space — "
                             "e.g. fuse a PET or MR onto a CT, or line up a follow-up with a baseline. "
                             "Produces an aligned copy of the moving volume plus a transform. Uses Slicer "
                             "core BRAINSFit run OFF the main thread (no UI freeze). registration: 'rigid' "
                             "(fast; same patient), 'affine' (adds scale/shear), 'bspline' (deformable, "
                             "slow). For prior-vs-current interval-change reading use compare_studies "
                             "instead (it also builds a subtraction change-map)."),
             "input_schema": {"type": "object", "properties": {
                 "moving_volume": {"type": "string", "description": "the volume to move/align; omit if only two volumes are loaded"},
                 "fixed_volume": {"type": "string", "description": "the reference volume to align TO"},
                 "registration": {"type": "string", "enum": ["rigid", "affine", "bspline"],
                                  "description": "alignment type; default rigid. bspline is deformable and slow."},
                 "output_name": {"type": "string", "description": "optional name for the aligned output volume"}}}},

            {"name": "run_nnunet",
             "description": ("Run a CUSTOM trained nnU-Net model (the user's own model) on a volume, via the "
                             "SlicerNNUnet extension. Give the trained model folder as model_path. Runs in the "
                             "background (no UI freeze). Use for site-specific models that TotalSegmentator / "
                             "MONAI don't cover. Requires the SlicerNNUnet extension AND a trained model folder."),
             "input_schema": {"type": "object", "properties": {
                 "model_path": {"type": "string", "description": "path to the trained nnU-Net model folder (Dataset<id>_.../<trainer>__<plan>__<config> containing dataset.json and fold_ folders)"},
                 "volume_name": {"type": "string", "description": "volume to segment; omit if only one is loaded"},
                 "folds": {"type": "string", "description": "comma-separated folds, e.g. '0' or '0,1,2,3,4'. Default '0'."}},
              "required": ["model_path"]}},

            {"name": "export_dicom_seg",
             "description": ("Export a segmentation as a standards-compliant DICOM Segmentation (SEG) object "
                             "for PACS. Uses dcmqi via the QuantitativeReporting extension. The volume should "
                             "have been loaded from DICOM (the SEG references its source series). Requires the "
                             "QuantitativeReporting extension."),
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "output_folder": {"type": "string", "description": "folder to write the DICOM SEG into"}}}},

            {"name": "extract_vessel_centerline",
             "description": ("Extract the centerline of a segmented vessel and report its length and per-point "
                             "radius/diameter (e.g. aorta, carotid) — analysis TotalSegmentator can't do. Uses "
                             "the SlicerVMTK extension's Extract Centerline. Requires SlicerVMTK installed."),
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string", "description": "the vessel segment to analyze"}}}},

            {"name": "run_monai_auto3dseg",
             "description": ("Automatic AI segmentation with MONAI Auto3DSeg — dozens of pretrained CT AND MR "
                             "models (abdominal organs, bones, vessels, heart, lungs, brain, prostate, plus some "
                             "lesion/tumor models). Complements TotalSegmentator (CT-focused) and run_nnunet "
                             "(custom models) — especially for MR. Runs in the background (no UI freeze). Requires "
                             "the MONAIAuto3DSeg extension. Omit 'model' to list the available models."),
             "input_schema": {"type": "object", "properties": {
                 "model": {"type": "string", "description": "the MONAI model id; omit to list the choices"},
                 "volume_name": {"type": "string", "description": "volume to segment; omit if only one is loaded"},
                 "force_cpu": {"type": "boolean", "description": "force CPU even if a GPU is present"}}}},

            {"name": "compute_dvh",
             "description": ("Radiotherapy dose-volume histogram (DVH) + dose metrics for organs-at-risk / targets: "
                             "given an RT dose volume and a segmentation, compute per-segment DVH plus V-metrics "
                             "(volume receiving at least a dose) and D-metrics (dose to a given volume). QUANTIFIES "
                             "dose only; plan acceptability is the clinician's call. Requires the SlicerRT extension."),
             "input_schema": {"type": "object", "properties": {
                 "dose_volume": {"type": "string", "description": "the RT dose volume (Gy)"},
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string", "description": "limit to one structure; omit for all"}}}},

            {"name": "export_dicom_sr",
             "description": ("Export segment measurements as a DICOM Structured Report (TID 1500) — the standards "
                             "way to store quantitative findings for the record / PACS. Uses dcmqi via the "
                             "QuantitativeReporting extension. Requires QuantitativeReporting; the volume should "
                             "have been loaded from DICOM. (For the segmentation itself, use export_dicom_seg.)"),
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "output_folder": {"type": "string", "description": "folder to write the DICOM SR into"}}}},

            {"name": "export_segmentation_model",
             "description": ("Export segment(s) as 3D surface mesh file(s) (STL or OBJ) for 3D printing, surgical "
                             "planning, or CAD. Builds the closed-surface representation and writes one file per "
                             "segment. Slicer core — no extension needed."),
             "input_schema": {"type": "object", "properties": {
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string", "description": "one segment; omit to export all"},
                 "output_folder": {"type": "string"},
                 "file_format": {"type": "string", "enum": ["STL", "OBJ"]}}}},

            {"name": "export_markups",
             "description": ("Save markup points (fiducials / landmarks) to a CSV file (RAS or LPS coordinates) for "
                             "records or reuse. Slicer core — no extension needed."),
             "input_schema": {"type": "object", "properties": {
                 "markups_name": {"type": "string", "description": "the markups node; omit if only one exists"},
                 "output_path": {"type": "string", "description": "CSV file path to write"}}}},

            {"name": "import_markups",
             "description": ("Load markup points (fiducials / landmarks) from a CSV file into the scene. Slicer "
                             "core — no extension needed."),
             "input_schema": {"type": "object", "properties": {
                 "input_path": {"type": "string", "description": "CSV file to load"},
                 "markups_name": {"type": "string", "description": "name for the created markups node"}},
              "required": ["input_path"]}},

            {"name": "threshold_segmentation",
             "description": "Create a new segment by intensity thresholding (e.g. bone from CT: 300..3000 HU; lungs: -1000..-400 HU). Optionally keep only the largest connected island.",
             "input_schema": {"type": "object", "properties": {
                 "volume_name": {"type": "string"},
                 "segment_name": {"type": "string"},
                 "lower_threshold": {"type": "number"},
                 "upper_threshold": {"type": "number"},
                 "keep_largest_island": {"type": "boolean"},
                 "red": {"type": "number"}, "green": {"type": "number"}, "blue": {"type": "number"}},
              "required": ["segment_name", "lower_threshold", "upper_threshold"]}},

            {"name": "filter_segment_islands",
             "description": "Clean up a segmentation's disconnected islands with Slicer's validated Islands effect — use this instead of writing Python. operation: 'remove_small' deletes fragments below min_size_ml (removes threshold speckle/noise); 'keep_largest' keeps only the single biggest island (do NOT use for both lungs — it deletes one of them); 'split_to_segments' puts every island in its own segment so you can measure and identify them. It CANNOT by itself strip air outside the patient (that blob is large) — for anatomically clean organs use run_total_segmentator.",
             "input_schema": {"type": "object", "properties": {
                 "operation": {"type": "string",
                               "enum": ["remove_small", "keep_largest", "split_to_segments"]},
                 "min_size_ml": {"type": "number",
                                 "description": "For remove_small: islands below this size (mL) are deleted. Default 1.0"},
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"}},
              "required": ["operation"]}},

            {"name": "smooth_segment",
             "description": ("Smooth a segment with Slicer's validated Smoothing effect so its 3D "
                             "surface looks clean instead of blocky/staircased — use this instead of "
                             "writing VTK. method: 'median' (default, edge-preserving, removes speckle), "
                             "'gaussian' (soft rounding), 'opening' (removes thin spurs), 'closing' "
                             "(fills small pits/gaps). Smoothing changes the volume slightly; re-measure "
                             "afterwards. Does NOT remove external air — that is a data problem."),
             "input_schema": {"type": "object", "properties": {
                 "method": {"type": "string",
                            "enum": ["median", "gaussian", "opening", "closing"]},
                 "kernel_mm": {"type": "number",
                               "description": "smoothing size in mm (default 3.0)"},
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"}}}},

            {"name": "grow_shrink_segment",
             "description": ("Grow (dilate) or shrink (erode) a segment by a margin in mm — e.g. add a "
                             "planning margin around a structure, or peel a leaky boundary. Positive = "
                             "grow, negative = shrink.\n"
                             "• UNIFORM (isotropic): give margin_mm — uses Slicer's validated Margin effect.\n"
                             "• ANISOTROPIC (different per axis, e.g. an RT PTV of 10 mm superior-inferior "
                             "and 5 mm in the axial plane): give margin_axial_mm (in-plane, R-L & A-P) and "
                             "margin_si_mm (superior-inferior). Applied with per-axis SimpleITK morphology "
                             "on the image axes (assumes an axial-acquired volume). All supplied axis "
                             "margins must share one sign (all grow or all shrink).\n"
                             "This tool DOES support anisotropic margins — use it, do NOT hand-write Python."),
             "input_schema": {"type": "object", "properties": {
                 "margin_mm": {"type": "number",
                               "description": "uniform margin in mm (positive grows, negative shrinks)"},
                 "margin_axial_mm": {"type": "number",
                                     "description": "anisotropic: in-plane (R-L & A-P) margin in mm"},
                 "margin_si_mm": {"type": "number",
                                  "description": "anisotropic: superior-inferior margin in mm"},
                 "segmentation_name": {"type": "string"},
                 "segment_name": {"type": "string"}}}},

            {"name": "merge_segments",
             "description": ("Merge two or more segments into one (union) — e.g. combine separate "
                             "left/right lung islands into a single 'Lungs' segment. The first name "
                             "is kept as the target; the rest are unioned into it and removed. Use "
                             "this instead of writing Python to combine segments."),
             "input_schema": {"type": "object", "properties": {
                 "segment_names": {"type": "array", "items": {"type": "string"},
                                   "description": "two or more segment names; first is the target"},
                 "new_name": {"type": "string", "description": "optional name for the merged segment"},
                 "segmentation_name": {"type": "string"}},
              "required": ["segment_names"]}},

            {"name": "delete_segments",
             "description": ("Permanently remove one or more segments from a segmentation — e.g. "
                             "delete the external-air island so it stops inflating the volume AND so "
                             "the 3D surface build is fast (hiding a segment is NOT enough — a hidden "
                             "segment still slows show_segmentation_3d). Destructive; needs approval "
                             "in Manual mode."),
             "input_schema": {"type": "object", "properties": {
                 "segment_names": {"type": "array", "items": {"type": "string"},
                                   "description": "names of the segments to delete"},
                 "segmentation_name": {"type": "string"}},
              "required": ["segment_names"]}},

            {"name": "clear_scene",
             "description": ("Remove ALL data from the scene — every volume, segmentation, "
                             "model, markup and transform — like File > Close Scene. Use when "
                             "the user asks to clear / reset / empty the scene or start over. "
                             "IRREVERSIBLE; needs approval. Suggest saving first if there is "
                             "unsaved work. To remove only specific segments (not the whole "
                             "scene), use delete_segments instead."),
             "input_schema": {"type": "object", "properties": {}}},

            {"name": "run_total_segmentator",
             "description": ("Run TotalSegmentator AI to auto-segment many anatomical structures "
                             "(task 'total' = 100+ on CT; 'total_mr' on MR; plus focused tasks like "
                             "'lung_vessels', 'body', 'coronary_arteries'). Requires the "
                             "SlicerTotalSegmentator extension. HEAVY and BLOCKS Slicer's UI until "
                             "done: seconds on GPU, but minutes ('fast') to 5-50 min ('normal') on "
                             "CPU. READ THE total-segmentator SKILL FIRST and confirm task + speed "
                             "with the user before calling. For a single lung/bone volume, prefer "
                             "the threshold workflow (seconds, no freeze)."),
             "input_schema": {"type": "object", "properties": {
                 "volume_name": {"type": "string"},
                 "task": {"type": "string",
                          "description": "TotalSegmentator task. CT: 'total', 'lung_vessels', 'body', 'coronary_arteries', 'hip_implant', 'cerebral_bleed', 'pleural_pericard_effusion', 'lung_nodules'. MR: 'total_mr', 'body_mr'. Some (e.g. tissue_types, vertebrae_body, liver_segments, face, brain_structures) need a license key. Default 'total'."},
                 "quality": {"type": "string", "enum": ["normal", "fast", "faster"],
                             "description": "normal=full-res (best, slow), fast=3mm (a few min), faster=6mm (fastest, least detail). Default fast. On CPU, 'normal' is refused unless roi_subset is set."},
                 "roi_subset": {"type": "array", "items": {"type": "string"},
                                "description": "Only segment these structures (e.g. ['liver','spleen','kidney_left','kidney_right']) — much faster/less memory. Only valid with task 'total'/'total_mr'."}}}},

            {"name": "place_point",
             "description": "Place a labeled fiducial point at an RAS coordinate (mm).",
             "input_schema": {"type": "object", "properties": {
                 "r": {"type": "number"}, "a": {"type": "number"}, "s": {"type": "number"},
                 "label": {"type": "string"}},
              "required": ["r", "a", "s"]}},

            {"name": "measure_distance",
             "description": "Place a measurement line between two RAS points and report its length in mm.",
             "input_schema": {"type": "object", "properties": {
                 "point1": {"type": "array", "items": {"type": "number"}, "description": "[r, a, s]"},
                 "point2": {"type": "array", "items": {"type": "number"}, "description": "[r, a, s]"},
                 "label": {"type": "string"}},
              "required": ["point1", "point2"]}},

            {"name": "enable_volume_rendering",
             "description": "Turn on 3D volume rendering of a volume with a named preset (e.g. 'CT-Chest-Contrast-Enhanced', 'CT-Bone', 'CT-Cardiac', 'MR-Default').",
             "input_schema": {"type": "object", "properties": {
                 "volume_name": {"type": "string"},
                 "preset": {"type": "string", "description": "Slicer volume rendering preset name, default CT-Chest-Contrast-Enhanced"}}}},

            {"name": "rotate_3d_view",
             "description": "Point the 3D camera along an anatomical axis.",
             "input_schema": {"type": "object", "properties": {
                 "direction": {"type": "string", "enum": sorted(VIEW_AXES.keys())}},
              "required": ["direction"]}},

            {"name": "center_views",
             "description": "Reset/center the 3D camera and fit all slice views to the data.",
             "input_schema": {"type": "object", "properties": {}}},

            {"name": "read_skill",
             "description": "Load the full instructions of a named workflow skill (the available skills are listed in your system prompt). Do this before executing a workflow a skill covers.",
             "input_schema": {"type": "object", "properties": {
                 "name": {"type": "string"}},
              "required": ["name"]}},

            {"name": "execute_python",
             "description": "Run Python code inside Slicer (slicer, vtk, qt, numpy available). THE USER MUST APPROVE each execution via a dialog. Use only for a genuinely novel read-only query when no dedicated tool exists. Do NOT use it to work around a missing capability or to edit segments/volumes by guessing at the API — if a segmentation/editing task has no dedicated tool, tell the user plainly instead. Set a variable named `result` for a value you want returned.",
             "input_schema": {"type": "object", "properties": {
                 "code": {"type": "string"},
                 "reason": {"type": "string", "description": "One line shown to the user explaining why"}},
              "required": ["code"]}},
        ]

    # -- dispatch ------------------------------------------------------------

    def execute(self, name, args):
        # connector tools (v2) run through the adapter; they return a string or a dict
        ext = self._external.get(name)
        if ext is not None and not hasattr(self, "_tool_" + name):
            try:
                out = ext.func(**(args or {}))
            except Exception as exc:                       # noqa: BLE001
                return _err(f"{name} failed: {exc}")
            return out if isinstance(out, dict) else _ok(str(out))
        handler = getattr(self, "_tool_" + name, None)
        if handler is None:
            return _err(f"unknown tool '{name}'")
        try:
            result = handler(**(args or {}))
        except TypeError as exc:
            return _err(f"bad arguments for {name}: {exc}")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            return _err(f"{name} failed: {exc}")
        # A successful dedicated tool clears any ad-hoc-Python failure streak
        # (and every turn starts with get_scene_overview, so streaks reset per turn).
        if name != "execute_python" and not (isinstance(result, dict) and result.get("is_error")):
            self._exec_fail_streak = 0
        return result

    # -- implementations -------------------------------------------------

    def _tool_get_scene_overview(self):
        from . import context
        return _ok(context.build_scene_context())

    def _tool_take_screenshot(self, view="full"):
        if not self.vision_available:
            return _err("this model cannot see images. Verify results with structured tools "
                        "instead: get_scene_overview, list_segments, measure_segment_volumes, "
                        "get_cursor_info.")
        slicer.app.processEvents()
        layout_manager = slicer.app.layoutManager()
        target = None
        if view in ("red", "yellow", "green"):
            widget = layout_manager.sliceWidget(view.capitalize())
            if widget is None:
                return _err(f"slice view '{view}' is not in the current layout")
            target = widget.sliceView()
        elif view == "3d":
            if layout_manager.threeDViewCount < 1:
                return _err("no 3D view in the current layout")
            target = layout_manager.threeDWidget(0).threeDView()

        import ScreenCapture
        capture_logic = ScreenCapture.ScreenCaptureLogic()
        path = os.path.join(tempfile.gettempdir(), "radassistant_capture.png")
        capture_logic.captureImageFromView(target, path)

        image = qt.QImage(path)
        if max(image.width(), image.height()) > 2048:
            if image.width() >= image.height():
                image = image.scaledToWidth(2048, qt.Qt.SmoothTransformation)
            else:
                image = image.scaledToHeight(2048, qt.Qt.SmoothTransformation)
            image.save(path)
        with open(path, "rb") as f:
            encoded = base64.standard_b64encode(f.read()).decode()
        return _ok(f"Screenshot of '{view}' view captured "
                   f"({image.width()}x{image.height()}). Inspect the attached image.",
                   image_b64=encoded)

    def _tool_load_sample_data(self, name):
        import SampleData
        try:
            nodes = SampleData.SampleDataLogic().downloadSamples(name)
        except Exception as exc:
            return _err(f"could not download sample '{name}': {exc}")
        if not nodes:
            return _err(f"no sample dataset named '{name}'")
        loaded = ", ".join(f'"{n.GetName()}"' for n in nodes)
        self._reset_views()
        return _ok(f"Loaded sample data: {loaded}.")

    def _tool_load_file(self, path):
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return _err(f"file not found: {path}")
        node = slicer.util.loadNodeFromFile(path)
        if node is None:
            return _err(f"Slicer could not load {path}")
        self._reset_views()
        return _ok(f'Loaded "{node.GetName()}" ({node.GetClassName()}).')

    def _tool_import_dicom_folder(self, path):
        path = os.path.expanduser(path)
        if not os.path.isdir(path):
            return _err(f"folder not found: {path}")
        from DICOMLib import DICOMUtils
        loaded_names = []
        DICOMUtils.importDicom(path, slicer.dicomDatabase)
        for patient_uid in slicer.dicomDatabase.patients():
            for node_id in DICOMUtils.loadPatientByUID(patient_uid):
                node = slicer.mrmlScene.GetNodeByID(node_id)
                if node:
                    loaded_names.append(node.GetName())
        if not loaded_names:
            return _err("DICOM import finished but nothing loaded — is the folder valid DICOM?")
        self._reset_views()
        return _ok("Imported and loaded: " + ", ".join(f'"{n}"' for n in loaded_names))

    @staticmethod
    def _dicom_patient_name(db, patient_uid):
        try:
            return db.nameForPatient(patient_uid) or patient_uid
        except Exception:
            return patient_uid

    def _tool_list_dicom_database(self):
        db = slicer.dicomDatabase
        try:
            patients = list(db.patients()) if db is not None else []
        except Exception:
            patients = []
        if not patients:
            return _err("the DICOM database is empty (or not open) — import a DICOM folder first "
                        "with import_dicom_folder.")

        def field(fn, uid, default):
            try:
                return getattr(db, fn)(uid) or default
            except Exception:
                return default

        lines = [f"DICOM database: {len(patients)} patient(s)."]
        for p in patients:
            studies = list(db.studiesForPatient(p))
            lines.append(f'- Patient "{self._dicom_patient_name(db, p)}": {len(studies)} study(ies)')
            for s in studies:
                series = list(db.seriesForStudy(s))
                lines.append(f'    - study "{field("descriptionForStudy", s, s)}": {len(series)} series')
                for se in series[:12]:
                    try:
                        desc = db.fieldForSeries("SeriesDescription", se) or se
                    except Exception:
                        desc = se
                    lines.append(f'        - {desc}')
        lines.append("\nUse load_dicom_patient to load one.")
        return _ok("\n".join(lines))

    def _tool_load_dicom_patient(self, patient_name=""):
        db = slicer.dicomDatabase
        try:
            patients = list(db.patients()) if db is not None else []
        except Exception:
            patients = []
        if not patients:
            return _err("no DICOM data is in the database — import a folder first with import_dicom_folder.")
        from DICOMLib import DICOMUtils

        target = None
        if patient_name:
            low = patient_name.lower()
            for p in patients:
                if low in str(self._dicom_patient_name(db, p)).lower() or low in str(p).lower():
                    target = p
                    break
            if target is None:
                avail = ", ".join(f'"{self._dicom_patient_name(db, p)}"' for p in patients)
                return _err(f"no DICOM patient matching '{patient_name}'. Available: {avail}")
        elif len(patients) == 1:
            target = patients[0]
        else:
            avail = ", ".join(f'"{self._dicom_patient_name(db, p)}"' for p in patients)
            return _err(f"several patients in the database — name one: {avail}")

        before = len(slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"))
        self._pump()
        DICOMUtils.loadPatientByUID(target)
        self._pump()
        after = len(slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"))
        self._reset_views()
        name = self._dicom_patient_name(db, target)
        if after <= before:
            return _err(f'loaded patient "{name}" but no new image volume appeared — the series may be '
                        "non-image DICOM (e.g. structured report or segmentation only).")
        return _ok(f'Loaded DICOM patient "{name}" — {after - before} new volume(s) in the scene. '
                   "Call get_scene_overview to see them.")

    def _tool_set_layout(self, layout):
        attr = LAYOUTS.get(layout)
        if attr is None:
            return _err(f"unknown layout '{layout}'. Options: {', '.join(sorted(LAYOUTS))}")
        slicer.app.layoutManager().setLayout(getattr(slicer.vtkMRMLLayoutNode, attr))
        return _ok(f"Layout switched to {layout}.")

    def _tool_set_window_level(self, volume_name="", preset=None, window=None, level=None):
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)
        if preset:
            if preset not in WINDOW_LEVEL_PRESETS:
                return _err(f"unknown preset '{preset}'. Options: {', '.join(sorted(WINDOW_LEVEL_PRESETS))}")
            window, level = WINDOW_LEVEL_PRESETS[preset]
        if window is None or level is None:
            return _err("give either a preset or explicit window and level values")
        display = volume.GetDisplayNode()
        display.SetAutoWindowLevel(False)
        display.SetWindowLevel(float(window), float(level))
        return _ok(f'Window/level of "{volume.GetName()}" set to {window:.0f}/{level:.0f}'
                   + (f" ({preset} preset)." if preset else "."))

    def _tool_jump_to_position(self, r, a, s):
        slicer.modules.markups.logic().JumpSlicesToLocation(float(r), float(a), float(s), True)
        return _ok(f"Slice views centered on RAS ({r:.1f}, {a:.1f}, {s:.1f}).")

    def _tool_jump_to_segment(self, segment_name, segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        seg_id, error = _find_segment_id(seg_node, segment_name)
        if error:
            return _err(error)
        center = seg_node.GetSegmentCenterRAS(seg_id)
        if center is None:
            return _err(f"segment '{segment_name}' appears to be empty")
        slicer.modules.markups.logic().JumpSlicesToLocation(center[0], center[1], center[2], True)
        return _ok(f'Slice views centered on segment "{segment_name}" at RAS '
                   f"({center[0]:.1f}, {center[1]:.1f}, {center[2]:.1f}).")

    def _tool_list_segments(self, segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        segmentation = seg_node.GetSegmentation()
        display = seg_node.GetDisplayNode()
        lines = []
        for i in range(segmentation.GetNumberOfSegments()):
            seg_id = segmentation.GetNthSegmentID(i)
            segment = segmentation.GetSegment(seg_id)
            color = segment.GetColor()
            visible = display.GetSegmentVisibility(seg_id) if display else True
            lines.append(f'- "{segment.GetName()}"  color=({color[0]:.2f},{color[1]:.2f},{color[2]:.2f})  '
                         f'{"visible" if visible else "hidden"}')
        return _ok(f'Segmentation "{seg_node.GetName()}" ({len(lines)} segments):\n' + "\n".join(lines))

    def _tool_set_segment_visibility(self, visible, segmentation_name="", segment_names=None):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        display = seg_node.GetDisplayNode()
        segmentation = seg_node.GetSegmentation()
        changed, failed = [], []
        if not segment_names:
            for i in range(segmentation.GetNumberOfSegments()):
                display.SetSegmentVisibility(segmentation.GetNthSegmentID(i), bool(visible))
            changed = ["all segments"]
        else:
            for name in segment_names:
                seg_id, seg_error = _find_segment_id(seg_node, name)
                if seg_error:
                    failed.append(name)
                else:
                    display.SetSegmentVisibility(seg_id, bool(visible))
                    changed.append(segmentation.GetSegment(seg_id).GetName())
        text = f'{"Showed" if visible else "Hid"}: {", ".join(changed) or "nothing"}.'
        if failed:
            text += f' NOT FOUND (check names with list_segments): {", ".join(failed)}.'
        return _ok(text)

    def _tool_set_segment_color(self, segment_name, red, green, blue, segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        seg_id, error = _find_segment_id(seg_node, segment_name)
        if error:
            return _err(error)
        clamp = lambda x: max(0.0, min(1.0, float(x)))
        segment = seg_node.GetSegmentation().GetSegment(seg_id)
        segment.SetColor(clamp(red), clamp(green), clamp(blue))
        return _ok(f'Segment "{segment.GetName()}" recolored to '
                   f"({clamp(red):.2f}, {clamp(green):.2f}, {clamp(blue):.2f}).")

    def _tool_highlight_segment(self, segment_name, segmentation_name="", background_opacity=0.15):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        seg_id, error = _find_segment_id(seg_node, segment_name)
        if error:
            return _err(error)
        display = seg_node.GetDisplayNode()
        segmentation = seg_node.GetSegmentation()
        for i in range(segmentation.GetNumberOfSegments()):
            other_id = segmentation.GetNthSegmentID(i)
            opacity = 1.0 if other_id == seg_id else max(0.0, min(1.0, float(background_opacity)))
            display.SetSegmentOpacity3D(other_id, opacity)
        return _ok(f'Segment "{segment_name}" highlighted; other segments faded to '
                   f"{background_opacity:.0%} opacity. Take a screenshot to verify.")

    def _tool_show_segmentation_3d(self, segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        self._pump()   # the marching-cubes mesh build is the slow step — paint busy state
        seg_node.CreateClosedSurfaceRepresentation()
        self._pump()
        seg_node.GetDisplayNode().SetVisibility(True)
        layout_manager = slicer.app.layoutManager()
        if layout_manager.threeDViewCount > 0:
            view = layout_manager.threeDWidget(0).threeDView()
            view.resetFocalPoint()
        return _ok(f'3D surface of "{seg_node.GetName()}" is now shown. '
                   "Take a screenshot of the 3d view to verify.")

    def _tool_measure_segment_volumes(self, segmentation_name="", segment_names=None):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        import SegmentStatistics
        stats_logic = SegmentStatistics.SegmentStatisticsLogic()
        parameter_node = stats_logic.getParameterNode()
        parameter_node.SetParameter("Segmentation", seg_node.GetID())
        stats_logic.computeStatistics()
        stats = stats_logic.getStatistics()

        segmentation = seg_node.GetSegmentation()
        wanted = None
        if segment_names:
            wanted = {n.lower() for n in segment_names}
        rows, total = [], 0.0
        for seg_id in stats["SegmentIDs"]:
            name = segmentation.GetSegment(seg_id).GetName()
            if wanted and not any(w in name.lower() for w in wanted):
                continue
            volume_cm3 = stats.get((seg_id, "LabelmapSegmentStatisticsPlugin.volume_cm3"))
            if volume_cm3 is None:
                continue
            total += volume_cm3
            rows.append(f"| {name} | {volume_cm3:.2f} |")
        if not rows:
            return _err("no matching segments with computable volume")
        table = (f'Segmentation "{seg_node.GetName()}":\n'
                 "| Segment | Volume (cm3 = mL) |\n|---|---|\n" + "\n".join(rows))
        if len(rows) > 1:
            table += f"\n| **Total** | **{total:.2f}** |"
        return _ok(table)

    def _tool_measure_segment_statistics(self, segmentation_name="", volume_name="", segment_names=None):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)
        import SegmentStatistics
        stats_logic = SegmentStatistics.SegmentStatisticsLogic()
        parameter_node = stats_logic.getParameterNode()
        parameter_node.SetParameter("Segmentation", seg_node.GetID())
        parameter_node.SetParameter("ScalarVolume", volume.GetID())
        parameter_node.SetParameter("ScalarVolumeSegmentStatisticsPlugin.enabled", "True")
        parameter_node.SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
        stats_logic.computeStatistics()
        stats = stats_logic.getStatistics()

        segmentation = seg_node.GetSegmentation()
        wanted = {n.lower() for n in segment_names} if segment_names else None

        def fmt(value, spec):
            return format(value, spec) if value is not None else "n/a"

        rows = []
        for seg_id in stats["SegmentIDs"]:
            name = segmentation.GetSegment(seg_id).GetName()
            if wanted and not any(w in name.lower() for w in wanted):
                continue
            volume_cm3 = stats.get((seg_id, "LabelmapSegmentStatisticsPlugin.volume_cm3"))
            if volume_cm3 is None:
                continue
            base = "ScalarVolumeSegmentStatisticsPlugin."
            rows.append("| {name} | {vol} | {mean} | {median} | {mn} | {mx} | {std} |".format(
                name=name,
                vol=fmt(volume_cm3, ".2f"),
                mean=fmt(stats.get((seg_id, base + "mean")), ".1f"),
                median=fmt(stats.get((seg_id, base + "median")), ".1f"),
                mn=fmt(stats.get((seg_id, base + "min")), ".0f"),
                mx=fmt(stats.get((seg_id, base + "max")), ".0f"),
                std=fmt(stats.get((seg_id, base + "stdev")), ".1f")))
        if not rows:
            return _err("no matching segments with computable statistics")
        return _ok(f'Segmentation "{seg_node.GetName()}":\n'
                   "| Segment | Vol (cm3) | Mean | Median | Min | Max | StdDev |\n"
                   "|---|---|---|---|---|---|---|\n" + "\n".join(rows)
                   + f'\n\n(intensity in the units of "{volume.GetName()}" — HU for CT)')

    def _tool_extract_radiomics(self, segment_name, segmentation_name="", volume_name="",
                                feature_classes=None, image_types=None, bin_width=25,
                                normalize=False):
        try:
            from radiomics import featureextractor
        except ImportError:
            return _err("PyRadiomics is not available. Install the SlicerRadiomics extension "
                        "from the Extensions Manager and restart Slicer, then retry.")
        import SimpleITK as sitk
        import sitkUtils

        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        seg_id, error = _find_segment_id(seg_node, segment_name)
        if error:
            return _err(error)
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)

        labelmap = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLabelMapVolumeNode", slicer.mrmlScene.GenerateUniqueName("radiomics_mask"))
        segment_ids = vtk.vtkStringArray()
        segment_ids.InsertNextValue(seg_id)
        exported = slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
            seg_node, segment_ids, labelmap, volume)
        if not exported:
            slicer.mrmlScene.RemoveNode(labelmap)
            return _err("could not export the segment to a labelmap aligned with the volume")

        try:
            image = sitkUtils.PullVolumeFromSlicer(volume)
            mask = sitkUtils.PullVolumeFromSlicer(labelmap)
            mask = sitk.NotEqual(mask, 0)  # any nonzero label -> 1 (no BinaryThreshold overflow)
            settings = {"binWidth": float(bin_width), "label": 1}
            if normalize:
                settings["normalize"] = True
            extractor = featureextractor.RadiomicsFeatureExtractor(**settings)
            extractor.disableAllImageTypes()
            for image_type in (image_types or ["Original"]):
                extractor.enableImageTypeByName(image_type)
            extractor.disableAllFeatures()
            for feature_class in (feature_classes or
                                  ["firstorder", "shape", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]):
                extractor.enableFeatureClassByName(feature_class)
            result = extractor.execute(image, mask, label=1)
        except Exception as exc:
            return _err(f"PyRadiomics extraction failed: {exc}")
        finally:
            slicer.mrmlScene.RemoveNode(labelmap)

        features = {}
        for key, value in result.items():
            if key.startswith("diagnostics_"):
                continue
            try:
                features[key] = float(value)
            except (TypeError, ValueError):
                pass
        if not features:
            return _err(f'no features extracted — is segment "{segment_name}" non-empty?')

        import csv
        path = os.path.join(tempfile.gettempdir(),
                            "radiomics_" + segment_name.replace(" ", "_") + ".csv")
        with open(path, "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["feature", "value"])
            for key, value in features.items():
                writer.writerow([key, value])

        lines = [f'Extracted {len(features)} radiomic features from segment "{segment_name}" '
                 f"(bin width {bin_width}). Full set saved to {path}.", "", "Preview:"]
        preview = ([k for k in features if "shape_" in k][:5]
                   + [k for k in features if "firstorder_" in k][:6])
        for key in preview:
            lines.append(f"- {key.replace('original_', '')}: {features[key]:.4g}")
        lines.append("(plus GLCM/GLRLM/GLSZM/GLDM/NGTDM texture features — see the CSV)")
        return _ok("\n".join(lines))

    def _tool_compare_segments(self, segment_a, segment_b, segmentation_a="",
                               segmentation_b="", volume_name=""):
        seg_node_a, error = _find_segmentation(segmentation_a)
        if error:
            return _err(error)
        id_a, error = _find_segment_id(seg_node_a, segment_a)
        if error:
            return _err(error)
        seg_node_b, error = _find_segmentation(segmentation_b or segmentation_a)
        if error:
            return _err(error)
        id_b, error = _find_segment_id(seg_node_b, segment_b)
        if error:
            return _err(error)
        volume, error = _find_volume(volume_name)     # provides the common voxel grid
        if error:
            return _err("need a reference volume to put both masks on one grid — " + error)

        import SimpleITK as sitk
        import sitkUtils
        made = []
        try:
            def _mask(seg_node, seg_id):
                lm = slicer.mrmlScene.AddNewNodeByClass(
                    "vtkMRMLLabelMapVolumeNode", slicer.mrmlScene.GenerateUniqueName("cmp_mask"))
                made.append(lm)
                ids = vtk.vtkStringArray()
                ids.InsertNextValue(seg_id)
                ok = slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
                    seg_node, ids, lm, volume)
                if not ok:
                    return None
                img = sitkUtils.PullVolumeFromSlicer(lm)
                return sitk.NotEqual(img, 0)   # any nonzero label -> 1 (no BinaryThreshold overflow)

            mask_a = _mask(seg_node_a, id_a)
            mask_b = _mask(seg_node_b, id_b)
            if mask_a is None or mask_b is None:
                return _err("could not rasterize a segment onto the reference grid")
            stat = sitk.StatisticsImageFilter()
            stat.Execute(mask_a); va = stat.GetSum()
            stat.Execute(mask_b); vb = stat.GetSum()
            if va == 0 or vb == 0:
                return _err(f"a segment is empty (voxels A={int(va)}, B={int(vb)}) — nothing to compare")
            overlap = sitk.LabelOverlapMeasuresImageFilter()
            overlap.Execute(mask_a, mask_b)
            dice = overlap.GetDiceCoefficient()
            jacc = overlap.GetJaccardCoefficient()
            volsim = overlap.GetVolumeSimilarity()
            hd = sitk.HausdorffDistanceImageFilter()
            hd.Execute(mask_a, mask_b)
            hd_max = hd.GetHausdorffDistance()
            hd_avg = hd.GetAverageHausdorffDistance()
        except Exception as exc:
            return _err(f"comparison failed: {exc}")
        finally:
            for node in made:
                slicer.mrmlScene.RemoveNode(node)

        grade = ("excellent" if dice >= 0.9 else "good" if dice >= 0.8
                 else "moderate" if dice >= 0.7 else "poor")
        name_a = seg_node_a.GetSegmentation().GetSegment(id_a).GetName()
        name_b = seg_node_b.GetSegmentation().GetSegment(id_b).GetName()
        return _ok(
            f'Agreement between "{name_a}" and "{name_b}":\n'
            f"- **Dice**: {dice:.3f} ({grade})\n"
            f"- Jaccard / IoU: {jacc:.3f}\n"
            f"- Hausdorff distance: {hd_max:.1f} mm max, {hd_avg:.2f} mm average\n"
            f"- Volume similarity: {volsim:+.3f} (0 = same volume)\n\n"
            "Dice 1.0 = perfect overlap (>0.9 excellent, 0.8-0.9 good); Hausdorff is the "
            "worst-case boundary gap. Good for AI-vs-manual or auto-segmentation QA.")

    def _run_cli(self, module, params):
        """Run a CLI module WITHOUT freezing the UI: launch it async (subprocess) and
        pump the Qt event loop until it finishes. Returns (ok, status_string). This is
        the reusable 'heavy job off the main thread' pattern."""
        import time
        cli = slicer.cli.run(module, None, params, wait_for_completion=False)
        while cli.IsBusy():
            slicer.app.processEvents()
            time.sleep(0.01)
        status = cli.GetStatusString()
        ok = (cli.GetStatus() == cli.Completed)
        slicer.mrmlScene.RemoveNode(cli)
        return ok, status

    def _tool_compare_studies(self, current_volume="", prior_volume="",
                              registration="rigid", show=True):
        current, error = _find_volume(current_volume)
        if error:
            return _err("name the CURRENT study — " + error)
        if prior_volume:
            prior, error = _find_volume(prior_volume)
            if error:
                return _err("prior study — " + error)
        else:
            others = [n for n in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
                      if n is not current]
            if len(others) == 1:
                prior = others[0]
            else:
                names = ", ".join(f'"{n.GetName()}"' for n in others) or "(none)"
                return _err(f"name the PRIOR study to compare against. Other volumes: {names}")
        if prior is current:
            return _err("prior and current are the same volume — load two different studies")

        transform_type = {"rigid": "Rigid", "affine": "Affine",
                          "bspline": "BSpline"}.get(str(registration).lower(), "Rigid")
        resampled = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode",
            slicer.mrmlScene.GenerateUniqueName(f"{prior.GetName()}_reg"))
        xform = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLinearTransformNode", slicer.mrmlScene.GenerateUniqueName("prior_to_current"))
        self._pump()
        ok, status = self._run_cli(slicer.modules.brainsfit, {
            "fixedVolume": current.GetID(),
            "movingVolume": prior.GetID(),
            "outputVolume": resampled.GetID(),
            "linearTransform": xform.GetID(),
            "transformType": transform_type,
            "initializeTransformMode": "useMomentsAlign",
            "samplingPercentage": 0.02,
        })
        if not ok:
            slicer.mrmlScene.RemoveNode(xform)
            slicer.mrmlScene.RemoveNode(resampled)
            return _err(f"registration (BRAINSFit) did not complete: {status}. The studies "
                        "may be too different to align this way.")

        diff = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode", slicer.mrmlScene.GenerateUniqueName("change_map"))
        ok, status = self._run_cli(slicer.modules.subtractscalarvolumes, {
            "inputVolume1": current.GetID(),
            "inputVolume2": resampled.GetID(),
            "outputVolume": diff.GetID(),
        })
        if not ok:
            slicer.mrmlScene.RemoveNode(diff)
            return _err(f"subtraction did not complete: {status}")

        try:
            import numpy as np
            change_note = f"peak voxel change ±{float(np.abs(slicer.util.arrayFromVolume(diff)).max()):.0f}"
        except Exception:
            change_note = "difference map created"

        shown = False
        if show:
            try:
                lm = slicer.app.layoutManager()
                if lm is not None:
                    lm.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutSideBySideView)
                    lm.sliceWidget("Red").mrmlSliceCompositeNode().SetBackgroundVolumeID(current.GetID())
                    lm.sliceWidget("Yellow").mrmlSliceCompositeNode().SetBackgroundVolumeID(diff.GetID())
                    self._pump()
                    shown = True
            except Exception:
                shown = False

        disp = ("Left = current study, right = change map. " if shown
                else "Set a side-by-side layout to view current vs the change map. ")
        return _ok(
            f'Compared "{prior.GetName()}" (prior) -> "{current.GetName()}" (current):\n'
            f"- Registered prior to current ({transform_type}).\n"
            f'- Built change map "{diff.GetName()}" ({change_note}).\n'
            + disp +
            "Bright/dark regions on the change map are interval change (new or resolved). "
            "Describe what changed; do not diagnose.")

    def _tool_register_volumes(self, moving_volume="", fixed_volume="",
                               registration="rigid", output_name=""):
        fixed, error = _find_volume(fixed_volume)
        if error:
            return _err("name the FIXED (reference) volume to align TO — " + error)
        if moving_volume:
            moving, error = _find_volume(moving_volume)
            if error:
                return _err("moving volume — " + error)
        else:
            others = [n for n in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
                      if n is not fixed]
            if len(others) == 1:
                moving = others[0]
            else:
                names = ", ".join(f'"{n.GetName()}"' for n in others) or "(none)"
                return _err(f"name the MOVING volume to align to the fixed one. Other volumes: {names}")
        if moving is fixed:
            return _err("fixed and moving are the same volume — name two different volumes")

        transform_type = {"rigid": "Rigid", "affine": "Affine",
                          "bspline": "BSpline"}.get(str(registration).lower(), "Rigid")
        deformable = (transform_type == "BSpline")
        resampled = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLScalarVolumeNode",
            slicer.mrmlScene.GenerateUniqueName(output_name or f"{moving.GetName()}_reg"))
        linear = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLLinearTransformNode", slicer.mrmlScene.GenerateUniqueName("registration_transform"))
        made = [resampled, linear]
        params = {
            "fixedVolume": fixed.GetID(),
            "movingVolume": moving.GetID(),
            "outputVolume": resampled.GetID(),
            "initializeTransformMode": "useMomentsAlign",
            "samplingPercentage": 0.02,
        }
        if deformable:                       # rigid pre-align, then BSpline refine
            bspline = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLBSplineTransformNode", slicer.mrmlScene.GenerateUniqueName("registration_bspline"))
            made.append(bspline)
            params["transformType"] = "Rigid,BSpline"
            params["linearTransform"] = linear.GetID()
            params["bsplineTransform"] = bspline.GetID()
            out_xform = bspline
        else:
            params["transformType"] = transform_type      # Rigid or Affine
            params["linearTransform"] = linear.GetID()
            out_xform = linear
        self._pump()
        ok, status = self._run_cli(slicer.modules.brainsfit, params)
        if not ok:
            for node in made:
                slicer.mrmlScene.RemoveNode(node)
            return _err(f"registration (BRAINSFit) did not complete: {status}. The two volumes "
                        "may be too different to align this way — try a different registration type.")
        return _ok(
            f'Registered "{moving.GetName()}" onto "{fixed.GetName()}" ({transform_type}). '
            f'Aligned copy: "{resampled.GetName()}"; transform: "{out_xform.GetName()}". '
            "The aligned volume now shares the fixed volume's space — overlay them (foreground over "
            "background) to check the fusion, or use compare_studies for a subtraction change-map.")

    def _tool_run_nnunet(self, model_path="", volume_name="", folds="0"):
        try:
            from SlicerNNUNetLib import SegmentationLogic, Parameter
        except ImportError:
            return _err("the SlicerNNUnet extension is not installed. Install it from the Extensions "
                        "Manager and restart Slicer, then retry.")
        if not model_path:
            return _err("provide the trained nnU-Net model folder (model_path) — shaped like "
                        "'Dataset<id>_<name>/<trainer>__<plan>__<config>' with a dataset.json and "
                        "fold_<i> weight folders.")
        if not os.path.isdir(model_path):
            return _err(f"nnU-Net model folder not found: {model_path}")
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)

        from pathlib import Path
        gpu = False
        try:
            import torch
            gpu = bool(torch.cuda.is_available())
        except Exception:
            gpu = False
        param = Parameter(folds=folds or "0", device=("cuda" if gpu else "cpu"),
                          modelPath=Path(model_path))
        valid, reason = param.isValid()
        if not valid:
            return _err("that nnU-Net model folder is not valid: " + reason)

        logic = SegmentationLogic()
        state = {"done": False, "error": None}
        try:
            logic.inferenceFinished.connect(lambda *a: state.update(done=True))
            logic.errorOccurred.connect(lambda e=None, *a: state.update(done=True, error=str(e)))
        except Exception:
            pass
        logic.setParameter(param)
        self._pump()
        import time
        try:
            logic.startSegmentation(volume)        # launches a background QProcess
            while not state["done"]:               # pump the event loop -> UI stays responsive
                slicer.app.processEvents()
                time.sleep(0.05)
            if state["error"]:
                return _err("nnU-Net segmentation failed: " + str(state["error"]))
            seg = logic.loadSegmentation()
        except Exception as exc:
            return _err(f"nnU-Net run failed: {exc}")
        count = seg.GetSegmentation().GetNumberOfSegments() if seg else 0
        return _ok(f'nnU-Net finished ({param._getDevice()}): "{seg.GetName()}" has {count} segments. '
                   "Use list_segments to see them, measure_segment_volumes for volumes, or "
                   "show_segmentation_3d to render.")

    def _tool_export_dicom_seg(self, segmentation_name="", output_folder=""):
        try:
            import DICOMSegmentationPlugin           # provided by QuantitativeReporting
            have = True
        except ImportError:
            have = hasattr(slicer.modules, "quantitativereporting")
        if not have:
            return _err("DICOM SEG export needs the QuantitativeReporting extension (it bundles dcmqi). "
                        "Install it from the Extensions Manager and restart Slicer, then retry.")
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        out = output_folder or os.path.join(tempfile.gettempdir(), "rad_dicom_seg")
        try:
            os.makedirs(out, exist_ok=True)
            import DICOMSegmentationPlugin
            exporter = DICOMSegmentationPlugin.DICOMSegmentationPluginClass()
            shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
            seg_item = shNode.GetItemByDataNode(seg_node)
            exportables = exporter.examineForExport(seg_item)
            if not exportables:
                return _err("could not prepare a DICOM SEG — the segmentation must reference a volume "
                            "that was loaded from DICOM (the SEG needs a source series to point at).")
            for exp in exportables:
                exp.directory = out
            exporter.export(exportables)
        except Exception as exc:
            return _err(f"DICOM SEG export failed: {exc}. The volume must have been loaded from DICOM.")
        return _ok(f'Exported "{seg_node.GetName()}" as a DICOM Segmentation object to: {out}. '
                   "It can be sent to PACS or re-imported with import_dicom_folder.")

    def _tool_extract_vessel_centerline(self, segmentation_name="", segment_name=""):
        if not hasattr(slicer.modules, "extractcenterline"):
            return _err("vessel centerline extraction needs the SlicerVMTK extension. Install it from "
                        "the Extensions Manager and restart Slicer, then retry.")
        seg_node, seg_id, error = self._resolve_segment_target(segmentation_name, segment_name)
        if error:
            return _err(error)
        try:
            import ExtractCenterline
            logic = ExtractCenterline.ExtractCenterlineLogic()
            seg_node.CreateClosedSurfaceRepresentation()
            surface = vtk.vtkPolyData()
            seg_node.GetClosedSurfaceRepresentation(seg_id, surface)
            self._pump()
            preprocessed = logic.preprocess(surface, logic.getDefaultPreprocessingParameters()
                                            if hasattr(logic, "getDefaultPreprocessingParameters") else None)
            endpoints = logic.extractNetwork(preprocessed if preprocessed else surface, None)
            centerline = logic.extractCenterline(preprocessed if preprocessed else surface, endpoints)
            length = 0.0
            try:
                import numpy as np
                pts = centerline.GetPoints()
                arr = np.array([pts.GetPoint(i) for i in range(pts.GetNumberOfPoints())])
                length = float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))
            except Exception:
                pass
        except Exception as exc:
            return _err(f"centerline extraction failed: {exc}. (SlicerVMTK's ExtractCenterline API — "
                        "confirm the vessel segment is a clean tube.)")
        name = seg_node.GetSegmentation().GetSegment(seg_id).GetName()
        extra = f" Centerline length ~{length:.0f} mm." if length else ""
        return _ok(f'Extracted the centerline of "{name}".{extra} Per-point radius/diameter is on the '
                   "centerline model — cross-section analysis gives diameter along the vessel.")

    def _tool_run_monai_auto3dseg(self, model="", volume_name="", force_cpu=False):
        try:
            import MONAIAuto3DSeg
        except ImportError:
            return _err("MONAI Auto3DSeg is not installed. Install the MONAIAuto3DSeg extension from the "
                        "Extensions Manager and restart Slicer, then retry.")
        try:
            logic = MONAIAuto3DSeg.MONAIAuto3DSegLogic()
            model_ids = [m["id"] for m in logic.models]
        except Exception as exc:
            return _err(f"could not read the MONAI Auto3DSeg model list: {exc}")
        if not model:
            preview = ", ".join(model_ids[:12])
            return _err("choose a MONAI model (pass 'model'). Available include: " + preview
                        + (" …" if len(model_ids) > 12 else "")
                        + f". Default: {logic.defaultModel}. Read the monai-auto3dseg skill to match "
                        "the model to the modality (CT vs MR) and the target organs.")
        if model not in model_ids:
            close = [m for m in model_ids if model.lower() in m.lower()][:8]
            hint = (" Did you mean: " + ", ".join(close) + "?") if close else ""
            return _err(f"unknown MONAI model '{model}'.{hint} Omit 'model' to list the choices.")
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)

        gpu = False
        if not force_cpu:
            try:
                import torch
                gpu = bool(torch.cuda.is_available())
            except Exception:
                gpu = False

        seg = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode", slicer.mrmlScene.GenerateUniqueName("MONAI_" + model))
        seg.CreateDefaultDisplayNodes()

        try:
            from MONAIAuto3DSegLib.process import EventCode
            end_code = EventCode.TASKLIST_PROCESSING_ENDED
        except Exception:
            end_code = None
        state = {"done": False}

        def _cb(code, info=None):
            try:
                if end_code is not None:
                    if code == end_code:
                        state["done"] = True
                elif "ENDED" in str(getattr(code, "name", code)):
                    state["done"] = True
            except Exception:
                pass

        import time
        try:
            self._pump()
            logic.process([volume], seg, model=model, cpu=(not gpu),
                          waitForCompletion=False, eventCallback=_cb)
            waited = 0.0
            while not state["done"] and waited < 3600:   # pump the UI; cap ~1h
                slicer.app.processEvents()
                time.sleep(0.05)
                waited += 0.05
        except Exception as exc:
            return _err(f"MONAI Auto3DSeg run failed: {exc}")
        count = seg.GetSegmentation().GetNumberOfSegments()
        if count == 0:
            return _err("MONAI Auto3DSeg finished but produced no segments — check the model matches the "
                        "modality (CT vs MR) and the input volume covers the target anatomy.")
        dev = "GPU" if gpu else "CPU"
        return _ok(f'MONAI Auto3DSeg ({model}, {dev}) finished: "{seg.GetName()}" has {count} segments. '
                   "Use list_segments / measure_segment_volumes / show_segmentation_3d.")

    def _tool_compute_dvh(self, dose_volume="", segmentation_name="", segment_name=""):
        if not hasattr(slicer.modules, "dosevolumehistogram"):
            return _err("DVH computation needs the SlicerRT extension. Install it from the Extensions "
                        "Manager and restart Slicer, then retry.")
        dose, error = _find_volume(dose_volume)
        if error:
            return _err("name the RT DOSE volume — " + error)
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        try:
            logic = slicer.modules.dosevolumehistogram.logic()
            dvh_node = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLDoseVolumeHistogramNode", slicer.mrmlScene.GenerateUniqueName("DVH"))
            for setter, node in (("SetAndObserveDoseVolumeNode", dose),
                                 ("SetAndObserveSegmentationNode", seg_node)):
                fn = getattr(dvh_node, setter, None)
                if fn:
                    fn(node)
            self._pump()
            logic.ComputeDvh(dvh_node)
            self._pump()
            for metric in ("ComputeVMetrics", "ComputeDMetrics"):
                fn = getattr(logic, metric, None)
                if fn:
                    try:
                        fn(dvh_node)
                    except Exception:
                        pass
        except Exception as exc:
            return _err(f"DVH computation failed: {exc}. (SlicerRT DVH — ensure a valid RT dose volume in "
                        "Gy and a segmentation of the structures are loaded.)")
        return _ok("Computed the dose-volume histogram for the segmentation against the dose volume "
                   "(DVH + V/D dose metrics are in the Dose Volume Histogram results table). This "
                   "QUANTIFIES dose per structure; whether the plan meets constraints is the clinician's call.")

    def _tool_export_dicom_sr(self, segmentation_name="", output_folder=""):
        have = hasattr(slicer.modules, "quantitativereporting")
        if not have:
            try:
                import QuantitativeReporting  # noqa: F401
                have = True
            except ImportError:
                have = False
        if not have:
            return _err("DICOM SR (structured report) export needs the QuantitativeReporting extension "
                        "(it bundles dcmqi). Install it from the Extensions Manager and restart Slicer, "
                        "then retry. For the segmentation object itself, export_dicom_seg works without it.")
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        out = output_folder or os.path.join(tempfile.gettempdir(), "rad_dicom_sr")
        try:
            os.makedirs(out, exist_ok=True)
            import QuantitativeReporting
            logic = QuantitativeReporting.QuantitativeReportingLogic()
            create_sr = getattr(logic, "createDICOMSR", None)
            if create_sr is None:
                return _err("this QuantitativeReporting version does not expose createDICOMSR from Python — "
                            "generate the DICOM SR from the QuantitativeReporting module UI, or use "
                            "export_dicom_seg for the segmentation object.")
            create_sr(out)
        except Exception as exc:
            return _err(f"DICOM SR export failed: {exc}. The volume must have been loaded from DICOM and "
                        "the segments measured; otherwise use export_dicom_seg.")
        return _ok(f'Exported a DICOM Structured Report (TID 1500) for "{seg_node.GetName()}" to: {out}. '
                   "It records the quantitative measurements and can be sent to PACS.")

    def _find_markups(self, name):
        nodes = slicer.util.getNodesByClass("vtkMRMLMarkupsNode")
        if not name:
            if len(nodes) == 1:
                return nodes[0], None
            if not nodes:
                return None, "no markup points/lines are in the scene"
            names = ", ".join(f'"{n.GetName()}"' for n in nodes)
            return None, f"several markup sets exist — name one of: {names}"
        for n in nodes:
            if n.GetName() == name:
                return n, None
        for n in nodes:
            if name.lower() in n.GetName().lower():
                return n, None
        return None, f"no markups named '{name}'"

    def _tool_export_segmentation_model(self, segmentation_name="", segment_name="",
                                        output_folder="", file_format="STL"):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        fmt = str(file_format or "STL").upper()
        if fmt not in ("STL", "OBJ"):
            return _err("file_format must be STL or OBJ")
        segmentation = seg_node.GetSegmentation()
        seg_ids = vtk.vtkStringArray()
        if segment_name:
            sid, err = _find_segment_id(seg_node, segment_name)
            if err:
                return _err(err)
            seg_ids.InsertNextValue(sid)
        else:
            for i in range(segmentation.GetNumberOfSegments()):
                seg_ids.InsertNextValue(segmentation.GetNthSegmentID(i))
        if seg_ids.GetNumberOfValues() == 0:
            return _err("that segmentation has no segments to export")
        out = output_folder or os.path.join(tempfile.gettempdir(), "rad_models")
        try:
            os.makedirs(out, exist_ok=True)
            seg_node.CreateClosedSurfaceRepresentation()
            self._pump()
            ok = slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsClosedSurfaceRepresentationToFiles(
                out, seg_node, seg_ids, fmt)
        except Exception as exc:
            return _err(f"model export failed: {exc}")
        if ok is False:
            return _err("model export did not complete — the segments may be empty")
        n = seg_ids.GetNumberOfValues()
        return _ok(f'Exported {n} segment(s) from "{seg_node.GetName()}" as {fmt} mesh file(s) to: {out}. '
                   "Ready for 3D printing, surgical planning, or CAD.")

    def _tool_export_markups(self, markups_name="", output_path=""):
        node, error = self._find_markups(markups_name)
        if error:
            return _err(error)
        out = output_path or os.path.join(tempfile.gettempdir(), (node.GetName() or "markups") + ".csv")
        try:
            parent = os.path.dirname(os.path.abspath(out))
            os.makedirs(parent, exist_ok=True)
            ok = slicer.modules.markups.logic().ExportControlPointsToCSV(node, out)
        except Exception as exc:
            return _err(f"markups export failed: {exc}")
        if ok is False:
            return _err("markups export did not complete")
        n = node.GetNumberOfControlPoints()
        return _ok(f'Exported {n} control point(s) from "{node.GetName()}" to CSV: {out}.')

    def _tool_import_markups(self, input_path="", markups_name=""):
        if not input_path or not os.path.isfile(input_path):
            return _err(f"CSV file not found: {input_path}")
        node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLMarkupsFiducialNode",
            slicer.mrmlScene.GenerateUniqueName(markups_name or "ImportedPoints"))
        try:
            ok = slicer.modules.markups.logic().ImportControlPointsFromCSV(node, input_path)
        except Exception as exc:
            slicer.mrmlScene.RemoveNode(node)
            return _err(f"markups import failed: {exc}")
        if ok is False:
            slicer.mrmlScene.RemoveNode(node)
            return _err("could not import points — is this a Slicer markups CSV (with position columns)?")
        n = node.GetNumberOfControlPoints()
        return _ok(f'Imported {n} control point(s) from {input_path} into "{node.GetName()}".')

    def _tool_threshold_segmentation(self, segment_name, lower_threshold, upper_threshold,
                                     volume_name="", keep_largest_island=False,
                                     red=None, green=None, blue=None):
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)

        seg_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode", slicer.mrmlScene.GenerateUniqueName(segment_name + "_seg"))
        seg_node.CreateDefaultDisplayNodes()
        seg_node.SetReferenceImageGeometryParameterFromVolumeNode(volume)
        # first positional arg is the segment ID, not the name — pass "" so Slicer
        # generates the ID and actually uses segment_name as the display name.
        seg_id = seg_node.GetSegmentation().AddEmptySegment("", segment_name)
        if red is not None and green is not None and blue is not None:
            seg_node.GetSegmentation().GetSegment(seg_id).SetColor(
                float(red), float(green), float(blue))

        editor_widget = slicer.qMRMLSegmentEditorWidget()
        editor_widget.setMRMLScene(slicer.mrmlScene)
        editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editor_widget.setMRMLSegmentEditorNode(editor_node)
        editor_widget.setSegmentationNode(seg_node)
        try:
            editor_widget.setSourceVolumeNode(volume)          # Slicer >= 5.2
        except AttributeError:
            editor_widget.setMasterVolumeNode(volume)          # older API
        editor_node.SetSelectedSegmentID(seg_id)

        editor_widget.setActiveEffectByName("Threshold")
        effect = editor_widget.activeEffect()
        effect.setParameter("MinimumThreshold", str(float(lower_threshold)))
        effect.setParameter("MaximumThreshold", str(float(upper_threshold)))
        self._pump()
        effect.self().onApply()
        self._pump()

        if keep_largest_island:
            editor_widget.setActiveEffectByName("Islands")
            effect = editor_widget.activeEffect()
            effect.setParameter("Operation", "KEEP_LARGEST_ISLAND")
            effect.self().onApply()

        editor_widget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editor_node)
        # NB: no 3D mesh build here — it's the slow marching-cubes step and it isn't
        # needed to measure volume. The segment already shows on the slice views;
        # show_segmentation_3d builds the surface on demand.
        return _ok(f'Created segmentation "{seg_node.GetName()}" with segment "{segment_name}" '
                   f"thresholded at [{lower_threshold}, {upper_threshold}]"
                   + (", kept largest island" if keep_largest_island else "")
                   + ". Visible on the slice views. Call measure_segment_volumes for the volume, "
                   "or show_segmentation_3d to render it in 3D (that mesh build is the slow step).")

    def _tool_run_total_segmentator(self, volume_name="", task="total", quality="",
                                    roi_subset=None, fast=None, force_cpu=False):
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)
        st = _extension_status("TotalSegmentator", "totalsegmentator")
        where = "Slicer %s (rev %s)" % (st["version"], st["revision"])
        if not st["module_loaded"]:
            if st["on_disk_here"] or st["package"]:
                # Files exist for THIS Slicer but the module didn't register — a load
                # failure or an enable-without-restart, NOT a missing install.
                return _err(
                    "TotalSegmentator's files are present in %s but its module didn't load. "
                    "Restart THIS Slicer once. If it still won't load, open the Python Console "
                    "(View > Python Console) and check the error log — the extension likely "
                    "failed to import (commonly a PyTorch/CUDA version mismatch)." % where)
            # Genuinely absent from the running Slicer. The usual real cause is that it
            # was installed into a DIFFERENT Slicer version (extensions are per-version).
            return _err(
                "the SlicerTotalSegmentator extension isn't loaded in the Slicer you're "
                "running now (%s). The most common cause is that it's installed in a DIFFERENT "
                "Slicer version — extensions are per-version and do NOT carry across installs, "
                "so a TotalSegmentator you installed in another Slicer won't appear here. In "
                "THIS Slicer: open Extensions Manager > Manage Extensions, confirm "
                "'TotalSegmentator' is installed and enabled, restart THIS Slicer, then retry. "
                "(If you meant to use the Slicer where it's already installed, load RadAssistant "
                "in that one instead.)" % where)
        import importlib.util
        if importlib.util.find_spec("totalsegmentator") is None:
            # First run pip-installs the package AND downloads ~1.5 GB of weights,
            # synchronously on the main thread — this is the multi-minute "jam".
            return _err(
                "TotalSegmentator's AI weights/packages are NOT installed yet. The FIRST run "
                "downloads ~1.5 GB and pip-installs packages synchronously, freezing Slicer for "
                "10-30+ minutes (worse on CPU) — that IS the jam you're seeing, and it recurs every "
                "run until it's cached. Do NOT start that mid-demo. Install it ONCE first: open "
                "Modules > Segmentation > TotalSegmentator and run it there once (it shows a progress "
                "bar and caches the weights), then this tool runs normally. Or run TotalSegmentator "
                "on the HPC GPU. For a lung result right now, use the threshold workflow instead — "
                "it's fast and you just saw it give ~2.8 L.")
        try:
            from TotalSegmentator import TotalSegmentatorLogic
        except ImportError as exc:
            return _err(f"TotalSegmentator module import failed: {exc}")

        # Resolve speed: explicit quality wins; else map the legacy `fast` bool; default fast.
        quality = (quality or "").strip().lower()
        if quality not in ("normal", "fast", "faster"):
            quality = "normal" if fast is False else "fast"

        # roi_subset only applies to the 'total'/'total_mr' tasks (per totalsegmentator API);
        # it restricts prediction to named structures and cuts runtime/memory a lot.
        subset = None
        if roi_subset:
            subset = roi_subset if isinstance(roi_subset, list) else [roi_subset]
            if not str(task).startswith("total"):
                return _err(f"roi_subset only works with task 'total' or 'total_mr', not '{task}'. "
                            "Drop roi_subset, or use task='total'.")

        # Device: TotalSegmentator uses torch/CUDA. On CPU a full-body model is minutes.
        gpu = False
        torch_cpu_only = False
        try:
            import torch
            gpu = bool(torch.cuda.is_available())
            torch_cpu_only = (getattr(torch.version, "cuda", None) is None)
        except Exception:
            gpu = False
        device = "cpu" if (force_cpu or not gpu) else "cuda"
        try:
            from . import logbook
            logbook.tool_call("run_total_segmentator[preflight]",
                              {"task": task, "quality": quality, "device": device,
                               "roi_subset": subset})
        except Exception:
            pass

        # logic.process() runs nnU-Net inference and reads the subprocess with a BLOCKING
        # readline() on the Qt main thread (TotalSegmentator.py logProcessOutput), so the UI
        # is frozen for the whole run — seconds on GPU, minutes to tens-of-minutes on CPU.
        # The one real trap is full-resolution 'normal' on CPU (5-50 min): the extension itself
        # offers to downgrade that to 'fast'. We can't prompt mid-call, so refuse and let the
        # model ask the user (see the total-segmentator skill) and re-run at fast/faster/HPC.
        if device == "cpu" and quality == "normal" and not subset:
            if torch_cpu_only and not force_cpu:
                # The frequent real cause: an NVIDIA GPU IS present but Slicer's PyTorch is the
                # CPU-only wheel, so CUDA can never be used until torch is reinstalled.
                return _err(
                    "TotalSegmentator can't use a GPU because Slicer's PyTorch is a CPU-ONLY build "
                    "(torch '+cpu', torch.version.cuda is None) — this is a setup issue, not a "
                    "missing GPU. If the machine has an NVIDIA GPU it is simply not being used, so "
                    "'normal' would fall back to CPU (5-50 min, UI frozen). FIX: open Slicer's "
                    "'PyTorch Util' module, choose a CUDA computation backend (e.g. cu121), click "
                    "Install PyTorch, and restart Slicer — then normal runs in seconds. Until then, "
                    "use quality='fast', or roi_subset=[...] for a targeted full-res run.")
            return _err(
                "TotalSegmentator 'normal' (full-resolution) has no GPU here and would take "
                "5-50 MINUTES with Slicer's UI frozen the whole time. Ask the user, then re-run "
                "one of: quality='fast' (~3 mm, a few minutes), quality='faster' (~6 mm, fastest, "
                "least detail), or roi_subset=[...] to segment only the organs they need (much "
                "faster) — or run it on the HPC GPU. For a simple lung/bone volume, the threshold "
                "workflow is seconds and never freezes.")

        seg_node = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentationNode",
            slicer.mrmlScene.GenerateUniqueName(f"TotalSeg_{volume.GetName()}"))
        logic = TotalSegmentatorLogic()
        self._pump()   # paint the "running" state before the blocking job
        try:
            # extension signature: process(inputVolume, outputSegmentation, quality, cpu, task, subset, ...)
            logic.process(volume, seg_node, quality, bool(force_cpu), task, subset)
        except TypeError:
            try:
                logic.process(volume, seg_node, quality, bool(force_cpu), task)
            except TypeError:
                logic.process(volume, seg_node)  # oldest signature
        self._pump()
        # defer the (very heavy, 100+ organ) 3D mesh build to show_segmentation_3d
        count = seg_node.GetSegmentation().GetNumberOfSegments()
        scope = f", roi_subset={subset}" if subset else ""
        return _ok(f'TotalSegmentator finished ({task}, {quality} mode, {device}{scope}): '
                   f'"{seg_node.GetName()}" now has {count} segments. Use list_segments to see '
                   "them, measure_segment_volumes for volumes, then show_segmentation_3d to render "
                   "(heavy for 100+ organs — consider roi_subset or hiding most first).")

    def _tool_place_point(self, r, a, s, label=""):
        node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode",
                                                  label or "RadAssistant point")
        node.AddControlPoint(vtk.vtkVector3d(float(r), float(a), float(s)),
                             label or "P1")
        return _ok(f'Point "{label or "P1"}" placed at RAS ({r:.1f}, {a:.1f}, {s:.1f}).')

    def _tool_measure_distance(self, point1, point2, label=""):
        if len(point1) != 3 or len(point2) != 3:
            return _err("point1 and point2 must each be [r, a, s]")
        line = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsLineNode",
                                                  label or "Measurement")
        line.AddControlPoint(vtk.vtkVector3d(*[float(v) for v in point1]))
        line.AddControlPoint(vtk.vtkVector3d(*[float(v) for v in point2]))
        length = math.dist(point1, point2)
        return _ok(f'Measurement line "{line.GetName()}" placed: {length:.1f} mm.')

    def _tool_enable_volume_rendering(self, volume_name="", preset="CT-Chest-Contrast-Enhanced"):
        volume, error = _find_volume(volume_name)
        if error:
            return _err(error)
        vr_logic = slicer.modules.volumerendering.logic()
        display = vr_logic.CreateDefaultVolumeRenderingNodes(volume)
        preset_node = vr_logic.GetPresetByName(preset)
        if preset_node is None:
            names = []
            presets = vr_logic.GetPresetsScene().GetNodesByClass("vtkMRMLVolumePropertyNode")
            presets.InitTraversal()
            node = presets.GetNextItemAsObject()
            while node:
                names.append(node.GetName())
                node = presets.GetNextItemAsObject()
            return _err(f"no volume rendering preset '{preset}'. Available: {', '.join(names)}")
        display.GetVolumePropertyNode().Copy(preset_node)
        display.SetVisibility(True)
        layout_manager = slicer.app.layoutManager()
        if layout_manager.threeDViewCount > 0:
            layout_manager.threeDWidget(0).threeDView().resetFocalPoint()
        return _ok(f'Volume rendering of "{volume.GetName()}" enabled with preset {preset}. '
                   "Screenshot the 3d view to verify.")

    def _tool_rotate_3d_view(self, direction):
        axis = VIEW_AXES.get(direction)
        if axis is None:
            return _err(f"unknown direction '{direction}'")
        layout_manager = slicer.app.layoutManager()
        if layout_manager.threeDViewCount < 1:
            return _err("no 3D view in the current layout")
        view = layout_manager.threeDWidget(0).threeDView()
        view.rotateToViewAxis(axis)
        return _ok(f"3D camera now looking from {direction}.")

    def _tool_center_views(self):
        layout_manager = slicer.app.layoutManager()
        if layout_manager.threeDViewCount > 0:
            layout_manager.threeDWidget(0).threeDView().resetFocalPoint()
        self._reset_views()
        return _ok("All views centered on the data.")

    def _tool_read_skill(self, name):
        return _ok(self._skills.read(name))

    def _tool_execute_python(self, code, reason=""):
        # Hard per-turn cap: catches the fail → other-tool → fail interleave that
        # slips past the consecutive breaker (the model alternates broken Python
        # with a "checking" tool call, so the streak keeps resetting). After 5 total
        # failures this turn, refuse all further Python until the next user message.
        if self._exec_fails_total >= 5:
            return _err(
                "circuit breaker: execute_python has failed 5 times this turn — it is not working. "
                "STOP writing Python entirely. Either use a dedicated tool, or tell the user plainly "
                "what is blocking you (e.g. an extension isn't installed, or the segmentation needs "
                "cleaning). No more Python will run until the next message. If the 3D just looks "
                "wrong, that is a DATA problem, not something to fix with code.")

        # Circuit breaker: stop the model from grinding through a dozen broken
        # snippets (the failure mode where hand-rolled VTK/segmentation code hits
        # one API error after another). Force a change of approach instead.
        if self._exec_fail_streak >= 3:
            self._exec_fail_streak = 0   # one clean slate, then it must justify again
            return _err(
                "circuit breaker: the last 3 execute_python attempts errored. STOP writing "
                "raw Slicer/VTK code. Use dedicated tools instead — threshold_segmentation, "
                "filter_segment_islands, run_total_segmentator, measure_segment_volumes, "
                "show_segmentation_3d. If the task truly needs an extension that isn't installed "
                "(e.g. TotalSegmentator), tell the user that plainly and stop. Only try "
                "execute_python again after the user confirms they want you to.")

        if self._needs_approval("execute_python"):
            approved = _confirm(
                "RadAssistant wants to run Python code",
                (reason or "The assistant wants to execute the following code in Slicer.")
                + "\nReview it before approving:",
                code=code)
            if not approved:
                self._exec_fail_streak = 0
                return _err("the user REJECTED this code execution. Do not retry the same "
                            "code; ask the user how they would like to proceed.")
        # else: Accept/Auto mode — auto-approved, no dialog (the tool_start event still
        # shows the user what's running).
        import numpy
        namespace = {"slicer": slicer, "vtk": vtk, "qt": qt, "ctk": ctk,
                     "np": numpy, "numpy": numpy}
        buffer = io.StringIO()
        self._pump()   # repaint before a potentially long-running exec
        try:
            with contextlib.redirect_stdout(buffer):
                exec(code, namespace)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._exec_fail_streak += 1
            self._exec_fails_total += 1
            output = buffer.getvalue().strip()
            hint = ""
            if self._exec_fail_streak >= 2:
                hint = (" — this keeps failing. Prefer a dedicated tool "
                        "(threshold_segmentation / filter_segment_islands / "
                        "run_total_segmentator) over hand-written segmentation code.")
            return _err(f"{type(exc).__name__}: {exc}{hint}"
                        + (f"\nstdout before the error:\n{output[:1500]}" if output else ""))
        self._exec_fail_streak = 0
        output = buffer.getvalue().strip()
        parts = ["Code executed successfully."]
        if output:
            parts.append("stdout:\n" + output[:4000])
        if "result" in namespace:
            parts.append("result = " + repr(namespace["result"])[:2000])
        return _ok("\n".join(parts))

    def _tool_filter_segment_islands(self, operation="remove_small", min_size_ml=1.0,
                                     segmentation_name="", segment_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        segmentation = seg_node.GetSegmentation()
        if segment_name:
            seg_id, error = _find_segment_id(seg_node, segment_name)
            if error:
                return _err(error)
        elif segmentation.GetNumberOfSegments():
            seg_id = segmentation.GetNthSegmentID(0)
        else:
            return _err("that segmentation has no segments")

        ops = {"remove_small": "REMOVE_SMALL_ISLANDS",
               "keep_largest": "KEEP_LARGEST_ISLAND",
               "split_to_segments": "SPLIT_ISLANDS_TO_SEGMENTS"}
        if operation not in ops:
            return _err(f"unknown operation '{operation}'. Options: {', '.join(sorted(ops))}")

        volume = _active_volume()
        if volume is None:
            vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
            volume = vols[0] if len(vols) == 1 else None

        min_voxels = 0
        if operation in ("remove_small", "split_to_segments"):
            if volume is None:
                return _err("need a reference volume to size islands by mL — load one first")
            sx, sy, sz = volume.GetSpacing()
            voxel_ml = (sx * sy * sz) / 1000.0
            min_voxels = max(1, int(round(float(min_size_ml) / voxel_ml)))

        editor_widget = slicer.qMRMLSegmentEditorWidget()
        editor_widget.setMRMLScene(slicer.mrmlScene)
        editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editor_widget.setMRMLSegmentEditorNode(editor_node)
        editor_widget.setSegmentationNode(seg_node)
        if volume is not None:
            try:
                editor_widget.setSourceVolumeNode(volume)          # Slicer >= 5.2
            except AttributeError:
                editor_widget.setMasterVolumeNode(volume)          # older API
        editor_node.SetSelectedSegmentID(seg_id)
        editor_widget.setActiveEffectByName("Islands")
        effect = editor_widget.activeEffect()
        effect.setParameter("Operation", ops[operation])
        if min_voxels:
            effect.setParameter("MinimumSize", str(min_voxels))
        try:
            effect.self().onApply()
        except Exception as exc:
            editor_widget.setActiveEffectByName("")
            slicer.mrmlScene.RemoveNode(editor_node)
            return _err(f"islands operation failed: {exc}")
        editor_widget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editor_node)

        n_after = seg_node.GetSegmentation().GetNumberOfSegments()
        detail = {
            "remove_small": f"removed islands smaller than {min_size_ml} mL "
                            f"(< {min_voxels} voxels)",
            "keep_largest": "kept only the single largest island",
            "split_to_segments": f"split islands into {n_after} separate segments",
        }[operation]
        return _ok(f'Islands cleanup on "{seg_node.GetName()}": {detail}. '
                   "Re-measure volumes; call show_segmentation_3d to view in 3D.")

    def _resolve_segment_target(self, segmentation_name, segment_name):
        """Shared: (seg_node, seg_id, error) for the segment-editor tools. Defaults to
        the most-recent segmentation and its first segment when names are omitted."""
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return None, None, error
        segmentation = seg_node.GetSegmentation()
        if segment_name:
            seg_id, error = _find_segment_id(seg_node, segment_name)
            if error:
                return None, None, error
        elif segmentation.GetNumberOfSegments():
            seg_id = segmentation.GetNthSegmentID(0)
        else:
            return None, None, "that segmentation has no segments"
        return seg_node, seg_id, None

    def _open_segment_editor(self, seg_node, seg_id):
        """Wire up a segment-editor widget on seg_id (same pattern as the islands/merge
        tools). Returns (editor_widget, editor_node); caller must remove editor_node.

        The Smoothing and Margin effects call confirmCurrentSegmentVisible() inside their
        onApply(); when the segment is hidden that pops a modal dialog (which crashes a
        --no-main-window session and blocks the agent in the live app). Force the target
        segment visible first so the confirm passes silently."""
        disp = seg_node.GetDisplayNode()
        if disp is None:
            seg_node.CreateDefaultDisplayNodes()
            disp = seg_node.GetDisplayNode()
        if disp is not None:
            disp.SetSegmentVisibility(seg_id, True)
        volume = _active_volume()
        if volume is None:
            vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
            volume = vols[0] if len(vols) == 1 else None
        editor_widget = slicer.qMRMLSegmentEditorWidget()
        editor_widget.setMRMLScene(slicer.mrmlScene)
        editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editor_widget.setMRMLSegmentEditorNode(editor_node)
        editor_widget.setSegmentationNode(seg_node)
        if volume is not None:
            try:
                editor_widget.setSourceVolumeNode(volume)          # Slicer >= 5.2
            except AttributeError:
                editor_widget.setMasterVolumeNode(volume)          # older API
        editor_node.SetSelectedSegmentID(seg_id)
        return editor_widget, editor_node

    def _tool_smooth_segment(self, method="median", kernel_mm=3.0,
                             segmentation_name="", segment_name=""):
        seg_node, seg_id, error = self._resolve_segment_target(segmentation_name, segment_name)
        if error:
            return _err(error)
        methods = {"median": "MEDIAN", "gaussian": "GAUSSIAN",
                   "opening": "MORPHOLOGICAL_OPENING", "closing": "MORPHOLOGICAL_CLOSING"}
        if method not in methods:
            return _err(f"unknown method '{method}'. Options: {', '.join(sorted(methods))}")
        try:
            kernel_mm = float(kernel_mm)
        except (TypeError, ValueError):
            return _err("kernel_mm must be a number (mm)")

        editor_widget, editor_node = self._open_segment_editor(seg_node, seg_id)
        editor_widget.setActiveEffectByName("Smoothing")
        effect = editor_widget.activeEffect()
        effect.setParameter("SmoothingMethod", methods[method])
        if method == "gaussian":
            effect.setParameter("GaussianStandardDeviationMm", str(kernel_mm))
        else:
            effect.setParameter("KernelSizeMm", str(kernel_mm))
        try:
            effect.self().onApply()
        except Exception as exc:
            editor_widget.setActiveEffectByName("")
            slicer.mrmlScene.RemoveNode(editor_node)
            return _err(f"smoothing failed: {exc}")
        editor_widget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editor_node)
        name = seg_node.GetSegmentation().GetSegment(seg_id).GetName()
        return _ok(f'Smoothed "{name}" ({method}, {kernel_mm} mm) — removes voxel staircase '
                   "artefacts. Re-measure its volume and rebuild the 3D (show_segmentation_3d) to see it.")

    def _tool_grow_shrink_segment(self, margin_mm=None, margin_axial_mm=None, margin_si_mm=None,
                                  segmentation_name="", segment_name=""):
        seg_node, seg_id, error = self._resolve_segment_target(segmentation_name, segment_name)
        if error:
            return _err(error)

        anisotropic = (margin_axial_mm is not None) or (margin_si_mm is not None)
        if anisotropic:
            return self._grow_shrink_anisotropic(seg_node, seg_id, margin_mm,
                                                 margin_axial_mm, margin_si_mm)

        # --- uniform (isotropic) path: Slicer's validated Margin effect ---
        try:
            margin_mm = float(margin_mm)
        except (TypeError, ValueError):
            return _err("give margin_mm (uniform) or margin_axial_mm + margin_si_mm (anisotropic); "
                        "positive grows, negative shrinks")
        if margin_mm == 0:
            return _err("margin_mm of 0 does nothing — give a positive (grow) or negative (shrink) value")

        editor_widget, editor_node = self._open_segment_editor(seg_node, seg_id)
        editor_widget.setActiveEffectByName("Margin")
        effect = editor_widget.activeEffect()
        effect.setParameter("MarginSizeMm", str(margin_mm))
        try:
            effect.self().onApply()
        except Exception as exc:
            editor_widget.setActiveEffectByName("")
            slicer.mrmlScene.RemoveNode(editor_node)
            return _err(f"margin failed: {exc}")
        editor_widget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editor_node)
        name = seg_node.GetSegmentation().GetSegment(seg_id).GetName()
        verb = "Grew" if margin_mm > 0 else "Shrank"
        return _ok(f'{verb} "{name}" by {abs(margin_mm)} mm (uniform Margin effect). '
                   "Re-measure its volume to see the change.")

    def _grow_shrink_anisotropic(self, seg_node, seg_id, margin_mm, margin_axial_mm, margin_si_mm):
        """Per-axis grow/shrink via SimpleITK morphology on the segment's binary labelmap.
        No Segment Editor GUI, so it is headless-safe. margin_axial_mm applies to the in-plane
        (R-L and A-P) image axes; margin_si_mm to the slice (superior-inferior) axis."""
        base = 0.0
        if margin_mm is not None:
            try:
                base = float(margin_mm)
            except (TypeError, ValueError):
                base = 0.0
        try:
            ax = float(margin_axial_mm) if margin_axial_mm is not None else base
            si = float(margin_si_mm) if margin_si_mm is not None else base
        except (TypeError, ValueError):
            return _err("margin_axial_mm and margin_si_mm must be numbers in mm")
        if ax == 0 and si == 0:
            return _err("both margins are 0 — give a nonzero axial or superior-inferior margin")
        nonzero = [v for v in (ax, si) if v != 0]
        if any(v > 0 for v in nonzero) and any(v < 0 for v in nonzero):
            return _err("mixed grow/shrink per axis isn't supported — use all-positive (grow) "
                        "or all-negative (shrink) margins")
        grow = (ax > 0) or (si > 0)

        ref = seg_node.GetNodeReference(
            slicer.vtkMRMLSegmentationNode.GetReferenceImageGeometryReferenceRole())
        if ref is None:
            ref = _active_volume()
        if ref is None:
            vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
            ref = vols[0] if vols else None
        if ref is None:
            return _err("need a reference volume to size the margin in mm — load the source volume first")

        try:
            import SimpleITK as sitk
            import numpy as np
            sx, sy, sz = ref.GetSpacing()             # mm per voxel, image (i, j, k) order
            rx = int(round(abs(ax) / sx)) if sx else 0
            ry = int(round(abs(ax) / sy)) if sy else 0
            rz = int(round(abs(si) / sz)) if sz else 0
            if rx == 0 and ry == 0 and rz == 0:
                return _err("the requested margin is smaller than one voxel on every axis — "
                            "nothing to do at this resolution")
            arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, seg_id, ref)  # (k, j, i)
            if arr is None or int(arr.max()) == 0:
                return _err("the segment is empty — nothing to grow or shrink")
            mask = sitk.GetImageFromArray((arr > 0).astype(np.uint8))   # sitk axes (x=i, y=j, z=k)
            radius = [rx, ry, rz]                                       # sitk (x, y, z) order
            if grow:
                out = sitk.BinaryDilate(mask, radius, sitk.sitkBall, 0.0, 1.0, False)
            else:
                out = sitk.BinaryErode(mask, radius, sitk.sitkBall, 0.0, 1.0, True)
            out_arr = sitk.GetArrayFromImage(out).astype(np.uint8)
            slicer.util.updateSegmentBinaryLabelmapFromArray(out_arr, seg_node, seg_id, ref)
        except Exception as exc:
            return _err(f"anisotropic margin failed: {exc}")

        name = seg_node.GetSegmentation().GetSegment(seg_id).GetName()
        verb = "Grew" if grow else "Shrank"
        return _ok(f'{verb} "{name}" anisotropically — {abs(ax):g} mm axial (in-plane R-L & A-P), '
                   f'{abs(si):g} mm superior-inferior (per-axis SimpleITK morphology; voxel radii '
                   f'x/y/z = {rx}/{ry}/{rz}). Re-measure its volume to see the change. '
                   "Computed on the image axes — assumes an axial-acquired volume.")

    def _tool_merge_segments(self, segment_names, new_name="", segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        if not segment_names or len(segment_names) < 2:
            return _err("give at least two segment names to merge")
        segmentation = seg_node.GetSegmentation()
        ids = []
        for nm in segment_names:
            sid, err = _find_segment_id(seg_node, nm)
            if err:
                return _err(err)
            ids.append(sid)
        target_id, others = ids[0], ids[1:]

        volume = _active_volume()
        if volume is None:
            vols = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
            volume = vols[0] if vols else None

        editor_widget = slicer.qMRMLSegmentEditorWidget()
        editor_widget.setMRMLScene(slicer.mrmlScene)
        editor_node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
        editor_widget.setMRMLSegmentEditorNode(editor_node)
        editor_widget.setSegmentationNode(seg_node)
        if volume is not None:
            try:
                editor_widget.setSourceVolumeNode(volume)
            except AttributeError:
                editor_widget.setMasterVolumeNode(volume)
        editor_node.SetSelectedSegmentID(target_id)
        editor_widget.setActiveEffectByName("Logical operators")
        effect = editor_widget.activeEffect()
        try:
            for other in others:
                effect.setParameter("Operation", "UNION")
                effect.setParameter("ModifierSegmentID", other)
                effect.setParameter("BypassMasking", "1")
                effect.self().onApply()
        except Exception as exc:
            editor_widget.setActiveEffectByName("")
            slicer.mrmlScene.RemoveNode(editor_node)
            return _err(f"merge failed: {exc}")
        editor_widget.setActiveEffectByName("")
        slicer.mrmlScene.RemoveNode(editor_node)

        for other in others:                 # remove the now-merged-in segments
            segmentation.RemoveSegment(other)
        if new_name:
            segmentation.GetSegment(target_id).SetName(new_name)
        final = new_name or segmentation.GetSegment(target_id).GetName()
        return _ok(f'Merged {len(ids)} segments into "{final}". '
                   "Re-measure its volume; call show_segmentation_3d to view it in 3D.")

    def _tool_delete_segments(self, segment_names, segmentation_name=""):
        seg_node, error = _find_segmentation(segmentation_name)
        if error:
            return _err(error)
        if not segment_names:
            return _err("give at least one segment name to delete")
        if self._needs_approval("delete_segments"):
            if not _confirm("Delete segments",
                            "Delete these segments (cannot be undone)?\n" + ", ".join(segment_names)):
                return _err("the user declined to delete these segments.")
        segmentation = seg_node.GetSegmentation()
        removed, missing = [], []
        for nm in segment_names:
            seg_id, err = _find_segment_id(seg_node, nm)
            if err:
                missing.append(nm)
                continue
            segmentation.RemoveSegment(seg_id)
            removed.append(nm)
        if not removed:
            return _err(f"no matching segments to delete. Not found: {', '.join(missing)}")
        msg = f'Deleted {len(removed)} segment(s): {", ".join(removed)}.'
        if missing:
            msg += f" Not found: {', '.join(missing)}."
        return _ok(msg + " Re-measure volumes or show_segmentation_3d as needed.")

    def _tool_clear_scene(self):
        # Count user-facing data nodes for an honest summary. Singleton nodes
        # (views, layout, cameras) are preserved by Clear() and don't count.
        data_classes = ("vtkMRMLScalarVolumeNode", "vtkMRMLLabelMapVolumeNode",
                        "vtkMRMLSegmentationNode", "vtkMRMLModelNode",
                        "vtkMRMLMarkupsNode", "vtkMRMLTransformNode")
        before = 0
        for cls in data_classes:
            try:
                before += len(slicer.util.getNodesByClass(cls))
            except Exception:
                pass
        if before == 0:
            return _ok("The scene is already empty — nothing to clear.")
        if self._needs_approval("clear_scene"):
            if not _confirm("Clear scene",
                            f"Remove ALL {before} data node(s) from the scene? This cannot be "
                            "undone. Save first if you need this data."):
                return _err("the user declined to clear the scene.")
        # Clear(0) keeps singleton view/layout nodes (the File > Close Scene behavior);
        # newer Slicer exposes a no-arg Clear() — support both.
        try:
            slicer.mrmlScene.Clear(0)
        except TypeError:
            slicer.mrmlScene.Clear()
        return _ok(f"Cleared the scene — removed {before} data node(s); it is now empty. "
                   "Load new data with load_sample_data, load_file, or import_dicom_folder.")
