# SlicerAdaptiveBrush Slicer-side helpers
#
# These functions run locally inside 3D Slicer (no RPyC overhead).
# They are loaded by load_connector_helpers() and registered as
# SlicerAdaptiveBrush_<name> on the RPyC service.

import logging


def _get_segment_editor_widget():
    """Get the preferred segment editor widget.

    Checks the Talk2View segment editor registry preference (which
    prefers NNInteractive over built-in SegmentEditor when available),
    falling back to the built-in SegmentEditor widget.
    """
    import slicer
    import qt

    preferred = qt.QSettings().value(
        "Talk2View/PreferredSegmentEditor", "SegmentEditor"
    )
    # Try preferred module first
    try:
        widget = slicer.util.getModuleWidget(preferred)
        editors = slicer.util.findChildren(
            widget.parent(), className="qMRMLSegmentEditorWidget"
        )
        if editors:
            return editors[0]
    except Exception:
        pass
    # Fallback to built-in
    return slicer.modules.segmenteditor.widgetRepresentation().self().editor


def _get_or_create_segment_editor_node():
    """Get or create the segment editor MRML node."""
    import slicer

    node = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentEditorNode")
    if node is None:
        node = slicer.vtkMRMLSegmentEditorNode()
        slicer.mrmlScene.AddNode(node)
    return node


def _read_params(python_effect):
    """Read current parameter values from the effect."""
    return {
        "algorithm": getattr(python_effect, "algorithm", None),
        "radiusMm": getattr(python_effect, "radiusMm", None),
        "edgeSensitivity": getattr(python_effect, "edgeSensitivity", None),
        "thresholdZone": getattr(python_effect, "thresholdZone", None),
    }


def _deactivate_other_segment_editors(active_widget):
    """Deactivate effects on segment editor widgets other than active_widget.

    When multiple segment editor widgets share the same MRML node (e.g.
    NNInteractive and built-in SegmentEditor), leaving an effect active
    on the other widget causes duplicate outline actors.
    """
    import slicer

    all_editors = slicer.util.findChildren(
        slicer.util.mainWindow(), className="qMRMLSegmentEditorWidget"
    )
    for editor in all_editors:
        if editor is not active_widget and editor.activeEffect() is not None:
            editor.setActiveEffectByName(None)


