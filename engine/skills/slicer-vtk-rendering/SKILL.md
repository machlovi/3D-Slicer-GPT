---
name: slicer-vtk-rendering
description: Low-level VTK rendering access and input customization including VTK views, renderers, cameras, actor properties (PBR, metallic, roughness), keyboard shortcuts, and mouse gesture configuration. Use for advanced rendering control and custom interaction.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer VTK Rendering and Input

## Overview

This skill covers low-level VTK rendering access and input customization in 3D Slicer. All code runs inside Slicer's embedded Python environment where the following modules are available by default:

- `slicer` -- Core Slicer Python API (nodes, scene, app, util)
- `vtk` -- VTK rendering pipeline classes (renderers, actors, mappers, cameras, properties)
- `qt` -- Qt bindings for UI elements (shortcuts, key sequences, widgets)
- `numpy` -- Numerical computing (optional but typically available)

Use this skill when you need direct control over VTK rendering objects, physically-based rendering properties, or custom keyboard/mouse interaction in Slicer viewers.

**Related skills:**
- `slicer-views-layouts` -- View layout management, view linking, and orientation configuration
- `slicer-models-meshes` -- Model node creation, display properties, and mesh manipulation
- `slicer-scene-management` -- Scene loading, saving, and node management

---

## Access VTK Rendering Classes

### Iterate Through All 3D Views in Current Layout

Access 3D view nodes, camera nodes, and their identifiers for all 3D views in the active layout.

```python
layoutManager = slicer.app.layoutManager()
for threeDViewIndex in range(layoutManager.threeDViewCount):
  view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
  threeDViewNode = view.mrmlViewNode()
  cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(threeDViewNode)
  print("View node for 3D widget " + str(threeDViewIndex))
  print("  Name: " + threeDViewNode.GetName())
  print("  ID: " + threeDViewNode.GetID())
  print("  Camera ID: " + cameraNode.GetID())
```

### Iterate Through All Slice Views in Current Layout

Access slice view nodes, slice logic, and composite nodes (which contain background/foreground/label volume assignments) for all slice views.

```python
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
  view = layoutManager.sliceWidget(sliceViewName).sliceView()
  sliceNode = view.mrmlSliceNode()
  sliceLogic = slicer.app.applicationLogic().GetSliceLogic(sliceNode)
  compositeNode = sliceLogic.GetSliceCompositeNode()
  print("Slice view " + str(sliceViewName))
  print("  Name: " + sliceNode.GetName())
  print("  ID: " + sliceNode.GetID())
  print("  Background volume: {0}".format(compositeNode.GetBackgroundVolumeID()))
  print("  Foreground volume: {0} (opacity: {1})".format(
    compositeNode.GetForegroundVolumeID(), compositeNode.GetForegroundOpacity()))
  print("  Label volume: {0} (opacity: {1})".format(
    compositeNode.GetLabelVolumeID(), compositeNode.GetLabelOpacity()))
```

### Access VTK Render Windows, Renderers, and Cameras

For low-level manipulation of views, access VTK render windows, renderers, and cameras directly. These objects provide full control over the VTK rendering pipeline.

**3D views -- render window, renderer, and camera:**

```python
layoutManager = slicer.app.layoutManager()
for threeDViewIndex in range(layoutManager.threeDViewCount):
  view = layoutManager.threeDWidget(threeDViewIndex).threeDView()
  threeDViewNode = view.mrmlViewNode()
  cameraNode = slicer.modules.cameras.logic().GetViewActiveCameraNode(threeDViewNode)
  print("View node for 3D widget " + str(threeDViewIndex))
  print("  Name: " + threeDViewNode.GetName())
  print("  ID: " + threeDViewNode.GetID())
  print("  Camera ID: " + cameraNode.GetID())

renderWindow = view.renderWindow()
renderers = renderWindow.GetRenderers()
renderer = renderers.GetItemAsObject(0)
camera = cameraNode.GetCamera()
```

**Slice views -- render window and renderer:**

```python
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
  view = layoutManager.sliceWidget(sliceViewName).sliceView()
  sliceNode = view.mrmlSliceNode()
  sliceLogic = slicer.app.applicationLogic().GetSliceLogic(sliceNode)
  compositeNode = sliceLogic.GetSliceCompositeNode()
  print("Slice view " + str(sliceViewName))
  print("  Name: " + sliceNode.GetName())
  print("  ID: " + sliceNode.GetID())

renderWindow = view.renderWindow()
renderers = renderWindow.GetRenderers()
renderer = renderers.GetItemAsObject(0)
```

### Access Displayable Managers

Displayable managers are responsible for creating VTK filters, mappers, and actors to display MRML nodes in renderers. Accessing displayable managers is useful for troubleshooting rendering and for modifying low-level VTK actor properties.

