---
name: slicer-views-layouts
description: View and layout management including 3D/slice view configuration, custom layouts, view linking, slice operations, orientation markers, crosshairs, and view display options. Use for controlling how data is displayed in Slicer's viewers.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Views and Layouts

## Overview

This skill covers programmatic control of 3D Slicer's view system: slice views, 3D views, layout management, crosshairs, orientation markers, screen capture, and view linking. All code runs in Slicer's embedded Python environment where `slicer`, `vtk`, `qt`, and `numpy` are available by default.

**Key objects:**
- `slicer.app.layoutManager()` -- central access point for all view widgets
- `vtkMRMLSliceNode` / `vtkMRMLViewNode` -- MRML nodes controlling slice and 3D view state
- `vtkMRMLSliceCompositeNode` -- controls which volumes are displayed in a slice view
- `vtkMRMLCrosshairNode` -- singleton node for crosshair position and behavior
- `vtkMRMLLayoutNode` -- defines which layout is active and stores custom layout descriptions

**Common workflow:**
1. Get a view widget from the layout manager
2. Access its MRML node to read/write view properties
3. Call `forceRender()` or `Modified()` to update the display

## Display Text in a 3D View or Slice View

Show information overlaid on a viewer using corner annotations. Useful for displaying status messages, measurement results, or custom labels directly in the view.

### 3D View Text Overlay

```python
view = slicer.app.layoutManager().threeDWidget(0).threeDView()
# Set text to "Something"
view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperRight, "Something")
# Set color to red
view.cornerAnnotation().GetTextProperty().SetColor(1, 0, 0)
# Update the view
view.forceRender()
```

### Slice View Text Overlay

```python
view = slicer.app.layoutManager().sliceWidget("Red").sliceView()
# Set text to "Something"
view.cornerAnnotation().SetText(vtk.vtkCornerAnnotation.UpperRight, "Something")
# Set color to red
view.cornerAnnotation().GetTextProperty().SetColor(1, 0, 0)
# Update the view
view.forceRender()
```

Corner positions available: `vtk.vtkCornerAnnotation.UpperRight`, `UpperLeft`, `LowerRight`, `LowerLeft`.

## Show Orientation Marker in All Views

Display orientation axes (or other marker types) in all views to help users understand spatial orientation. Useful when reviewing medical images where anatomical orientation is critical.

```python
viewNodes = slicer.util.getNodesByClass("vtkMRMLAbstractViewNode")
for viewNode in viewNodes:
    viewNode.SetOrientationMarkerType(slicer.vtkMRMLAbstractViewNode.OrientationMarkerTypeAxes)
```

Available marker types:
- `OrientationMarkerTypeNone`
- `OrientationMarkerTypeAxes`
- `OrientationMarkerTypeCube`
- `OrientationMarkerTypeHuman`

## Change View Axis Labels

Customize the axis labels displayed on 3D or slice views. Useful for non-standard coordinate systems or when working with non-medical data.

```python
labels = ["x", "X", "y", "Y", "z", "Z"]
viewNode = slicer.app.layoutManager().threeDWidget(0).mrmlViewNode()
# for slice view:
# viewNode = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
for index, label in enumerate(labels):
    viewNode.SetAxisLabel(index, label)
```

The six label indices correspond to: -X, +X, -Y, +Y, -Z, +Z directions.

## Hide View Controller Bars

Hide the controller bar at the top of views to maximize the display area. Useful for presentations, screenshots, or when building custom UIs that replace the default controllers.

```python
slicer.app.layoutManager().threeDWidget(0).threeDController().setVisible(False)
slicer.app.layoutManager().sliceWidget("Red").sliceController().setVisible(False)
slicer.app.layoutManager().plotWidget(0).plotController().setVisible(False)
slicer.app.layoutManager().tableWidget(0).tableController().setVisible(False)
```

## Hide Slicer Logo from Main Window

```python
slicer.util.findChild(slicer.util.mainWindow(), "LogoLabel").visible = False
```

## Customize Widgets in View Controller Bars

Add, remove, or modify widgets in the slice view controller bar. Useful for building custom interfaces that extend or simplify the default controls.

```python
sliceController = slicer.app.layoutManager().sliceWidget("Red").sliceController()

# hide what is not needed
sliceController.pinButton().hide()
#sliceController.viewLabel().hide()
sliceController.fitToWindowToolButton().hide()
sliceController.sliceOffsetSlider().hide()

# add custom widgets
myButton = qt.QPushButton("My custom button")
sliceController.barLayout().addWidget(myButton)
```

## Display a Node in Only Some Views

Restrict a displayable node to appear in specific views only. Useful when you have multiple views showing different data and want to avoid cluttering all views with all nodes.