def activate_brush(segmentation_name, segment_name, preset_id=None):
    """Set up segment editor and activate Adaptive Brush in a single call.

    Args:
        segmentation_name: Name of the segmentation node.
        segment_name: Name of the segment to edit.
        preset_id: Optional preset ID to apply after activation.

    Returns:
        Dict with 'success' and 'params', or 'error' key on failure.
    """
    import slicer

    # Get the preferred segment editor widget
    segmentEditorWidget = _get_segment_editor_widget()
    segmentEditorNode = _get_or_create_segment_editor_node()
    segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)

    # Deactivate effects on other segment editor widgets
    _deactivate_other_segment_editors(segmentEditorWidget)

    # Deactivate current effect to prevent stale outlines
    segmentEditorWidget.setActiveEffectByName(None)

    # Ensure we're in a segmentation module
    preferred_modules = ["SlicerNNInteractive", "NNInteractive", "SegmentEditor"]
    currentModule = slicer.util.selectedModule()
    if not isinstance(currentModule, str):
        currentModule = currentModule.name if currentModule else ""
    if currentModule not in preferred_modules:
        moduleNames = slicer.util.moduleNames()
        target = "SegmentEditor"
        for name in preferred_modules:
            if name in moduleNames:
                target = name
                break
        slicer.util.selectModule(target)

    # Find and set segmentation node
    segNodes = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    segmentationNode = None
    for n in segNodes:
        if n.GetName() == segmentation_name:
            segmentationNode = n
            break
    if segmentationNode is None:
        if segNodes:
            available = [n.GetName() for n in segNodes]
            return {"error": (
                f"Segmentation '{segmentation_name}' not found. "
                f"Available: {available}"
            )}
        return {"error": (
            f"Segmentation '{segmentation_name}' not found. "
            "No segmentations in scene. Create one now with "
            "create_segmentation and add_segment, then call "
            "activate_adaptive_brush again."
        )}

    segmentEditorWidget.setSegmentationNode(segmentationNode)

    # Set source volume if available
    volumeNodes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    if volumeNodes:
        segmentEditorWidget.setSourceVolumeNode(volumeNodes[0])

    # Select the segment
    segmentation = segmentationNode.GetSegmentation()
    segmentId = segmentation.GetSegmentIdBySegmentName(segment_name)
    if not segmentId:
        numSegments = segmentation.GetNumberOfSegments()
        available = [
            segmentation.GetNthSegment(i).GetName()
            for i in range(numSegments)
        ]
        if available:
            return {"error": (
                f"Segment '{segment_name}' not found. "
                f"Available segments: {available}"
            )}
        return {"error": (
            f"Segment '{segment_name}' not found. "
            "No segments exist. Create one now with add_segment, "
            "then call activate_adaptive_brush again."
        )}
    segmentEditorNode.SetSelectedSegmentID(segmentId)

    # Activate Adaptive Brush
    segmentEditorWidget.setActiveEffectByName("Adaptive Brush")
    slicer.app.processEvents()

    effect = segmentEditorWidget.activeEffect()
    if effect is None:
        return {"error": (
            "Failed to activate Adaptive Brush effect. "
            "Is the SlicerAdaptiveBrush extension installed?"
        )}
    pythonEffect = effect.self()

    # Apply preset if requested
    if preset_id:
        pythonEffect.applyPreset(preset_id)
        slicer.app.processEvents()

    params = _read_params(pythonEffect)
    logging.info(
        f"[AdaptiveBrush-Helper] activate_brush: "
        f"algorithm={params['algorithm']}, radius={params['radiusMm']}mm, "
        f"sensitivity={params['edgeSensitivity']}, "
        f"threshold={params['thresholdZone']}"
    )
    return {"success": True, "params": params}


def set_param(param_name, value):
    """Set a single Adaptive Brush parameter.

    Args:
        param_name: One of 'radiusMm', 'algorithm', 'edgeSensitivity',
            'thresholdZone', 'sphereMode'.
        value: The value to set.

    Returns:
        Dict with 'success' and 'params', or 'error' key on failure.
    """
    import slicer

    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()

    setters = {
        "radiusMm": lambda: pe.setRadiusMm(value),
        "algorithm": lambda: pe.setAlgorithm(value),
        "edgeSensitivity": lambda: pe.setEdgeSensitivity(value),
        "thresholdZone": lambda: pe.onZoneChanged(value),
        "sphereMode": lambda: setattr(pe, "sphereMode", value),
    }
    if param_name not in setters:
        return {"error": f"Unknown parameter: {param_name}. Valid: {list(setters.keys())}"}

    setters[param_name]()
    slicer.app.processEvents()

    params = _read_params(pe)
    logging.info(
        f"[AdaptiveBrush-Helper] set_param({param_name}={value}): "
        f"algorithm={params['algorithm']}, radius={params['radiusMm']}mm"
    )
    return {"success": True, "params": params}


def get_status():
    """Get Adaptive Brush status and all parameters.

    Returns:
        Dict with 'active' bool and optional 'params' dict.
    """
    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"active": False}
    pe = effect.self()
    return {
        "active": True,
        "params": {
            "algorithm": getattr(pe, "algorithm", None),
            "radiusMm": getattr(pe, "radiusMm", None),
            "edgeSensitivity": getattr(pe, "edgeSensitivity", None),
            "thresholdZone": getattr(pe, "thresholdZone", None),
            "sphereMode": getattr(pe, "sphereMode", None),
            "eraseMode": getattr(pe, "eraseMode", None),
            "samplingMethod": getattr(pe, "samplingMethod", None),
        },
    }