```python
threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
modelDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(
  threeDViewNode, "vtkMRMLModelDisplayableManager")
if modelDisplayableManager is None:
  logging.error("Failed to find the model displayable manager")
```

Common displayable manager class names:
- `vtkMRMLModelDisplayableManager` -- Manages model node rendering (meshes, surfaces)
- `vtkMRMLCameraDisplayableManager` -- Manages camera interactions in 3D views
- `vtkMRMLCrosshairDisplayableManager` -- Manages crosshair display and interaction in slice views
- `vtkMRMLScalarBarDisplayableManager` -- Manages scalar bar (color legend) and window/level widget

### VTK Actor Properties with Physically-Based Rendering (PBR)

Access and modify VTK actor properties to use physically-based rendering. This enables metallic, roughness, and other PBR material settings on model surfaces.

```python
modelNode = slicer.util.getNode("MyModel")

threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
modelDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(
  threeDViewNode, "vtkMRMLModelDisplayableManager")
actor = modelDisplayableManager.GetActorByID(modelNode.GetDisplayNode().GetID())
property = actor.GetProperty()
property.SetInterpolationToPBR()
property.SetMetallic(0.5)
property.SetRoughness(0.5)
property.SetColor(0.5, 0.5, 0.9)
slicer.util.forceRenderAllViews()
```

**Key VTK property methods for PBR:**
- `property.SetInterpolationToPBR()` -- Enable physically-based rendering interpolation
- `property.SetMetallic(value)` -- Set metallic factor (0.0 = dielectric, 1.0 = fully metallic)
- `property.SetRoughness(value)` -- Set roughness factor (0.0 = smooth/mirror, 1.0 = fully rough)
- `property.SetColor(r, g, b)` -- Set base color (RGB, each 0.0 to 1.0)
- `property.SetOpacity(value)` -- Set opacity (0.0 = transparent, 1.0 = opaque)

After modifying actor properties, always call `slicer.util.forceRenderAllViews()` to update the display.

---

## Keyboard Shortcuts and Mouse Gestures

### Register Custom Keyboard Shortcuts

Keyboard shortcuts can be specified for activating any Slicer feature by adding a couple of lines to your `.slicerrc.py` file. The following example registers shortcuts to switch between different view layouts.

```python
shortcuts = [
  ("Ctrl+b", lambda: slicer.app.layoutManager().setLayout(
    slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)),
  ("Ctrl+n", lambda: slicer.app.layoutManager().setLayout(
    slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)),
  ("Ctrl+m", lambda: slicer.app.layoutManager().setLayout(
    slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)),
  ("Ctrl+,", lambda: slicer.app.layoutManager().setLayout(
    slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView))
]

for (shortcutKey, callback) in shortcuts:
  shortcut = qt.QShortcut(slicer.util.mainWindow())
  shortcut.setKey(qt.QKeySequence(shortcutKey))
  shortcut.connect("activated()", callback)
```

**Pattern for registering any keyboard shortcut:**
1. Create a `qt.QShortcut` attached to the main window
2. Set the key sequence with `setKey(qt.QKeySequence("..."))`
3. Connect the `activated()` signal to a callback

### Cycle Through Segment Editor Effects

Cycle forward and backward through available Segment Editor effects using backtick and tilde keys.

```python
def cycleEffect(delta=1):
  try:
    orderedNames = list(slicer.modules.SegmentEditorWidget.editor.effectNameOrder())
    allNames = slicer.modules.SegmentEditorWidget.editor.availableEffectNames()
    for name in allNames:
      try:
        orderedNames.index(name)
      except ValueError:
        orderedNames.append(name)
    orderedNames.insert(0, None)
    activeEffect = slicer.modules.SegmentEditorWidget.editor.activeEffect()
    if activeEffect:
      activeName = slicer.modules.SegmentEditorWidget.editor.activeEffect().name
    else:
      activeName = None
    newIndex = (orderedNames.index(activeName) + delta) % len(orderedNames)
    slicer.modules.SegmentEditorWidget.editor.setActiveEffectByName(
      orderedNames[newIndex])
  except AttributeError:
    pass

shortcuts = [
  ("`", lambda: cycleEffect(-1)),
  ("~", lambda: cycleEffect(1)),
]

for (shortcutKey, callback) in shortcuts:
  shortcut = qt.QShortcut(slicer.util.mainWindow())
  shortcut.setKey(qt.QKeySequence(shortcutKey))
  shortcut.connect("activated()", callback)
