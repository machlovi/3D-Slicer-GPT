# SlicerAdaptiveBrush Connector
#
# This connector provides AI access to the SlicerAdaptiveBrush segment editor
# effect, enabling intelligent configuration of the adaptive brush for medical
# image segmentation.
#
# SlicerAdaptiveBrush must be installed in 3D Slicer for these tools to work.
# The effect is accessed through the Segment Editor widget.

import re
import time
import logging
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Known preset IDs (used for exact matching in _resolve_preset_id)
# ---------------------------------------------------------------------------

PRESET_IDS = [
    "default",
    # CT
    "ct_bone", "ct_soft_tissue", "ct_lung", "ct_airway",
    "ct_vessel_contrast", "ct_muscle", "ct_fat", "ct_lymph_node",
    # MRI T1
    "mri_t1_brain_gm", "mri_t1_brain_wm", "mri_t1_fat", "mri_t1_muscle",
    # MRI T1+Gd
    "mri_t1gd_tumor", "mri_t1gd_vessel",
    # MRI T2/FLAIR
    "mri_t2_lesion", "mri_flair_lesion", "mri_t2_csf",
    # MRI DWI
    "mri_dwi_stroke",
    # PET
    "pet_tumor", "pet_suv_threshold",
    # Ultrasound
    "us_general", "us_cyst",
    # CBCT
    "cbct_bone",
    # Microscopy
    "micro_cell", "micro_nucleus",
    # Generic
    "generic_tumor", "generic_vessel", "generic_organ", "generic_lesion",
    "generic_high_contrast", "generic_low_contrast",
    # Speed / Precision
    "speed_fast", "precision_high",
]

# Human-readable aliases that map to preset IDs.
# Each preset has a list of keyword sets; input is matched by word overlap.
_PRESET_KEYWORDS = {
    "default": ["default"],
    # CT
    "ct_bone": ["ct bone", "ct skeleton"],
    "ct_soft_tissue": ["ct soft tissue"],
    "ct_lung": ["ct lung", "ct pulmonary"],
    "ct_airway": ["ct airway", "ct trachea", "ct bronch"],
    "ct_vessel_contrast": ["ct vessel contrast", "ct angiography", "ct cta"],
    "ct_muscle": ["ct muscle"],
    "ct_fat": ["ct fat", "ct adipose"],
    "ct_lymph_node": ["ct lymph node", "ct lymph"],
    # MRI T1
    "mri_t1_brain_gm": ["mri t1 brain gray matter", "mri t1 brain gm",
                         "mri t1 gray matter", "mri brain gray"],
    "mri_t1_brain_wm": ["mri t1 brain white matter", "mri t1 brain wm",
                         "mri t1 white matter", "mri brain white"],
    "mri_t1_fat": ["mri t1 fat"],
    "mri_t1_muscle": ["mri t1 muscle"],
    # MRI T1+Gd
    "mri_t1gd_tumor": ["mri t1 gd tumor", "mri t1 gd enhancing tumor",
                        "mri t1+gd tumor", "mri t1 gadolinium tumor",
                        "mri contrast tumor", "mri enhancing tumor",
                        "mri gd tumor", "brain tumor mri"],
    "mri_t1gd_vessel": ["mri t1 gd vessel", "mri t1+gd vessel",
                         "mri contrast vessel", "mri gadolinium vessel"],
    # MRI T2/FLAIR
    "mri_t2_lesion": ["mri t2 lesion"],
    "mri_flair_lesion": ["mri flair lesion", "flair lesion"],
    "mri_t2_csf": ["mri t2 csf", "mri csf", "cerebrospinal fluid"],
    # MRI DWI
    "mri_dwi_stroke": ["mri dwi stroke", "dwi stroke", "diffusion stroke"],
    # PET
    "pet_tumor": ["pet tumor", "pet ct tumor"],
    "pet_suv_threshold": ["pet suv", "pet threshold", "suv threshold"],
    # Ultrasound
    "us_general": ["ultrasound general", "us general", "ultrasound"],
    "us_cyst": ["ultrasound cyst", "us cyst"],
    # CBCT
    "cbct_bone": ["cbct bone", "cone beam bone"],
    # Microscopy
    "micro_cell": ["microscopy cell", "micro cell", "cell"],
    "micro_nucleus": ["microscopy nucleus", "micro nucleus", "nucleus"],
    # Generic
    "generic_tumor": ["tumor", "generic tumor", "tumour"],
    "generic_vessel": ["vessel", "generic vessel", "blood vessel"],
    "generic_organ": ["organ", "generic organ"],
    "generic_lesion": ["lesion", "generic lesion"],
    "generic_high_contrast": ["high contrast"],
    "generic_low_contrast": ["low contrast"],
    # Speed / Precision
    "speed_fast": ["fast", "speed fast", "quick"],
    "precision_high": ["precision", "precision high", "accurate", "high precision"],
}


