"""Builds a compact text summary of the current Slicer scene.

Injected into each user turn (not the system prompt, which stays byte-stable
for prompt caching). Gives the model grounding without it having to call an
inventory tool first on every request.
"""

import slicer


def _volume_summary(node):
    dims = "?"
    spacing = "?"
    image = node.GetImageData()
    if image is not None:
        dims = "x".join(str(d) for d in image.GetDimensions())
        spacing = "x".join(f"{s:.2f}" for s in node.GetSpacing())
    wl = ""
    display = node.GetDisplayNode()
    if display is not None and hasattr(display, "GetWindow"):
        try:
            wl = f", W/L={display.GetWindow():.0f}/{display.GetLevel():.0f}"
        except Exception:
            pass
    return f'- volume "{node.GetName()}" (dims {dims}, spacing {spacing} mm{wl})'


def _segmentation_summary(node):
    segmentation = node.GetSegmentation()
    names = []
    for i in range(segmentation.GetNumberOfSegments()):
        segment = segmentation.GetNthSegment(i)
        names.append(segment.GetName())
    shown = ", ".join(names[:12])
    if len(names) > 12:
        shown += f", … ({len(names)} total)"
    return f'- segmentation "{node.GetName()}" with {len(names)} segment(s): {shown}'


def _markups_summary(node):
    n = node.GetNumberOfControlPoints() if hasattr(node, "GetNumberOfControlPoints") else 0
    return f'- markups {node.GetClassName().replace("vtkMRMLMarkups", "").replace("Node", "").lower()} "{node.GetName()}" ({n} point(s))'


def build_scene_context():
    """Return a short plain-text inventory of the scene for the model."""
    lines = []

    volumes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
    segmentations = slicer.util.getNodesByClass("vtkMRMLSegmentationNode")
    models = slicer.util.getNodesByClass("vtkMRMLModelNode")
    markups = slicer.util.getNodesByClass("vtkMRMLMarkupsNode")

    # Filter out Slicer's internal helper models (slice view planes etc.)
    models = [m for m in models if not m.GetHideFromEditors()]

    if not (volumes or segmentations or models or markups):
        return "The Slicer scene is currently empty (no data loaded)."

    for node in volumes:
        lines.append(_volume_summary(node))
    for node in segmentations:
        lines.append(_segmentation_summary(node))
    for node in models:
        lines.append(f'- model "{node.GetName()}"')
    for node in markups:
        lines.append(_markups_summary(node))

    layout_manager = slicer.app.layoutManager()
    layout_id = layout_manager.layout if layout_manager else -1
    lines.append(f"- current layout id: {layout_id}")

    return "Current Slicer scene:\n" + "\n".join(lines)