```python
displayableNode = getNode("L")

viewNodeIDs = [
    slicer.app.layoutManager().sliceWidget(viewName).mrmlSliceNode().GetID()
    for viewName in ["Red+", "Green+", "Yellow+"]
]

displayableNode.GetDisplayNode().SetViewNodeIDs(viewNodeIDs)
```

To display a node in a 3D view only:

```python
viewNodeIDs = [slicer.app.layoutManager().threeDWidget(0).mrmlViewNode().GetID()]
displayableNode.GetDisplayNode().SetViewNodeIDs(viewNodeIDs)
```

To reset and show the node in all views, pass an empty list:

```python
displayableNode.GetDisplayNode().SetViewNodeIDs([])
```

## Get Current Mouse Coordinates in a Slice View

Get 3D (RAS) coordinates of the current mouse cursor from the crosshair singleton node. Useful for building interactive tools that respond to mouse position.

```python
def onMouseMoved(observer, eventid):
    ras = [0, 0, 0]
    crosshairNode.GetCursorPositionRAS(ras)
    print(ras)

crosshairNode = slicer.util.getNode("Crosshair")
crosshairNode.AddObserver(slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, onMouseMoved)
```

## Display Crosshair at a 3D Position

Programmatically set the crosshair to a specific RAS coordinate and center all slice views on that position. Useful for navigating to a point of interest identified by analysis or user selection.

```python
position_RAS = [23.4, 5.6, 78.9]
crosshairNode = slicer.util.getNode("Crosshair")
# Set crosshair position
crosshairNode.SetCrosshairRAS(position_RAS)
# Center the position in all slice views
slicer.vtkMRMLSliceNode.JumpAllSlices(slicer.mrmlScene, *position_RAS, slicer.vtkMRMLSliceNode.CenteredJumpSlice)
# Make the crosshair visible
crosshairNode.SetCrosshairMode(slicer.vtkMRMLCrosshairNode.ShowBasic)
```

## Change the Crosshair Color

```python
# Get the crosshair node
crosshairNode = slicer.util.getNode("Crosshair")
# Set the crosshair color to Red
crosshairNode.SetCrosshairColor(1.0, 0.0, 0.0)
```

## Display Mouse Pointer Coordinates in Alternative Coordinate System

Show mouse coordinates transformed to a different coordinate system (e.g., MNI space for brain imaging). Useful when working with atlas-registered data.

```python
def onMouseMoved(observer, eventid):
    mniToWorldTransformNode = getNode("LinearTransform_3")
    worldToMniTransform = vtk.vtkGeneralTransform()
    mniToWorldTransformNode.GetTransformToWorld(worldToMniTransform)
    ras = [0, 0, 0]
    mni = [0, 0, 0]
    crosshairNode.GetCursorPositionRAS(ras)
    worldToMniTransform.TransformPoint(ras, mni)
    _ras = "; ".join([str(k) for k in ras])
    _mni = "; ".join([str(k) for k in mni])
    slicer.util.showStatusMessage(f"RAS={_ras}   MNI={_mni}")

crosshairNode = slicer.util.getNode("Crosshair")
observationId = crosshairNode.AddObserver(slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, onMouseMoved)

# Run this to stop displaying values:
# crosshairNode.RemoveObserver(observationId)
```

## Get 3D Coordinates from 2D Display Coordinates

Convert pixel coordinates on screen to 3D RAS coordinates by picking a model surface point. Useful for implementing click-to-select or measurement tools.

```python
# Display position is in pixels, origin is top-left corner
displayPosition = [10, 12]

# Get model displayable manager
threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
modelDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(threeDViewNode, "vtkMRMLModelDisplayableManager")

# Use model displayable manager's point picker
if modelDisplayableManager.Pick(displayPosition[0], displayPosition[1]) and modelDisplayableManager.GetPickedNodeID():
    rasPosition = modelDisplayableManager.GetPickedRAS()
    print(rasPosition)
else:
    print(f"No model is visible at {displayPosition}")
```

## Get DataProbe Text

Read the current DataProbe information (volume name, IJK coordinates, voxel value) from the info widget. Useful for logging or custom display of voxel information.

```python
def printDataProbe():
    infoWidget = slicer.modules.DataProbeInstance.infoWidget
    for layer in ("B", "F", "L"):
        print(infoWidget.layerNames[layer].text, infoWidget.layerIJKs[layer].text, infoWidget.layerValues[layer].text)

s = qt.QShortcut(qt.QKeySequence("."), mainWindow())
s.connect("activated()", printDataProbe)
```

## Custom View Layouts