```

### Jump Slices to World Origin with Keyboard Shortcut

Add a keyboard shortcut (Ctrl+E) to jump all slice views to the center of the world coordinate system (0, 0, 0).

```python
shortcut = qt.QShortcut(qt.QKeySequence("Ctrl+e"), slicer.util.mainWindow())
shortcut.connect("activated()",
  lambda: slicer.modules.markups.logic().JumpSlicesToLocation(0,0,0, True))
```

### Customize Mouse Gestures: Right-Click Rotation in 3D View

Make the 3D view rotate using right-click-and-drag instead of the default left-click-and-drag. This modifies the camera widget's event translation table.

```python
threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
cameraDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(
  threeDViewNode, "vtkMRMLCameraDisplayableManager")
cameraWidget = cameraDisplayableManager.GetCameraWidget()

cameraWidget.SetEventTranslationClickAndDrag(cameraWidget.WidgetStateIdle,
  vtk.vtkCommand.RightButtonPressEvent, vtk.vtkEvent.NoModifier,
  cameraWidget.WidgetStateRotate, cameraWidget.WidgetEventRotateStart,
  cameraWidget.WidgetEventRotateEnd)
```

**`SetEventTranslationClickAndDrag` parameters:**
1. Current widget state (e.g., `WidgetStateIdle`)
2. VTK mouse event (e.g., `vtk.vtkCommand.RightButtonPressEvent`)
3. Modifier key (e.g., `vtk.vtkEvent.NoModifier`, `vtk.vtkEvent.AltModifier`, `vtk.vtkEvent.ControlModifier`)
4. Target widget state (e.g., `WidgetStateRotate`)
5. Start event (e.g., `WidgetEventRotateStart`)
6. End event (e.g., `WidgetEventRotateEnd`)

### Crosshair Positioning in Slice Views

Set the crosshair position with left-click and move the crosshair with Alt+left-click-and-drag in slice views.

```python
sliceViewLabel = "Red"
sliceViewNode = slicer.mrmlScene.GetNodeByID(f"vtkMRMLSliceNode{sliceViewLabel}")
appLogic = slicer.app.applicationLogic()
displayableManager = appLogic.GetViewDisplayableManagerByClassName(
  sliceViewNode, "vtkMRMLCrosshairDisplayableManager")

widget = displayableManager.GetSliceIntersectionWidget()

widget.SetEventTranslation(widget.WidgetStateIdle,
  slicer.vtkMRMLInteractionEventData.LeftButtonClickEvent,
  vtk.vtkEvent.NoModifier, widget.WidgetEventSetCrosshairPosition)

widget.SetEventTranslationClickAndDrag(widget.WidgetStateIdle,
  vtk.vtkCommand.LeftButtonPressEvent, vtk.vtkEvent.AltModifier,
  widget.WidgetStateMoveCrosshair, widget.WidgetEventMoveCrosshairStart,
  widget.WidgetEventMoveCrosshairEnd)
```

**Notes:**
- `sliceViewLabel` can be `"Red"`, `"Yellow"`, `"Green"`, or any custom slice view name
- `SetEventTranslation` maps a single click event to an action
- `SetEventTranslationClickAndDrag` maps a click-and-drag gesture to a state transition
- To apply to all slice views, iterate over `slicer.app.layoutManager().sliceViewNames()`

### Crosshair Positioning in 3D Views

Set the crosshair position with left-click and move the crosshair with Alt+left-click-and-drag in 3D views. This uses the camera widget rather than the slice intersection widget.

```python
threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
cameraDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(
  threeDViewNode, "vtkMRMLCameraDisplayableManager")
widget = cameraDisplayableManager.GetCameraWidget()

widget.SetEventTranslation(widget.WidgetStateIdle,
  slicer.vtkMRMLInteractionEventData.LeftButtonClickEvent,
  vtk.vtkEvent.NoModifier, widget.WidgetEventSetCrosshairPosition)

widget.SetEventTranslationClickAndDrag(widget.WidgetStateIdle,
  vtk.vtkCommand.LeftButtonPressEvent, vtk.vtkEvent.AltModifier,
  widget.WidgetStateMoveCrosshair, widget.WidgetEventMoveCrosshairStart,
  widget.WidgetEventMoveCrosshairEnd)
```

### Window/Level Adjustment with Ctrl+Right-Click

Enable window/level adjustment in any mouse interaction mode using Ctrl+right-click-and-drag. This provides a convenient always-available window/level shortcut regardless of the current toolbar mode.

```python
sliceViewLabel = "Red"
sliceViewNode = slicer.mrmlScene.GetNodeByID(f"vtkMRMLSliceNode{sliceViewLabel}")
appLogic = slicer.app.applicationLogic()
displayableManager = appLogic.GetViewDisplayableManagerByClassName(
  sliceViewNode, "vtkMRMLScalarBarDisplayableManager")
