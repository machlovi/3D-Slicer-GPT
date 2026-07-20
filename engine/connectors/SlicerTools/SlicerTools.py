import time
import logging
import requests
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, List

from utils.connector_base import log_and_return_error

# Pydantic schemas for tool inputs - not to be instantiated as tools
class _ListSegmentsInput(BaseModel):
    """Input schema for listing segments in a node."""
    node_id: str = Field(description="The name/ID of the segmentation node to inspect. Use list_segmentation_nodes() first to discover node names.")

class _GetVisibleSegmentsInput(BaseModel):
    """Input schema for getting visible segments."""
    segmentation_node: str = Field(description="The node ID of the segmentation node to inspect. Use list_segmentation_nodes() first to discover node names.")

class _ShowSegmentation3dInput(BaseModel):
    """Input schema for showing a segmentation in 3D."""
    segmentation_node_name: str = Field(description="The name of the segmentation node to display in 3D")

class _ShowAllSegmentsInput(BaseModel):
    """Input schema for showing all segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node to modify")

class _HideAllSegmentsInput(BaseModel):
    """Input schema for hiding all segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node to modify")

class _ShowSpecificSegmentsInput(BaseModel):
    """Input schema for showing specific segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node to modify. Use list_segmentation_nodes() first to discover node names.")
    segment_names: List[str] = Field(description="List of segment names to show. Example: ['rib_1', 'rib_2', 'skull']")

class _HideSpecificSegmentsInput(BaseModel):
    """Input schema for hiding specific segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node to modify. Use list_segmentation_nodes() first to discover node names.")
    segment_names: List[str] = Field(description="List of segment names to hide. Example: ['rib_1', 'rib_2', 'skull']")

class _SetSegmentColorInput(BaseModel):
    """Input schema for setting segment colors."""
    segmentation_node_name: str = Field(description="The name of the segmentation node")
    segment_names: List[str] = Field(description="List of segment names to modify")
    red: float = Field(description="Red component (0.0 to 1.0). Example: 0.5 for greyscale, 1.0 for red")
    green: float = Field(description="Green component (0.0 to 1.0). Example: 0.5 for greyscale, 0.0 for red")
    blue: float = Field(description="Blue component (0.0 to 1.0). Example: 0.5 for greyscale, 0.0 for red")

class _HighlightSegmentsInput(BaseModel):
    """Input schema for highlighting segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node. Use get_data_context() first to discover node names.")
    segment_names: List[str] = Field(description="List of segment names to highlight (make opaque). Example: ['skull', 'brain']")
    background_opacity: float = Field(description="Opacity for other visible segments (0.0 to 1.0). Typically 0.1 for very transparent background. Example: 0.1")

class _RenameSegmentsInput(BaseModel):
    """Input schema for renaming segments."""
    segmentation_node_name: str = Field(description="The name of the segmentation node")
    rename_map: List[List[str]] = Field(description="List of [old_name, new_name] pairs. Example: [['rib_1', 'costilla_1'], ['rib_2', 'costilla_2']]")

class _SetOpacityInput(BaseModel):
    """Input schema for setting opacity."""
    target_name: str = Field(description="Name of the visible volume, model, or segmentation node")
    opacity: float = Field(description="Transparency from 0.0 to 1.0. Lower = more transparent. Example: 0.2 for very transparent, 0.5 for semi-transparent, 0.8 for mostly solid")
    segment_names: List[str] = Field(description="For segmentations - list of specific segment names to modify. Pass empty list [] to apply to all segments. Example: [] for all, or ['rib_1', 'rib_2'] for specific")

class _MeasureSegmentsVolumeInput(BaseModel):
    """Input schema for measuring segment volumes."""
    segmentation_node_name: str = Field(description="The name of the segmentation node containing segments to measure. Use list_segmentation_nodes() first to discover node names.")
    specific_segments: List[str] = Field(description="List of specific segment names to measure. Use list_segments() first to discover segment names. Example: ['skull', 'brain', 'vertebra_C1']")

class _CompareSegmentsInput(BaseModel):
    """Input schema for comparing two segments via Dice and Hausdorff metrics."""
    reference_segmentation_node_name: str = Field(description="Name of the reference (ground truth) segmentation node. Use list_segmentation_nodes() to discover names.")
    reference_segment_name: str = Field(description="Name of the segment in the reference segmentation. Use list_segments() to discover names.")
    compare_segmentation_node_name: str = Field(description="Name of the segmentation node to compare against the reference (e.g. an automated or agentic result).")
    compare_segment_name: str = Field(description="Name of the segment in the compare segmentation.")

class _JumpToSegmentInput(BaseModel):
    """Input schema for jumping to segment."""
    node_name: str = Field(description="Name of the segmentation node containing the segment. Use list_segmentation_nodes() first to discover node names.")
    segment_names: List[str] = Field(description="List of segment names to jump to. If multiple segments provided, jumps to combined center. Example: ['skull']")

class _JumpToPositionInput(BaseModel):
    """Input schema for jumping to an RAS position."""
    r: float = Field(description="Right coordinate in RAS space (mm)")
    a: float = Field(description="Anterior coordinate in RAS space (mm)")
    s: float = Field(description="Superior coordinate in RAS space (mm)")

class _SetModelVisibilityInput(BaseModel):
    """Input schema for setting model visibility."""
    model_names: List[str] = Field(description="List of model node names to show or hide. Use get_data_context() first to discover model names.")
    visible: bool = Field(description="True to show the models, False to hide them")

class _SetModelOpacityInput(BaseModel):
    """Input schema for setting model opacity."""
    model_names: List[str] = Field(description="List of model node names to modify. Use get_data_context() first to discover model names.")
    opacity: float = Field(description="Opacity value from 0.0 to 1.0. Lower = more transparent. Example: 0.2 for very transparent, 0.5 for semi-transparent, 0.8 for mostly solid")

class _SetModelColorInput(BaseModel):
    """Input schema for setting model colors."""
    model_names: List[str] = Field(description="List of model node names to modify")
    red: float = Field(description="Red component (0.0 to 1.0). Example: 0.5 for greyscale, 1.0 for red")
    green: float = Field(description="Green component (0.0 to 1.0). Example: 0.5 for greyscale, 0.0 for red")
    blue: float = Field(description="Blue component (0.0 to 1.0). Example: 0.5 for greyscale, 0.0 for red")

class _HighlightModelsInput(BaseModel):
    """Input schema for highlighting models."""
    model_names: List[str] = Field(description="List of model names to highlight (make opaque). Use get_data_context() first to discover model names.")
    background_opacity: float = Field(description="Opacity for other visible models (0.0 to 1.0). Typically 0.1 for very transparent background. Example: 0.1")

class _SetModelSliceVisibilityInput(BaseModel):
    """Input schema for showing or hiding model intersections in 2D slice views."""
    model_names: List[str] = Field(description="List of model node names to modify. Use get_data_context() first to discover model names.")
    visible: bool = Field(description="True to show colored model outlines on 2D slice views, False to hide them. Independent of 3D visibility (set_model_visibility).")

class _SetModelRepresentationInput(BaseModel):
    """Input schema for setting the 3D rendering representation of model nodes."""
    model_names: List[str] = Field(description="List of model node names to modify. Use get_data_context() first to discover model names.")
    representation: str = Field(description="Rendering style. One of: 'surface' (filled, the Slicer default), 'wireframe' (triangle edges only), 'points' (vertices only).")
    show_edges: bool = Field(default=False, description="If True, overlay triangle edges on top of the surface. Only meaningful with representation='surface'; produces the 'Surface with edges' look.")

class _GetDocsInput(BaseModel):
    """Input schema for getting 3D Slicer documentation."""
    query: str = Field(description="The topic to search for in 3D Slicer documentation. Example: 'segmentation', 'volume rendering', 'DICOM'")

class _RotateToViewAxisInput(BaseModel):
    """Input schema for rotating the 3D view to a specific axis."""
    axis: int = Field(description="The axis to rotate to. Valid values: 0 (-X, Right), 1 (+X, Left), 2 (-Y, Posterior), 3 (+Y, Anterior), 4 (-Z, Inferior), 5 (+Z, Superior)")

class _SetWindowLevelInput(BaseModel):
    """Input schema for setting window/level on a volume."""
    volume_name: str = Field(description="Name of the volume node to adjust. Use empty string for the first available volume.")
    window: float = Field(description="Window width (contrast). Larger values = lower contrast. Typical CT: 400 (soft tissue), 1500 (bone), 1800 (lung)")
    level: float = Field(description="Window center (brightness). Typical CT: 40 (soft tissue), 300 (bone), -500 (lung)")

class _SetWindowLevelPresetInput(BaseModel):
    """Input schema for setting window/level using a preset."""
    volume_name: str = Field(description="Name of the volume node to adjust. Use empty string for the first available volume.")
    preset: str = Field(description="Preset name: 'ct_soft_tissue', 'ct_bone', 'ct_lung', 'ct_brain', 'ct_liver', 'ct_abdomen', 'mri_t1', 'mri_t2', 'auto'")

class _ResetWindowLevelInput(BaseModel):
    """Input schema for resetting window/level to automatic."""
    volume_name: str = Field(description="Name of the volume node to reset. Use empty string for the first available volume.")

class _WindowLevelToolActivateInput(BaseModel):
    """Input schema for activating window/level mouse tool."""
    model_config = ConfigDict(extra="forbid")

class _WindowLevelToolDeactivateInput(BaseModel):
    """Input schema for deactivating window/level mouse tool."""
    model_config = ConfigDict(extra="forbid")


# Segment Editor Effect Input Models

class _SegmentEditorActivateInput(BaseModel):
    """Input schema for activating an interactive segment editor effect."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to edit")
    effect_name: str = Field(description="Effect to activate: 'paint', 'draw', 'erase', 'scissors', 'level_tracing'")
    brush_size_mm: float = Field(default=3.0, description="Brush size in mm (for paint/erase effects)")

class _SegmentEditorDeactivateInput(BaseModel):
    """Input schema for deactivating the segment editor effect."""
    model_config = ConfigDict(extra="forbid")

class _SegmentEditorUndoInput(BaseModel):
    """Input schema for undoing the last segment editor operation."""
    model_config = ConfigDict(extra="forbid")

class _SegmentEditorRedoInput(BaseModel):
    """Input schema for redoing the last undone segment editor operation."""
    model_config = ConfigDict(extra="forbid")

class _SegmentBooleanOperationInput(BaseModel):
    """Input schema for boolean operations between segments."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    target_segment_name: str = Field(description="Name of the segment to modify")
    modifier_segment_name: str = Field(description="Name of the segment to use as modifier")
    operation: str = Field(description="Operation: 'add' (union), 'subtract', 'intersect', 'copy'")

class _SegmentMarginInput(BaseModel):
    """Input schema for growing or shrinking a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to modify")
    margin_mm: float = Field(description="Margin in mm. Positive=grow, negative=shrink")

class _SegmentIslandsInput(BaseModel):
    """Input schema for island operations on a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to modify")
    operation: str = Field(description="Operation: 'keep_largest', 'remove_small', 'split_islands'")
    minimum_size_voxels: int = Field(default=1000, description="Minimum island size in voxels (for remove_small)")

class _SegmentSmoothingInput(BaseModel):
    """Input schema for smoothing a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to smooth")
    method: str = Field(description="Method: 'median', 'gaussian', 'opening', 'closing'")
    kernel_size_mm: float = Field(default=3.0, description="Kernel size in mm")

class _SegmentHollowInput(BaseModel):
    """Input schema for creating a hollow segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to hollow")
    shell_thickness_mm: float = Field(description="Shell thickness in mm")
    shell_mode: str = Field(default="inside", description="Shell mode: 'inside', 'medial', or 'outside'")

class _SegmentThresholdInput(BaseModel):
    """Input schema for applying threshold to create/modify a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to modify")
    volume_node_name: str = Field(description="Name of the source volume node for intensity values")
    lower_threshold: float = Field(description="Lower intensity threshold")
    upper_threshold: float = Field(description="Upper intensity threshold")

class _SegmentInvertInput(BaseModel):
    """Input schema for inverting a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to invert")

class _SegmentClearInput(BaseModel):
    """Input schema for clearing a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment to clear")

class _SegmentFillHolesInput(BaseModel):
    """Input schema for filling holes in a segment."""
    segmentation_node_name: str = Field(description="Name of the segmentation node")
    segment_name: str = Field(description="Name of the segment")
    hole_size_mm: float = Field(default=3.0, description="Maximum hole size to fill in mm")

class _CreateSegmentationInput(BaseModel):
    """Input schema for creating a new segmentation node with a segment."""
    segmentation_name: str = Field(description="Name for the new segmentation node (e.g., 'Segmentation')")
    segment_name: str = Field(description="Name for the initial segment (e.g., 'Liver', 'Tumor')")
    reference_volume_name: str = Field(description="Name of a volume node to use as geometry reference, or empty string to use first available volume")
    color_red: float = Field(default=-1.0, description="Red component (0.0-1.0) for segment color, or -1 for auto color")
    color_green: float = Field(default=-1.0, description="Green component (0.0-1.0) for segment color, or -1 for auto color")
    color_blue: float = Field(default=-1.0, description="Blue component (0.0-1.0) for segment color, or -1 for auto color")

class _AddSegmentInput(BaseModel):
    """Input schema for adding a new segment to an existing segmentation."""
    segmentation_node_name: str = Field(description="Name of the existing segmentation node")
    segment_name: str = Field(description="Name for the new segment (e.g., 'Liver', 'Spine')")
    color_red: float = Field(default=-1.0, description="Red component (0.0-1.0), or -1 for auto color")
    color_green: float = Field(default=-1.0, description="Green component (0.0-1.0), or -1 for auto color")
    color_blue: float = Field(default=-1.0, description="Blue component (0.0-1.0), or -1 for auto color")

class _SelectSegmentInput(BaseModel):
    """Input schema for selecting the active segment in the Segment Editor."""
    segmentation_node_name: str = Field(description="Name of the segmentation node containing the segment")
    segment_name: str = Field(description="Name of the segment to make active (e.g., 'Tumor', 'Ventricle')")

class _ConvertLabelmapToSegmentationInput(BaseModel):
    """Input schema for converting a labelmap volume node to a segmentation node."""
    labelmap_node_name: str = Field(description="Name of an existing vtkMRMLLabelMapVolumeNode in the scene. Each unique non-zero label value becomes a separate segment.")
    segmentation_name: str = Field(default="", description="Name for the new segmentation node. If empty, defaults to '<labelmap_name>-segmentation'.")

class _ImportDicomDirectoryInput(BaseModel):
    """Input schema for indexing a DICOM directory into Slicer's database."""
    dicom_directory: str = Field(description="Absolute path to a directory containing DICOM files (e.g., '/tmp/brain_mri'). Files are indexed but NOT loaded into the scene.")

class _LoadDicomPatientInput(BaseModel):
    """Input schema for loading a patient from the DICOM database."""
    patient_name: str = Field(default="", description="Patient name as shown by query_dicom_database (e.g., 'UPENN-GBM-00001', 'BRAIN^TUMOR^001'). ALWAYS call query_dicom_database first to verify the exact name. Leave empty if using patient_uid.")
    patient_uid: str = Field(default="", description="Internal DICOM database patient UID. Use query_dicom_database to discover. Leave empty if using patient_name.")

class _LoadDicomStudyInput(BaseModel):
    """Input schema for loading a study from the DICOM database."""
    study_uid: str = Field(description="StudyInstanceUID as shown by query_dicom_database.")

class _LoadDicomSeriesInput(BaseModel):
    """Input schema for loading a series from the DICOM database."""
    series_uid: str = Field(description="SeriesInstanceUID as shown by query_dicom_database.")

class _ExportSegmentationToModelsInput(BaseModel):
    """Input schema for exporting segmentation segments as model nodes."""
    segmentation_node_name: str = Field(description="Name of the segmentation node to export")

class _DeleteNodeInput(BaseModel):
    """Input schema for deleting a node from the scene."""
    node_name: str = Field(description="Name of the node to delete")

class _ShowSlicesIn3dInput(BaseModel):
    """Input schema for showing/hiding slice planes in 3D view."""
    visible: bool = Field(default=True, description="True to show slices in 3D, False to hide them")

class _LoadFileInput(BaseModel):
    """Input schema for loading a file into the scene."""
    file_path: str = Field(description="Absolute path to the file to load (e.g., '/tmp/model.stl', '/data/scan.nrrd')")
    node_name: str = Field(default="", description="Optional name to assign to the loaded node. Leave empty for auto-naming.")

class _SaveFileInput(BaseModel):
    """Input schema for saving a node to a file."""
    node_name: str = Field(description="Name of the node to save. Use get_data_context() to discover node names.")
    file_path: str = Field(description="Absolute path where to save the file (e.g., '/tmp/output.stl')")

class _ApplyTransformInput(BaseModel):
    """Input schema for applying a transform to a node."""
    node_name: str = Field(description="Name of the node to transform (model, volume, segmentation, etc.)")
    transform_name: str = Field(description="Name of the transform node to apply")

class _CreateTransformInput(BaseModel):
    """Input schema for creating a new linear transform."""
    name: str = Field(description="Name for the new transform node")
    translation: list = Field(default=None, description="[x, y, z] translation in mm, or null for no translation")
    rotation: list = Field(default=None, description="[rx, ry, rz] rotation in degrees, or null for no rotation")


# Constants for documentation tool
_CONTEXT7_KEY_URL = "https://db.talk2view.com/functions/v1/get_context7_api_key"
_CONTEXT7_DOCS_URL = "https://context7.com/api/v2/docs"
_LITELLM_URL = "https://t2v4-staging.talk2view.com/chat/completions"