Define custom view arrangements using XML layout descriptions. Slicer layouts are described in XML that specifies view types, orientations, and split ratios. Use custom layout IDs starting from 501 to avoid conflicts with built-in layouts.

### Define and Activate a Custom Layout

```python
customLayout = """
<layout type="vertical" split="true">
  <item>
  <view class="vtkMRMLViewNode" singletontag="1">
    <property name="viewlabel" action="default">1</property>
  </view>
  </item>
  <item>
  <view class="vtkMRMLSliceNode" singletontag="Red">
    <property name="orientation" action="default">Axial</property>
    <property name="viewlabel" action="default">R</property>
    <property name="viewcolor" action="default">#F34A33</property>
  </view>
  </item>
</layout>
"""

customLayoutId = 501

layoutManager = slicer.app.layoutManager()
layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId, customLayout)

# Switch to the new custom layout
layoutManager.setLayout(customLayoutId)
```

**Layout XML reference:**
- `type`: `"vertical"`, `"horizontal"`, `"grid"`, or `"tab"`
- `split`: `"true"` to allow resizing between items
- View classes: `vtkMRMLViewNode` (3D), `vtkMRMLSliceNode` (slice), `vtkMRMLPlotViewNode` (plot), `vtkMRMLTableViewNode` (table)
- `singletontag`: Unique identifier for the view (e.g., `"1"` for 3D, `"Red"`/`"Green"`/`"Yellow"` for slices)
- Slice properties: `orientation` (Axial/Sagittal/Coronal), `viewlabel`, `viewcolor`

See standard layout definitions in the Slicer source: `Libs/MRML/Logic/vtkMRMLLayoutLogic.cxx`

### Add Layout Button to Toolbar

Add a button to the layout selector toolbar so users can switch to the custom layout from the UI.

```python
# Add button to layout selector toolbar for this custom layout
viewToolBar = mainWindow().findChild("QToolBar", "ViewToolBar")
layoutMenu = viewToolBar.widgetForAction(viewToolBar.actions()[0]).menu()
layoutSwitchActionParent = layoutMenu
layoutSwitchAction = layoutSwitchActionParent.addAction("My view")
layoutSwitchAction.setData(customLayoutId)
layoutSwitchAction.setIcon(qt.QIcon(":Icons/Go.png"))
layoutSwitchAction.setToolTip("3D and slice view")
```

### Switch Between Built-in Layouts

Use `vtkMRMLLayoutNode` constants to switch between standard layouts programmatically.

```python
layoutManager = slicer.app.layoutManager()

# Common built-in layout constants:
layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpRedSliceView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpYellowSliceView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUpGreenSliceView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDual3DView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutThreeOverThreeView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourOverFourView)
# layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutTabbedSliceView)
```

## Turn on Slice Intersections

Display the intersection lines of other slice planes on each slice view. Useful for understanding the spatial relationship between slices, especially when using oblique orientations.

```python
sliceDisplayNodes = slicer.util.getNodesByClass("vtkMRMLSliceDisplayNode")
for sliceDisplayNode in sliceDisplayNodes:
    sliceDisplayNode.SetIntersectingSlicesVisibility(1)

# Workaround to force visual update
sliceNodes = slicer.util.getNodesByClass('vtkMRMLSliceNode')
for sliceNode in sliceNodes:
    sliceNode.Modified()
```

To turn off slice intersections:

```python
sliceDisplayNodes = slicer.util.getNodesByClass("vtkMRMLSliceDisplayNode")
for sliceDisplayNode in sliceDisplayNodes:
    sliceDisplayNode.SetIntersectingSlicesVisibility(0)
```

## Hide Slice View Annotations

Hide the default corner annotations in slice views (volume name, orientation labels, etc.). Useful for clean screenshots or presentations.

```python
# Disable slice annotations immediately
sliceAnnotations = slicer.modules.DataProbeInstance.infoWidget.sliceAnnotations
sliceAnnotations.sliceViewAnnotationsEnabled = False
sliceAnnotations.updateSliceViewFromGUI()
# Disable slice annotations persistently (after Slicer restarts)
settings = qt.QSettings()
settings.setValue("DataProbe/sliceViewAnnotations.enabled", 0)
```

## Change Slice Offset

Move a slice view to a specific position along its normal axis. Useful for navigating to a known anatomical landmark or iterating through slices programmatically.

```python
layoutManager = slicer.app.layoutManager()
red = layoutManager.sliceWidget("Red")
redLogic = red.sliceLogic()
# Print current slice offset position
print(redLogic.GetSliceOffset())
# Change slice position
redLogic.SetSliceOffset(20)
```

## Change Slice Orientation

Apply a rotation to a slice view to create an oblique orientation. Useful for viewing structures that are not aligned with standard anatomical planes.