def apply_preset(preset_id):
    """Apply a preset and return updated parameters.

    Args:
        preset_id: Exact preset ID string.

    Returns:
        Dict with 'success' and 'params', or 'error' key on failure.
    """
    import slicer

    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()

    pe.applyPreset(preset_id)
    slicer.app.processEvents()

    params = _read_params(pe)
    logging.info(
        f"[AdaptiveBrush-Helper] apply_preset('{preset_id}'): "
        f"algorithm={params['algorithm']}, radius={params['radiusMm']}mm"
    )
    return {"success": True, "params": params}


def list_presets():
    """List all available presets from the active effect.

    Returns:
        Dict with 'presets' (id->info mapping) or 'error' key.
    """
    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()

    presets = getattr(pe, "_presets", {})
    # Return a plain dict (not RPyC netref) with serializable values
    result = {}
    for pid, preset in presets.items():
        result[pid] = {
            "name": preset.get("name", pid),
            "description": preset.get("description", ""),
        }
    return {"presets": result}


def set_erase_mode(erase):
    """Set erase mode on the Adaptive Brush.

    Args:
        erase: True to erase, False to paint.

    Returns:
        Dict with 'success' or 'error' key.
    """
    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()
    pe.eraseMode = erase
    return {"success": True}


def set_sphere_mode(enabled):
    """Set sphere (3D) mode on the Adaptive Brush.

    Args:
        enabled: True to enable 3D sphere mode, False for 2D.

    Returns:
        Dict with 'success' or 'error' key.
    """
    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()
    pe.sphereMode = enabled
    if hasattr(pe, "sphereModeCheckbox"):
        pe.sphereModeCheckbox.checked = enabled
    return {"success": True}


def paint_at(r, a, s, erase=False):
    """Paint at a specific RAS position using the Adaptive Brush.

    Args:
        r, a, s: RAS coordinates in mm.
        erase: If True, erase instead of paint.

    Returns:
        Dict with 'success' and optional voxel count info, or 'error' key.
    """
    import slicer

    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active. Use activate_adaptive_brush first."}
    pe = effect.self()

    params = _read_params(pe)

    # Count voxels before painting
    voxels_before = None
    seg_node = widget.segmentationNode()
    segment_id = widget.currentSegmentID()
    if seg_node and segment_id:
        try:
            arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, segment_id)
            if arr is not None:
                voxels_before = int(arr.sum())
            else:
                voxels_before = 0
        except Exception:
            pass

    slicer.app.processEvents()
    pe.paintAt(r, a, s, erase)
    slicer.app.processEvents()

    # Count voxels after painting
    voxels_after = None
    if seg_node and segment_id and voxels_before is not None:
        try:
            arr = slicer.util.arrayFromSegmentBinaryLabelmap(seg_node, segment_id)
            if arr is not None:
                voxels_after = int(arr.sum())
        except Exception:
            pass

    result = {"success": True, "params": params}
    if voxels_before is not None and voxels_after is not None:
        result["voxels_before"] = voxels_before
        result["voxels_after"] = voxels_after
        result["voxel_diff"] = voxels_after - voxels_before
    return result


def get_effect_presets():
    """Get the _presets dict from the active Adaptive Brush effect.

    Used by the connector to resolve natural-language preset names
    against GUI preset names and descriptions.

    Returns:
        Dict with 'presets' mapping or 'error' key.
    """
    widget = _get_segment_editor_widget()
    effect = widget.activeEffect()
    if effect is None or effect.name != "Adaptive Brush":
        return {"error": "Adaptive Brush not active."}
    pe = effect.self()
    presets = getattr(pe, "_presets", {})
    # Return plain dict
    result = {}
    for pid, preset in presets.items():
        result[pid] = {
            "name": preset.get("name", pid),
            "description": preset.get("description", ""),
        }
    return {"presets": result}