w = displayableManager.GetWindowLevelWidget()
w.SetEventTranslationClickAndDrag(w.WidgetStateIdle,
  vtk.vtkCommand.RightButtonPressEvent, vtk.vtkEvent.ControlModifier,
  w.WidgetStateAdjustWindowLevel,
  w.WidgetEventAlwaysOnAdjustWindowLevelStart,
  w.WidgetEventAlwaysOnAdjustWindowLevelEnd)
```

**Notes:**
- The `vtkMRMLScalarBarDisplayableManager` manages the window/level widget in slice views
- `WidgetEventAlwaysOnAdjustWindowLevelStart` makes window/level work regardless of the current interaction mode
- To apply to all slice views, iterate over `slicer.app.layoutManager().sliceViewNames()`

### Disable Slice Browsing Interactions

Disable slice browsing (scrolling through slices with mouse wheel and keyboard shortcuts) in a specific slice view. This is useful for kiosk-mode or locked displays.

```python
interactorObserver = slicer.app.layoutManager().sliceWidget("Red").sliceView().interactorObserver()
interactorObserver.SetActionEnabled(interactorObserver.BrowseSlice, False)
```

**Available actions that can be enabled/disabled on the interactor observer:**
- `BrowseSlice` -- Mouse wheel and keyboard slice browsing
- Other actions depend on the Slicer version; check `dir(interactorObserver)` for available constants

### Hide Slice View Controllers

Hide the controller bar at the top of all slice views for a cleaner display.

```python
lm = slicer.app.layoutManager()
for sliceViewName in lm.sliceViewNames():
  lm.sliceWidget(sliceViewName).sliceController().setVisible(False)
```

To restore controllers:

```python
lm = slicer.app.layoutManager()
for sliceViewName in lm.sliceViewNames():
  lm.sliceWidget(sliceViewName).sliceController().setVisible(True)
```

### Hide 3D View Controllers

Hide the controller bar at the top of all 3D views.

```python
lm = slicer.app.layoutManager()
for viewIndex in range(slicer.app.layoutManager().threeDViewCount):
  lm.threeDWidget(viewIndex).threeDController().setVisible(False)
```

To restore controllers:

```python
lm = slicer.app.layoutManager()
for viewIndex in range(slicer.app.layoutManager().threeDViewCount):
  lm.threeDWidget(viewIndex).threeDController().setVisible(True)
```

---

## Quick Reference

### Common View Access Patterns

| Task | Code |
|------|------|
| Get layout manager | `slicer.app.layoutManager()` |
| Get 3D view widget | `layoutManager.threeDWidget(index).threeDView()` |
| Get slice view widget | `layoutManager.sliceWidget(name).sliceView()` |
| Get 3D view MRML node | `view.mrmlViewNode()` |
| Get slice view MRML node | `view.mrmlSliceNode()` |
| Get VTK render window | `view.renderWindow()` |
| Get VTK renderer | `renderWindow.GetRenderers().GetItemAsObject(0)` |
| Get active camera node | `slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)` |
| Get VTK camera | `cameraNode.GetCamera()` |
| Force render update | `slicer.util.forceRenderAllViews()` |

### Common Displayable Managers

| Manager Class | View Type | Purpose |
|---------------|-----------|---------|
| `vtkMRMLModelDisplayableManager` | 3D | Model rendering, actor access |
| `vtkMRMLCameraDisplayableManager` | 3D | Camera interaction, rotation gestures |
| `vtkMRMLCrosshairDisplayableManager` | Slice | Crosshair display and positioning |
| `vtkMRMLScalarBarDisplayableManager` | Slice | Scalar bar, window/level widget |

### Event Translation Constants

| Constant | Description |
|----------|-------------|
| `vtk.vtkCommand.LeftButtonPressEvent` | Left mouse button press |
| `vtk.vtkCommand.RightButtonPressEvent` | Right mouse button press |
| `vtk.vtkCommand.MiddleButtonPressEvent` | Middle mouse button press |
| `vtk.vtkEvent.NoModifier` | No keyboard modifier |
| `vtk.vtkEvent.AltModifier` | Alt key held |
| `vtk.vtkEvent.ControlModifier` | Ctrl key held |
| `vtk.vtkEvent.ShiftModifier` | Shift key held |

## Resources

- [3D Slicer Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html) -- Source for all code examples in this skill
- [MRML Overview](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html) -- Core concepts for MRML nodes and display nodes
- [VTK Documentation](https://vtk.org/doc/nightly/html/) -- Full VTK class reference
- [Volume Rendering](https://slicer.readthedocs.io/en/latest/user_guide/modules/volumerendering.html) -- Volume rendering concepts in Slicer