```python
sliceNode = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
sliceToRas = sliceNode.GetSliceToRAS()
transform = vtk.vtkTransform()
transform.SetMatrix(sliceToRas)
transform.RotateX(20)
transform.RotateY(15)
sliceToRas.DeepCopy(transform.GetMatrix())
sliceNode.UpdateMatrices()
```

## Measure Angle Between Two Slice Planes

Calculate and monitor the angle between two slice planes. Useful for verifying orthogonality or measuring angular relationships between oblique views.

```python
sliceNodeIds = ["vtkMRMLSliceNodeRed", "vtkMRMLSliceNodeYellow"]

# Print angles between slice nodes
def ShowAngle(unused1=None, unused2=None):
    sliceNormalVector = []
    for sliceNodeId in sliceNodeIds:
        sliceToRAS = slicer.mrmlScene.GetNodeByID(sliceNodeId).GetSliceToRAS()
        sliceNormalVector.append([sliceToRAS.GetElement(0, 2), sliceToRAS.GetElement(1, 2), sliceToRAS.GetElement(2, 2)])
    angleRad = vtk.vtkMath.AngleBetweenVectors(sliceNormalVector[0], sliceNormalVector[1])
    angleDeg = vtk.vtkMath.DegreesFromRadians(angleRad)
    print("Angle between slice planes = {0:0.3f}".format(angleDeg))

# Observe slice node changes
for sliceNodeId in sliceNodeIds:
    slicer.mrmlScene.GetNodeByID(sliceNodeId).AddObserver(vtk.vtkCommand.ModifiedEvent, ShowAngle)

# Print current angle
ShowAngle()
```

## Set Slice Position and Orientation from a Normal Vector and Position

Set a slice view to display an arbitrary plane defined by a normal vector and a point. Useful for viewing along a specific anatomical direction, such as along a vessel or nerve pathway.

```python
def setSlicePoseFromSliceNormalAndPosition(sliceNode, sliceNormal, slicePosition, defaultViewUpDirection=None, backupViewRightDirection=None):
    """
    Set slice pose from the provided plane normal and position. View up direction is determined automatically,
    to make view up point towards defaultViewUpDirection.
    :param defaultViewUpDirection Slice view will be spinned in-plane to match point approximately this up direction. Default: patient superior.
    :param backupViewRightDirection Slice view will be spinned in-plane to match point approximately this right direction
      if defaultViewUpDirection is too similar to sliceNormal. Default: patient left.
    """
    # Fix up input directions
    if defaultViewUpDirection is None:
        defaultViewUpDirection = [0, 0, 1]
    if backupViewRightDirection is None:
        backupViewRightDirection = [-1, 0, 0]
    if sliceNormal[1] >= 0:
        sliceNormalStandardized = sliceNormal
    else:
        sliceNormalStandardized = [-sliceNormal[0], -sliceNormal[1], -sliceNormal[2]]
    # Compute slice axes
    sliceNormalViewUpAngle = vtk.vtkMath.AngleBetweenVectors(sliceNormalStandardized, defaultViewUpDirection)
    angleTooSmallThresholdRad = 0.25
    if sliceNormalViewUpAngle > angleTooSmallThresholdRad and sliceNormalViewUpAngle < vtk.vtkMath.Pi() - angleTooSmallThresholdRad:
        viewUpDirection = defaultViewUpDirection
        sliceAxisY = viewUpDirection
        sliceAxisX = [0, 0, 0]
        vtk.vtkMath.Cross(sliceAxisY, sliceNormalStandardized, sliceAxisX)
    else:
        sliceAxisX = backupViewRightDirection
    # Set slice axes
    sliceNode.SetSliceToRASByNTP(sliceNormalStandardized[0], sliceNormalStandardized[1], sliceNormalStandardized[2],
        sliceAxisX[0], sliceAxisX[1], sliceAxisX[2],
        slicePosition[0], slicePosition[1], slicePosition[2], 0)

# Example usage:
sliceNode = getNode("vtkMRMLSliceNodeRed")
transformNode = getNode("Transform_3")
transformMatrix = vtk.vtkMatrix4x4()
transformNode.GetMatrixTransformToParent(transformMatrix)
sliceNormal = [transformMatrix.GetElement(0, 2), transformMatrix.GetElement(1, 2), transformMatrix.GetElement(2, 2)]
slicePosition = [transformMatrix.GetElement(0, 3), transformMatrix.GetElement(1, 3), transformMatrix.GetElement(2, 3)]
setSlicePoseFromSliceNormalAndPosition(sliceNode, sliceNormal, slicePosition)
```

## Show Slice Views in 3D Window