def _tokenize(text):
    """Lowercase and split text into word tokens, stripping punctuation."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _resolve_preset_id(text, effect_presets=None):
    """
    Resolve a natural-language preset description to an exact preset ID.

    Args:
        text: User-provided preset string (exact ID or natural language).
        effect_presets: Optional dict from the effect's _presets attribute.
            Keys are preset IDs, values are dicts with 'name' and 'description'.
            When provided, the GUI preset names are also used for matching.

    Returns (preset_id, None) on success, or (None, error_message) on failure.
    """
    if not text:
        return None, None  # No preset requested

    stripped = text.strip()

    # 1. Exact match against known IDs
    if stripped in PRESET_IDS:
        return stripped, None

    # 2. Case-insensitive exact match (e.g. "CT_Bone" -> "ct_bone")
    lower = stripped.lower()
    for pid in PRESET_IDS:
        if lower == pid:
            return pid, None

    # 3. Match against GUI preset names (exact, case-insensitive)
    if effect_presets:
        for pid, preset_info in effect_presets.items():
            name = preset_info.get("name", "")
            if name and lower == name.lower():
                return pid, None

    # 4. Fuzzy match via word overlap with keyword aliases + GUI names
    input_tokens = _tokenize(stripped)
    if not input_tokens:
        return None, f"Could not parse preset: '{text}'. Available: {PRESET_IDS}"

    best_id = None
    best_score = 0

    # Build combined aliases: static keywords + GUI names/descriptions
    combined = {}
    for pid, aliases in _PRESET_KEYWORDS.items():
        combined[pid] = list(aliases)
    if effect_presets:
        for pid, preset_info in effect_presets.items():
            if pid not in combined:
                combined[pid] = []
            name = preset_info.get("name", "")
            desc = preset_info.get("description", "")
            if name:
                combined[pid].append(name)
            if desc:
                combined[pid].append(desc)

    for pid, aliases in combined.items():
        for alias in aliases:
            alias_tokens = _tokenize(alias)
            overlap = len(input_tokens & alias_tokens)
            # Score: overlap normalized by alias length (prefer specific matches)
            if alias_tokens:
                score = overlap / len(alias_tokens)
                # Bonus if all alias tokens are present in input
                if alias_tokens <= input_tokens:
                    score += 1.0
                if score > best_score:
                    best_score = score
                    best_id = pid

    if best_id and best_score >= 0.5:
        return best_id, None

    return None, (
        f"Could not match preset '{text}'. "
        f"Available presets: {PRESET_IDS}"
    )


# ---------------------------------------------------------------------------
# Input Schemas
# ---------------------------------------------------------------------------

class _ActivateInput(BaseModel):
    """Input schema for activating the adaptive brush."""
    segmentation_node_name: str = Field(
        description="Name of the segmentation node"
    )
    segment_name: str = Field(
        description="Name of the segment to edit"
    )
    preset_id: Optional[str] = Field(
        default=None,
        description=(
            "Preset to configure the brush for the target anatomy. "
            "Accepts exact IDs (e.g. 'ct_bone', 'mri_t1gd_tumor') or "
            "natural language descriptions (e.g. 'MRI T1+GD enhancing tumor', "
            "'bone CT', 'brain gray matter MRI'). "
            "Use 'default' if modality/anatomy is unknown."
        )
    )


class _ApplyPresetInput(BaseModel):
    """Input schema for applying a parameter preset."""
    preset_id: str = Field(
        description=(
            "Preset to apply. Accepts exact IDs or natural language descriptions.\n"
            "CT: ct_bone, ct_soft_tissue, ct_lung, ct_airway, ct_vessel_contrast, "
            "ct_muscle, ct_fat, ct_lymph_node\n"
            "MRI T1: mri_t1_brain_gm, mri_t1_brain_wm, mri_t1_fat, mri_t1_muscle\n"
            "MRI T1+Gd: mri_t1gd_tumor, mri_t1gd_vessel\n"
            "MRI T2/FLAIR: mri_t2_lesion, mri_flair_lesion, mri_t2_csf\n"
            "MRI DWI: mri_dwi_stroke\n"
            "PET: pet_tumor, pet_suv_threshold\n"
            "Ultrasound: us_general, us_cyst\n"
            "CBCT: cbct_bone\n"
            "Microscopy: micro_cell, micro_nucleus\n"
            "Generic: generic_tumor, generic_vessel, generic_organ, generic_lesion, "
            "generic_high_contrast, generic_low_contrast\n"
            "Speed/Precision: speed_fast, precision_high\n"
            "Default: default\n"
            "Or use natural language like 'MRI T1+GD enhancing tumor', 'bone CT'."
        )
    )


class _SetAlgorithmInput(BaseModel):
    """Input schema for setting the segmentation algorithm."""
    algorithm: Literal[
        "watershed", "geodesic_distance", "random_walker",
        "gradient_region_growing", "level_set", "connected_threshold",
        "region_growing", "threshold_brush",
    ] = Field(
        description=(
            "Algorithm to use. "
            "'geodesic_distance' - recommended, good boundary following. "
            "'watershed' - robust general-purpose. "
            "'random_walker' - smooth boundaries (needs scikit-image). "
            "'gradient_region_growing' - gradient-based growing. "
            "'level_set' - iterative contour evolution. "
            "'connected_threshold' - fast threshold-based. "
            "'region_growing' - classic region growing. "
            "'threshold_brush' - simple threshold painting."
        )
    )


class _SetBrushRadiusInput(BaseModel):
    """Input schema for setting brush radius."""
    radius_mm: float = Field(
        description="Brush radius in millimeters (1.0-100.0)",
        ge=1.0,
        le=100.0,
    )


class _SetEdgeSensitivityInput(BaseModel):
    """Input schema for setting edge sensitivity."""
    sensitivity: int = Field(
        description=(
            "Edge sensitivity (0-100). Higher values make the brush follow "
            "edges more strongly. Lower values allow more uniform filling."
        ),
        ge=0,
        le=100,
    )


class _SetThresholdZoneInput(BaseModel):
    """Input schema for setting threshold zone size."""
    threshold_zone: int = Field(
        description=(
            "Threshold zone size as percentage of brush radius (10-100). "
            "Intensities are sampled from this inner zone to compute "
            "thresholds. Larger values = more robust, smaller = more precise."
        ),
        ge=10,
        le=100,
    )


class _SetSphereModeInput(BaseModel):
    """Input schema for setting sphere (3D) brush mode."""
    enabled: bool = Field(
        description=(
            "Enable 3D sphere mode. When True, the brush paints in a 3D "
            "spherical volume instead of a 2D circle on the current slice. "
            "Essential for volumetric segmentation workflows."
        )
    )


class _SetEraseModeInput(BaseModel):
    """Input schema for setting erase mode."""
    erase: bool = Field(
        description=(
            "Set to True to erase from the segment, False to add to it."
        )
    )


class _PaintAtPositionInput(BaseModel):
    """Input schema for painting at a specific RAS position."""
    r: float = Field(description="Right coordinate in mm (RAS)")
    a: float = Field(description="Anterior coordinate in mm (RAS)")
    s: float = Field(description="Superior coordinate in mm (RAS)")
    erase: bool = Field(
        default=False,
        description="If True, erase instead of paint at the position",
    )


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------

class SlicerAdaptiveBrush():
    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn

        # Load Slicer-side batch helpers (registered as
        # SlicerAdaptiveBrush_<name> on the RPyC service).
        self.talk2view_core.root.load_connector_helpers("SlicerAdaptiveBrush")

        self.tools = [
            tool(self.activate_adaptive_brush,
                 args_schema=_ActivateInput),
            tool(self.apply_preset,
                 args_schema=_ApplyPresetInput),
            tool(self.list_presets),
            tool(self.set_brush_radius,
                 args_schema=_SetBrushRadiusInput),
            tool(self.set_algorithm,
                 args_schema=_SetAlgorithmInput),
            tool(self.set_edge_sensitivity,
                 args_schema=_SetEdgeSensitivityInput),
            tool(self.set_threshold_zone,
                 args_schema=_SetThresholdZoneInput),
            tool(self.get_adaptive_brush_status),
            tool(self.set_sphere_mode,
                 args_schema=_SetSphereModeInput),
            tool(self.set_erase_mode,
                 args_schema=_SetEraseModeInput),
            tool(self.paint_at_position,
                 args_schema=_PaintAtPositionInput),
        ]
        self.tool_node = ToolNode(self.tools)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def activate_adaptive_brush(
        self, segmentation_node_name: str, segment_name: str,
        preset_id: str = None
    ) -> str:
        """
        Activate the Adaptive Brush for interactive segmentation.

        Use when the user wants to:
        - Segment anatomy using the adaptive brush
        - Start painting with intelligent edge-following
        - Use AI-recommended brush settings for a specific tissue type

        Sets up the segment editor, selects the segment, and activates the
        Adaptive Brush effect. The brush stays active for the user to paint
        interactively in slice views.

        If you can determine the imaging modality and target anatomy, provide
        a preset_id to configure the brush optimally. Examples:
        - Brain tumor in MRI -> 'mri_t1gd_tumor' or 'generic_tumor'
        - Bone in CT -> 'ct_bone'
        - Lung in CT -> 'ct_lung'
        - Soft tissue in CT -> 'ct_soft_tissue'

        After activation, you can further adjust parameters with set_algorithm,
        set_brush_radius, set_edge_sensitivity, set_threshold_zone,
        set_sphere_mode, etc.

        Args:
            segmentation_node_name: Name of the segmentation node.
            segment_name: Name of the segment to edit.
            preset_id: Preset for imaging modality and anatomy if known (e.g. 'ct_bone', 'generic_tumor').

        Returns:
            str: Status message.
        """
        tic = time.time()

        # Resolve preset locally (static matching, no RPyC needed)
        resolved_id = None
        if preset_id:
            resolved_id, err = _resolve_preset_id(preset_id)
            if err:
                # Static matching failed; try with effect presets from Slicer
                presets_result = self.talk2view_core.root.SlicerAdaptiveBrush_get_effect_presets()
                if "error" not in presets_result:
                    resolved_id, err = _resolve_preset_id(
                        preset_id, presets_result.get("presets")
                    )
                if err:
                    return f"Error: {err}"

        # Single RPyC call for all setup + activation
        result = self.talk2view_core.root.SlicerAdaptiveBrush_activate_brush(
            segmentation_node_name, segment_name, resolved_id
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"activate_adaptive_brush executed in {toc - tic:.4f} seconds"
        )

        preset_msg = ""
        if resolved_id:
            preset_msg = (
                f" Preset '{resolved_id}' applied"
                f" (algorithm={params['algorithm']},"
                f" radius={params['radiusMm']}mm,"
                f" sensitivity={params['edgeSensitivity']},"
                f" threshold={params['thresholdZone']})."
            )
            if resolved_id != preset_id:
                preset_msg += f" (matched from '{preset_id}')"

        return (
            f"Activated Adaptive Brush on segment '{segment_name}'.{preset_msg}"
            " You can now paint in the slice views."
        )

    def apply_preset(self, preset_id: str) -> str:
        """
        Apply a parameter preset to configure the Adaptive Brush for a
        specific imaging modality and anatomy.

        Use when the user says:
        - "I need to segment a tumor in this CT" -> apply ct_soft_tissue or generic_tumor
        - "Set up the brush for bone segmentation" -> apply ct_bone
        - "Configure for lung CT" -> apply ct_lung
        - "I'm working with brain MRI" -> apply mri_t1_brain_gm

        This is the highest-value tool: a single call configures algorithm,
        edge sensitivity, threshold zone, sampling method, and all advanced
        parameters for optimal results on the target anatomy.

        Args:
            preset_id: Preset identifier (see schema for full list).

        Returns:
            str: Confirmation with preset details.
        """
        tic = time.time()

        # Resolve preset locally first
        resolved_id, err = _resolve_preset_id(preset_id)
        if err:
            # Static matching failed; try with effect presets from Slicer
            presets_result = self.talk2view_core.root.SlicerAdaptiveBrush_get_effect_presets()
            if "error" in presets_result:
                return f"Error: {presets_result['error']}"
            resolved_id, err = _resolve_preset_id(
                preset_id, presets_result.get("presets")
            )
            if err:
                return f"Error: {err}"
        if not resolved_id:
            return "Error: No preset specified."

        # Single RPyC call
        result = self.talk2view_core.root.SlicerAdaptiveBrush_apply_preset(resolved_id)
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"[AdaptiveBrush] apply_preset: '{resolved_id}' "
            f"(from '{preset_id}'): "
            f"algorithm={params['algorithm']}, "
            f"radius={params['radiusMm']}mm, "
            f"sensitivity={params['edgeSensitivity']}, "
            f"threshold={params['thresholdZone']} "
            f"in {toc - tic:.4f}s"
        )
        msg = (
            f"Applied preset '{resolved_id}' to Adaptive Brush"
            f" (algorithm={params['algorithm']},"
            f" radius={params['radiusMm']}mm,"
            f" sensitivity={params['edgeSensitivity']},"
            f" threshold={params['thresholdZone']})."
        )
        if resolved_id != preset_id:
            msg += f" (matched from '{preset_id}')"
        return msg

    def list_presets(self) -> str:
        """
        List all available Adaptive Brush presets with descriptions.

        Use when the user asks:
        - "What presets are available?"
        - "What brush settings can you configure?"
        - "Show me the adaptive brush options"

        Returns:
            str: Formatted list of presets grouped by category.
        """
        tic = time.time()

        # Single RPyC call
        result = self.talk2view_core.root.SlicerAdaptiveBrush_list_presets()
        if "error" in result:
            return f"Error: {result['error']}"

        presets = result["presets"]
        lines = ["Available Adaptive Brush Presets:", ""]

        # Group presets by category prefix
        categories = {}
        for pid, preset in presets.items():
            if pid == "default":
                cat = "General"
            elif pid.startswith("ct_"):
                cat = "CT"
            elif pid.startswith("mri_t1gd_"):
                cat = "MRI T1+Gd (Contrast)"
            elif pid.startswith("mri_t1_"):
                cat = "MRI T1"
            elif pid.startswith("mri_t2_") or pid.startswith("mri_flair_"):
                cat = "MRI T2/FLAIR"
            elif pid.startswith("mri_dwi_"):
                cat = "MRI DWI"
            elif pid.startswith("pet_"):
                cat = "PET"
            elif pid.startswith("us_"):
                cat = "Ultrasound"
            elif pid.startswith("cbct_"):
                cat = "CBCT"
            elif pid.startswith("micro_"):
                cat = "Microscopy"
            elif pid.startswith("generic_"):
                cat = "Generic"
            elif pid.startswith("speed_") or pid.startswith("precision_"):
                cat = "Speed / Precision"
            else:
                cat = "Other"

            if cat not in categories:
                categories[cat] = []
            name = preset.get("name", pid)
            desc = preset.get("description", "")
            categories[cat].append(f"  - {pid}: {name} -- {desc}")

        for cat_name, entries in categories.items():
            lines.append(f"[{cat_name}]")
            lines.extend(entries)
            lines.append("")

        toc = time.time()
        logging.info(f"list_presets executed in {toc - tic:.4f} seconds")
        return "\n".join(lines)

    def set_brush_radius(self, radius_mm: float) -> str:
        """
        Set the Adaptive Brush radius.

        Use when the user says:
        - "Make the brush bigger/smaller"
        - "Set brush size to 10mm"
        - "I need a larger brush for this structure"

        Args:
            radius_mm: Brush radius in millimeters (1.0-100.0).

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_param(
            "radiusMm", radius_mm
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"[AdaptiveBrush] set_brush_radius: {radius_mm}mm "
            f"in {toc - tic:.4f}s"
        )
        msg = f"Brush radius set to {radius_mm} mm."
        if params['radiusMm'] is not None and params['radiusMm'] != radius_mm:
            msg += f" WARNING: read-back value is {params['radiusMm']} mm."
        return msg

    def set_algorithm(self, algorithm: str) -> str:
        """
        Set the segmentation algorithm used by the Adaptive Brush.

        Use when the user says:
        - "Use watershed algorithm"
        - "Switch to geodesic distance"
        - "Try a different algorithm"

        Args:
            algorithm: Algorithm identifier.

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_param(
            "algorithm", algorithm
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"[AdaptiveBrush] set_algorithm: {algorithm} "
            f"in {toc - tic:.4f}s"
        )
        msg = f"Algorithm set to '{algorithm}'."
        if params['algorithm'] is not None and params['algorithm'] != algorithm:
            msg += f" WARNING: read-back value is '{params['algorithm']}'."
        return msg

    def set_edge_sensitivity(self, sensitivity: int) -> str:
        """
        Set edge sensitivity for the Adaptive Brush.

        Use when the user says:
        - "Make the brush follow edges more"
        - "The brush is leaking past boundaries"
        - "Increase/decrease edge sensitivity"

        Higher values make the brush respect edges more strongly.
        Lower values allow more uniform filling.

        Args:
            sensitivity: Edge sensitivity value (0-100).

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_param(
            "edgeSensitivity", sensitivity
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"[AdaptiveBrush] set_edge_sensitivity: {sensitivity} "
            f"in {toc - tic:.4f}s"
        )
        msg = f"Edge sensitivity set to {sensitivity}."
        if params['edgeSensitivity'] is not None and params['edgeSensitivity'] != sensitivity:
            msg += f" WARNING: read-back value is {params['edgeSensitivity']}."
        return msg

    def set_threshold_zone(self, threshold_zone: int) -> str:
        """
        Set the threshold zone size for the Adaptive Brush.

        The threshold zone is the inner portion of the brush (as a percentage
        of brush radius) from which intensities are sampled to compute
        adaptive thresholds. Particularly important for the threshold_brush
        algorithm.

        Args:
            threshold_zone: Zone size as percentage of brush radius (10-100).

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_param(
            "thresholdZone", threshold_zone
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result["params"]
        toc = time.time()
        logging.info(
            f"[AdaptiveBrush] set_threshold_zone: {threshold_zone} "
            f"in {toc - tic:.4f}s"
        )
        msg = f"Threshold zone set to {threshold_zone}%."
        if params['thresholdZone'] is not None and params['thresholdZone'] != threshold_zone:
            msg += f" WARNING: read-back value is {params['thresholdZone']}%."
        return msg

    def get_adaptive_brush_status(self) -> str:
        """
        Get the current status and parameters of the Adaptive Brush.

        Use when the user asks:
        - "What are the current brush settings?"
        - "Show me the adaptive brush status"
        - "What algorithm is active?"

        Returns:
            str: Current parameter summary.
        """
        tic = time.time()

        # Single RPyC call
        result = self.talk2view_core.root.SlicerAdaptiveBrush_get_status()
        if not result.get("active"):
            return (
                "Error: Adaptive Brush is not active. "
                "Use activate_adaptive_brush first."
            )

        params = result["params"]
        lines = [
            "Adaptive Brush Status:",
            f"  Algorithm: {params.get('algorithm', 'unknown')}",
            f"  Brush radius: {params.get('radiusMm', 'unknown')} mm",
            f"  Edge sensitivity: {params.get('edgeSensitivity', 'unknown')}",
            f"  Threshold zone: {params.get('thresholdZone', 'unknown')}",
            f"  Sphere (3D) mode: {params.get('sphereMode', 'unknown')}",
            f"  Erase mode: {params.get('eraseMode', 'unknown')}",
            f"  Sampling method: {params.get('samplingMethod', 'unknown')}",
        ]

        toc = time.time()
        logging.info(
            f"get_adaptive_brush_status executed in {toc - tic:.4f} seconds"
        )
        return "\n".join(lines)

    def set_sphere_mode(self, enabled: bool) -> str:
        """
        Enable or disable 3D sphere brush mode.

        Use when the user says:
        - "Enable 3D brush mode"
        - "Paint in 3D"
        - "Switch to volumetric painting"
        - "Turn off sphere mode"

        When enabled, the brush paints in a 3D spherical volume instead of a
        2D circle on the current slice. Essential for volumetric segmentation.

        Args:
            enabled: True to enable sphere mode, False to disable.

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_sphere_mode(enabled)
        if "error" in result:
            return f"Error: {result['error']}"

        toc = time.time()
        logging.info(f"set_sphere_mode executed in {toc - tic:.4f} seconds")
        state = "enabled" if enabled else "disabled"
        return f"Sphere (3D) brush mode {state}."

    def set_erase_mode(self, erase: bool) -> str:
        """
        Toggle between paint (add) and erase mode.

        Use when the user says:
        - "Switch to erase mode"
        - "I need to remove some of the segmentation"
        - "Go back to paint mode"

        Args:
            erase: True to erase, False to paint/add.

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        result = self.talk2view_core.root.SlicerAdaptiveBrush_set_erase_mode(erase)
        if "error" in result:
            return f"Error: {result['error']}"

        toc = time.time()
        logging.info(f"set_erase_mode executed in {toc - tic:.4f} seconds")
        mode = "erase" if erase else "paint"
        return f"Brush mode set to {mode}."

    def paint_at_position(
        self, r: float, a: float, s: float, erase: bool = False
    ) -> str:
        """
        Apply a brush stroke at a specific RAS coordinate.

        IMPORTANT: activate_adaptive_brush must be called first to set up
        the segment editor context (segmentation node, segment, source
        volume). The brush uses whatever parameters are currently set
        (algorithm, radius, sensitivity). Use apply_preset or individual
        setters to configure before painting.

        Use when the user says:
        - "Paint at this location" (with known coordinates)
        - "Segment at coordinates R=10, A=20, S=30"
        - For automated workflows that paint at computed positions

        Args:
            r: Right coordinate in mm.
            a: Anterior coordinate in mm.
            s: Superior coordinate in mm.
            erase: If True, erase instead of paint.

        Returns:
            str: Confirmation message.
        """
        tic = time.time()

        # Single RPyC call handles processEvents + voxel counting
        result = self.talk2view_core.root.SlicerAdaptiveBrush_paint_at(
            r, a, s, erase
        )
        if "error" in result:
            return f"Error: {result['error']}"

        params = result.get("params", {})
        voxel_diff = result.get("voxel_diff")

        toc = time.time()
        logging.info(
            f"paint_at_position executed in {toc - tic:.4f} seconds"
        )

        action = "Erased" if erase else "Painted"
        if voxel_diff is not None and voxel_diff == 0:
            return (
                f"WARNING: {action} at RAS ({r:.1f}, {a:.1f}, {s:.1f}) "
                f"but no voxels were modified. "
                f"Current params: algorithm={params.get('algorithm')}, "
                f"radius={params.get('radiusMm')}mm, "
                f"sensitivity={params.get('edgeSensitivity')}, "
                f"threshold={params.get('thresholdZone')}."
            )
        elif voxel_diff is not None:
            return (
                f"{action} at RAS ({r:.1f}, {a:.1f}, {s:.1f}). "
                f"{abs(voxel_diff)} voxels modified."
            )
        return f"{action} at RAS ({r:.1f}, {a:.1f}, {s:.1f})."