class SlicerTools():
    def __init__(self, rpyc_conn):
        self.talk2view_core = rpyc_conn
        self.supabase_manager = None

        # Load Slicer-side helpers (registered as
        # SlicerTools_<name> on the RPyC service).
        self.talk2view_core.root.load_connector_helpers("SlicerTools")

        self.tools = [
            # Context and navigation tools
            tool(self.get_data_context),
            # tool(self.get_system_info),
            tool(self.center_view),
            tool(self.rotate_3d_view, args_schema=_RotateToViewAxisInput),
            tool(self.jump_to_segment, args_schema=_JumpToSegmentInput),
            tool(self.jump_to_position, args_schema=_JumpToPositionInput),
            # tool(self.jump_to_model),

            # Data loading and file operations
            tool(self.import_dicom_directory, args_schema=_ImportDicomDirectoryInput),
            tool(self.query_dicom_database),
            tool(self.load_dicom_patient, args_schema=_LoadDicomPatientInput),
            tool(self.load_dicom_study, args_schema=_LoadDicomStudyInput),
            tool(self.load_dicom_series, args_schema=_LoadDicomSeriesInput),
            tool(self.load_file, args_schema=_LoadFileInput),
            tool(self.save_file, args_schema=_SaveFileInput),
            tool(self.save_scene),
            tool(self.clear_scene),
            tool(self.delete_node, args_schema=_DeleteNodeInput),

            # Screenshot and image capture
            # tool(self.take_screenshot),
            # tool(self.capture_3d_view),
            # tool(self.capture_slice_view),

            # Python execution (DISABLED FOR SECURITY)
            # tool(self.execute_python),

            # Segmentation tools
            tool(self.list_segmentation_nodes),
            tool(self.list_segments, args_schema=_ListSegmentsInput),
            tool(self.get_visible_segments, args_schema=_GetVisibleSegmentsInput),
            tool(self.show_all_segments, args_schema=_ShowAllSegmentsInput),
            tool(self.hide_all_segments, args_schema=_HideAllSegmentsInput),
            tool(self.show_specific_segments, args_schema=_ShowSpecificSegmentsInput),
            tool(self.hide_specific_segments, args_schema=_HideSpecificSegmentsInput),
            tool(self.set_segment_color, args_schema=_SetSegmentColorInput),
            tool(self.highlight_segments, args_schema=_HighlightSegmentsInput),
            tool(self.rename_segments, args_schema=_RenameSegmentsInput),
            tool(self.measure_segments_volume, args_schema=_MeasureSegmentsVolumeInput),
            tool(self.compare_segments, args_schema=_CompareSegmentsInput),
            tool(self.show_segmentation_3d, args_schema=_ShowSegmentation3dInput),
            tool(self.export_segmentation_to_models, args_schema=_ExportSegmentationToModelsInput),

            # Model tools
            tool(self.get_visible_models),
            tool(self.set_model_visibility, args_schema=_SetModelVisibilityInput),
            tool(self.set_model_slice_visibility, args_schema=_SetModelSliceVisibilityInput),
            tool(self.set_model_representation, args_schema=_SetModelRepresentationInput),
            tool(self.set_model_opacity, args_schema=_SetModelOpacityInput),
            tool(self.set_model_color, args_schema=_SetModelColorInput),
            tool(self.highlight_models, args_schema=_HighlightModelsInput),

            # Volume tools
            tool(self.list_volume_nodes),
            tool(self.get_cursor_info),
            # tool(self.get_volume_info),
            # tool(self.set_volume_visibility),
            # tool(self.set_volume_opacity),
            # tool(self.set_volume_window_level),
            # tool(self.enable_volume_rendering),

            # Layout and view tools
            # tool(self.set_layout),
            # tool(self.reset_views),
            # tool(self.set_slice_offset),
            # tool(self.fit_slice_to_background),
            tool(self.show_slices_in_3d, args_schema=_ShowSlicesIn3dInput),

            # Markup and measurement tools
            # tool(self.create_markup_point),
            # tool(self.create_markup_line),
            # tool(self.get_markup_points),
            # tool(self.set_markup_visibility),

            # Transform tools
            # tool(self.get_transform_info),
            tool(self.apply_transform, args_schema=_ApplyTransformInput),
            tool(self.create_transform, args_schema=_CreateTransformInput),

            # General opacity tool
            tool(self.set_opacity, args_schema=_SetOpacityInput),

            # Window/Level tools
            tool(self.set_window_level, args_schema=_SetWindowLevelInput),
            tool(self.set_window_level_preset, args_schema=_SetWindowLevelPresetInput),
            tool(self.reset_window_level, args_schema=_ResetWindowLevelInput),
            tool(self.window_level_tool_activate, args_schema=_WindowLevelToolActivateInput),
            tool(self.window_level_tool_deactivate, args_schema=_WindowLevelToolDeactivateInput),

            # Documentation tool
            tool(self.get_docs, args_schema=_GetDocsInput),

            # Segment Editor Effect tools
            tool(self.create_segmentation, args_schema=_CreateSegmentationInput),
            tool(self.convert_labelmap_to_segmentation, args_schema=_ConvertLabelmapToSegmentationInput),
            tool(self.add_segment, args_schema=_AddSegmentInput),
            tool(self.select_segment, args_schema=_SelectSegmentInput),
            tool(self.segment_editor_activate, args_schema=_SegmentEditorActivateInput),
            tool(self.segment_editor_deactivate, args_schema=_SegmentEditorDeactivateInput),
            tool(self.segment_editor_undo, args_schema=_SegmentEditorUndoInput),
            tool(self.segment_editor_redo, args_schema=_SegmentEditorRedoInput),
            tool(self.segment_boolean_operation, args_schema=_SegmentBooleanOperationInput),
            tool(self.segment_margin, args_schema=_SegmentMarginInput),
            tool(self.segment_islands, args_schema=_SegmentIslandsInput),
            tool(self.segment_smoothing, args_schema=_SegmentSmoothingInput),
            tool(self.segment_hollow, args_schema=_SegmentHollowInput),
            tool(self.segment_threshold, args_schema=_SegmentThresholdInput),
            tool(self.segment_invert, args_schema=_SegmentInvertInput),
            tool(self.segment_clear, args_schema=_SegmentClearInput),
            tool(self.segment_fill_holes, args_schema=_SegmentFillHolesInput),
        ]

        # Mark tools that should stream raw output to user but not end the workflow.
        # Unlike return_direct, stream_to_user lets the LLM continue after the tool runs.
        stream_to_user_tools = {'measure_segments_volume', 'compare_segments', 'get_docs'}
        for t in self.tools:
            if t.name in stream_to_user_tools:
                t.metadata = {"stream_to_user": True}

        self.tool_node = ToolNode(self.tools)

    def set_supabase_manager(self, supabase_manager):
        """Set the supabase manager instance for API key access."""
        self.supabase_manager = supabase_manager

    def _get_context7_api_key(self) -> str | None:
        """
        Fetches the Context7 API key from the edge function.

        Returns:
            str: The Context7 API key, or None if unavailable.
        """
        if not self.supabase_manager:
            logging.warning("SlicerTools: supabase_manager not set")
            return None

        user_id = self.supabase_manager.get_user_id()
        lite_llm_key = self.supabase_manager.get_litellm_api_key()

        if not user_id or not lite_llm_key:
            logging.warning("SlicerTools: Missing user_id or litellm_api_key")
            return None

        try:
            response = requests.post(
                _CONTEXT7_KEY_URL,
                headers={"Content-Type": "application/json"},
                json={"user_id": user_id, "lite_llm_key": lite_llm_key},
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("context7_api_key")
            logging.warning(f"SlicerTools: Failed to get Context7 API key: {response.status_code}")
            return None
        except requests.RequestException as e:
            logging.warning(f"SlicerTools: Error fetching Context7 API key: {e}")
            return None

    def list_volume_nodes(self) -> str:
        """
        Lists all volume nodes currently loaded in the scene.

        Returns:
            str: A formatted list of volume node names and their types.
        """
        tic = time.time()

        # Get all volume nodes
        volume_nodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLScalarVolumeNode')

        if not volume_nodes:
            return "No volume nodes found in the scene."

        # Build formatted list
        volume_list = []
        for node in volume_nodes:
            node_name = node.GetName()
            node_type = "Scalar Volume"
            if node.IsA('vtkMRMLLabelMapVolumeNode'):
                node_type = "Label Map"
            volume_list.append(f"- {node_name} ({node_type})")

        toc = time.time()
        logging.info(f"list_volume_nodes executed in {toc - tic:.4f} seconds")

        return f"Available volume nodes in the scene:\n" + "\n".join(volume_list)

    def get_cursor_info(self) -> str:
        """
        Gets information about the current mouse cursor position from the Data Probe.
        Returns RAS coordinates, segment names at cursor, and volume values.

        Use this to understand what the user is pointing at in the slice views.

        Returns:
            str: Cursor position info including RAS, segments, and volume values.
        """
        tic = time.time()

        info = self.talk2view_core.root.get_data_probe_info()
        if not info:
            return "Data Probe info not available. Move cursor into a slice view."

        result_parts = []

        # View info (RAS position)
        if info.get("view_info"):
            result_parts.append(f"Position: {info['view_info']}")

        # Segments at cursor
        if info.get("segments_info"):
            result_parts.append(f"Segments: {info['segments_info']}")

        # Volume info
        layers = info.get("layers", {})
        bg = layers.get("B", {})
        if bg.get("name"):
            result_parts.append(f"Volume: {bg['name']} {bg.get('ijk', '')} Value: {bg.get('value', '')}")

        toc = time.time()
        logging.info(f"get_cursor_info executed in {toc - tic:.4f} seconds")

        return "\n".join(result_parts) if result_parts else "Cursor not in a slice view."

    def list_segmentation_nodes(self) -> str:
        """
        Lists all segmentation nodes currently loaded in the scene.

        IMPORTANT: You MUST use this tool first before working with any segmentation nodes
        to discover their actual names. Do not guess or assume node names.

        Returns:
            str: A formatted list of segmentation node names.
        """
        tic = time.time()

        # Get all segmentation nodes
        segmentation_nodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLSegmentationNode')

        if not segmentation_nodes:
            return "No segmentation nodes found in the scene."

        segmentation_list = []
        for node in segmentation_nodes:
            node_name = node.GetName()
            segment_count = node.GetSegmentation().GetNumberOfSegments()
            segmentation_list.append(f"- {node_name} ({segment_count} segments)")

        toc = time.time()
        logging.info(f"list_segmentation_nodes executed in {toc - tic:.4f} seconds")
        return f"Available segmentation nodes in the scene:\n" + "\n".join(segmentation_list)

    # def get_node_by_class(self, class_name: str):
    #     """
    #     Return all nodes in the scene of the specified class.

    #     Args:
    #         class_name (str): The name of the class to get nodes for.

    #         class_name: vtkMRMLVolumeNode - stores a 3D image. Each voxel of a volume may be a scalar (to store images with continuous grayscale values, such as a CT image), label (to store discrete labels, such as a segmentation result), vector (for storing displacement fields or RGB color images), or tensor (MRI diffusion images). 2D image volumes are represented as single-slice 3D volumes. 4D volumes are stored in sequence nodes (vtkMRMLSequenceNode).

    #         class_name: vtkMRMLModelNode - stores a surface mesh (polygonal elements, points, lines, etc.) or a volumetric mesh (tetrahedral, wedge elements, unstructured grid, etc.).

    #         class_name: vtkMRMLSegmentationNode - complex data node that can store an image segmentation (also known as contouring, labeling). It can store multiple representations internally; for example it can store both a binary labelmap image and a closed surface mesh.

    #         class_name: vtkMRMLMarkupsNode and subclasses - stores simple geometrical objects, such as point lists (formerly called “fiducial lists”), lines, angles, curves, planes for annotation and measurements.

    #         class_name: vtkMRMLTransformNode - stores a geometrical transformation that can be applied to any transformable nodes. A transformation can contain any number of linear or non-linear (warping) transforms chained together. In general, it is recommended to use vtkMRMLTransformNode. Child types (vtkMRMLLinearTransformNode, vtkMRMLBSplineTransformNode, vtkMRMLGridTransformNode) are kept for backward compatibility and to allow filtering for specific transformation types in user interface widgets.

    #         class_name: vtkMRMLTextNode - stores text data, such as configuration files, descriptive text, etc.

    #         class_name: vtkMRMLTableNode - stores tabular data (multiple scalar or vector arrays), used mainly for showing quantitative results in tables and plots


    #     Returns:
    #         str: A formatted string listing node names, or indicating if none exist.
    #     """
    #     tic = time.time()
    #     info = []
    #     nodes = self.talk2view_core.root.slicer_util_getNodesByClass(class_name)
    #     if nodes:
    #         info.append(f"{class_name} nodes:")
    #         for node in nodes:
    #             info.append(f"- ID: {node.GetID()}, ClassName: {node.GetClassName()}, Name: {node.GetName()}")
    #     else:
    #         info.append(f"No {class_name} nodes found in scene")

    #     # Filter information (too much context slows down the model)
    #     info = "\n".join(info)
    #     logging.info(info)
    #     toc = time.time()
    #     logging.info(f"get_node_by_class executed in {toc - tic:.4f} seconds")
    #     return info

    def get_data_context(self):
        """
        Context tool: Retrieves names of all loaded volume, segmentation, and model nodes.

        CRITICAL: ALWAYS use this tool FIRST. 
        This tells you whether anatomy is loaded as segmentations (use segment tools) or models (use model tools).
        
        Use this tool to determine:
        - What anatomical structures are currently loaded
        - Whether they are segmentations (vtkMRMLSegmentationNode) or models (vtkMRMLModelNode)
        - The exact node names to use in subsequent tool calls

        Returns:
            str: A formatted string listing volume, segmentation, and model node names, or indicating if none exist.
        """
        tic = time.time()
        info = []

        # Get scalar volume nodes
        volumeNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLScalarVolumeNode')
        if volumeNodes:
            info.append("Volume nodes:")
            for node in volumeNodes:
                info.append(f"- {node.GetName()}")
        else:
            info.append("No volume nodes found in scene")

        # Get segmentation nodes
        segmentationNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLSegmentationNode')
        if segmentationNodes:
            info.append("\nSegmentation nodes:")
            for node in segmentationNodes:
                info.append(f"- {node.GetName()}")
        else:
            info.append("No segmentation nodes found in scene")

        # Get model nodes
        modelNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLModelNode')
        if modelNodes:
            info.append("\nModel nodes:")
            for node in modelNodes:
                info.append(f"- {node.GetName()}")
        else:
            info.append("No model nodes found in scene")

        toc = time.time()
        logging.info(f"get_data_context executed in {toc - tic:.4f} seconds")
        return "\n".join(info)

    def list_segments(self, node_id: str):
        """
        Context tool: Provides detailed information about a specific segmentation node.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of segmentation nodes. Do not guess or assume node names.

        Args:
            node_id (str): The name/ID of the node to inspect.

        Returns:
            str: A string listing segments within a segmentation node, or indicating it's not a segmentation node.
        """
        tic = time.time()

        try:
            node = self.talk2view_core.root.slicer_util_getNode(node_id)
        except ValueError as e:
            return log_and_return_error(e, f"Error: {e}")

        if not node:
            logging.warning(f"SlicerTools.list_segments: No node found with name '{node_id}'")
            return f"Error: No node found with name '{node_id}'. You must use get_data_context() first to discover the actual node names in the scene."

        # Restrict to segmentation nodes for current purpose. Will be expanded in the future.
        if node.GetClassName() == "vtkMRMLSegmentationNode":
            segmentation = node.GetSegmentation()

            # Compute volumes using SegmentStatistics
            segStatLogic = self.talk2view_core.root.slicer_util_getModuleLogic("SegmentStatistics")
            segStatLogic.reset()
            parameterNode = segStatLogic.getParameterNode()
            parameterNode.SetParameter("Segmentation", node.GetID())
            parameterNode.SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
            parameterNode.SetParameter("ScalarVolumeSegmentStatisticsPlugin.enabled", "False")
            parameterNode.SetParameter("ClosedSurfaceSegmentStatisticsPlugin.enabled", "False")
            segStatLogic.computeStatistics()
            stats = segStatLogic.getStatistics()

            segments = []
            for i in range(segmentation.GetNumberOfSegments()):
                segment_name = segmentation.GetNthSegment(i).GetName()
                seg_id = segmentation.GetNthSegmentID(i)
                vol = stats[seg_id, "LabelmapSegmentStatisticsPlugin.volume_cm3"]
                segments.append(f"{segment_name} ({vol:.2f} cm³)")

            info = f"The segmentation node {node_id} contains the following segments: {', '.join(segments)}"
        else:
            info = f"The node {node_id} is not a segmentation node"
        toc = time.time()
        logging.info(f"list_segments executed in {toc - tic:.4f} seconds")
        return info

    def get_visible_segments(self, segmentation_node: str):
        """
        Context tool: Lists all currently visible segments in a specified segmentation node, including their color.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes. Do not guess or assume node names.

        Args:
            segmentation_node (str): The node ID of the segmentation node to inspect.

        Returns:
            str: A formatted string listing visible segments with names and RGB colors, or an empty list message.
        """
        tic = time.time()
        info = []
        segmentationNode = self.talk2view_core.root.slicer_util_getNode(segmentation_node)
        if not segmentationNode:
            return f"Error: No segmentation node found with name '{segmentation_node}'"

        segmentationDisplayNode = segmentationNode.GetDisplayNode()
        if not segmentationDisplayNode:
            return f"Error: Segmentation '{segmentation_node}' has no display node"

        visible_segment_ids = segmentationDisplayNode.GetVisibleSegmentIDs()

        for segmentId in visible_segment_ids:
            segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
            # Get segment display properties
            color = [0.0, 0.0, 0.0]  # Initialize RGB array
            segmentationDisplayNode.GetSegmentColor(segmentId, color)
            info.append(f"{segment.GetName()} (Color: RGB({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f})")

        info = f"The segmentation node {segmentation_node} contains the following visible segments: {','.join(info)}"
        toc = time.time()
        logging.info(f"get_visible_segments executed in {toc - tic:.4f} seconds")
        return info

    def _get_segmentation_and_display_node(self, segmentation_node_name: str):
        nodes = self.talk2view_core.root.slicer_mrmlScene_GetNodesByName(segmentation_node_name)
        if nodes.GetNumberOfItems() != 1:
            raise ValueError(f"Expected exactly one node named '{segmentation_node_name}', found {nodes.GetNumberOfItems()}")

        segmentationNode = nodes.GetItemAsObject(0)

        # Check if the node is actually a segmentation node
        if not segmentationNode.IsA('vtkMRMLSegmentationNode'):
            raise TypeError(f"Node '{segmentation_node_name}' is not a segmentation node. Found: {segmentationNode.GetClassName()}")

        displayNode = segmentationNode.GetDisplayNode()
        if not displayNode:
            raise ValueError(f"Segmentation node '{segmentation_node_name}' has no display node")

        return segmentationNode, displayNode

    def show_segmentation_3d(self, segmentation_node_name: str):
        """
        Action tool: Shows a segmentation in the 3D view by creating a closed
        surface representation. This is equivalent to clicking the "Show 3D"
        button in the Segment Editor.

        Use when the user says:
        - "show 3D"
        - "show segmentation in 3D"
        - "show segments in 3D view"
        - "create 3D surface"

        Args:
            segmentation_node_name (str): The name of the segmentation node.
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        segmentationNode.CreateClosedSurfaceRepresentation()
        displayNode.SetAllSegmentsVisibility(True)

        # Reset 3D view to show the segmentation
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)
        if threeDWidget:
            threeDView = threeDWidget.threeDView()
            threeDView.resetFocalPoint()
            self.talk2view_core.root.slicer_util_forceRenderAllViews()

        toc = time.time()
        logging.info(f"show_segmentation_3d executed in {toc - tic:.4f} seconds")
        return f"3D surface created and visible for {segmentation_node_name}"

    def show_all_segments(self, segmentation_node_name: str):
        """
        Action tool: Shows all segments in a segmentation node.

        Args:
            segmentation_node_name (str): The name of the segmentation node to modify.
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        displayNode.SetAllSegmentsVisibility(True)

        toc = time.time()
        logging.info(f"show_all_segments executed in {toc - tic:.4f} seconds")
        return f"All segments in {segmentation_node_name} are now visible"

    def hide_all_segments(self, segmentation_node_name: str):
        """
        Action tool: Hides all segments in a segmentation node.

        Args:
            segmentation_node_name (str): The name of the segmentation node to modify.
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        displayNode.SetAllSegmentsVisibility(False)

        toc = time.time()
        logging.info(f"hide_all_segments executed in {toc - tic:.4f} seconds")
        return f"All segments in {segmentation_node_name} are now hidden"

    def show_specific_segments(self, segmentation_node_name: str, segment_names: list[str]):
        """
        Action tool: Shows specific segments by name within a segmentation node and centers the view.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes. Do not guess or assume node names.

        Use this when the user says:
        - "show [anatomy]"
        - "display [anatomy]"
        - "make [anatomy] visible"
        - "show only [anatomy]" (hide all first, then show these)

        Args:
            segmentation_node_name (str): The node name of the segmentation node to modify.
            segment_names (list[str]): A list of segment names to show.
        """
        tic = time.time()
        try:
            segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        except (TypeError, ValueError) as e:
            if "vtkMRMLModelNode" in str(e):
                return log_and_return_error(e, f"Error: Node '{segmentation_node_name}' is a model node, not a segmentation node. Use get_data_context().")
            else:
                return log_and_return_error(e)
        segmentation = segmentationNode.GetSegmentation()
        successful_segments = []
        failed_segments = []

        RenderBlocker = self.talk2view_core.root.slicer_util_RenderBlocker()
        with RenderBlocker():
            for segment_name in segment_names:
                segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
                if segment_id:
                    displayNode.SetSegmentVisibility(segment_id, True)
                    successful_segments.append(segment_name)
                else:
                    failed_segments.append(segment_name)

        self.center_view()

        # Build result message
        result_parts = []
        if successful_segments:
            result_parts.append(f"Showed {len(successful_segments)} segments: {', '.join(successful_segments)}")
        if failed_segments:
            result_parts.append(f"Could not find segments: {', '.join(failed_segments)}")

        toc = time.time()
        logging.info(f"show_specific_segments executed in {toc - tic:.4f} seconds")
        #return "\n".join(result_parts) if result_parts else "No segments were modified"
        return f"The following segments are now visible in segmentation node {segmentation_node_name}: {self.get_visible_segments(segmentation_node_name)}"

    def hide_specific_segments(self, segmentation_node_name: str, segment_names: list[str]):
        """
        Action tool: Hides specific segments by name within a segmentation node.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes. Do not guess or assume node names.

        Use this when the user says:
        - "hide [anatomy]"
        - "remove [anatomy]"
        - "don't show [anatomy]"
        - "make [anatomy] invisible"

        Args:
            segmentation_node_name (str): The node name of the segmentation node to modify.
            segment_names (list[str]): A list of segment names to hide.
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        segmentation = segmentationNode.GetSegmentation()
        successful_segments = []
        failed_segments = []

        RenderBlocker = self.talk2view_core.root.slicer_util_RenderBlocker()
        with RenderBlocker():
            for segment_name in segment_names:
                segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
                if segment_id:
                    displayNode.SetSegmentVisibility(segment_id, False)
                    successful_segments.append(segment_name)
                else:
                    failed_segments.append(segment_name)

        # Build result message
        result_parts = []
        if successful_segments:
            result_parts.append(f"Hid {len(successful_segments)} segments: {', '.join(successful_segments)}")
        if failed_segments:
            result_parts.append(f"Could not find segments: {', '.join(failed_segments)}")

        toc = time.time()
        logging.info(f"hide_specific_segments executed in {toc - tic:.4f} seconds")
        #return "\n".join(result_parts) if result_parts else "No segments were modified"
        return f"The following segments are now visible in segmentation node {segmentation_node_name}: {self.get_visible_segments(segmentation_node_name)}"

    def set_segment_color(self, segmentation_node_name: str, segment_names: list[str], red: float, green: float, blue: float):
        """
        Action tool: Sets the color of specific segments using RGB values.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes. Do not guess or assume node names.

        Args:
            segmentation_node_name (str): The name of the segmentation node.
            segment_names (list[str]): A list of segment names to modify.
            red (float): Red component (0.0 to 1.0).
            green (float): Green component (0.0 to 1.0).
            blue (float): Blue component (0.0 to 1.0).

        Returns:
            str: A message indicating which segments were modified and any errors.
        """
        tic = time.time()

        # Clamp color values to valid range
        red = max(0.0, min(1.0, red))
        green = max(0.0, min(1.0, green))
        blue = max(0.0, min(1.0, blue))

        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        segmentation = segmentationNode.GetSegmentation()
        successful_segments = []
        failed_segments = []

        RenderBlocker = self.talk2view_core.root.slicer_util_RenderBlocker()
        with RenderBlocker():
            for segment_name in segment_names:
                segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
                if segment_id:
                    segment = segmentation.GetSegment(segment_id)
                    segment.SetColor([red, green, blue])
                    successful_segments.append(segment_name)
                else:
                    failed_segments.append(segment_name)

        # Build result message
        result_parts = []
        if successful_segments:
            result_parts.append(f"Set color to RGB({red:.2f}, {green:.2f}, {blue:.2f}) for {len(successful_segments)} segments: {', '.join(successful_segments)}")
        if failed_segments:
            result_parts.append(f"Could not find segments: {', '.join(failed_segments)}")

        toc = time.time()
        logging.info(f"set_segment_color executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No segments were modified"

    def rename_segments(self, segmentation_node_name: str, rename_map: List[List[str]]) -> str:
        """
        Action tool: Renames segments in a segmentation node.

        IMPORTANT: You must first use list_segments() to get current segment names,
        then create the rename_map with translations or modifications.

        Use this tool when users want to modify segment names, such as:
        - Adding annotations (e.g., "add (left) or (right) to segment names")
        - Translating names (e.g., "translate segments to Spanish")
        - Adding etymologies (e.g., "add Latin names in parentheses")
        - Standardizing names (e.g., "use medical terminology")
        - Adding numbering (e.g., "number the vertebrae")

        Args:
            segmentation_node_name: The name of the segmentation node
            rename_map: List of [old_name, new_name] pairs
                       Example: [["rib_1", "costilla_1"], ["rib_2", "costilla_2"]]

        Returns:
            A message indicating which segments were renamed

        Example workflow:
            1. First call list_segments() to get: ["rib_1", "rib_2", "rib_3"]
            2. Create translations: [["rib_1", "costilla_1"], ["rib_2", "costilla_2"], ["rib_3", "costilla_3"]]
            3. Call rename_segments with the list of pairs

        Common Spanish translations:
            - rib/ribs → costilla/costillas
            - skull → cráneo
            - brain → cerebro
            - spine → columna vertebral
            - jaw/mandible → mandíbula
            - bone → hueso
            - vertebra → vértebra
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        segmentation = segmentationNode.GetSegmentation()

        successful_renames = []
        failed_renames = []

        for old_name, new_name in rename_map:
            segment_id = segmentation.GetSegmentIdBySegmentName(old_name)
            if segment_id:
                segment = segmentation.GetSegment(segment_id)
                segment.SetName(new_name)
                successful_renames.append(f"{old_name} → {new_name}")
            else:
                failed_renames.append(old_name)

        # Build result message
        result_parts = []
        if successful_renames:
            result_parts.append(f"Renamed {len(successful_renames)} segments:\n" + "\n".join(successful_renames))
        if failed_renames:
            result_parts.append(f"Could not find segments: {', '.join(failed_renames)}")

        toc = time.time()
        logging.info(f"rename_segments executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No segments were renamed"

    def measure_segments_volume(self, segmentation_node_name: str, specific_segments: List[str]) -> str:
        """
        Analysis tool: Measures and returns the volume of specific segments in a segmentation node.
        
        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes, then use list_segments() to discover the exact segment names.
        Do not guess or assume node or segment names.
        
        Use this when the user asks to:
        - "measure volume of [specific segments]"
        - "calculate volume of the skull"
        - "get volume of vertebra C1 and C2"
        - "how big is the brain segment"
        - "quantify volume of specific structures"
        
        Args:
            segmentation_node_name (str): The name of the segmentation node containing segments to measure.
            specific_segments (List[str]): List of specific segment names to measure volumes for.
                                         Use list_segments() to discover exact names first.
            
        Returns:
            str: Formatted volume measurements for each specified segment in cm³ (cubic centimeters).
        """
        tic = time.time()
        
        # Validate inputs
        if not specific_segments:
            return "Error: No segments specified. Please provide a list of segment names to measure."
            
        try:
            segmentationNode = self.talk2view_core.root.slicer_util_getNode(segmentation_node_name)
        except ValueError as e:
            return log_and_return_error(e)

        if not segmentationNode:
            return f"Error: No segmentation node found with name '{segmentation_node_name}'"

        if not segmentationNode.IsA('vtkMRMLSegmentationNode'):
            return f"Error: Node '{segmentation_node_name}' is not a segmentation node"

        # Get SegmentStatistics logic
        segStatLogic = self.talk2view_core.root.slicer_util_getModuleLogic("SegmentStatistics")
        if not segStatLogic:
            return "Error: SegmentStatistics extension is not available. Please install the SegmentStatistics extension in 3D Slicer."

        # Reset and configure the statistics logic
        segStatLogic.reset()
        segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())

        # Enable only the Labelmap plugin for volume calculation
        parameterNode = segStatLogic.getParameterNode()
        parameterNode.SetParameter("LabelmapSegmentStatisticsPlugin.enabled", "True")
        parameterNode.SetParameter("ScalarVolumeSegmentStatisticsPlugin.enabled", "False")
        parameterNode.SetParameter("ClosedSurfaceSegmentStatisticsPlugin.enabled", "False")

        # Get segmentation object
        segmentation = segmentationNode.GetSegmentation()

        # Find segment IDs and validate segment names
        valid_segments = []  # [(segment_name, segment_id), ...]
        missing_segments = []

        for segment_name in specific_segments:
            segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
            if segment_id:
                valid_segments.append((segment_name, segment_id))
            else:
                missing_segments.append(segment_name)

        if not valid_segments:
            return f"Error: None of the specified segments found in '{segmentation_node_name}': {', '.join(specific_segments)}"

        # Compute statistics for each valid segment
        volume_results = []
        total_volume = 0.0

        for segment_name, segment_id in valid_segments:
            try:
                # Compute statistics for this specific segment
                segStatLogic.updateStatisticsForSegment(segment_id)
                stats = segStatLogic.getStatistics()

                # Get volume in cm³
                volume_cm3 = stats[segment_id, "LabelmapSegmentStatisticsPlugin.volume_cm3"]
                volume_results.append(f"{segment_name}: {volume_cm3:.2f} cm³")
                total_volume += volume_cm3

            except KeyError as e:
                volume_results.append(f"{segment_name}: Error computing volume - {str(e)}")

        # Build result message with proper markdown table formatting
        result_message = []
        if volume_results:
            result_message.append(f"**Volume Measurements for '{segmentation_node_name}'**")
            result_message.append("")

            # Format as markdown table
            result_message.append("| Segment | Volume |")
            result_message.append("|---------|--------|")
            for segment_name, segment_id in valid_segments:
                try:
                    volume_cm3 = segStatLogic.getStatistics()[segment_id, "LabelmapSegmentStatisticsPlugin.volume_cm3"]
                    result_message.append(f"| {segment_name} | {volume_cm3:.2f} cm³ |")
                except KeyError:
                    result_message.append(f"| {segment_name} | Error |")
            result_message.append(f"| **Total** | **{total_volume:.2f} cm³** |")

        if missing_segments:
            result_message.append("")
            result_message.append(f"**Segments Not Found:** {', '.join(missing_segments)}")

        main_content = "\n".join(result_message) if result_message else "No valid segments found"

        header = f"*Connector's response using 'SlicerTools.measure_segments_volume':*\n---\n"

        # Add footer with measurement info
        footer = f"\n\n---\n*Volume measurements computed using 3D Slicer's SegmentStatistics module. Results are calculated from labelmap voxel data.*"

        result = header + main_content + footer

        toc = time.time()
        logging.info(f"measure_segments_volume executed in {toc - tic:.4f} seconds")
        return result

    def compare_segments(self,
                         reference_segmentation_node_name: str, reference_segment_name: str,
                         compare_segmentation_node_name: str, compare_segment_name: str) -> str:
        """
        Analysis tool: Computes Dice coefficient and Hausdorff distance metrics
        between two segments — typically a reference (ground truth) and a
        comparison (manual, automated, or agentic) result.

        Use when user asks to:
        - "compare two segmentations", "evaluate segmentation accuracy"
        - "compute Dice coefficient", "compute Hausdorff distance"
        - "validate this segmentation against the ground truth"
        - "measure overlap between Tumor in seg_A and Tumor in seg_B"

        Both segmentations should be geometrically aligned (same source volume
        / spacing). The reference is the ground truth; the compare is what is
        being evaluated against it.

        Requires the SlicerRT extension (provides the SegmentComparison module).
        If unavailable, the user is told to install it via Slicer's Extension
        Manager.

        Args:
            reference_segmentation_node_name: Name of the reference segmentation node
            reference_segment_name: Name of the segment in the reference segmentation
            compare_segmentation_node_name: Name of the segmentation to compare against
            compare_segment_name: Name of the segment in the compare segmentation

        Returns:
            str: Markdown report with Dice coefficient and Hausdorff distance
                 metrics (maximum, average, and 95th-percentile if available).
        """
        tic = time.time()

        # --- Validate reference segmentation + segment ---
        try:
            refSegNode = self.talk2view_core.root.slicer_util_getNode(reference_segmentation_node_name)
        except ValueError as e:
            msg = f"Reference segmentation '{reference_segmentation_node_name}' not found"
            logging.warning(f"compare_segments: {msg}: {e}")
            return f"Error: {msg}"

        if not refSegNode.IsA('vtkMRMLSegmentationNode'):
            msg = f"Node '{reference_segmentation_node_name}' is not a segmentation node"
            logging.warning(f"compare_segments: {msg}")
            return f"Error: {msg}"

        refSegmentation = refSegNode.GetSegmentation()
        refSegmentId = refSegmentation.GetSegmentIdBySegmentName(reference_segment_name)
        if not refSegmentId:
            n = refSegmentation.GetNumberOfSegments()
            available = [refSegmentation.GetNthSegment(i).GetName() for i in range(n)]
            msg = (f"Reference segment '{reference_segment_name}' not found in "
                   f"'{reference_segmentation_node_name}'. Available: {available}")
            logging.warning(f"compare_segments: {msg}")
            return f"Error: {msg}"

        # --- Validate compare segmentation + segment ---
        try:
            cmpSegNode = self.talk2view_core.root.slicer_util_getNode(compare_segmentation_node_name)
        except ValueError as e:
            msg = f"Compare segmentation '{compare_segmentation_node_name}' not found"
            logging.warning(f"compare_segments: {msg}: {e}")
            return f"Error: {msg}"

        if not cmpSegNode.IsA('vtkMRMLSegmentationNode'):
            msg = f"Node '{compare_segmentation_node_name}' is not a segmentation node"
            logging.warning(f"compare_segments: {msg}")
            return f"Error: {msg}"

        cmpSegmentation = cmpSegNode.GetSegmentation()
        cmpSegmentId = cmpSegmentation.GetSegmentIdBySegmentName(compare_segment_name)
        if not cmpSegmentId:
            n = cmpSegmentation.GetNumberOfSegments()
            available = [cmpSegmentation.GetNthSegment(i).GetName() for i in range(n)]
            msg = (f"Compare segment '{compare_segment_name}' not found in "
                   f"'{compare_segmentation_node_name}'. Available: {available}")
            logging.warning(f"compare_segments: {msg}")
            return f"Error: {msg}"

        # --- Get SlicerRT SegmentComparison module logic ---
        try:
            segCompLogic = self.talk2view_core.root.slicer_util_getModuleLogic("SegmentComparison")
        except Exception as e:
            msg = ("SegmentComparison module not available. Please install the SlicerRT "
                   "extension via 3D Slicer's Extension Manager (provides Dice and "
                   "Hausdorff metrics for segmentation evaluation).")
            logging.warning(f"compare_segments: SegmentComparison getModuleLogic raised: {e}")
            return f"Error: {msg}"

        if not segCompLogic:
            msg = ("SegmentComparison module not available. Please install the SlicerRT "
                   "extension via 3D Slicer's Extension Manager.")
            logging.warning("compare_segments: SegmentComparison module logic returned None")
            return f"Error: {msg}"

        # --- Create parameter node and configure ---
        parameterNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass(
            "vtkMRMLSegmentComparisonNode"
        )
        if not parameterNode:
            msg = "Failed to create SegmentComparison parameter node"
            logging.warning(f"compare_segments: {msg}")
            return f"Error: {msg}"

        try:
            parameterNode.SetAndObserveReferenceSegmentationNodeID(refSegNode.GetID())
            parameterNode.SetReferenceSegmentID(refSegmentId)
            parameterNode.SetAndObserveCompareSegmentationNodeID(cmpSegNode.GetID())
            parameterNode.SetCompareSegmentID(cmpSegmentId)

            # Compute Dice
            try:
                dice_status = segCompLogic.ComputeDiceStatistics(parameterNode)
                if dice_status and "successful" not in str(dice_status).lower():
                    logging.warning(f"compare_segments: Dice status: {dice_status}")
            except Exception as e:
                logging.warning(f"compare_segments: Dice computation raised: {e}")
                return f"Error: Dice computation failed: {e}"

            # Compute Hausdorff
            try:
                hausdorff_status = segCompLogic.ComputeHausdorffDistances(parameterNode)
                if hausdorff_status and "successful" not in str(hausdorff_status).lower():
                    logging.warning(f"compare_segments: Hausdorff status: {hausdorff_status}")
            except Exception as e:
                logging.warning(f"compare_segments: Hausdorff computation raised: {e}")
                return f"Error: Hausdorff computation failed: {e}"

            # Read results
            dice = parameterNode.GetDiceCoefficient()
            hausdorff_max = parameterNode.GetMaximumHausdorffDistanceForVolumeMm()
            hausdorff_avg = parameterNode.GetAverageHausdorffDistanceForVolumeMm()

            # 95th-percentile is only available in newer SlicerRT
            try:
                hausdorff_95 = parameterNode.GetHausdorffDistanceForVolumeMm95Percent()
            except (AttributeError, TypeError):
                hausdorff_95 = None
        finally:
            try:
                self.talk2view_core.root.slicer_mrmlScene_RemoveNode(parameterNode)
            except Exception as cleanup_err:
                logging.warning(f"compare_segments: failed to clean up parameter node: {cleanup_err}")

        # --- Format markdown report ---
        lines = [
            f"**Comparison: '{reference_segment_name}' (reference) vs '{compare_segment_name}' (compare)**",
            f"Reference segmentation: `{reference_segmentation_node_name}`",
            f"Compare segmentation:   `{compare_segmentation_node_name}`",
            "",
            "| Metric                       | Value      |",
            "|------------------------------|------------|",
            f"| Dice coefficient             | {dice:.4f}     |",
            f"| Maximum Hausdorff (mm)       | {hausdorff_max:.4f} |",
            f"| Average Hausdorff (mm)       | {hausdorff_avg:.4f} |",
        ]
        if hausdorff_95 is not None:
            lines.append(f"| 95-percentile Hausdorff (mm) | {hausdorff_95:.4f} |")

        lines.append("")
        lines.append(
            "*Computed using SlicerRT SegmentComparison. "
            "Dice = 1.0 is perfect overlap; 0.0 is no overlap. "
            "Hausdorff distance measures the maximum boundary discrepancy in millimetres — lower is better.*"
        )

        toc = time.time()
        logging.info(f"compare_segments executed in {toc - tic:.4f} seconds")

        return "\n".join(lines)

    def set_opacity(self, target_name: str, opacity: float, segment_names: list[str]):
        """
        Action tool: Controls transparency/opacity of visible objects. Use for making objects transparent,
        see-through, or solid. DO NOT use for hiding/showing - use visibility tools instead.

        IMPORTANT: Only affects VISIBLE objects. To show/hide, use show_all_segments(), hide_all_segments(), show_specific_segments(), or hide_specific_segments().

        Opacity value guide:
        - 0.1-0.3 = very transparent/see-through (can clearly see behind)
        - 0.4-0.6 = semi-transparent (balanced)
        - 0.7-0.9 = mostly solid (slightly see-through)
        - 1.0 = completely opaque/solid (cannot see through)

        NOTE: Avoid 0.0 - use visibility tools to hide instead.

        For relative adjustments like "more transparent" or "less see-through":
        - "more transparent/see-through" - decrease current opacity by ~0.2-0.3
        - "less transparent/see-through" - increase current opacity by ~0.2-0.3
        - "slightly more transparent" - decrease by ~0.1
        - "much more solid" - increase by ~0.3-0.4

        The AI should get current opacity first if doing relative adjustments.

        Args:
            target_name (str): Name of the visible volume, model, or segmentation.
            opacity (float): Transparency from 0.0 to 1.0. Lower = more transparent.
            segment_names (list[str]): For segmentations - specific segments to modify. Pass empty list [] to apply to all segments.

        Examples:
        - "Make the skull transparent" - set_opacity("skull", 0.2, [])
        - "Make the brain semi-transparent" - set_opacity("brain", 0.5, [])
        - "Make the tumor more solid" - set_opacity("tumor", 0.8, [])
        - "Make ribs slightly see-through" - set_opacity("segmentation", 0.7, ["rib_1", "rib_2"])

        Returns:
            str: Success message with what was modified.
        """
        tic = time.time()
        # Validate opacity value
        if not 0.0 <= opacity <= 1.0:
            return f"Error: Opacity must be between 0.0 and 1.0, got {opacity}"

        # Try to get the node by name
        node = self.talk2view_core.root.slicer_util_getNode(target_name)

        if not node:
            return f"Error: No node found with name '{target_name}'"

        node_class = node.GetClassName()

        # Handle different node types
        if node_class in ['vtkMRMLScalarVolumeNode', 'vtkMRMLVectorVolumeNode', 'vtkMRMLLabelMapVolumeNode']:
            # Volume node - set opacity on volume display node
            displayNode = node.GetDisplayNode()
            if displayNode:
                displayNode.SetOpacity(opacity)
                result = f"Volume '{target_name}' opacity set to {opacity}"
            else:
                return f"Error: Volume '{target_name}' has no display node"

        elif node_class == 'vtkMRMLModelNode':
            # Model node - set opacity on model display node
            displayNode = node.GetDisplayNode()
            if displayNode:
                displayNode.SetOpacity(opacity)
                result = f"Model '{target_name}' opacity set to {opacity}"
            else:
                return f"Error: Model '{target_name}' has no display node"

        elif node_class == 'vtkMRMLSegmentationNode':
            # Segmentation node - can set opacity for entire segmentation or specific segments
            displayNode = node.GetDisplayNode()
            if not displayNode:
                return f"Error: Segmentation '{target_name}' has no display node"

            if segment_names and len(segment_names) > 0:
                # Set opacity for specific segments
                segmentation = node.GetSegmentation()
                modified_segments = []
                RenderBlocker = self.talk2view_core.root.slicer_util_RenderBlocker()
                with RenderBlocker():
                    for segment_name in segment_names:
                        segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
                        if segment_id:
                            displayNode.SetSegmentOpacity(segment_id, opacity)
                            modified_segments.append(segment_name)
                        else:
                            logging.warning(f"Segment '{segment_name}' not found in segmentation '{target_name}'")

                if modified_segments:
                    result = f"Segments {', '.join(modified_segments)} in '{target_name}' opacity set to {opacity}"
                else:
                    return f"Error: No valid segments found in the provided list"
            else:
                # Set opacity for all segments in segmentation (empty list means all)
                displayNode.SetAllSegmentsOpacity(opacity)
                result = f"Segmentation '{target_name}' set all segments opacity set to {opacity}"

        elif 'vtkMRMLMarkups' in node_class:
            # Markups node (fiducials, lines, curves, etc.)
            displayNode = node.GetDisplayNode()
            if displayNode:
                displayNode.SetOpacity(opacity)
                result = f"Markup '{target_name}' opacity set to {opacity}"
            else:
                return f"Error: Markup '{target_name}' has no display node"

        else:
            return f"Error: Node type '{node_class}' does not support opacity settings"

        logging.info(f"set_opacity result: {result}")
        toc = time.time()
        logging.info(f"set_opacity executed in {toc - tic:.4f} seconds")
        return result

    # =========================================================================
    # Window/Level Methods
    # =========================================================================

    def _get_volume_node(self, volume_name: str):
        """Helper to get a volume node by name, or the first available if name is empty.

        Returns:
            tuple: (volumeNode, error_message) - volumeNode is None if not found,
                   error_message contains helpful info about available volumes
        """
        volumeNodes = self.talk2view_core.root.slicer_util_getNodesByClass("vtkMRMLScalarVolumeNode")

        if volume_name:
            # Try to find the specified volume
            try:
                return self.talk2view_core.root.slicer_util_getNode(volume_name), None
            except ValueError:
                # Volume not found - return helpful error
                if volumeNodes:
                    available = [n.GetName() for n in volumeNodes]
                    return None, f"Volume '{volume_name}' not found. Available volumes: {available}"
                else:
                    return None, f"Volume '{volume_name}' not found. No volumes are loaded in the scene."
        else:
            # Get first available scalar volume
            if volumeNodes:
                return volumeNodes[0], None
            return None, "No volumes are loaded in the scene."

    def set_window_level(self, volume_name: str, window: float, level: float) -> str:
        """
        Action tool: Sets the window (contrast) and level (brightness) for a volume.

        Use when user says:
        - "set window to 400 and level to 40"
        - "change contrast", "adjust brightness"
        - "window level 1500/300" (for bone)

        Common CT presets (window/level):
        - Soft tissue: 400/40
        - Bone: 1500/300
        - Lung: 1800/-500
        - Brain: 80/40
        - Liver: 150/30
        - Abdomen: 350/40

        Args:
            volume_name: Name of the volume node, or empty string for first available
            window: Window width (contrast). Larger = lower contrast
            level: Window center (brightness)

        Returns:
            str: Status message
        """
        tic = time.time()

        volumeNode, error = self._get_volume_node(volume_name)
        if not volumeNode:
            return f"Error: {error}"

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return f"Error: Volume '{volumeNode.GetName()}' has no display node"

        # Disable auto window/level and set custom values
        displayNode.AutoWindowLevelOff()
        displayNode.SetWindow(window)
        displayNode.SetLevel(level)

        toc = time.time()
        logging.info(f"set_window_level executed in {toc - tic:.4f} seconds")

        return f"Set window/level to {window}/{level} on volume '{volumeNode.GetName()}'"

    def set_window_level_preset(self, volume_name: str, preset: str) -> str:
        """
        Action tool: Sets window/level using a named preset for common imaging scenarios.

        Use when user says:
        - "show bone window", "bone preset"
        - "lung window", "soft tissue view"
        - "CT abdomen settings"

        Available presets:
        - ct_soft_tissue: Window 400, Level 40 (general soft tissue)
        - ct_bone: Window 1500, Level 300 (skeletal structures)
        - ct_lung: Window 1800, Level -500 (pulmonary parenchyma)
        - ct_brain: Window 80, Level 40 (brain parenchyma)
        - ct_liver: Window 150, Level 30 (hepatic imaging)
        - ct_abdomen: Window 350, Level 40 (abdominal organs)
        - mri_t1: Window 500, Level 250 (T1-weighted MRI)
        - mri_t2: Window 400, Level 200 (T2-weighted MRI)
        - auto: Reset to automatic window/level

        Args:
            volume_name: Name of the volume node, or empty string for first available
            preset: Preset name (see above)

        Returns:
            str: Status message
        """
        tic = time.time()

        # Define presets (window, level)
        presets = {
            'ct_soft_tissue': (400, 40),
            'ct_bone': (1500, 300),
            'ct_lung': (1800, -500),
            'ct_brain': (80, 40),
            'ct_liver': (150, 30),
            'ct_abdomen': (350, 40),
            'mri_t1': (500, 250),
            'mri_t2': (400, 200),
        }

        preset_lower = preset.lower().replace(' ', '_').replace('-', '_')

        if preset_lower == 'auto':
            return self.reset_window_level(volume_name)

        if preset_lower not in presets:
            available = ', '.join(list(presets.keys()) + ['auto'])
            return f"Error: Unknown preset '{preset}'. Available: {available}"

        window, level = presets[preset_lower]

        volumeNode, error = self._get_volume_node(volume_name)
        if not volumeNode:
            return f"Error: {error}"

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return f"Error: Volume '{volumeNode.GetName()}' has no display node"

        displayNode.AutoWindowLevelOff()
        displayNode.SetWindow(window)
        displayNode.SetLevel(level)

        toc = time.time()
        logging.info(f"set_window_level_preset executed in {toc - tic:.4f} seconds")

        return f"Applied '{preset}' preset (W:{window}/L:{level}) to volume '{volumeNode.GetName()}'"

    def reset_window_level(self, volume_name: str) -> str:
        """
        Action tool: Resets window/level to automatic (computed from image data).

        Use when user says:
        - "reset window level", "auto window level"
        - "default brightness/contrast"

        Args:
            volume_name: Name of the volume node, or empty string for first available

        Returns:
            str: Status message
        """
        tic = time.time()

        volumeNode, error = self._get_volume_node(volume_name)
        if not volumeNode:
            return f"Error: {error}"

        displayNode = volumeNode.GetDisplayNode()
        if not displayNode:
            return f"Error: Volume '{volumeNode.GetName()}' has no display node"

        displayNode.AutoWindowLevelOn()

        toc = time.time()
        logging.info(f"reset_window_level executed in {toc - tic:.4f} seconds")

        return f"Reset window/level to automatic on volume '{volumeNode.GetName()}'"

    def window_level_tool_activate(self) -> str:
        """
        Action tool: Activates the window/level mouse interaction tool.

        Use when user says:
        - "let me adjust window level with mouse", "enable window level tool"
        - "activate window level mouse", "I want to adjust brightness with mouse"

        The tool stays active until deactivated, allowing the user to click and drag
        in slice views to adjust window/level. Call window_level_tool_deactivate when done.

        Returns:
            str: Status message
        """
        tic = time.time()

        # Get the interaction node and set mode to AdjustWindowLevel
        interactionNode = self.talk2view_core.root.slicer_app_applicationLogic().GetInteractionNode()
        # AdjustWindowLevel = 5 in vtkMRMLInteractionNode
        interactionNode.SetCurrentInteractionMode(5)

        toc = time.time()
        logging.info(f"window_level_tool_activate executed in {toc - tic:.4f} seconds")

        return "Window/level mouse tool activated. Click and drag in slice views to adjust brightness/contrast. Say 'done' when finished."

    def window_level_tool_deactivate(self) -> str:
        """
        Action tool: Deactivates the window/level mouse interaction tool.

        Use when user says:
        - "done", "finished adjusting", "stop window level"
        - "deactivate window level tool"

        Returns:
            str: Status message
        """
        tic = time.time()

        # Get the interaction node and set mode back to ViewTransform (default navigation)
        interactionNode = self.talk2view_core.root.slicer_app_applicationLogic().GetInteractionNode()
        # ViewTransform = 2 in vtkMRMLInteractionNode
        interactionNode.SetCurrentInteractionMode(2)

        toc = time.time()
        logging.info(f"window_level_tool_deactivate executed in {toc - tic:.4f} seconds")

        return "Window/level mouse tool deactivated. Normal navigation restored."

    def highlight_segments(self, segmentation_node_name: str, segment_names: list[str], background_opacity: float):
        """
        Action tool: Highlight specific SEGMENTATION SEGMENTS by making them opaque while 
        making other segments transparent. Use this for segmented anatomical structures.

        IMPORTANT: You MUST use get_data_context() first to check if segmentation nodes are available.
        Only use this tool when SEGMENTATION NODES (not model nodes) are loaded in the scene.

        Use this when:
        - User requests highlighting and SEGMENTATION NODES are present (check get_data_context())
        - Working with segmented medical imaging data
        - Need to highlight individual segments within a segmentation

        Do NOT use this for 3D model data - use highlight_models() instead.

        Args:
            segmentation_node_name (str): Name of the segmentation node (from get_data_context()).
            segment_names (list[str]): List of segment names to highlight.
            background_opacity (float): Opacity for other segments (0.0-1.0, typically 0.1).

        Returns:
            str: Summary of highlighting operation.
        """
        tic = time.time()
        segmentationNode, displayNode = self._get_segmentation_and_display_node(segmentation_node_name)
        segmentation = segmentationNode.GetSegmentation()

        # Get currently visible segments
        visible_segment_ids = displayNode.GetVisibleSegmentIDs()
        if not visible_segment_ids:
            return f"No segments are currently visible in '{segmentation_node_name}'"

        highlighted_segments = []
        background_segments = []
        failed_segments = []

        RenderBlocker = self.talk2view_core.root.slicer_util_RenderBlocker()
        with RenderBlocker():
            # Find segments to highlight
            highlight_ids = []
            for segment_name in segment_names:
                segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
                if segment_id:
                    highlight_ids.append(segment_id)
                    highlighted_segments.append(segment_name)
                else:
                    failed_segments.append(segment_name)

            # Set opacity for all visible segments
            for segment_id in visible_segment_ids:
                if segment_id in highlight_ids:
                    # Make highlighted segments opaque
                    displayNode.SetSegmentOpacity(segment_id, 1.0)
                else:
                    # Make other segments very transparent
                    displayNode.SetSegmentOpacity(segment_id, background_opacity)
                    segment = segmentation.GetSegment(segment_id)
                    background_segments.append(segment.GetName())
        self.center_view()

        # Build result message
        result_parts = []
        if highlighted_segments:
            result_parts.append(f"Highlighted {len(highlighted_segments)} segments: {', '.join(highlighted_segments)}")
        if background_segments:
            result_parts.append(f"Made {len(background_segments)} segments transparent (opacity {background_opacity})")
        if failed_segments:
            result_parts.append(f"Could not find segments: {', '.join(failed_segments)}")

        toc = time.time()
        logging.info(f"highlight_segments executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No segments were modified"

    def center_view(self) -> str:
        """
        Action tool: Centers all 2D slice views and the 3D view on the currently loaded data.

        Returns:
            str: A success or error message.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()

        threeDWidget = layoutManager.threeDWidget(0)
        if threeDWidget:
            threeDWidget.threeDView().resetFocalPoint()

        for name in ['Red', 'Yellow', 'Green']:
            sliceWidget = layoutManager.sliceWidget(name)
            if sliceWidget:
                sliceWidget.sliceController().fitSliceToBackground()
        toc = time.time()
        logging.info(f"center_view executed in {toc - tic:.4f} seconds")
        return "Successfully centered all views"

    def rotate_3d_view(self, axis: int) -> str:
        """
        Action tool: Rotates the 3D view to look from a specific anatomical direction.

        Use this when the user wants to see the 3D model from a specific direction/orientation,
        such as "show me from the front", "rotate to anterior view", "look from the right side".

        Args:
            axis (int): The axis to rotate to:
                - 0: -X (Right) - view from the right side
                - 1: +X (Left) - view from the left side
                - 2: -Y (Posterior) - view from behind
                - 3: +Y (Anterior) - view from the front
                - 4: -Z (Inferior) - view from below
                - 5: +Z (Superior) - view from above

        Returns:
            str: A success or error message.
        """
        tic = time.time()

        # Validate axis
        if axis < 0 or axis > 5:
            return f"Error: Invalid axis {axis}. Must be 0-5 (-X, +X, -Y, +Y, -Z, +Z)."

        axis_names = {
            0: "Right (-X)",
            1: "Left (+X)",
            2: "Posterior (-Y)",
            3: "Anterior (+Y)",
            4: "Inferior (-Z)",
            5: "Superior (+Z)"
        }

        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)

        if not threeDWidget:
            return "Error: No 3D view available"

        threeDView = threeDWidget.threeDView()
        threeDView.rotateToViewAxis(axis)
        threeDView.resetFocalPoint()
        threeDView.resetCamera()

        toc = time.time()
        logging.info(f"rotate_3d_view executed in {toc - tic:.4f} seconds")
        return f"Successfully rotated 3D view to {axis_names[axis]} direction"

    def jump_to_segment(self, node_name: str, segment_names: list[str]) -> str:
        """
        Action tool: Jumps/navigates the 2D slice views to show anatomical segments.
        This positions the slice views directly at the center of the segment(s) so they become
        visible in the Red (sagittal), Yellow (coronal), and Green (axial) slice views.

        IMPORTANT: You MUST use list_segmentation_nodes() first to discover the actual names of
        segmentation nodes. Do not guess or assume node names.

        Use this when the user says:
        - "scroll to [anatomy]"
        - "jump to [anatomy]"
        - "navigate to [anatomy]"
        - "show [anatomy] on the slices"
        - "I can't see [anatomy] in the slices"
        - "go to [anatomy]"

        Args:
            node_name (str): Name of the segmentation node containing the segment.
            segment_names (list[str]): List of segment names to jump to. If multiple segments
                                     are provided, jumps to the combined center of all segments.

        Returns:
            str: Success message with the position coordinates.
        """

        # Get segmentation node
        try:
            segmentation_node = self.talk2view_core.root.slicer_util_getNode(node_name)
        except ValueError as e:
            return log_and_return_error(e, f"Error: {e}")


        if not segmentation_node or "Segmentation" not in str(type(segmentation_node)):
            return f"Error: Node '{node_name}' not found or is not a segmentation node"

        segmentation = segmentation_node.GetSegmentation()

        # Calculate combined center from all valid segments
        valid_segments = []
        centers = []

        empty_segments = []
        for segment_name in segment_names:
            segment_id = segmentation.GetSegmentIdBySegmentName(segment_name)
            if segment_id:
                # Use server-side helper that calls GetSegmentCenterRAS()
                # (returns None for empty segments, or [r,a,s] position)
                center_ras = self.talk2view_core.root.get_segment_center(
                    node_name, segment_id
                )
                if center_ras is None:
                    empty_segments.append(segment_name)
                    continue

                valid_segments.append(segment_name)
                centers.append(center_ras)

        if not valid_segments:
            if empty_segments:
                msg = f"Cannot jump: segments are empty (not yet painted): {', '.join(empty_segments)}"
            else:
                msg = f"None of the specified segments found in '{node_name}': {', '.join(segment_names)}"
            logging.warning(f"SlicerTools.jump_to_segment: {msg}")
            return msg

        # Calculate combined center of all segments
        if len(centers) == 1:
            combined_center = centers[0]
        else:
            combined_center = [
                sum(center[0] for center in centers) / len(centers),
                sum(center[1] for center in centers) / len(centers),
                sum(center[2] for center in centers) / len(centers)
            ]

        # Use Slicer's proper jump method to navigate slices
        self.talk2view_core.root.jump_all_slices_to_position(
            combined_center[0], combined_center[1], combined_center[2]
        )

        # Build result message
        if len(valid_segments) == 1:
            return f"Jumped to segment '{valid_segments[0]}' at position ({combined_center[0]:.1f}, {combined_center[1]:.1f}, {combined_center[2]:.1f})"
        else:
            return f"Jumped to combined center of {len(valid_segments)} segments ({', '.join(valid_segments[:3])}{'...' if len(valid_segments) > 3 else ''}) at position ({combined_center[0]:.1f}, {combined_center[1]:.1f}, {combined_center[2]:.1f})"

    def jump_to_model(self, model_names: list[str]) -> str:
        """
        Action tool: Jumps/navigates the 2D slice views to show anatomical models.
        This positions the slice views directly at the center of the model(s) so they become
        visible in the Red (sagittal), Yellow (coronal), and Green (axial) slice views.

        Use this when the user says:
        - "scroll to [model]"
        - "jump to [model]"
        - "navigate to [model]"
        - "show [model] on the slices"
        - "I can't see [model] in the slices"
        - "go to [model]"

        Args:
            model_names (list[str]): List of model names to jump to. If multiple models
                                   are provided, jumps to the combined center of all models.

        Returns:
            str: Success message with the position coordinates.
        """
        if not model_names:
            return "Error: model_names must be provided and contain at least one model"

        # Calculate combined center from all valid models
        valid_models = []
        centers = []

        for model_name in model_names:
            try:
                # Get model node
                model_node = self.talk2view_core.root.slicer_util_getNode(model_name)

                if model_node and "Model" in str(type(model_node)):
                    valid_models.append(model_name)

                    # Use server-side helper because GetBounds uses an
                    # output parameter (double[6]) that doesn't work over RPyC
                    bounds = self.talk2view_core.root.get_node_bounds(model_name)

                    # Calculate center from bounds
                    center_ras = [
                        (bounds[0] + bounds[1]) / 2,
                        (bounds[2] + bounds[3]) / 2,
                        (bounds[4] + bounds[5]) / 2
                    ]

                    centers.append(center_ras)
            except ValueError:
                # Model not found - skip silently, handled by valid_models check below
                pass

        if not valid_models:
            return f"Error: None of the specified models found: {', '.join(model_names)}"

        # Calculate combined center of all models
        if len(centers) == 1:
            combined_center = centers[0]
        else:
            combined_center = [
                sum(center[0] for center in centers) / len(centers),
                sum(center[1] for center in centers) / len(centers),
                sum(center[2] for center in centers) / len(centers)
            ]

        # Use Slicer's proper jump method to navigate slices
        self.talk2view_core.root.jump_all_slices_to_position(
            combined_center[0], combined_center[1], combined_center[2]
        )

        # Build result message
        if len(valid_models) == 1:
            return f"Jumped to model '{valid_models[0]}' at position ({combined_center[0]:.1f}, {combined_center[1]:.1f}, {combined_center[2]:.1f})"
        else:
            return f"Jumped to combined center of {len(valid_models)} models ({', '.join(valid_models[:3])}{'...' if len(valid_models) > 3 else ''}) at position ({combined_center[0]:.1f}, {combined_center[1]:.1f}, {combined_center[2]:.1f})"

    def jump_to_position(self, r: float, a: float, s: float) -> str:
        """
        Action tool: Jumps/navigates all 2D slice views to a specific RAS coordinate position.
        This positions the Red (axial), Yellow (sagittal), and Green (coronal) slice views
        at the given coordinates so the user can see the anatomy at that location.

        Use this when the user says:
        - "jump to position [x, y, z]"
        - "go to RAS [x, y, z]"
        - "navigate to coordinates [x, y, z]"
        - "scroll to position [x, y, z]"
        - A skill step specifies "jump to RAS [x, y, z]"

        Args:
            r (float): Right coordinate in RAS space (mm).
            a (float): Anterior coordinate in RAS space (mm).
            s (float): Superior coordinate in RAS space (mm).

        Returns:
            str: Confirmation message with the position jumped to.
        """
        self.talk2view_core.root.jump_all_slices_to_position(r, a, s)
        return f"Jumped all slice views to RAS position ({r:.1f}, {a:.1f}, {s:.1f})"

    # Model-specific tools
    def get_visible_models(self):
        """
        Context tool: Lists all currently visible model nodes with their display properties.

        Returns:
            str: A formatted string listing visible models with their colors and opacity, or indicating if none are visible.
        """
        tic = time.time()
        info = []

        modelNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLModelNode')
        if modelNodes:
            visible_models = []
            for node in modelNodes:
                displayNode = node.GetDisplayNode()
                if displayNode and displayNode.GetVisibility():
                    color = displayNode.GetColor()
                    opacity = displayNode.GetOpacity()
                    visible_models.append(
                        f"{node.GetName()} (Color: RGB({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f}), Opacity: {opacity:.2f})"
                    )

            if visible_models:
                info = f"The following model nodes are visible: {', '.join(visible_models)}"
            else:
                info = "No model nodes are currently visible"
        else:
            info = "No model nodes found in scene"

        toc = time.time()
        logging.info(f"get_visible_models executed in {toc - tic:.4f} seconds")
        return info

    def set_model_visibility(self, model_names: list[str], visible: bool):
        """
        Action tool: Shows or hides specific model nodes by name.

        Args:
            model_names (list[str]): A list of model node names to modify.
            visible (bool): True to show the models, False to hide them.

        Returns:
            str: A message indicating which models were modified and any errors.
        """
        tic = time.time()
        successful_models = []
        failed_models = []

        for model_name in model_names:
            try:
                node = self.talk2view_core.root.slicer_util_getNode(model_name)
                if node and node.IsA('vtkMRMLModelNode'):
                    displayNode = node.GetDisplayNode()
                    if not displayNode:
                        # Create display node if it doesn't exist
                        displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLModelDisplayNode')
                        node.SetAndObserveDisplayNodeID(displayNode.GetID())

                    displayNode.SetVisibility(visible)
                    successful_models.append(model_name)
                else:
                    failed_models.append(f"{model_name} (not a model node)")
            except ValueError:
                failed_models.append(f"{model_name} (not found)")

        # Center view after visibility changes
        if successful_models:
            self.center_view()

        # Build result message
        result_parts = []
        if successful_models:
            action = "visible" if visible else "hidden"
            result_parts.append(f"Made {len(successful_models)} models {action}: {', '.join(successful_models)}")
        if failed_models:
            result_parts.append(f"Could not find or modify models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"set_model_visibility executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    def set_model_opacity(self, model_names: list[str], opacity: float = 0.5):
        """
        Action tool: Controls transparency/opacity of model nodes. Use for making models transparent,
        see-through, or solid. DO NOT use for hiding/showing - use set_model_visibility() instead.

        Opacity value guide:
        - 0.1-0.3 = very transparent/see-through (can clearly see behind)
        - 0.4-0.6 = semi-transparent (balanced, default is 0.5)
        - 0.7-0.9 = mostly solid (slightly see-through)
        - 1.0 = completely opaque/solid (cannot see through)

        NOTE: Avoid 0.0 - use set_model_visibility() to hide instead.

        Args:
            model_names (list[str]): A list of model node names to modify.
            opacity (float): The opacity value (0.0 to 1.0).

        Returns:
            str: A message indicating which models were modified and any errors.
        """
        tic = time.time()

        # Clamp opacity to valid range
        opacity = max(0.0, min(1.0, opacity))

        successful_models = []
        failed_models = []

        for model_name in model_names:
            try:
                node = self.talk2view_core.root.slicer_util_getNode(model_name)
                if node and node.IsA('vtkMRMLModelNode'):
                    displayNode = node.GetDisplayNode()
                    if displayNode:
                        displayNode.SetOpacity(opacity)
                        successful_models.append(model_name)
                    else:
                        failed_models.append(f"{model_name} (no display node)")
                else:
                    failed_models.append(f"{model_name} (not a model node)")
            except ValueError:
                failed_models.append(f"{model_name} (not found)")

        # Build result message
        result_parts = []
        if successful_models:
            result_parts.append(f"Set opacity to {opacity:.2f} for {len(successful_models)} models: {', '.join(successful_models)}")
        if failed_models:
            result_parts.append(f"Could not modify models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"set_model_opacity executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    def set_model_color(self, model_names: list[str], red: float, green: float, blue: float):
        """
        Action tool: Sets the color of model nodes using RGB values.

        Args:
            model_names (list[str]): A list of model node names to modify.
            red (float): Red component (0.0 to 1.0).
            green (float): Green component (0.0 to 1.0).
            blue (float): Blue component (0.0 to 1.0).

        Returns:
            str: A message indicating which models were modified and any errors.
        """
        tic = time.time()

        # Clamp color values to valid range
        red = max(0.0, min(1.0, red))
        green = max(0.0, min(1.0, green))
        blue = max(0.0, min(1.0, blue))

        successful_models = []
        failed_models = []

        for model_name in model_names:
            try:
                node = self.talk2view_core.root.slicer_util_getNode(model_name)
                if node and node.IsA('vtkMRMLModelNode'):
                    displayNode = node.GetDisplayNode()
                    if displayNode:
                        displayNode.SetScalarVisibility(False)
                        displayNode.SetColor(red, green, blue)
                        successful_models.append(model_name)
                    else:
                        failed_models.append(f"{model_name} (no display node)")
                else:
                    failed_models.append(f"{model_name} (not a model node)")
            except ValueError:
                failed_models.append(f"{model_name} (not found)")

        # Build result message
        result_parts = []
        if successful_models:
            result_parts.append(f"Set color to RGB({red:.2f}, {green:.2f}, {blue:.2f}) for {len(successful_models)} models: {', '.join(successful_models)}")
        if failed_models:
            result_parts.append(f"Could not modify models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"set_model_color executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    def highlight_models(self, model_names: list[str], background_opacity: float = 0.1):
        """
        Action tool: Highlight specific MODEL NODES (3D meshes/surfaces) by making them opaque while 
        making other visible models transparent. Use this for anatomical atlas models loaded from files (.vtk, .vtp, .stl, etc.).

        IMPORTANT: You MUST use get_data_context() first to check if model nodes are available.
        Only use this tool when MODEL NODES (not segmentation nodes) are loaded in the scene.

        Use this when:
        - User requests highlighting and MODEL NODES are present (check get_data_context())
        - Working with anatomical atlas models
        - 3D mesh/surface data loaded from files

        Do NOT use this for segmentation data - use highlight_segments() instead.

        Args:
            model_names (list[str]): List of model node names to highlight (from get_data_context()).
            background_opacity (float): Opacity for other visible models (default 0.1).

        Returns:
            str: Summary of highlighting operation.
        """
        tic = time.time()

        # Clamp background opacity to valid range
        background_opacity = max(0.0, min(1.0, background_opacity))

        # Get all model nodes
        modelNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLModelNode')
        if not modelNodes:
            return "No model nodes found in scene"

        # Find models to highlight and background models
        highlight_models = []
        background_models = []
        failed_models = []

        # First, identify all visible models
        visible_models = []
        for node in modelNodes:
            displayNode = node.GetDisplayNode()
            if displayNode and displayNode.GetVisibility():
                visible_models.append(node)

        if not visible_models:
            return "No visible models found to highlight"

        # Categorize models
        for model_name in model_names:
            found = False
            for node in visible_models:
                if node.GetName() == model_name:
                    highlight_models.append(node)
                    found = True
                    break
            if not found:
                failed_models.append(model_name)

        # Add remaining visible models to background
        for node in visible_models:
            if node not in highlight_models:
                background_models.append(node)

        # Apply highlighting
        successful_highlight = []
        successful_background = []

        # Make highlighted models fully opaque
        for node in highlight_models:
            displayNode = node.GetDisplayNode()
            displayNode.SetOpacity(1.0)
            successful_highlight.append(node.GetName())

        # Make background models transparent
        for node in background_models:
            displayNode = node.GetDisplayNode()
            displayNode.SetOpacity(background_opacity)
            successful_background.append(node.GetName())

        # Center view after highlighting
        if successful_highlight:
            self.center_view()

        # Build result message
        result_parts = []
        if successful_highlight:
            result_parts.append(f"Highlighted {len(successful_highlight)} models (opacity 1.0): {', '.join(successful_highlight)}")
        if successful_background:
            result_parts.append(f"Made {len(successful_background)} models transparent (opacity {background_opacity}): {', '.join(successful_background)}")
        if failed_models:
            result_parts.append(f"Could not process models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"highlight_models executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    def set_model_slice_visibility(self, model_names: list[str], visible: bool) -> str:
        """
        Action tool: Shows or hides model intersections in 2D slice views.

        When enabled, colored outlines of the model are drawn on the Red,
        Green, and Yellow slice views wherever they intersect each slice.
        This is independent of 3D visibility — use set_model_visibility for
        the 3D view.

        Args:
            model_names (list[str]): A list of model node names to modify.
            visible (bool): True to show slice intersections, False to hide.

        Returns:
            str: A message indicating which models were modified and any errors.
        """
        tic = time.time()
        successful_models = []
        failed_models = []

        for model_name in model_names:
            try:
                node = self.talk2view_core.root.slicer_util_getNode(model_name)
                if node and node.IsA('vtkMRMLModelNode'):
                    displayNode = node.GetDisplayNode()
                    if not displayNode:
                        displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLModelDisplayNode')
                        node.SetAndObserveDisplayNodeID(displayNode.GetID())
                    displayNode.SetVisibility2D(visible)
                    successful_models.append(model_name)
                else:
                    logging.warning(f"set_model_slice_visibility: '{model_name}' is not a model node")
                    failed_models.append(f"{model_name} (not a model node)")
            except ValueError as e:
                logging.warning(f"set_model_slice_visibility: model '{model_name}' not found: {e}")
                failed_models.append(f"{model_name} (not found)")

        result_parts = []
        if successful_models:
            action = "shown" if visible else "hidden"
            result_parts.append(f"Slice intersections {action} for {len(successful_models)} models: {', '.join(successful_models)}")
        if failed_models:
            result_parts.append(f"Could not modify models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"set_model_slice_visibility executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    def set_model_representation(self, model_names: list[str], representation: str, show_edges: bool = False) -> str:
        """
        Action tool: Sets the 3D rendering representation of model nodes.

        Representations:
        - 'surface'   : solid filled surface (Slicer default)
        - 'wireframe' : triangle edges only, no fill
        - 'points'    : mesh vertices only

        Combine representation='surface' with show_edges=True for the
        'Surface with edges' Slicer preset, useful for inspecting mesh
        quality or topology.

        Args:
            model_names (list[str]): A list of model node names to modify.
            representation (str): 'surface' | 'wireframe' | 'points'.
            show_edges (bool): If True, overlay triangle edges (only
                meaningful with representation='surface').

        Returns:
            str: A message indicating which models were modified and any errors.
        """
        tic = time.time()

        rep_map = {'points': 0, 'wireframe': 1, 'surface': 2}
        rep_lower = representation.lower()
        if rep_lower not in rep_map:
            msg = f"Invalid representation '{representation}'. Use 'surface', 'wireframe', or 'points'."
            logging.warning(f"set_model_representation: {msg}")
            return f"Error: {msg}"
        rep_value = rep_map[rep_lower]

        successful_models = []
        failed_models = []

        for model_name in model_names:
            try:
                node = self.talk2view_core.root.slicer_util_getNode(model_name)
                if node and node.IsA('vtkMRMLModelNode'):
                    displayNode = node.GetDisplayNode()
                    if not displayNode:
                        displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLModelDisplayNode')
                        node.SetAndObserveDisplayNodeID(displayNode.GetID())
                    displayNode.SetRepresentation(rep_value)
                    displayNode.SetEdgeVisibility(1 if show_edges else 0)
                    successful_models.append(model_name)
                else:
                    logging.warning(f"set_model_representation: '{model_name}' is not a model node")
                    failed_models.append(f"{model_name} (not a model node)")
            except ValueError as e:
                logging.warning(f"set_model_representation: model '{model_name}' not found: {e}")
                failed_models.append(f"{model_name} (not found)")

        result_parts = []
        if successful_models:
            descriptor = rep_lower
            if rep_lower == 'surface' and show_edges:
                descriptor = "surface with edges"
            result_parts.append(f"Set representation to '{descriptor}' for {len(successful_models)} models: {', '.join(successful_models)}")
        if failed_models:
            result_parts.append(f"Could not modify models: {', '.join(failed_models)}")

        toc = time.time()
        logging.info(f"set_model_representation executed in {toc - tic:.4f} seconds")
        return "\n".join(result_parts) if result_parts else "No models were modified"

    # System and context tools
    def get_system_info(self) -> str:
        """
        Context tool: Retrieves system information about the Slicer application.

        Returns:
            str: System version, build information, and application details.
        """
        tic = time.time()
        info = []

        # Get application version and build info
        app = self.talk2view_core.root.slicer_app
        info.append(f"Application Name: {app.applicationName}")
        info.append(f"Application Version: {app.applicationVersion}")
        info.append(f"Revision: {app.repositoryRevision}")
        info.append(f"Build Date: {app.buildDate}")

        # Get platform information
        import platform
        info.append(f"Platform: {platform.system()} {platform.release()}")
        info.append(f"Architecture: {platform.machine()}")

        toc = time.time()
        logging.info(f"get_system_info executed in {toc - tic:.4f} seconds")
        return "\\n".join(info)

    # File operations tools
    def load_file(self, file_path: str, node_name: str = "") -> str:
        """
        Action tool: Loads a file into the Slicer scene. Auto-detects file type.
        Supports volumes (NIfTI, NRRD, DICOM), models (STL, OBJ, PLY, VTK, VTP),
        segmentations, transforms, and other formats supported by 3D Slicer.

        Args:
            file_path (str): Path to the file to load.
            node_name (str, optional): Name to assign to the loaded node.

        Returns:
            str: Success message with loaded node information or error message.
        """
        tic = time.time()
        # Use loadNodeFromFile which auto-detects file type
        node = self.talk2view_core.root.slicer_util_loadNodeFromFile(file_path)

        if node:
            if node_name:
                node.SetName(node_name)

            toc = time.time()
            logging.info(f"load_file executed in {toc - tic:.4f} seconds")
            return f"Successfully loaded file '{file_path}' as node '{node.GetName()}' ({node.GetClassName()})"
        else:
            return f"Failed to load file '{file_path}'"

    def save_file(self, node_name: str, file_path: str) -> str:
        """
        Action tool: Saves a node to a file.
        Shows a confirmation dialog to the user before saving.

        Args:
            node_name (str): Name of the node to save.
            file_path (str): Path where to save the file.

        Returns:
            str: Success, cancellation, or error message.
        """
        node = self.talk2view_core.root.slicer_util_getNode(node_name)
        if not node:
            return f"Error: No node found with name '{node_name}'"

        confirmed = self.talk2view_core.root.slicer_util_confirmOkCancelDisplay(
            f"Save '{node_name}' to '{file_path}'?", "Save File"
        )
        if not confirmed:
            return f"User cancelled saving '{node_name}'"

        tic = time.time()
        success = self.talk2view_core.root.slicer_util_saveNode(node, file_path)

        toc = time.time()
        logging.info(f"save_file executed in {toc - tic:.4f} seconds")

        if success:
            return f"Successfully saved node '{node_name}' to '{file_path}'"
        else:
            return f"Failed to save node '{node_name}' to '{file_path}'"

    def save_scene(self) -> str:
        """
        Action tool: Opens Slicer's Save Data dialog so the user can choose what and where to save.

        Returns:
            str: Whether the user saved or cancelled.
        """
        tic = time.time()
        saved = self.talk2view_core.root.slicer_util_openSaveDataDialog()

        toc = time.time()
        logging.info(f"save_scene executed in {toc - tic:.4f} seconds")

        if saved:
            return "User saved the scene"
        else:
            return "User cancelled save"

    def import_dicom_directory(self, dicom_directory: str) -> str:
        """
        Action tool: Index DICOM files from a directory into Slicer's persistent
        DICOM database.

        Use this ONLY when DICOM files exist on disk but are NOT yet in the
        Slicer database. If query_dicom_database already lists the case you
        need, call load_dicom_patient / load_dicom_study / load_dicom_series
        instead — do not re-import.

        Files are indexed (so they appear in the DICOM Browser and can be
        loaded later) but are NOT loaded into the scene. Use load_dicom_series,
        load_dicom_study, or load_dicom_patient afterwards to load specific
        data into the scene.

        Re-importing a directory whose files are already indexed is a no-op
        at the database level — the response will report "no new patients."

        For IDC downloads, use idc_download instead — it composes the
        download + import + load pipeline.

        Args:
            dicom_directory: Absolute path to a directory of DICOM files.

        Returns:
            str: Message describing what was indexed.
        """
        tic = time.time()
        result = self.talk2view_core.root.import_dicom_directory(dicom_directory, False)
        toc = time.time()
        logging.info(f"import_dicom_directory executed in {toc - tic:.4f} seconds")

        if not result.get("success"):
            return f"Error indexing DICOM: {result.get('message', 'Unknown error')}"
        return result["message"]

    def query_dicom_database(self) -> str:
        """
        Query tool: List patients, studies, and series currently in Slicer's
        DICOM database.

        ALWAYS call this before claiming the database is empty, before
        importing a directory, and before any load_dicom_* call. Returns
        the exact patient names, study UIDs, and series UIDs needed by the
        load_dicom_* tools.

        Returns:
            str: Formatted tree of patients > studies > series with names,
                 dates, modalities, and UIDs. Reports "empty" if no data.
        """
        tic = time.time()
        result = self.talk2view_core.root.query_dicom_database()
        toc = time.time()
        logging.info(f"query_dicom_database executed in {toc - tic:.4f} seconds")

        if not result.get("success"):
            return "DICOM database is not open."

        patients = result.get("patients", [])
        if not patients:
            return "DICOM database is empty. Use import_dicom_directory or idc_download to add data."

        lines = [f"DICOM database contents ({result['patient_count']} patient(s)):"]
        for p in patients:
            lines.append(
                f"- Patient: {p['patient_name']} "
                f"(id={p['patient_id']}, uid={p['patient_uid']})"
            )
            for s in p.get("studies", []):
                lines.append(
                    f"    Study: {s['study_description'] or '(no description)'} "
                    f"date={s['study_date']} uid={s['study_uid']}"
                )
                for series in s.get("series", []):
                    lines.append(
                        f"      Series #{series['series_number']} "
                        f"[{series['modality']}] "
                        f"{series['series_description'] or '(no description)'} "
                        f"({series['instance_count']} instances) "
                        f"uid={series['series_uid']}"
                    )
        return "\n".join(lines)

    def load_dicom_patient(self, patient_name: str = "", patient_uid: str = "") -> str:
        """
        Action tool: Load all studies/series for one patient from the DICOM
        database into the scene.

        Specify exactly one of patient_name or patient_uid. Use
        query_dicom_database first to discover the values.

        Args:
            patient_name: Patient name as shown in the DICOM database.
            patient_uid: Internal DICOM database patient UID.

        Returns:
            str: Success message naming the loaded nodes, or error message.
        """
        tic = time.time()
        result = self.talk2view_core.root.load_dicom_patient(patient_uid, patient_name)
        toc = time.time()
        logging.info(f"load_dicom_patient executed in {toc - tic:.4f} seconds")

        if not result.get("success"):
            return f"Error: {result.get('message', 'Unknown error')}"
        return result["message"]

    def load_dicom_study(self, study_uid: str) -> str:
        """
        Action tool: Load all series in one study from the DICOM database
        into the scene.

        Use query_dicom_database first to find the study_uid.
        """
        tic = time.time()
        result = self.talk2view_core.root.load_dicom_study(study_uid)
        toc = time.time()
        logging.info(f"load_dicom_study executed in {toc - tic:.4f} seconds")

        if not result.get("success"):
            return f"Error: {result.get('message', 'Unknown error')}"
        return result["message"]

    def load_dicom_series(self, series_uid: str) -> str:
        """
        Action tool: Load one DICOM series from the database into the scene.

        Use query_dicom_database first to find the series_uid.
        """
        tic = time.time()
        result = self.talk2view_core.root.load_dicom_series(series_uid)
        toc = time.time()
        logging.info(f"load_dicom_series executed in {toc - tic:.4f} seconds")

        if not result.get("success"):
            return f"Error: {result.get('message', 'Unknown error')}"
        return result["message"]

    def clear_scene(self) -> str:
        """
        Action tool: Clears all data from the current scene.
        Shows a confirmation dialog to the user before clearing.

        Returns:
            str: Success or cancellation message.
        """
        confirmed = self.talk2view_core.root.slicer_util_confirmOkCancelDisplay(
            "Clear all data from the scene?", "Clear Scene"
        )
        if not confirmed:
            return "User cancelled clear"

        tic = time.time()
        self.talk2view_core.root.slicer_mrmlScene_Clear(0)

        toc = time.time()
        logging.info(f"clear_scene executed in {toc - tic:.4f} seconds")
        return "Successfully cleared scene"

    # Screenshot and image capture tools
    def take_screenshot(self, file_path: str = None) -> str:
        """
        Action tool: Takes a screenshot of the entire Slicer application window.

        Args:
            file_path (str, optional): Path to save the screenshot. If not provided, returns image data.

        Returns:
            str: Success message with file path or image data.
        """
        tic = time.time()
        if file_path:
            success = self.talk2view_core.root.slicer_util_takeScreenshot(file_path)
            toc = time.time()
            logging.info(f"take_screenshot executed in {toc - tic:.4f} seconds")
            if success:
                return f"Screenshot saved to '{file_path}'"
            else:
                return f"Failed to save screenshot to '{file_path}'"
        else:
            # Return screenshot as data
            image_data = self.talk2view_core.root.slicer_util_takeScreenshot()
            toc = time.time()
            logging.info(f"take_screenshot executed in {toc - tic:.4f} seconds")
            return f"Screenshot captured (size: {len(image_data)} bytes)"

    def capture_3d_view(self, file_path: str = None) -> str:
        """
        Action tool: Captures the current 3D view as an image.

        Args:
            file_path (str, optional): Path to save the image.

        Returns:
            str: Success message with file path.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)

        if not threeDWidget:
            return "Error: No 3D view available"

        threeDView = threeDWidget.threeDView()

        if file_path:
            self.talk2view_core.root.slicer_util_saveScreenshot(file_path)
            toc = time.time()
            logging.info(f"capture_3d_view executed in {toc - tic:.4f} seconds")
            return f"3D view saved to '{file_path}'"
        else:
            # Capture to temporary file
            import tempfile
            temp_file = tempfile.mktemp(suffix='.png')
            self.talk2view_core.root.slicer_util_saveScreenshot(temp_file)
            toc = time.time()
            logging.info(f"capture_3d_view executed in {toc - tic:.4f} seconds")
            return f"3D view captured to '{temp_file}'"

    def capture_slice_view(self, slice_name: str = 'Red', file_path: str = None) -> str:
        """
        Action tool: Captures a specific slice view as an image.

        Args:
            slice_name (str): Name of the slice view ('Red', 'Yellow', or 'Green').
            file_path (str, optional): Path to save the image.

        Returns:
            str: Success message with file path.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        sliceWidget = layoutManager.sliceWidget(slice_name)

        if not sliceWidget:
            return f"Error: Slice view '{slice_name}' not found"

        sliceView = sliceWidget.sliceView()

        if file_path:
            self.talk2view_core.root.slicer_util_saveScreenshot(file_path)
            toc = time.time()
            logging.info(f"capture_slice_view executed in {toc - tic:.4f} seconds")
            return f"Slice view '{slice_name}' saved to '{file_path}'"
        else:
            # Capture to temporary file
            import tempfile
            temp_file = tempfile.mktemp(suffix='.png')
            self.talk2view_core.root.slicer_util_saveScreenshot(temp_file)
            toc = time.time()
            logging.info(f"capture_slice_view executed in {toc - tic:.4f} seconds")
            return f"Slice view '{slice_name}' captured to '{temp_file}'"

    # Python execution tool
    def execute_python(self, code: str) -> str:
        """
        Action tool: Executes Python code in the Slicer Python environment.
        This provides direct access to the Slicer API for advanced operations.

        Args:
            code (str): Python code to execute.

        Returns:
            str: Output from the executed code or error message.
        """
        raise NotImplementedError("Arbitrary Python code execution is disabled for security")
        tic = time.time()
        result = self.talk2view_core.root.execute_python_code(code)
        toc = time.time()
        logging.info(f"execute_python executed in {toc - tic:.4f} seconds")
        return result

    # Volume tools
    def get_volume_info(self, volume_name: str) -> str:
        """
        Context tool: Retrieves detailed information about a specific volume node.

        IMPORTANT: You MUST use list_volume_nodes() first to get the exact volume name before calling this tool.

        Args:
            volume_name (str): Exact name of the volume node as returned by list_volume_nodes().

        Returns:
            str: Formatted information about the volume including dimensions, spacing, and other properties.
        """
        tic = time.time()

        node = self.talk2view_core.root.slicer_util_getNode(volume_name)

        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            return f"Error: Volume '{volume_name}' not found"

        info = []
        info.append(f"Volume: {node.GetName()}")

        imageData = node.GetImageData()
        if imageData:
            dims = imageData.GetDimensions()
            spacing = node.GetSpacing()
            info.append(f"  Dimensions: {dims[0]} x {dims[1]} x {dims[2]} voxels")
            info.append(f"  Spacing: {spacing[0]:.3f} x {spacing[1]:.3f} x {spacing[2]:.3f} mm")

            # Use server-side helper because GetRASBounds uses an
            # output parameter (double[6]) that doesn't work over RPyC
            bounds = self.talk2view_core.root.get_node_bounds(volume_name, ras_bounds=True)
            info.append(f"  RAS Bounds: [{bounds[0]:.1f}, {bounds[1]:.1f}] x [{bounds[2]:.1f}, {bounds[3]:.1f}] x [{bounds[4]:.1f}, {bounds[5]:.1f}]")

            # Get data type
            scalarType = imageData.GetScalarTypeAsString()
            info.append(f"  Data Type: {scalarType}")

            # Get scalar range
            scalarRange = imageData.GetScalarRange()
            info.append(f"  Scalar Range: [{scalarRange[0]:.1f}, {scalarRange[1]:.1f}]")
        else:
            info.append("  No image data available")

        toc = time.time()
        logging.info(f"get_volume_info executed in {toc - tic:.4f} seconds")
        return "\n".join(info)

    def set_volume_visibility(self, volume_name: str, visible: bool) -> str:
        """
        Action tool: Shows or hides a volume in slice views.

        IMPORTANT: You MUST use list_volume_nodes() first to get the exact volume name before calling this tool.

        Args:
            volume_name (str): Exact name of the volume node as returned by list_volume_nodes().
            visible (bool): True to show, False to hide.

        Returns:
            str: Success or error message.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(volume_name)

        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            return f"Error: Volume '{volume_name}' not found"

        displayNode = node.GetDisplayNode()
        if not displayNode:
            displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLScalarVolumeDisplayNode')
            node.SetAndObserveDisplayNodeID(displayNode.GetID())

        displayNode.SetVisibility(visible)

        toc = time.time()
        logging.info(f"set_volume_visibility executed in {toc - tic:.4f} seconds")
        return f"Volume '{volume_name}' is now {'visible' if visible else 'hidden'}"

    def set_volume_opacity(self, volume_name: str, opacity: float = 0.5) -> str:
        """
        Action tool: Sets the opacity of a volume.

        IMPORTANT: You MUST use list_volume_nodes() first to get the exact volume name before calling this tool.

        Args:
            volume_name (str): Exact name of the volume node as returned by list_volume_nodes().
            opacity (float): Opacity value from 0.0 to 1.0.

        Returns:
            str: Success or error message.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(volume_name)

        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            return f"Error: Volume '{volume_name}' not found"

        displayNode = node.GetDisplayNode()
        if not displayNode:
            return f"Error: Volume '{volume_name}' has no display node"

        displayNode.SetOpacity(max(0.0, min(1.0, opacity)))

        toc = time.time()
        logging.info(f"set_volume_opacity executed in {toc - tic:.4f} seconds")
        return f"Volume '{volume_name}' opacity set to {opacity}"

    def set_volume_window_level(self, volume_name: str, window: float = None, level: float = None) -> str:
        """
        Action tool: Sets the window/level (brightness/contrast) for a volume.

        IMPORTANT: You MUST use list_volume_nodes() first to get the exact volume name before calling this tool.

        Args:
            volume_name (str): Exact name of the volume node as returned by list_volume_nodes().
            window (float, optional): Window width for contrast.
            level (float, optional): Window level for brightness.

        Returns:
            str: Success message with applied values.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(volume_name)

        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            return f"Error: Volume '{volume_name}' not found"

        displayNode = node.GetDisplayNode()
        if not displayNode:
            return f"Error: Volume '{volume_name}' has no display node"

        if window is not None and level is not None:
            displayNode.SetWindowLevel(window, level)
            displayNode.SetAutoWindowLevel(0)
        else:
            displayNode.SetAutoWindowLevel(1)

        toc = time.time()
        logging.info(f"set_volume_window_level executed in {toc - tic:.4f} seconds")

        if window is not None and level is not None:
            return f"Volume '{volume_name}' window/level set to {window}/{level}"
        else:
            return f"Volume '{volume_name}' set to auto window/level"

    def enable_volume_rendering(self, volume_name: str, preset: str = 'CT-Chest-Contrast-Enhanced') -> str:
        """
        Action tool: Enables 3D volume rendering for a volume with a specific preset.

        IMPORTANT: You MUST use list_volume_nodes() first to get the exact volume name before calling this tool.

        Args:
            volume_name (str): Exact name of the volume node as returned by list_volume_nodes().
            preset (str): Rendering preset name. Options include:
                - 'CT-Chest-Contrast-Enhanced'
                - 'CT-Bones'
                - 'CT-Muscle'
                - 'CT-Soft-Tissue'
                - 'MR-Default'
                - 'MR-Angio'

        Returns:
            str: Success or error message.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(volume_name)

        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            return f"Error: Volume '{volume_name}' not found"

        # Get or create volume rendering display node
        volRenLogic = self.talk2view_core.root.slicer_modules_volumerendering_logic()
        displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(node)

        if not displayNode:
            return f"Error: Could not create volume rendering for '{volume_name}'"

        # Apply preset
        displayNode.GetVolumePropertyNode().Copy(
            volRenLogic.GetPresetByName(preset)
        )

        # Make visible
        displayNode.SetVisibility(True)

        toc = time.time()
        logging.info(f"enable_volume_rendering executed in {toc - tic:.4f} seconds")
        return f"Volume rendering enabled for '{volume_name}' with preset '{preset}'"

    # Layout and view tools
    def set_layout(self, layout_name: str) -> str:
        """
        Action tool: Changes the view layout of Slicer.

        Args:
            layout_name (str): Layout name. Options include:
                - 'FourUp': Classic 3 slices + 3D view
                - 'OneUp3D': Only 3D view
                - 'OneUpRedSlice': Only Red (axial) slice
                - 'OneUpYellowSlice': Only Yellow (sagittal) slice
                - 'OneUpGreenSlice': Only Green (coronal) slice
                - 'Tabbed3D': Tabbed 3D view
                - 'TabbedSlice': Tabbed slice views
                - 'Dual3D': Two 3D views side by side
                - 'Conventional': 3 slices in row

        Returns:
            str: Success message.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()

        layout_map = {
            'FourUp': 2,
            'OneUp3D': 3,
            'OneUpRedSlice': 4,
            'OneUpYellowSlice': 5,
            'OneUpGreenSlice': 6,
            'Tabbed3D': 7,
            'TabbedSlice': 8,
            'Dual3D': 9,
            'Conventional': 10
        }

        if layout_name in layout_map:
            layoutManager.setLayout(layout_map[layout_name])
            toc = time.time()
            logging.info(f"set_layout executed in {toc - tic:.4f} seconds")
            return f"Layout changed to '{layout_name}'"
        else:
            return f"Error: Unknown layout '{layout_name}'. Available: {', '.join(layout_map.keys())}"

    def reset_views(self) -> str:
        """
        Action tool: Resets all slice views to center on the data and resets the 3D view.

        Returns:
            str: Success message.
        """
        tic = time.time()
        self.center_view()

        # Also reset 3D camera
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        threeDWidget = layoutManager.threeDWidget(0)
        if threeDWidget:
            threeDWidget.threeDView().resetCamera()

        toc = time.time()
        logging.info(f"reset_views executed in {toc - tic:.4f} seconds")
        return "All views have been reset"

    def set_slice_offset(self, slice_name: str, offset: float) -> str:
        """
        Action tool: Sets the offset (position) for a specific slice view.

        Args:
            slice_name (str): Name of the slice ('Red', 'Yellow', or 'Green').
            offset (float): Offset value in mm.

        Returns:
            str: Success message.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        sliceWidget = layoutManager.sliceWidget(slice_name)

        if not sliceWidget:
            return f"Error: Slice view '{slice_name}' not found"

        sliceLogic = sliceWidget.sliceLogic()
        sliceLogic.SetSliceOffset(offset)

        toc = time.time()
        logging.info(f"set_slice_offset executed in {toc - tic:.4f} seconds")
        return f"Slice '{slice_name}' offset set to {offset}mm"

    def fit_slice_to_background(self, slice_name: str = None) -> str:
        """
        Action tool: Fits slice view(s) to show the full extent of the background volume.

        Args:
            slice_name (str, optional): Specific slice to fit ('Red', 'Yellow', 'Green').
                                       If None, fits all slices.

        Returns:
            str: Success message.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()

        if slice_name:
            sliceWidget = layoutManager.sliceWidget(slice_name)
            if sliceWidget:
                sliceWidget.sliceController().fitSliceToBackground()
                result = f"Fitted slice '{slice_name}' to background"
            else:
                result = f"Error: Slice view '{slice_name}' not found"
        else:
            for name in ['Red', 'Yellow', 'Green']:
                sliceWidget = layoutManager.sliceWidget(name)
                if sliceWidget:
                    sliceWidget.sliceController().fitSliceToBackground()
            result = "All slices fitted to background"

        toc = time.time()
        logging.info(f"fit_slice_to_background executed in {toc - tic:.4f} seconds")
        return result

    # Markup and measurement tools
    def create_markup_point(self, name: str, position: list, color: list = None) -> str:
        """
        Action tool: Creates a fiducial/markup point at a specific position.

        Args:
            name (str): Name for the markup point.
            position (list): [x, y, z] coordinates in RAS space.
            color (list, optional): [r, g, b] color values (0.0 to 1.0).

        Returns:
            str: Success message with point ID.
        """
        tic = time.time()
        markupsNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLMarkupsFiducialNode')
        markupsNode.SetName(name)

        # Add point
        markupsNode.AddControlPoint(position[0], position[1], position[2])

        # Set color if provided
        if color and len(color) == 3:
            displayNode = markupsNode.GetDisplayNode()
            if not displayNode:
                displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLMarkupsDisplayNode')
                markupsNode.SetAndObserveDisplayNodeID(displayNode.GetID())
            displayNode.SetSelectedColor(color[0], color[1], color[2])

        toc = time.time()
        logging.info(f"create_markup_point executed in {toc - tic:.4f} seconds")
        return f"Created markup point '{name}' at position ({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})"

    def create_markup_line(self, name: str, start_pos: list, end_pos: list, color: list = None) -> str:
        """
        Action tool: Creates a line measurement between two points.

        Args:
            name (str): Name for the line markup.
            start_pos (list): [x, y, z] coordinates of start point.
            end_pos (list): [x, y, z] coordinates of end point.
            color (list, optional): [r, g, b] color values (0.0 to 1.0).

        Returns:
            str: Success message with distance measurement.
        """
        tic = time.time()
        lineNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLMarkupsLineNode')
        lineNode.SetName(name)

        # Add start and end points
        lineNode.AddControlPoint(start_pos[0], start_pos[1], start_pos[2])
        lineNode.AddControlPoint(end_pos[0], end_pos[1], end_pos[2])

        # Set color if provided
        if color and len(color) == 3:
            displayNode = lineNode.GetDisplayNode()
            if not displayNode:
                displayNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass('vtkMRMLMarkupsDisplayNode')
                lineNode.SetAndObserveDisplayNodeID(displayNode.GetID())
            displayNode.SetSelectedColor(color[0], color[1], color[2])

        # Get distance
        distance = lineNode.GetLineLengthWorld()

        toc = time.time()
        logging.info(f"create_markup_line executed in {toc - tic:.4f} seconds")
        return f"Created line '{name}' with length {distance:.2f}mm"

    def get_markup_points(self, markup_name: str = None) -> str:
        """
        Context tool: Retrieves positions of markup points.

        Args:
            markup_name (str, optional): Name of specific markup node. If None, gets all.

        Returns:
            str: Formatted list of markup points and their positions.
        """
        tic = time.time()
        info = []

        if markup_name:
            node = self.talk2view_core.root.slicer_util_getNode(markup_name)
            if node and 'Markups' in node.GetClassName():
                # Use server-side helper because GetNthControlPointPosition
                # uses an output parameter (double[3]) that doesn't work over RPyC
                points = self.talk2view_core.root.get_markup_control_points(markup_name)
                for i, pt in enumerate(points):
                    info.append(f"  Point {i} '{pt['label']}': ({pt['position'][0]:.1f}, {pt['position'][1]:.1f}, {pt['position'][2]:.1f})")
            else:
                info.append(f"Markup '{markup_name}' not found")
        else:
            markupNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLMarkupsNode')
            if markupNodes:
                for node in markupNodes:
                    name = node.GetName()
                    info.append(f"{name}:")
                    # Use server-side helper for control point positions
                    points = self.talk2view_core.root.get_markup_control_points(name)
                    for i, pt in enumerate(points):
                        info.append(f"  Point {i} '{pt['label']}': ({pt['position'][0]:.1f}, {pt['position'][1]:.1f}, {pt['position'][2]:.1f})")
            else:
                info.append("No markup nodes found")

        toc = time.time()
        logging.info(f"get_markup_points executed in {toc - tic:.4f} seconds")
        return "\n".join(info)

    def set_markup_visibility(self, markup_name: str, visible: bool) -> str:
        """
        Action tool: Shows or hides markup nodes.

        Args:
            markup_name (str): Name of the markup node.
            visible (bool): True to show, False to hide.

        Returns:
            str: Success or error message.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(markup_name)

        if not node or 'Markups' not in node.GetClassName():
            return f"Error: Markup '{markup_name}' not found"

        displayNode = node.GetDisplayNode()
        if displayNode:
            displayNode.SetVisibility(visible)

        toc = time.time()
        logging.info(f"set_markup_visibility executed in {toc - tic:.4f} seconds")
        return f"Markup '{markup_name}' is now {'visible' if visible else 'hidden'}"

    # Transform tools
    def get_transform_info(self) -> str:
        """
        Context tool: Retrieves information about all transform nodes in the scene.

        Returns:
            str: Formatted list of transforms and their properties.
        """
        tic = time.time()
        info = []

        transformNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLTransformNode')
        if transformNodes:
            for node in transformNodes:
                matrix = node.GetMatrixTransformToParent()
                if matrix:
                    info.append(f"{node.GetName()}: Matrix transform")
                else:
                    info.append(f"{node.GetName()}: Non-linear transform")
        else:
            info.append("No transform nodes found")

        toc = time.time()
        logging.info(f"get_transform_info executed in {toc - tic:.4f} seconds")
        return "\n".join(info)

    def apply_transform(self, node_name: str, transform_name: str) -> str:
        """
        Action tool: Applies a transform to a node.

        Args:
            node_name (str): Name of the node to transform.
            transform_name (str): Name of the transform node to apply.

        Returns:
            str: Success or error message.
        """
        tic = time.time()
        node = self.talk2view_core.root.slicer_util_getNode(node_name)
        transform = self.talk2view_core.root.slicer_util_getNode(transform_name)

        if not node:
            return f"Error: Node '{node_name}' not found"
        if not transform or not transform.IsA('vtkMRMLTransformNode'):
            return f"Error: Transform '{transform_name}' not found"

        node.SetAndObserveTransformNodeID(transform.GetID())

        toc = time.time()
        logging.info(f"apply_transform executed in {toc - tic:.4f} seconds")
        return f"Applied transform '{transform_name}' to '{node_name}'"

    def create_transform(self, name: str, translation: list = None, rotation: list = None) -> str:
        """
        Action tool: Creates a new linear transform node.

        Args:
            name (str): Name for the new transform.
            translation (list, optional): [x, y, z] translation in mm.
            rotation (list, optional): [rx, ry, rz] rotation in degrees.

        Returns:
            str: Success message.
        """
        tic = time.time()

        # Use server-side helper because vtk.vtkTransform() can't be
        # constructed over RPyC
        self.talk2view_core.root.SlicerTools_create_linear_transform(name, translation, rotation)

        toc = time.time()
        logging.info(f"create_transform executed in {toc - tic:.4f} seconds")

        result = f"Created transform '{name}'"
        if translation:
            result += f" with translation ({translation[0]}, {translation[1]}, {translation[2]})"
        if rotation:
            result += f" and rotation ({rotation[0]}°, {rotation[1]}°, {rotation[2]}°)"

        return result

    def export_segmentation_to_models(self, segmentation_node_name: str) -> str:
        """
        Action tool: Exports all segments from a segmentation node as separate model nodes.

        This is useful for saving segments as STL files for 3D printing or further processing.
        After export, use save_file() on the resulting model nodes to save them as STL/OBJ/PLY files.

        Args:
            segmentation_node_name (str): Name of the segmentation node to export.

        Returns:
            str: Success message with exported model names, or error message.
        """
        tic = time.time()
        segmentationNode = self.talk2view_core.root.slicer_util_getNode(segmentation_node_name)
        if segmentationNode is None:
            return f"Error: Segmentation node '{segmentation_node_name}' not found"

        # Create a folder in subject hierarchy to hold exported models
        shNode = self.talk2view_core.root.slicer_mrmlScene_GetSubjectHierarchyNode()
        exportFolderItemId = shNode.CreateFolderItem(
            shNode.GetSceneItemID(),
            f"{segmentation_node_name}_models"
        )

        # Use the exposed segmentations logic method
        self.talk2view_core.root.slicer_modules_segmentations_logic_ExportAllSegmentsToModels(
            segmentationNode, exportFolderItemId
        )

        # List the newly created model nodes to confirm export
        modelNodes = self.talk2view_core.root.slicer_util_getNodesByClass('vtkMRMLModelNode')
        model_names = []
        for node in modelNodes:
            # Check if this model is in our export folder
            itemId = shNode.GetItemByDataNode(node)
            if itemId and shNode.GetItemParent(itemId) == exportFolderItemId:
                model_names.append(node.GetName())

        toc = time.time()
        logging.info(f"export_segmentation_to_models executed in {toc - tic:.4f} seconds")

        if model_names:
            return f"Exported {len(model_names)} segment(s) as models: {', '.join(model_names)}"
        return f"No segments exported from '{segmentation_node_name}'"

    def delete_node(self, node_name: str) -> str:
        """
        Action tool: Deletes a node from the scene after user confirmation.

        Shows a confirmation dialog before deleting.

        Args:
            node_name (str): Name of the node to delete.

        Returns:
            str: Success, cancellation, or error message.
        """
        node = self.talk2view_core.root.slicer_util_getNode(node_name)
        if node is None:
            return f"Error: Node '{node_name}' not found"

        confirmed = self.talk2view_core.root.slicer_util_confirmOkCancelDisplay(
            f"Delete '{node_name}' from the scene?", "Delete Node"
        )
        if not confirmed:
            return f"User cancelled deletion of '{node_name}'"

        tic = time.time()
        self.talk2view_core.root.slicer_mrmlScene_RemoveNode(node)

        toc = time.time()
        logging.info(f"delete_node executed in {toc - tic:.4f} seconds")
        return f"Deleted '{node_name}' from scene"

    def show_slices_in_3d(self, visible: bool = True) -> str:
        """
        Action tool: Shows or hides slice planes in the 3D view.

        When enabled, the axial, sagittal, and coronal slice planes become
        visible in the 3D viewer as intersecting planes.

        Args:
            visible (bool): True to show slices in 3D, False to hide them.

        Returns:
            str: Success message.
        """
        tic = time.time()
        layoutManager = self.talk2view_core.root.slicer_app_layoutManager()
        for sliceName in ["Red", "Yellow", "Green"]:
            sliceWidget = layoutManager.sliceWidget(sliceName)
            controller = sliceWidget.sliceController()
            controller.setSliceVisible(visible)

        self.talk2view_core.root.slicer_util_forceRenderAllViews()

        toc = time.time()
        logging.info(f"show_slices_in_3d executed in {toc - tic:.4f} seconds")
        return f"Slice planes {'shown' if visible else 'hidden'} in 3D view"

    def get_docs(self, query: str) -> str:
        """
        Retrieves 3D Slicer documentation from Context7 API and processes it with an LLM.

        Args:
            query: The topic to search for (e.g., 'segmentation', 'volume rendering', 'DICOM')

        Returns:
            str: LLM-processed documentation with references.
        """
        tic = time.time()

        context7_api_key = self._get_context7_api_key()
        if not context7_api_key:
            return "Failed to retrieve Context7 API key. Please ensure you are logged in."

        headers = {"Authorization": f"Bearer {context7_api_key}"}
        results = []
        references = []

        # Fetch code snippets
        self._fetch_code_snippets(query, headers, results, references)

        # Fetch info snippets
        self._fetch_info_snippets(query, headers, results, references)

        if not results:
            logging.info(f"get_docs executed in {time.time() - tic:.4f} seconds")
            return f"No documentation found for topic: {query}"

        logging.info(f"get_docs: Found {len(results)} result items and {len(references)} references")

        context = "\n".join(results)
        response = self._process_docs_with_llm(query, context, references)

        logging.info(f"get_docs executed in {time.time() - tic:.4f} seconds")
        return response

    def _fetch_code_snippets(self, query: str, headers: dict, results: list, references: list) -> None:
        """Fetch code snippets from Context7 API and append to results/references."""
        try:
            url = f"{_CONTEXT7_DOCS_URL}/code/slicer/slicer?type=json&topic={query}"
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return

            snippets = response.json().get("snippets", [])
            if not snippets:
                return

            results.append("=== CODE SNIPPETS ===\n")
            for snippet in snippets:
                ref_num = len(references) + 1
                title = snippet.get("codeTitle", "Untitled")
                page_title = snippet.get("pageTitle", "")
                code_id = snippet.get("codeId", "")
                description = snippet.get("codeDescription", "")
                default_lang = snippet.get("codeLanguage", "")

                # Add reference
                references.append(f"[{ref_num}] {page_title or title}: {code_id or 'No URL'}")

                # Add content
                results.append(f"### [{ref_num}] {title}")
                if page_title:
                    results.append(f"From: {page_title}")
                if description:
                    results.append(description)

                for code_item in snippet.get("codeList", []):
                    lang = code_item.get("language", default_lang)
                    code = code_item.get("code", "")
                    results.append(f"```{lang}\n{code}\n```")
                results.append("")

        except requests.RequestException as e:
            logging.warning(f"Failed to fetch code docs: {e}")

    def _fetch_info_snippets(self, query: str, headers: dict, results: list, references: list) -> None:
        """Fetch info snippets from Context7 API and append to results/references."""
        try:
            url = f"{_CONTEXT7_DOCS_URL}/info/slicer/slicer?type=json&topic={query}"
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return

            snippets = response.json().get("snippets", [])
            if not snippets:
                return

            results.append("=== DOCUMENTATION ===\n")
            for snippet in snippets:
                ref_num = len(references) + 1
                breadcrumb = snippet.get("breadcrumb", "")
                content = snippet.get("content", "")
                page_id = snippet.get("pageId", "")

                # Add reference
                ref_label = breadcrumb or "Documentation"
                references.append(f"[{ref_num}] {ref_label}: {page_id or 'No URL'}")

                # Add content
                results.append(f"### [{ref_num}] {ref_label}")
                if content:
                    results.append(content)
                results.append("")

        except requests.RequestException as e:
            logging.warning(f"Failed to fetch info docs: {e}")

    def _process_docs_with_llm(self, query: str, context: str, references: list) -> str:
        """
        Process documentation context with LLM to generate a helpful response.

        Args:
            query: The user's original query
            context: The documentation context retrieved from Context7
            references: List of reference strings with URLs

        Returns:
            str: LLM-generated response with header, references, and footer.
        """
        header = "*Connector's response using 'SlicerTools.get_docs':*\n---\n"
        references_section = "\n\n---\n**References:**\n" + "\n".join(references) if references else ""
        footer = "\n\n---\n*Generated using 3D Slicer documentation via Context7. Always verify code examples.*"

        def format_response(content: str) -> str:
            return header + content + references_section + footer

        # Check for API key availability
        if not self.supabase_manager:
            logging.warning("SlicerTools: supabase_manager not set, returning raw context")
            return format_response(context)

        api_key = self.supabase_manager.get_litellm_api_key()
        if not api_key:
            logging.warning("SlicerTools: No API key found, returning raw context")
            return format_response(context)

        # Call LLM
        try:
            response = requests.post(
                _LITELLM_URL,
                headers={
                    'Content-Type': 'application/json',
                    'x-litellm-api-key': f'Bearer {api_key}'
                },
                json={
                    "model": "openai/gpt-4.1",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a 3D Slicer documentation assistant. Answer the user's query "
                                "using the provided context. Cite reference numbers in brackets (e.g., [1], [2]). "
                                "Format code in ```python blocks. Use **bold** for emphasis, not # headers. "
                                "Be concise."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Query: {query}\n\nContext:\n{context}"
                        }
                    ],
                    "max_tokens": 2048
                },
                timeout=30
            )
            response.raise_for_status()
            llm_response = response.json()['choices'][0]['message']['content']
            return format_response(llm_response)

        except requests.RequestException as e:
            logging.error(f"SlicerTools: Failed to process docs with LLM: {e}")
            return format_response(context)

    # =========================================================================
    # Segment Editor Effect Methods
    # =========================================================================

    def create_segmentation(self, segmentation_name: str = "Segmentation",
                            segment_name: str = "Segment_1",
                            reference_volume_name: str = "",
                            color_red: float = -1.0,
                            color_green: float = -1.0,
                            color_blue: float = -1.0) -> str:
        """
        Action tool: Creates a new segmentation node, optionally with an initial segment.

        Use when user says:
        - "create a new segmentation", "start segmenting"
        - "I want to draw/paint a segment", "let me segment"
        - "create a segmentation called X with a blue segment called Y"
        - Any request to use segment editor tools when no segmentation exists

        Args:
            segmentation_name: Name for the new segmentation node
            segment_name: Name for initial segment. Use descriptive name like 'Liver'.
                          Default 'Segment_1' matches Slicer behavior. Use empty string for no initial segment.
            reference_volume_name: Volume for geometry reference, or empty for first available
            color_red: Red (0.0-1.0) for segment color, -1 for Slicer default
            color_green: Green (0.0-1.0) for segment color, -1 for Slicer default
            color_blue: Blue (0.0-1.0) for segment color, -1 for Slicer default

        Returns:
            str: Status message with created node and segment names
        """
        tic = time.time()

        # Ensure we're in a segmentation module
        self._ensure_segmentation_module_active()

        # Check if a node with this name already exists and generate unique name if needed
        existing_nodes = self.talk2view_core.root.slicer_mrmlScene_GetNodesByName(segmentation_name)
        if existing_nodes.GetNumberOfItems() > 0:
            # Generate unique name by appending a number
            base_name = segmentation_name
            counter = 2
            while True:
                segmentation_name = f"{base_name}_{counter}"
                existing = self.talk2view_core.root.slicer_mrmlScene_GetNodesByName(segmentation_name)
                if existing.GetNumberOfItems() == 0:
                    break
                counter += 1

        # Create new segmentation node
        segmentationNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass(
            "vtkMRMLSegmentationNode"
        )
        segmentationNode.SetName(segmentation_name)

        # Set reference geometry from a volume if available
        volumeNode, error = self._get_volume_node(reference_volume_name)
        if error and reference_volume_name:
            # User specified a volume that doesn't exist - return helpful error
            return f"Error: {error}"

        if volumeNode:
            segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

        # Create display node for visualization
        segmentationNode.CreateDefaultDisplayNodes()

        # Add initial segment if name is provided
        segmentation = segmentationNode.GetSegmentation()
        segment_created = False
        segmentId = None
        if segment_name:
            # AddEmptySegment(segmentId, segmentName, color) - first arg is ID, second is name
            segmentId = segmentation.AddEmptySegment("", segment_name)
            segment_created = True

            # Set color if specified (all components must be valid 0.0-1.0)
            if color_red >= 0 and color_green >= 0 and color_blue >= 0:
                segment = segmentation.GetSegment(segmentId)
                if segment:
                    segment.SetColor(color_red, color_green, color_blue)

        # Set the new segmentation as active in the segment editor widget
        segmentEditorWidget, segmentEditorNode = self._get_segment_editor_widget_and_node()
        segmentEditorWidget.setSegmentationNode(segmentationNode)
        if volumeNode:
            segmentEditorWidget.setSourceVolumeNode(volumeNode)
        # Select the segment if one was created
        if segment_name and segment_created:
            segmentEditorNode.SetSelectedSegmentID(segmentId)

        toc = time.time()
        logging.info(f"create_segmentation executed in {toc - tic:.4f} seconds")

        result = f"Created segmentation '{segmentation_name}'"
        if segment_created:
            result += f" with segment '{segment_name}'"
            if color_red >= 0 and color_green >= 0 and color_blue >= 0:
                result += f" (color: RGB({color_red:.2f},{color_green:.2f},{color_blue:.2f}))"
        if volumeNode:
            result += f" (reference: '{volumeNode.GetName()}')"
        return result

    def convert_labelmap_to_segmentation(self, labelmap_node_name: str, segmentation_name: str = "") -> str:
        """
        Action tool: Converts a labelmap volume node to a new segmentation node.

        Each unique non-zero label value in the labelmap becomes a separate
        segment. Useful after loading a labelmap NRRD that came from another
        tool (e.g. NNInteractive batch output, ground-truth annotation files,
        external segmentation pipelines).

        Use when user says:
        - "convert this labelmap to a segmentation"
        - "import labelmap.nrrd as a segmentation"
        - "I have a labelmap volume, make it a segmentation node"

        Args:
            labelmap_node_name: Name of an existing vtkMRMLLabelMapVolumeNode.
                Use list_volume_nodes() to discover, or load_labelmap_volume()
                to load one first.
            segmentation_name: Name for the new segmentation node. If empty,
                defaults to '<labelmap_name>-segmentation'. A unique suffix is
                appended if the name already exists.

        Returns:
            str: Status with the new segmentation node name and segment count.
        """
        tic = time.time()

        # Validate labelmap node
        try:
            labelmapNode = self.talk2view_core.root.slicer_util_getNode(labelmap_node_name)
        except ValueError as e:
            msg = f"Labelmap node '{labelmap_node_name}' not found"
            logging.warning(f"convert_labelmap_to_segmentation: {msg}: {e}")
            return f"Error: {msg}"

        if not labelmapNode.IsA('vtkMRMLLabelMapVolumeNode'):
            msg = (f"Node '{labelmap_node_name}' is not a labelmap volume "
                   f"(found {labelmapNode.GetClassName()}). Load with "
                   f"load_labelmap_volume, or convert via the Volumes module.")
            logging.warning(f"convert_labelmap_to_segmentation: {msg}")
            return f"Error: {msg}"

        # Default and uniquify the segmentation name
        if not segmentation_name:
            segmentation_name = f"{labelmap_node_name}-segmentation"

        existing = self.talk2view_core.root.slicer_mrmlScene_GetNodesByName(segmentation_name)
        if existing.GetNumberOfItems() > 0:
            base_name = segmentation_name
            counter = 2
            while True:
                segmentation_name = f"{base_name}_{counter}"
                existing = self.talk2view_core.root.slicer_mrmlScene_GetNodesByName(segmentation_name)
                if existing.GetNumberOfItems() == 0:
                    break
                counter += 1

        # Create new segmentation node
        segmentationNode = self.talk2view_core.root.slicer_mrmlScene_AddNewNodeByClass(
            "vtkMRMLSegmentationNode"
        )
        segmentationNode.SetName(segmentation_name)
        segmentationNode.CreateDefaultDisplayNodes()

        # Get Segmentations module logic
        try:
            segmentationsLogic = self.talk2view_core.root.slicer_util_getModuleLogic("Segmentations")
        except Exception as e:
            msg = "Segmentations module logic not available"
            logging.warning(f"convert_labelmap_to_segmentation: {msg}: {e}")
            try:
                self.talk2view_core.root.slicer_mrmlScene_RemoveNode(segmentationNode)
            except Exception as cleanup_err:
                logging.warning(f"convert_labelmap_to_segmentation: cleanup of empty segmentation failed: {cleanup_err}")
            return f"Error: {msg}"

        if not segmentationsLogic:
            msg = "Segmentations module logic returned None"
            logging.warning(f"convert_labelmap_to_segmentation: {msg}")
            try:
                self.talk2view_core.root.slicer_mrmlScene_RemoveNode(segmentationNode)
            except Exception as cleanup_err:
                logging.warning(f"convert_labelmap_to_segmentation: cleanup of empty segmentation failed: {cleanup_err}")
            return f"Error: {msg}"

        # Run the conversion
        try:
            success = segmentationsLogic.ImportLabelmapToSegmentationNode(labelmapNode, segmentationNode)
        except Exception as e:
            msg = f"ImportLabelmapToSegmentationNode raised: {e}"
            logging.warning(f"convert_labelmap_to_segmentation: {msg}")
            try:
                self.talk2view_core.root.slicer_mrmlScene_RemoveNode(segmentationNode)
            except Exception as cleanup_err:
                logging.warning(f"convert_labelmap_to_segmentation: cleanup of empty segmentation failed: {cleanup_err}")
            return f"Error: {msg}"

        if not success:
            msg = "ImportLabelmapToSegmentationNode returned False"
            logging.warning(f"convert_labelmap_to_segmentation: {msg}")
            try:
                self.talk2view_core.root.slicer_mrmlScene_RemoveNode(segmentationNode)
            except Exception as cleanup_err:
                logging.warning(f"convert_labelmap_to_segmentation: cleanup of empty segmentation failed: {cleanup_err}")
            return f"Error: {msg}"

        n = segmentationNode.GetSegmentation().GetNumberOfSegments()

        toc = time.time()
        logging.info(f"convert_labelmap_to_segmentation executed in {toc - tic:.4f} seconds")

        return (f"Converted labelmap '{labelmap_node_name}' to segmentation "
                f"'{segmentation_name}' ({n} segment{'s' if n != 1 else ''}).")

    def add_segment(self, segmentation_node_name: str, segment_name: str,
                    color_red: float = -1.0, color_green: float = -1.0,
                    color_blue: float = -1.0) -> str:
        """
        Action tool: Adds a new segment to an existing segmentation.

        Use when user says:
        - "add a new segment called Spine", "create another segment"
        - "add a blue segment called Tumor"
        - "I need another segment for the liver"

        Args:
            segmentation_node_name: Name of the existing segmentation node
            segment_name: Name for the new segment (use descriptive names like 'Liver', 'Spine')
            color_red: Red (0.0-1.0), -1 for Slicer default auto-color
            color_green: Green (0.0-1.0), -1 for Slicer default auto-color
            color_blue: Blue (0.0-1.0), -1 for Slicer default auto-color

        Returns:
            str: Status message with segment name
        """
        tic = time.time()

        try:
            segmentationNode = self.talk2view_core.root.slicer_util_getNode(segmentation_node_name)
        except ValueError:
            segNodes = self.talk2view_core.root.slicer_util_getNodesByClass("vtkMRMLSegmentationNode")
            if segNodes:
                available = [n.GetName() for n in segNodes]
                return f"Error: Segmentation '{segmentation_node_name}' not found. Available: {available}"
            else:
                return f"Error: Segmentation '{segmentation_node_name}' not found. No segmentations in scene."

        segmentation = segmentationNode.GetSegmentation()
        # AddEmptySegment(segmentId, segmentName, color) - first arg is ID, second is name
        segmentId = segmentation.AddEmptySegment("", segment_name)

        # Set color if specified (all components must be valid 0.0-1.0)
        color_set = False
        if color_red >= 0 and color_green >= 0 and color_blue >= 0:
            segment = segmentation.GetSegment(segmentId)
            if segment:
                segment.SetColor(color_red, color_green, color_blue)
                color_set = True

        toc = time.time()
        logging.info(f"add_segment executed in {toc - tic:.4f} seconds")

        result = f"Added segment '{segment_name}' to '{segmentation_node_name}'"
        if color_set:
            result += f" (color: RGB({color_red:.2f},{color_green:.2f},{color_blue:.2f}))"
        return result

    def select_segment(self, segmentation_node_name: str, segment_name: str) -> str:
        """
        Action tool: Sets the active segment for subsequent paint / threshold /
        NNInteractive / adaptive-brush operations.

        Use when:
        - Multiple segments exist and you need a specific one to be current
        - Switching segments mid-workflow ("now work on Tumor instead of Ventricle")
        - After add_segment, before any segment-editor effect on that new segment

        The selection persists until another segment is selected (manually or by
        another tool call). Side effect: ensures a segmentation module is active
        (SlicerNNInteractive or SegmentEditor, whichever is available).

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to make active

        Returns:
            str: Confirmation, or an error listing the available segments.
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            logging.warning(f"select_segment: {result[3]}")
            return f"Error: {result[3]}"

        toc = time.time()
        logging.info(f"select_segment executed in {toc - tic:.4f} seconds")

        return f"Selected segment '{segment_name}' in '{segmentation_node_name}'. Subsequent edit operations will target this segment."

    def _ensure_segmentation_module_active(self):
        """
        Ensure a segmentation-related module is active.
        Prefers SlicerNNInteractive if available, falls back to SegmentEditor.
        Does nothing if already in one of these modules.
        """
        # Get current module name (selectedModule returns the module name as a string)
        currentModuleName = self.talk2view_core.root.slicer_util_selectedModule()
        if not isinstance(currentModuleName, str):
            # In case it returns a module object in some Slicer versions
            currentModuleName = currentModuleName.name if currentModuleName else ""

        # Check if already in a segmentation module
        segmentation_modules = ["SegmentEditor", "SlicerNNInteractive", "NNInteractive"]
        if currentModuleName in segmentation_modules:
            return  # Already in a segmentation module

        # Try to switch to SlicerNNInteractive first, fall back to SegmentEditor
        moduleNames = self.talk2view_core.root.slicer_util_moduleNames()
        if "SlicerNNInteractive" in moduleNames or "NNInteractive" in moduleNames:
            target_module = "SlicerNNInteractive" if "SlicerNNInteractive" in moduleNames else "NNInteractive"
            self.talk2view_core.root.slicer_util_selectModule(target_module)
        else:
            self.talk2view_core.root.slicer_util_selectModule("SegmentEditor")

    def _get_segment_editor_widget_and_node(self):
        """Helper to get segment editor widget and node."""
        segmentEditorWidget = self.talk2view_core.root.slicer_modules_segmenteditor_widget()
        segmentEditorNode = self.talk2view_core.root.slicer_modules_segmenteditor_node()
        # Connect widget to node
        segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
        return segmentEditorWidget, segmentEditorNode

    def _setup_segment_editor(self, segmentation_node_name, segment_name):
        """
        Helper to set up segment editor for a specific segment.
        Returns (segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId)
        or (None, None, None, error_message) if setup fails.
        """
        # Ensure we're in a segmentation module
        self._ensure_segmentation_module_active()

        segmentEditorWidget, segmentEditorNode = self._get_segment_editor_widget_and_node()

        # Get segmentation node with helpful error if not found
        try:
            segmentationNode = self.talk2view_core.root.slicer_util_getNode(segmentation_node_name)
        except ValueError:
            # List available segmentations
            segNodes = self.talk2view_core.root.slicer_util_getNodesByClass("vtkMRMLSegmentationNode")
            if segNodes:
                available = [n.GetName() for n in segNodes]
                return None, None, None, f"Segmentation '{segmentation_node_name}' not found. Available: {available}"
            else:
                return None, None, None, f"Segmentation '{segmentation_node_name}' not found. No segmentations in scene."

        segmentEditorWidget.setSegmentationNode(segmentationNode)

        # Set source volume if available via widget
        volumeNodes = self.talk2view_core.root.slicer_util_getNodesByClass("vtkMRMLScalarVolumeNode")
        if volumeNodes:
            segmentEditorWidget.setSourceVolumeNode(volumeNodes[0])

        # Get segment ID with helpful error if not found
        segmentation = segmentationNode.GetSegmentation()
        segmentId = segmentation.GetSegmentIdBySegmentName(segment_name)
        if not segmentId:
            # List available segments
            numSegments = segmentation.GetNumberOfSegments()
            available = [segmentation.GetNthSegment(i).GetName() for i in range(numSegments)]
            return None, None, None, f"Segment '{segment_name}' not found. Available segments: {available}"

        segmentEditorNode.SetSelectedSegmentID(segmentId)

        return segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId

    def segment_editor_activate(self, segmentation_node_name: str, segment_name: str,
                                 effect_name: str, brush_size_mm: float = 3.0) -> str:
        """
        Action tool: Activates an interactive segment editor effect for user interaction.

        Use when user says:
        - "let me paint on the segment", "I want to draw on the segment"
        - "activate paint tool", "turn on erase mode"
        - "let me manually edit", "I'll fix it myself"

        The effect stays active until deactivated, allowing the user to interact
        with slice views using mouse. Call segment_editor_deactivate when done.

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to edit
            effect_name: Effect to activate: 'paint', 'draw', 'erase', 'scissors', 'level_tracing'
            brush_size_mm: Brush size in mm (for paint/erase effects)

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Map friendly names to Slicer effect names
        effect_name_map = {
            'paint': 'Paint',
            'draw': 'Draw',
            'erase': 'Erase',
            'scissors': 'Scissors',
            'level_tracing': 'Level tracing'
        }
        slicer_effect_name = effect_name_map.get(effect_name.lower(), effect_name)

        # Activate effect
        segmentEditorWidget.setActiveEffectByName(slicer_effect_name)
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return f"Error: Effect '{effect_name}' not found"

        # Set brush size for applicable effects
        if effect_name.lower() in ['paint', 'erase']:
            effect.setParameter("BrushSphere", "1")
            effect.setParameter("BrushDiameterMm", str(brush_size_mm))

        toc = time.time()
        logging.info(f"segment_editor_activate executed in {toc - tic:.4f} seconds")

        return f"Activated '{slicer_effect_name}' effect on segment '{segment_name}'. You can now interact with the slice views. Say 'done' when finished."

    def segment_editor_deactivate(self) -> str:
        """
        Action tool: Deactivates the current segment editor effect.

        Use when user says:
        - "done", "finished", "stop editing"
        - "deactivate", "turn off the tool"

        Returns:
            str: Status message
        """
        tic = time.time()

        segmentEditorWidget, _ = self._get_segment_editor_widget_and_node()
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_editor_deactivate executed in {toc - tic:.4f} seconds")

        return "Segment editor effect deactivated."

    def segment_editor_undo(self) -> str:
        """
        Action tool: Undoes the last segment editor operation.

        Use when user says:
        - "undo", "undo that", "revert"
        - "go back", "restore previous"
        - "the segment disappeared", "that was too much"

        Returns:
            str: Status message
        """
        tic = time.time()

        segmentEditorWidget, _ = self._get_segment_editor_widget_and_node()
        segmentEditorWidget.undo()

        toc = time.time()
        logging.info(f"segment_editor_undo executed in {toc - tic:.4f} seconds")

        return "Undid the last segment editor operation."

    def segment_editor_redo(self) -> str:
        """
        Action tool: Redoes the last undone segment editor operation.

        Use when user says:
        - "redo", "redo that"
        - "bring it back", "restore what I undid"

        Returns:
            str: Status message
        """
        tic = time.time()

        segmentEditorWidget, _ = self._get_segment_editor_widget_and_node()
        segmentEditorWidget.redo()

        toc = time.time()
        logging.info(f"segment_editor_redo executed in {toc - tic:.4f} seconds")

        return "Redid the last undone segment editor operation."

    def segment_boolean_operation(self, segmentation_node_name: str, target_segment_name: str,
                                   modifier_segment_name: str, operation: str) -> str:
        """
        Action tool: Performs boolean operations between two segments.

        Use when user says:
        - "combine segments", "merge segments", "add segment to another"
        - "subtract segment from", "remove segment from"
        - "find intersection of segments", "keep overlap"
        - "copy segment to another"

        Args:
            segmentation_node_name: Name of the segmentation node
            target_segment_name: Name of the segment to modify
            modifier_segment_name: Name of the segment to use as modifier
            operation: 'add' (union), 'subtract', 'intersect', or 'copy'

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, target_segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, targetSegmentId = result

        # Get modifier segment ID
        segmentation = segmentationNode.GetSegmentation()
        modifierSegmentId = segmentation.GetSegmentIdBySegmentName(modifier_segment_name)

        if not modifierSegmentId:
            # List available segments
            numSegments = segmentation.GetNumberOfSegments()
            available = [segmentation.GetNthSegment(i).GetName() for i in range(numSegments)]
            return f"Error: Modifier segment '{modifier_segment_name}' not found. Available: {available}"

        # Map operation names
        op_map = {
            'add': 'UNION',
            'union': 'UNION',
            'subtract': 'SUBTRACT',
            'intersect': 'INTERSECT',
            'copy': 'COPY'
        }
        slicer_operation = op_map.get(operation.lower(), operation.upper())

        # Activate Logical operators effect
        segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Logical operators effect not found"

        # Set parameters
        effect.setParameter("Operation", slicer_operation)
        effect.setParameter("ModifierSegmentID", modifierSegmentId)

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_boolean_operation executed in {toc - tic:.4f} seconds")

        return f"Applied {operation} operation: '{modifier_segment_name}' -> '{target_segment_name}'"

    def segment_margin(self, segmentation_node_name: str, segment_name: str, margin_mm: float) -> str:
        """
        Action tool: Grows or shrinks a segment by a specified margin.

        Use when user says:
        - "grow the segment", "expand the segment"
        - "shrink the segment", "erode the segment"
        - "dilate by 2mm", "contract by 3mm"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to modify
            margin_mm: Margin in mm. Positive=grow, negative=shrink

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Activate Margin effect
        segmentEditorWidget.setActiveEffectByName("Margin")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Margin effect not found"

        # Set parameters
        effect.setParameter("MarginSizeMm", str(margin_mm))

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_margin executed in {toc - tic:.4f} seconds")

        action = "Grew" if margin_mm > 0 else "Shrunk"
        return f"{action} segment '{segment_name}' by {abs(margin_mm)} mm"

    def segment_islands(self, segmentation_node_name: str, segment_name: str,
                        operation: str, minimum_size_voxels: int = 1000) -> str:
        """
        Action tool: Performs island operations on a segment.

        Use when user says:
        - "keep only the largest island", "remove small islands"
        - "clean up small pieces", "keep largest connected component"
        - "split islands into separate segments"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to modify
            operation: 'keep_largest', 'remove_small', or 'split_islands'
            minimum_size_voxels: Minimum island size in voxels (for remove_small)

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Map operation names
        op_map = {
            'keep_largest': 'KEEP_LARGEST_ISLAND',
            'remove_small': 'REMOVE_SMALL_ISLANDS',
            'split_islands': 'SPLIT_ISLANDS_TO_SEGMENTS'
        }
        slicer_operation = op_map.get(operation.lower(), operation)

        # Activate Islands effect
        segmentEditorWidget.setActiveEffectByName("Islands")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Islands effect not found"

        # Set parameters
        effect.setParameter("Operation", slicer_operation)
        effect.setParameter("MinimumSize", str(minimum_size_voxels))

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_islands executed in {toc - tic:.4f} seconds")

        return f"Applied '{operation}' operation on segment '{segment_name}'"

    def segment_smoothing(self, segmentation_node_name: str, segment_name: str,
                          method: str, kernel_size_mm: float = 3.0) -> str:
        """
        Action tool: Applies smoothing to a segment.

        Use when user says:
        - "smooth the segment", "clean up the edges"
        - "apply gaussian smoothing", "median filter"
        - "morphological opening/closing"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to smooth
            method: 'median', 'gaussian', 'opening', or 'closing'
            kernel_size_mm: Kernel size in mm

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Map method names
        method_map = {
            'median': 'MEDIAN',
            'gaussian': 'GAUSSIAN',
            'opening': 'MORPHOLOGICAL_OPENING',
            'closing': 'MORPHOLOGICAL_CLOSING'
        }
        slicer_method = method_map.get(method.lower(), method)

        # Activate Smoothing effect
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Smoothing effect not found"

        # Set parameters
        effect.setParameter("SmoothingMethod", slicer_method)
        effect.setParameter("KernelSizeMm", str(kernel_size_mm))

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_smoothing executed in {toc - tic:.4f} seconds")

        return f"Applied {method} smoothing to segment '{segment_name}' with kernel size {kernel_size_mm} mm"

    def segment_hollow(self, segmentation_node_name: str, segment_name: str,
                       shell_thickness_mm: float, shell_mode: str = "inside") -> str:
        """
        Action tool: Creates a hollow shell from a segment.

        Use when user says:
        - "hollow out the segment", "make it hollow"
        - "create a shell", "extract the surface"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to hollow
            shell_thickness_mm: Shell thickness in mm
            shell_mode: 'inside', 'medial', or 'outside'

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Map mode names
        mode_map = {
            'inside': 'INSIDE_SURFACE',
            'medial': 'MEDIAL_SURFACE',
            'outside': 'OUTSIDE_SURFACE'
        }
        slicer_mode = mode_map.get(shell_mode.lower(), 'INSIDE_SURFACE')

        # Activate Hollow effect
        segmentEditorWidget.setActiveEffectByName("Hollow")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Hollow effect not found"

        # Set parameters
        effect.setParameter("ShellThicknessMm", str(shell_thickness_mm))
        effect.setParameter("ShellMode", slicer_mode)

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_hollow executed in {toc - tic:.4f} seconds")

        return f"Created {shell_mode} shell with {shell_thickness_mm} mm thickness for segment '{segment_name}'"

    def segment_threshold(self, segmentation_node_name: str, segment_name: str,
                          volume_node_name: str, lower_threshold: float,
                          upper_threshold: float) -> str:
        """
        Action tool: Applies intensity threshold to create/modify a segment.

        Use when user says:
        - "threshold the segment", "segment by intensity"
        - "select voxels between X and Y", "apply threshold"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to modify
            volume_node_name: Name of the source volume node for intensity values
            lower_threshold: Lower intensity threshold
            upper_threshold: Upper intensity threshold

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Set source volume
        volumeNode = self.talk2view_core.root.slicer_util_getNode(volume_node_name)
        segmentEditorNode.SetAndObserveSourceVolumeNode(volumeNode)

        # Activate Threshold effect
        segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Threshold effect not found"

        # Set parameters
        effect.setParameter("MinimumThreshold", str(lower_threshold))
        effect.setParameter("MaximumThreshold", str(upper_threshold))

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_threshold executed in {toc - tic:.4f} seconds")

        return f"Applied threshold [{lower_threshold}, {upper_threshold}] to segment '{segment_name}'"

    def segment_invert(self, segmentation_node_name: str, segment_name: str) -> str:
        """
        Action tool: Inverts a segment (swaps inside/outside).

        Use when user says:
        - "invert the segment", "flip inside/outside"
        - "swap foreground/background"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to invert

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Activate Logical operators effect
        segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Logical operators effect not found"

        # Set parameters
        effect.setParameter("Operation", "INVERT")

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_invert executed in {toc - tic:.4f} seconds")

        return f"Inverted segment '{segment_name}'"

    def segment_clear(self, segmentation_node_name: str, segment_name: str) -> str:
        """
        Action tool: Clears all content from a segment.

        Use when user says:
        - "clear the segment", "empty the segment"
        - "remove all content from segment"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment to clear

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Activate Logical operators effect
        segmentEditorWidget.setActiveEffectByName("Logical operators")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Logical operators effect not found"

        # Set parameters
        effect.setParameter("Operation", "CLEAR")

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_clear executed in {toc - tic:.4f} seconds")

        return f"Cleared segment '{segment_name}'"

    def segment_fill_holes(self, segmentation_node_name: str, segment_name: str,
                           hole_size_mm: float = 3.0) -> str:
        """
        Action tool: Fills holes in a segment using morphological closing.

        Use when user says:
        - "fill holes in the segment", "close gaps"
        - "fill internal cavities"

        Args:
            segmentation_node_name: Name of the segmentation node
            segment_name: Name of the segment
            hole_size_mm: Maximum hole size to fill in mm

        Returns:
            str: Status message
        """
        tic = time.time()

        result = self._setup_segment_editor(segmentation_node_name, segment_name)
        if result[0] is None:
            return f"Error: {result[3]}"
        segmentEditorWidget, segmentEditorNode, segmentationNode, segmentId = result

        # Activate Smoothing effect with MORPHOLOGICAL_CLOSING
        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()

        if effect is None:
            return "Error: Smoothing effect not found"

        # Set parameters
        effect.setParameter("SmoothingMethod", "MORPHOLOGICAL_CLOSING")
        effect.setParameter("KernelSizeMm", str(hole_size_mm))

        # Apply
        effect.self().onApply()

        # Deactivate effect
        segmentEditorWidget.setActiveEffectByName(None)

        toc = time.time()
        logging.info(f"segment_fill_holes executed in {toc - tic:.4f} seconds")

        return f"Filled holes up to {hole_size_mm} mm in segment '{segment_name}'"