Display the slice planes as visible surfaces in the 3D view. Useful for understanding the spatial relationship between slices and 3D structures.

```python
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
    controller = layoutManager.sliceWidget(sliceViewName).sliceController()
    controller.setSliceVisible(True)
```

To hide slices from the 3D view:

```python
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
    controller = layoutManager.sliceWidget(sliceViewName).sliceController()
    controller.setSliceVisible(False)
```

## Change Default Slice View Orientation

Modify the orientation presets for slice views. Useful when working with non-standard imaging conventions or when the default orientations do not match the data acquisition.

```python
# Axial slice axes:
#  1 0 0
#  0 1 0
#  0 0 1
axialSliceToRas = vtk.vtkMatrix3x3()

# Coronal slice axes:
#  1 0 0
#  0 0 -1
#  0 1 0
coronalSliceToRas = vtk.vtkMatrix3x3()
coronalSliceToRas.SetElement(1, 1, 0)
coronalSliceToRas.SetElement(1, 2, -1)
coronalSliceToRas.SetElement(2, 1, 1)
coronalSliceToRas.SetElement(2, 2, 0)

# Replace orientation presets in all existing slice nodes and in the default slice node
sliceNodes = slicer.util.getNodesByClass("vtkMRMLSliceNode")
sliceNodes.append(slicer.mrmlScene.GetDefaultNodeByClass("vtkMRMLSliceNode"))
for sliceNode in sliceNodes:
    orientationPresetName = sliceNode.GetOrientation()
    sliceNode.RemoveSliceOrientationPreset("Axial")
    sliceNode.AddSliceOrientationPreset("Axial", axialSliceToRas)
    sliceNode.RemoveSliceOrientationPreset("Coronal")
    sliceNode.AddSliceOrientationPreset("Coronal", coronalSliceToRas)
    sliceNode.SetOrientation(orientationPresetName)
```

## Set All Slice Views Linked by Default

Link all slice views so that scrolling, zoom, and other interactions in one slice view are mirrored in all others. Useful for comparing corresponding locations across multiple views.

```python
# Set linked slice views in all existing slice composite nodes and in the default node
sliceCompositeNodes = slicer.util.getNodesByClass("vtkMRMLSliceCompositeNode")
defaultSliceCompositeNode = slicer.mrmlScene.GetDefaultNodeByClass("vtkMRMLSliceCompositeNode")
if not defaultSliceCompositeNode:
    defaultSliceCompositeNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLSliceCompositeNode")
    defaultSliceCompositeNode.UnRegister(None)
    slicer.mrmlScene.AddDefaultNode(defaultSliceCompositeNode)
sliceCompositeNodes.append(defaultSliceCompositeNode)
for sliceCompositeNode in sliceCompositeNodes:
    sliceCompositeNode.SetLinkedControl(True)
```

## Set Crosshair Jump Mode to Centered by Default

Configure the crosshair so that clicking in one slice view centers all other slice views on the clicked position. This is a persistent setting.

```python
crosshair = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLCrosshairNode")
crosshair.SetCrosshairBehavior(crosshair.CenteredJumpSlice)
```

Other jump modes:
- `crosshair.OffsetJumpSlice` -- Jump to the position without centering
- `crosshair.NoAction` -- Do not jump other views

## Set Up Custom Units in Slice View Ruler

Replace the default ruler scale presets with custom units. Useful when working with microscopy or other non-clinical imaging where standard mm units are not appropriate.

```python
appLogic = slicer.app.applicationLogic()
layoutManagerLogic = slicer.app.layoutManager().layoutLogic()
for viewNode in layoutManagerLogic.GetViewNodes():
    if type(viewNode) is not slicer.vtkMRMLSliceNode:
        continue
    displayableManager = appLogic.GetViewDisplayableManagerByClassName(viewNode, "vtkMRMLRulerDisplayableManager")
    displayableManager.RemoveAllRulerScalePresets()
    displayableManager.AddRulerScalePreset(   0.001, 5, 2, "nm", 1000.0)
    displayableManager.AddRulerScalePreset(   0.010, 5, 2, "nm", 1000.0)
    displayableManager.AddRulerScalePreset(   0.100, 5, 2, "nm", 1000.0)
    displayableManager.AddRulerScalePreset(   0.500, 5, 1, "nm", 1000.0)
    displayableManager.AddRulerScalePreset(   1.0,   5, 2, "um",    1.0)
    displayableManager.AddRulerScalePreset(   5.0,   5, 1, "um",    1.0)
    displayableManager.AddRulerScalePreset(  10.0,   5, 2, "um",    1.0)
    displayableManager.AddRulerScalePreset(  50.0,   5, 1, "um",    1.0)
    displayableManager.AddRulerScalePreset( 100.0,   5, 2, "um",    1.0)
    displayableManager.AddRulerScalePreset( 500.0,   5, 1, "um",    1.0)
    displayableManager.AddRulerScalePreset(1000.0,   5, 2, "mm",    0.001)
```

`AddRulerScalePreset` parameters: `(scaleLength, numberOfMajorDivisions, numberOfMinorDivisions, displayedUnitName, displayedScale)`

## Center the 3D View on the Scene

Reset the 3D view camera to frame all visible content. Useful after loading new data or changing visibility settings.

```python
layoutManager = slicer.app.layoutManager()
threeDWidget = layoutManager.threeDWidget(0)
threeDView = threeDWidget.threeDView()
threeDView.resetFocalPoint()
```

To also reset zoom level:

```python
threeDView.resetCamera()
```

## Rotate the 3D View

Apply yaw, pitch, or roll rotations to the 3D view camera. Useful for programmatic view animation or setting specific viewing angles.

```python
layoutManager = slicer.app.layoutManager()
threeDWidget = layoutManager.threeDWidget(0)
threeDView = threeDWidget.threeDView()
threeDView.yaw()
```

Other rotation methods:
- `threeDView.pitch()` -- rotate around the horizontal axis
- `threeDView.roll()` -- rotate around the viewing direction
- `threeDView.rotateToViewAxis(n)` -- rotate to a predefined axis (0=L, 1=P, 2=S, 3=oblique)

### Set a Specific View Direction

```python
layoutManager = slicer.app.layoutManager()
threeDWidget = layoutManager.threeDWidget(0)
threeDView = threeDWidget.threeDView()
# Look from anterior
threeDView.rotateToViewAxis(3)
threeDView.resetFocalPoint()
threeDView.resetCamera()
```

## Change 3D View Background Color

Set the background color of a 3D view. Slicer uses a gradient between two colors. Set both to the same value for a solid background.

```python
viewNode = slicer.app.layoutManager().threeDWidget(0).mrmlViewNode()
viewNode.SetBackgroundColor(1, 0, 0)
viewNode.SetBackgroundColor2(1, 0, 0)
```

For a black background (useful for screenshots):

```python
viewNode = slicer.app.layoutManager().threeDWidget(0).mrmlViewNode()
viewNode.SetBackgroundColor(0, 0, 0)
viewNode.SetBackgroundColor2(0, 0, 0)
```

## Change Box Color in 3D View

Change the color of the orientation box displayed in the 3D view.

```python
viewNode = slicer.app.layoutManager().threeDWidget(0).mrmlViewNode()
viewNode.SetBoxColor(1, 0, 0)
```

To hide the box entirely:

```python
viewNode = slicer.app.layoutManager().threeDWidget(0).mrmlViewNode()
viewNode.SetBoxVisible(False)
```

## Show a Slice View Outside the View Layout

Create a standalone slice view widget that is not managed by the layout manager. Useful for building custom multi-view interfaces, secondary monitors, or pop-out views.

```python
# layout name is used to create and identify the underlying slice node and should be set to a value
# that is not used in any of the layouts owned by the layout manager
layoutName = "TestSlice1"
layoutLabel = "TS1"
layoutColor = [1.0, 1.0, 0.0]
# ownerNode manages this view instead of the layout manager (it can be any node in the scene)
viewOwnerNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode")

# Create MRML nodes
viewLogic = slicer.vtkMRMLSliceLogic()
viewLogic.SetMRMLScene(slicer.mrmlScene)
viewNode = viewLogic.AddSliceNode(layoutName)
viewNode.SetLayoutLabel(layoutLabel)
viewNode.SetLayoutColor(layoutColor)
viewNode.SetAndObserveParentLayoutNodeID(viewOwnerNode.GetID())

# Create widget
viewWidget = slicer.qMRMLSliceWidget()
viewWidget.setMRMLScene(slicer.mrmlScene)
viewWidget.setMRMLSliceNode(viewNode)
sliceLogics = slicer.app.applicationLogic().GetSliceLogics()
viewWidget.setSliceLogics(sliceLogics)
sliceLogics.AddItem(viewWidget.sliceLogic())
viewWidget.show()
```

## Show a 3D View Outside the View Layout

Create a standalone 3D view widget that is not managed by the layout manager.

```python
# layout name is used to create and identify the underlying view node and should be set to a value
# that is not used in any of the layouts owned by the layout manager
layoutName = "Test3DView"
layoutLabel = "T3"
layoutColor = [1.0, 1.0, 0.0]
# ownerNode manages this view instead of the layout manager (it can be any node in the scene)
viewOwnerNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScriptedModuleNode")

# Create MRML node
viewLogic = slicer.vtkMRMLViewLogic()
viewLogic.SetMRMLScene(slicer.mrmlScene)
viewNode = viewLogic.AddViewNode(layoutName)
viewNode.SetLayoutLabel(layoutLabel)
viewNode.SetLayoutColor(layoutColor)
viewNode.SetAndObserveParentLayoutNodeID(viewOwnerNode.GetID())

# Create widget
viewWidget = slicer.qMRMLThreeDWidget()
viewWidget.setMRMLScene(slicer.mrmlScene)
viewWidget.setMRMLViewNode(viewNode)
viewWidget.show()
```

## Access VTK Views, Renderers, and Cameras

Access low-level VTK rendering objects for advanced visualization customization. Useful for adding custom VTK actors, modifying rendering parameters, or integrating with VTK-based processing pipelines.

### Iterate Through 3D Views

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

### Iterate Through Slice Views

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

### Access Low-Level VTK Rendering Objects

```python
renderWindow = view.renderWindow()
renderers = renderWindow.GetRenderers()
renderer = renderers.GetItemAsObject(0)
camera = cameraNode.GetCamera()
```

## Color Tables and Color Legends

### Create Custom Color Table

Create a custom color lookup table for specialized visualization needs.

```python
invertedocean = slicer.vtkMRMLColorTableNode()
invertedocean.SetTypeToUser()
invertedocean.SetNumberOfColors(256)
invertedocean.SetName("InvertedOcean")

for i in range(0, 255):
    invertedocean.SetColor(i, 0.0, 1 - (i + 1e-16) / 255.0, 1.0, 1.0)

slicer.mrmlScene.AddNode(invertedocean)
```

### Show Color Legend for a Volume Node

Display a color legend overlay showing the mapping between scalar values and colors for a volume.

```python
volumeNode = getNode('MRHead')
colorLegendDisplayNode = slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(volumeNode)
```

### Create Custom Color Map and Display Color Legend

Create a procedural colormap with continuous color transitions and display it as a legend.

```python
modelNode = getNode('MyModel')
colorTableRangeMm = 40
title = "Radial\nCompression\n"
labelFormat = "%4.1f mm"

# Create color node
colorNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLProceduralColorNode")
colorNode.UnRegister(None)
colorNode.SetName(slicer.mrmlScene.GenerateUniqueName("MyColormap"))
colorNode.SetAttribute("Category", "MyModule")
colorNode.SetHideFromEditors(False)
slicer.mrmlScene.AddNode(colorNode)

# Specify colormap
colorMap = colorNode.GetColorTransferFunction()
colorMap.RemoveAllPoints()
colorMap.AddRGBPoint(colorTableRangeMm * 0.0, 0.0, 0.0, 1.0)
colorMap.AddRGBPoint(colorTableRangeMm * 0.2, 0.0, 1.0, 1.0)
colorMap.AddRGBPoint(colorTableRangeMm * 0.5, 1.0, 1.0, 0.0)
colorMap.AddRGBPoint(colorTableRangeMm * 1.0, 1.0, 0.0, 0.0)

# Display color legend
modelNode.GetDisplayNode().SetAndObserveColorNodeID(colorNode.GetID())
colorLegendDisplayNode = slicer.modules.colors.logic().AddDefaultColorLegendDisplayNode(modelNode)
colorLegendDisplayNode.SetTitleText(title)
colorLegendDisplayNode.SetLabelFormat(labelFormat)
```

## Screen Capture

Capture views as image files for documentation, presentations, or automated reporting.

### Capture the Full Slicer Screen

```python
img = qt.QPixmap.grabWidget(slicer.util.mainWindow()).toImage()
img.save("/tmp/test.png")
```

### Capture All Views

```python
import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
cap.showViewControllers(False)
cap.captureImageFromView(None, "/tmp/test.png")
cap.showViewControllers(True)
```

### Capture a Single View

```python
viewNodeID = "vtkMRMLViewNode1"
import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
view = cap.viewFromNode(slicer.mrmlScene.GetNodeByID(viewNodeID))
cap.captureImageFromView(view, "/tmp/test.png")
```

### Capture a Slice View Sweep into a Series of PNG Files

Sweep through a slice range and save each position as an image.

```python
import ScreenCapture
ScreenCapture.ScreenCaptureLogic().captureSliceSweep(
    getNode("vtkMRMLSliceNodeRed"), -125.0, 75.0, 30,
    "/tmp", "image_%05d.png"
)
```

### Capture 3D View with Transparent Background

```python
view = slicer.app.layoutManager().threeDWidget(0).threeDView()
view.mrmlViewNode().SetBackgroundColor(0, 0, 0)
view.mrmlViewNode().SetBackgroundColor2(0, 0, 0)
view.forceRender()
renderWindow = view.renderWindow()
renderWindow.SetAlphaBitPlanes(1)
wti = vtk.vtkWindowToImageFilter()
wti.SetInputBufferTypeToRGBA()
wti.SetInput(renderWindow)
writer = vtk.vtkPNGWriter()
writer.SetFileName("/tmp/screenshot.png")
writer.SetInputConnection(wti.GetOutputPort())
writer.Write()
```

### Capture Slice View with White Background

```python
sliceViewName = "Red"
filename = "/tmp/screenshot.png"

view = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceView()
view.setBackgroundColor(qt.QColor.fromRgbF(1, 1, 1))
view.forceRender()

import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
cap.captureImageFromView(view, filename)
```

### Save a Series of Images from a Slice View

Iterate through all slices and save each as a separate image file.

```python
layoutName = "Green"
imagePathPattern = "/tmp/image-%03d.png"
steps = 10

widget = slicer.app.layoutManager().sliceWidget(layoutName)
view = widget.sliceView()
logic = widget.sliceLogic()
bounds = [0,] * 6
logic.GetSliceBounds(bounds)

for step in range(steps):
    offset = bounds[4] + step / (1. * steps) * (bounds[5] - bounds[4])
    logic.SetSliceOffset(offset)
    view.forceRender()
    image = qt.QPixmap.grabWidget(view).toImage()
    image.save(imagePathPattern % step)
```

## Hanging Protocol (PET/CT Example)

Set up a hanging protocol that automatically arranges CT and PET volumes with appropriate display settings. This example creates a Ctrl+9 keyboard shortcut for a PET/CT viewing configuration.

```python
def useHangingProtocolPetCt():
    ctImage = None
    petImage = None

    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    petColor = slicer.mrmlScene.GetFirstNodeByName('PET-Heat')
    for imageNode in slicer.util.getNodesByClass('vtkMRMLScalarVolumeNode'):
        imageNode.HardenTransform()
        imageItem = shNode.GetItemByDataNode(imageNode)
        modality = shNode.GetItemAttribute(imageItem, 'DICOM.Modality')
        if modality == "CT":
            ctImage = imageNode
            ctImage.GetVolumeDisplayNode().SetAndObserveColorNodeID(petColor.GetID())
            slicer.modules.volumes.logic().ApplyVolumeDisplayPreset(ctImage.GetVolumeDisplayNode(), "CT_ABDOMEN")
        elif modality == "PT":
            petImage = imageNode
            petImage.GetVolumeDisplayNode().SetAndObserveColorNodeID(petColor.GetID())
            petImage.GetVolumeDisplayNode().SetWindowLevelMinMax(0, 20)

    slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpView)
    slicer.util.setSliceViewerLayers(background=ctImage, foreground=petImage, foregroundOpacity=0.3, fit=True)

    vrLogic = slicer.modules.volumerendering.logic()
    vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(petImage)
    vrDisplayNode.SetVisibility(True)
    vrDisplayNode.SetFollowVolumeDisplayNode(True)

    layoutManager = slicer.app.layoutManager()
    for sliceViewName in layoutManager.sliceViewNames():
        controller = layoutManager.sliceWidget(sliceViewName).sliceController()
        controller.setSliceVisible(True)

    layoutManager = slicer.app.layoutManager()
    threeDWidget = layoutManager.threeDWidget(0)
    threeDView = threeDWidget.threeDView()
    threeDView.rotateToViewAxis(3)
    threeDView.resetFocalPoint()
    threeDView.resetCamera()

    return [ctImage, petImage]

# Register keyboard shortcut
shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("Ctrl+9"))
shortcut.connect("activated()", useHangingProtocolPetCt)
```

## Related Skills

- **slicer-volumes** -- Volume loading, display presets, window/level, and volume rendering. Cross-references with `setSliceViewerLayers()` for setting background/foreground volumes.
- **slicer-segmentation** -- Segmentation editing and visualization. Segments can be displayed in specific views using the same `SetViewNodeIDs()` pattern.
- **slicer-markups** -- Markup points, lines, and curves. Markups interact with crosshair position and can be restricted to specific views.
- **slicer-transforms** -- Spatial transforms that affect slice positioning and orientation.

## Resources

- **Script Repository**: https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html
- **Layout Logic Source**: https://github.com/Slicer/Slicer/blob/main/Libs/MRML/Logic/vtkMRMLLayoutLogic.cxx
- **MRML Overview**: https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html
- **Developer Guide**: https://slicer.readthedocs.io/en/latest/developer_guide/slicer.html
