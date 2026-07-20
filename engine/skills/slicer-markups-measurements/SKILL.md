---
name: slicer-markups-measurements
description: Markup creation, placement, measurement, and analysis including control points, curves, planes, ROIs, fiducials, distance/angle measurements, display properties, and JSON/CSV import/export. Use for annotations, measurements, and spatial analysis.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Markups and Measurements

## Overview

This skill covers all markup and measurement operations in 3D Slicer. Markups are interactive annotations that can be placed in 2D and 3D views, including point lists (fiducials), lines, curves, angles, planes, and regions of interest (ROIs). They support distance, angle, and spatial measurements, and can be saved/loaded in JSON, CSV, and FCSV formats.

All code runs in 3D Slicer's Python environment where the following modules are available:
- `slicer` - Core Slicer Python API
- `vtk` - Visualization Toolkit for 3D geometry operations
- `qt` - Qt framework for UI elements
- `numpy` / `np` - Numerical computing (import explicitly)
- `slicer.util` - Utility functions for node access, file I/O, and rendering
- `slicer.modules.markups.logic()` - Markups module logic for placement, fitting, and import/export

See also: `slicer-volumes` skill for volume operations, `slicer-segmentations` skill for segmentation, `slicer-models` skill for 3D model manipulation.

---

## Save Markups to File

Save a markups node to a JSON file using `slicer.util.saveNode()`. The recommended file extension is `.mkp.json`.

```python
markupsNode = slicer.util.getNode('F')
slicer.util.saveNode(markupsNode, "<output_path>/MyMarkups.mkp.json")
```

Export control points to CSV format:

```python
slicer.modules.markups.logic().ExportControlPointsToCSV(markupsNode, "<output_path>/MyControlPoints.csv")
```

## Load Markups from File

Load markups from a JSON file:

```python
markupsNode = slicer.util.loadMarkups("<input_path>/MyMarkups.mkp.json")
```

Import control points from CSV into an existing markups node:

```python
markupsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode")
slicer.modules.markups.logic().ImportControlPointsFromCSV(markupsNode, "<input_path>/MyControlPoints.csv")
```

## Load Markups Point List from File

Load a legacy FCSV file as a markups point list:

```python
slicer.util.loadMarkups("<input_path>/F.fcsv")
```

## Adding Control Points Programmatically

Add a control point at the origin using the markups logic:

```python
slicer.modules.markups.logic().AddControlPoint()
```

Add a control point at a specific RAS coordinate:

```python
slicer.modules.markups.logic().AddControlPoint(1.0, -2.0, 3.3)
```

Create a fiducial node and add named control points:

```python
markupsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "F")
markupsNode.AddControlPoint(vtk.vtkVector3d(10, 20, 30), "point 1")
markupsNode.AddControlPoint(vtk.vtkVector3d(40, 50, 60), "point 2")
```

## Draw a Curve from Numpy Array

Create a curve node and populate it from a numpy array of 3D point positions using `slicer.util.updateMarkupsControlPointsFromArray()`:

```python
# Create random numpy array to use as input
import numpy as np
pointPositions = np.random.uniform(-50,50,size=[15,3])

# Create curve from numpy array
curveNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode")
slicer.util.updateMarkupsControlPointsFromArray(curveNode, pointPositions)
```

Alternatively, add control points one at a time from a numpy array:

```python
import numpy as np

curveNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode", "C")
curveNode.CreateDefaultDisplayNodes()

points = np.array([
  [10.0, 10.0, 0.0],
  [20.0, 15.0, 0.0],
  [30.0, 10.0, 0.0],
  [40.0, 20.0, 0.0],
])

for point in points:
  curveNode.AddControlPoint(vtk.vtkVector3d(point))
```

## Add a Button to Module GUI to Activate Control Point Placement

Use `slicer.qSlicerMarkupsPlaceWidget` to create a placement button widget that can be embedded in a module GUI:

```python
w=slicer.qSlicerMarkupsPlaceWidget()
w.setMRMLScene(slicer.mrmlScene)
markupsNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsCurveNode")
w.setCurrentNode(slicer.mrmlScene.GetNodeByID(markupsNode.GetID()))
# Hide all buttons and only show place button
w.buttonsVisible=False
w.placeButton().show()
w.show()
```

## Adding Control Points via Mouse Clicks

Start placement mode so that mouse clicks add control points. Set `placeModePersistence` to `1` to keep placing multiple points, or `0` for a single point.

Simple approach using markups logic:

```python
placeModePersistence = 1
slicer.modules.markups.logic().StartPlaceMode(placeModePersistence)
```

Lower-level approach using selection and interaction nodes directly:

```python
selectionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSelectionNodeSingleton")
selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
placeModePersistence = 1
interactionNode.SetPlaceModePersistence(placeModePersistence)
# mode 1 is Place, can also be accessed via slicer.vtkMRMLInteractionNode().Place
interactionNode.SetCurrentInteractionMode(1)
```

To stop placement mode and return to view transform mode:

```python
interactionNode = slicer.mrmlScene.GetNodeByID("vtkMRMLInteractionNodeSingleton")
interactionNode.SwitchToViewTransformMode()
# also turn off place mode persistence if required
interactionNode.SetPlaceModePersistence(0)
```

## Access Markups Point List Properties

Access and modify control point properties such as position, label, selection state, and visibility:

```python
pointListNode = getNode("vtkMRMLMarkupsFiducialNode1")
n = pointListNode.AddControlPoint([4.0, 5.5, -6.0])
pointListNode.SetNthControlPointLabel(n, "new label")
# each control point is given a unique id which can be accessed from the superclass level
id1 = pointListNode.GetNthControlPointID(n)
# manually set the position
pointListNode.SetNthControlPointPosition(n, 6.0, 7.0, 8.0)
# set the label
pointListNode.SetNthControlPointLabel(n, "New label")
# set the selected flag, only selected = 1 control points will be passed to CLIs
pointListNode.SetNthControlPointSelected(n, 1)
# set the visibility flag
pointListNode.SetNthControlPointVisibility(n, 0)
```

Loop through all control points and print their RAS and world positions:

```python
pointListNode = slicer.util.getNode("F")
numControlPoints = pointListNode.GetNumberOfControlPoints()
for i in range(numControlPoints):
  ras = vtk.vtkVector3d(0,0,0)
  pointListNode.GetNthControlPointPosition(i,ras)
  # the world position is the RAS position with any transform matrices applied
  world = [0.0, 0.0, 0.0]
  pointListNode.GetNthControlPointPositionWorld(i,world)
  print(i,": RAS =",ras,", world =",world)
```

## Define/Edit a Circular Region of Interest in a Slice Viewer

Create a sphere model defined by two control points (center and circumference) that updates interactively as the control points are moved:

```python
# Update the sphere from the control points
def UpdateSphere(param1, param2):
  """Update the sphere from the control points
  """
  import math
  pointListNode = slicer.util.getNode("F")
  centerPointCoord = [0.0, 0.0, 0.0]
  pointListNode.GetNthControlPointPosition(0,centerPointCoord)
  circumferencePointCoord = [0.0, 0.0, 0.0]
  pointListNode.GetNthControlPointPosition(1,circumferencePointCoord)
  sphere.SetCenter(centerPointCoord)
  radius=math.sqrt((centerPointCoord[0]-circumferencePointCoord[0])**2+(centerPointCoord[1]-circumferencePointCoord[1])**2+(centerPointCoord[2]-circumferencePointCoord[2])**2)
  sphere.SetRadius(radius)
  sphere.SetPhiResolution(30)
  sphere.SetThetaResolution(30)
  sphere.Update()

# Get point list node from scene
pointListNode = slicer.util.getNode("F")
sphere = vtk.vtkSphereSource()
UpdateSphere(0,0)

# Create model node and add to scene
modelsLogic = slicer.modules.models.logic()
model = modelsLogic.AddModel(sphere.GetOutput())
model.GetDisplayNode().SetSliceIntersectionVisibility(True)
model.GetDisplayNode().SetSliceIntersectionThickness(3)
model.GetDisplayNode().SetColor(1,1,0)

# Call UpdateSphere whenever the control points are changed
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, UpdateSphere, 2)
```

## Fit Sphere to Control Points

Fit a sphere to a set of markup fiducial control points using least-squares optimization from scipy. This is useful for measuring spherical structures.

```python
# Get markup node from scene
pointListNode = slicer.util.getNode("F")

from scipy.optimize import least_squares
import numpy

def fit_sphere_least_squares(x_values, y_values, z_values, initial_parameters, bounds=((-numpy.inf, -numpy.inf, -numpy.inf, -numpy.inf),(numpy.inf, numpy.inf, numpy.inf, numpy.inf))):
  """
  Source: https://github.com/thompson318/scikit-surgery-sphere-fitting/blob/master/sksurgeryspherefitting/algorithms/sphere_fitting.py
  Uses scipy's least squares optimisor to fit a sphere to a set
  of 3D Points
  :return: x: an array containing the four fitted parameters
  :return: ier: int An integer flag. If it is equal to 1, 2, 3 or 4, the
          solution was found.
  :param: (x,y,z) three arrays of equal length containing the x, y, and z
          coordinates.
  :param: an array containing four initial values (centre, and radius)
  """
  return least_squares(_calculate_residual_sphere, initial_parameters, bounds=bounds, method="trf", jac="3-point", args=(x_values, y_values, z_values))

def _calculate_residual_sphere(parameters, x_values, y_values, z_values):
  """
  Source: https://github.com/thompson318/scikit-surgery-sphere-fitting/blob/master/sksurgeryspherefitting/algorithms/sphere_fitting.py
  Calculates the residual error for an x,y,z coordinates, fitted
  to a sphere with centre and radius defined by the parameters tuple
  :return: The residual error
  :param: A tuple of the parameters to be optimised, should contain [x_centre, y_centre, z_centre, radius]
  :param: arrays containing the x,y, and z coordinates.
  """
  #extract the parameters
  x_centre, y_centre, z_centre, radius = parameters
  #use numpy's sqrt function here, which works by element on arrays
  distance_from_centre = numpy.sqrt((x_values - x_centre)**2 + (y_values - y_centre)**2 + (z_values - z_centre)**2)
  return distance_from_centre - radius

# Fit a sphere to the markups fidicual points
markupsPositions = slicer.util.arrayFromMarkupsControlPoints(pointListNode)
import numpy as np
# initial guess
center0 = np.mean(markupsPositions, 0)
radius0 = np.linalg.norm(np.amin(markupsPositions,0)-np.amax(markupsPositions,0))/2.0
fittingResult = fit_sphere_least_squares(markupsPositions[:,0], markupsPositions[:,1], markupsPositions[:,2], [center0[0], center0[1], center0[2], radius0])
[centerX, centerY, centerZ, radius] = fittingResult["x"]

# Create a sphere using the fitted parameters
sphere = vtk.vtkSphereSource()
sphere.SetPhiResolution(30)
sphere.SetThetaResolution(30)
sphere.SetCenter(centerX, centerY, centerZ)
sphere.SetRadius(radius)
sphere.Update()

# Add the sphere to the scene
modelsLogic = slicer.modules.models.logic()
model = modelsLogic.AddModel(sphere.GetOutput())
model.GetDisplayNode().SetSliceIntersectionVisibility(True)
model.GetDisplayNode().SetSliceIntersectionThickness(3)
model.GetDisplayNode().SetColor(1,1,0)
```

## Fit Markups ROI to Volume

Create a markups ROI node and fit it to encompass a volume node, optionally snapping to voxel grid alignment:

```python
volumeNode = getNode('MRHead')

# Create a new ROI that will be fit to volumeNode
roiNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")

cropVolumeParameters = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
cropVolumeParameters.SetInputVolumeNodeID(volumeNode.GetID())
cropVolumeParameters.SetROINodeID(roiNode.GetID())
slicer.modules.cropvolume.logic().SnapROIToVoxelGrid(cropVolumeParameters)  # optional (rotates the ROI to match the volume axis directions)
slicer.modules.cropvolume.logic().FitROIToInputVolume(cropVolumeParameters)
slicer.mrmlScene.RemoveNode(cropVolumeParameters)
```

## Fit Markups Plane to Model

Compute the best-fitting plane to a model's surface points and display it as a markups plane node:

```python
inputModel = getNode('InputModel')

# Compute best fit plane
center = [0.0, 0.0, 0.0]
normal = [0.0, 0.0, 1.0]
vtk.vtkPlane.ComputeBestFittingPlane(inputModel.GetPolyData().GetPoints(), center, normal)

# Display best fit plane as a markups plane
planeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLMarkupsPlaneNode')
planeNode.SetCenter(center)
planeNode.SetNormal(normal)
```

## Measure Angle Between Two Markup Planes

Compute and display the angle between two markup plane nodes using their world normals, with live updates via observers:

```python
planeNodeNames = ["P", "P_1"]

# Print angles between slice nodes
def ShowAngle(unused1=None, unused2=None):
  planeNormalVectors = []
  for planeNodeName in planeNodeNames:
    planeNode = slicer.util.getFirstNodeByClassByName("vtkMRMLMarkupsPlaneNode", planeNodeName)
    planeNormalVector = [0.0, 0.0, 0.0]
    planeNode.GetNormalWorld(planeNormalVector)
    planeNormalVectors.append(planeNormalVector)
  angleRad = vtk.vtkMath.AngleBetweenVectors(planeNormalVectors[0], planeNormalVectors[1])
  angleDeg = vtk.vtkMath.DegreesFromRadians(angleRad)
  print("Angle between planes {0} and {1} = {2:0.3f}".format(planeNodeNames[0], planeNodeNames[1], angleDeg))

# Observe plane node changes
for planeNodeName in planeNodeNames:
  planeNode = slicer.util.getFirstNodeByClassByName("vtkMRMLMarkupsPlaneNode", planeNodeName)
  planeNode.AddObserver(slicer.vtkMRMLMarkupsPlaneNode.PointModifiedEvent, ShowAngle)

# Print current angle
ShowAngle()
```

## Measure Angle Between Two Markup Lines

Compute and display the angle between two markup line nodes using their direction vectors, with live updates via observers:

```python
lineNodeNames = ["L", "L_1"]

# Print angles between slice nodes
def ShowAngle(unused1=None, unused2=None):
  import numpy as np
  lineDirectionVectors = []
  for lineNodeName in lineNodeNames:
    lineNode = slicer.util.getFirstNodeByClassByName("vtkMRMLMarkupsLineNode", lineNodeName)
    lineStartPos = np.zeros(3)
    lineEndPos = np.zeros(3)
    lineNode.GetNthControlPointPositionWorld(0, lineStartPos)
    lineNode.GetNthControlPointPositionWorld(1, lineEndPos)
    lineDirectionVector = (lineEndPos-lineStartPos)/np.linalg.norm(lineEndPos-lineStartPos)
    lineDirectionVectors.append(lineDirectionVector)
  angleRad = vtk.vtkMath.AngleBetweenVectors(lineDirectionVectors[0], lineDirectionVectors[1])
  angleDeg = vtk.vtkMath.DegreesFromRadians(angleRad)
  print("Angle between lines {0} and {1} = {2:0.3f}".format(lineNodeNames[0], lineNodeNames[1], angleDeg))

# Observe line node changes
for lineNodeName in lineNodeNames:
  lineNode = slicer.util.getFirstNodeByClassByName("vtkMRMLMarkupsLineNode", lineNodeName)
  lineNode.AddObserver(slicer.vtkMRMLMarkupsLineNode.PointModifiedEvent, ShowAngle)

# Print current angle
ShowAngle()
```

## Project a Line to a Plane

Project a markup line onto a markup plane by transforming line endpoints into the plane's coordinate system, zeroing the normal component, and transforming back:

```python
lineNode = getNode('L')
planeNode = getNode('P')

# Create new node for storing the projected line node
projectedLineNode = slicer.mrmlScene.AddNewNodeByClass(lineNode.GetClassName(), lineNode.GetName()+" projected")

# Get transforms
planeToWorld = vtk.vtkMatrix4x4()
planeNode.GetObjectToWorldMatrix(planeToWorld)
worldToPlane = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Invert(planeToWorld, worldToPlane)

# Project each point
for pointIndex in range(2):
    point_World = [*lineNode.GetNthControlPointPositionWorld(pointIndex), 1.0]
    point_Plane = worldToPlane.MultiplyPoint(point_World)
    projectedPoint_Plane = [point_Plane[0], point_Plane[1], 0.0, 1.0]
    projectedPoint_World = planeToWorld.MultiplyPoint(projectedPoint_Plane)
    projectedLineNode.AddControlPoint(projectedPoint_World[0:3])
```

## Measure Distances of Points from a Plane

Measure the distance of each control point in a point list from a markup plane by transforming into the plane's coordinate system:

```python
pointListNode = getNode('F')
planeNode = getNode('P')

# Get transformation that gets point coordinates relative to the plane
planeToWorld = vtk.vtkMatrix4x4()
planeNode.GetObjectToWorldMatrix(planeToWorld)
worldToPlane = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Invert(planeToWorld, worldToPlane)

for pointIndex in range(pointListNode.GetNumberOfControlPoints()):
    # Get point position in world coordinate system
    point_World = [*pointListNode.GetNthControlPointPositionWorld(pointIndex), 1.0]
    # Get point position in the plane coordinate system
    point_Plane = worldToPlane.MultiplyPoint(point_World)
    # Third axis in the plane coordinate system is the plane normal direction, therefore the third coordinate
    # value is the distance from the plane
    distanceFromPlane = abs(point_Plane[2])
    print(f"Distance of point {pointListNode.GetNthControlPointLabel(pointIndex)} from plane: {distanceFromPlane:.2f}")
```

## Measure Distances of Points from a Line

Compute the perpendicular distance of each control point in a point list from a markup line using cross product:

```python
pointListNode = getNode("F")
lineNode = getNode("L")

# Get point list control point positions and line endpoints as numpy arrays
points = slicer.util.arrayFromMarkupsControlPoints(pointListNode)
line = slicer.util.arrayFromMarkupsControlPoints(lineNode)
# Compute distance of control points from the line
from numpy import cross
from numpy.linalg import norm
for i, point in enumerate(points):
    d = norm(cross(line[1]-line[0],point-line[0])/norm(line[1]-line[0]))
    print(f"Point {i}: Position = {point}. Distance from line = {d}.")
```

## Set Slice Position and Orientation from 3 Markups Control Points

Compute a slice plane from three control points and apply it to a slice view. The plane is defined by the cross product of two edge vectors, and an observer updates the slice automatically when points move:

```python
# Update plane from control points
def UpdateSlicePlane(param1=None, param2=None):
  # Get control point positions as numpy array
  import numpy as np
  nOfControlPoints = pointListNode.GetNumberOfControlPoints()
  if nOfControlPoints < 3:
    return  # not enough control points
  points = np.zeros([3,nOfControlPoints])
  for i in range(0, nOfControlPoints):
    pointListNode.GetNthControlPointPosition(i, points[:,i])
  # Compute plane position and normal
  planePosition = points.mean(axis=1)
  planeNormal = np.cross(points[:,1] - points[:,0], points[:,2] - points[:,0])
  planeX = points[:,1] - points[:,0]
  sliceNode.SetSliceToRASByNTP(planeNormal[0], planeNormal[1], planeNormal[2],
    planeX[0], planeX[1], planeX[2],
    planePosition[0], planePosition[1], planePosition[2], 0)

# Get point list node from scene
sliceNode = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
pointListNode = slicer.util.getNode("F")

# Update slice plane manually
UpdateSlicePlane()

# Update slice plane automatically whenever points are changed
pointListObservation = [pointListNode, pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, UpdateSlicePlane, 2)]
```

To stop automatic slice plane updates:

```python
pointListObservation[0].RemoveObserver(pointListObservation[1])
```

## Switching to Markups Control Point Placement Mode

Programmatically switch the interaction mode to place control points for a specific markup node:

```python
interactionNode = slicer.app.applicationLogic().GetInteractionNode()
selectionNode = slicer.app.applicationLogic().GetSelectionNode()
selectionNode.SetReferenceActivePlaceNodeClassName("vtkMRMLMarkupsFiducialNode")
pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
selectionNode.SetActivePlaceNodeID(pointListNode.GetID())
interactionNode.SetCurrentInteractionMode(interactionNode.Place)
```

Using a place widget with a callback for placement mode changes:

```python
# Temporary markups point list node
pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")

def placementModeChanged(active):
  print("Placement: " +("active" if active else "inactive"))
  # You can inspect what is in the markups node here, delete the temporary markup point list node, etc.

# Create and set up widget that contains a single "place control point" button. The widget can be placed in the module GUI.
placeWidget = slicer.qSlicerMarkupsPlaceWidget()
placeWidget.setMRMLScene(slicer.mrmlScene)
placeWidget.setCurrentNode(pointListNode)
placeWidget.buttonsVisible=False
placeWidget.placeButton().show()
placeWidget.connect("activeMarkupsFiducialPlaceModeChanged(bool)", placementModeChanged)
placeWidget.show()
```

## Change Markup Point List Display Properties

Modify display properties of markup nodes including visibility, color, and view restriction:

```python
pointListNode = getNode("F")
pointListDisplayNode = pointListNode.GetDisplayNode()
pointListDisplayNode.SetVisibility(False) # Hide all points
pointListDisplayNode.SetVisibility(True) # Show all points
pointListDisplayNode.SetSelectedColor(1,1,0) # Set color to yellow
pointListDisplayNode.SetViewNodeIDs(["vtkMRMLSliceNodeRed", "vtkMRMLViewNode1"]) # Only show in red slice view and first 3D view
```

Additional display property examples:

```python
pointListNode = getNode("F")
displayNode = pointListNode.GetDisplayNode()

# Change color (SelectedColor is used when control points are in "selected" state, which is the default)
displayNode.SetSelectedColor(1, 0, 0)  # red

# Change glyph (point marker) scale
displayNode.SetGlyphScale(3)

# Change label visibility
displayNode.SetPointLabelsVisibility(False)

# Change opacity
displayNode.SetOpacity(0.5)

# Change text scale
displayNode.SetTextScale(3)
```

## Get Notification on Markup Control Point Position Change

Register observers for point modification, start interaction, and end interaction events to track control point changes in real time:

```python
def onMarkupChanged(caller,event):
  markupsNode = caller
  sliceView = markupsNode.GetAttribute(slicer.vtkMRMLMarkupsDisplayNode.GetMovingInSliceViewAttributeName())
  movingMarkupIndex = markupsNode.GetDisplayNode().GetActiveControlPoint()
  if movingMarkupIndex >= 0:
    pos = [0,0,0]
    markupsNode.GetNthControlPointPosition(movingMarkupIndex, pos)
    isPreview = markupsNode.GetNthControlPointPositionStatus(movingMarkupIndex) == slicer.vtkMRMLMarkupsNode.PositionPreview
    if isPreview:
      logging.info("Point {0} is previewed at {1} in slice view {2}".format(movingMarkupIndex, pos, sliceView))
    else:
      logging.info("Point {0} was moved {1} in slice view {2}".format(movingMarkupIndex, pos, sliceView))
  else:
    logging.info("Points modified: slice view = {0}".format(sliceView))

def onMarkupStartInteraction(caller, event):
  markupsNode = caller
  sliceView = markupsNode.GetAttribute(slicer.vtkMRMLMarkupsDisplayNode.GetMovingInSliceViewAttributeName())
  movingMarkupIndex = markupsNode.GetDisplayNode().GetActiveControlPoint()
  logging.info("Start interaction: point ID = {0}, slice view = {1}".format(movingMarkupIndex, sliceView))

def onMarkupEndInteraction(caller, event):
  markupsNode = caller
  sliceView = markupsNode.GetAttribute(slicer.vtkMRMLMarkupsDisplayNode.GetMovingInSliceViewAttributeName())
  movingMarkupIndex = markupsNode.GetDisplayNode().GetActiveControlPoint()
  logging.info("End interaction: point ID = {0}, slice view = {1}".format(movingMarkupIndex, sliceView))

pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
pointListNode.AddControlPoint([0,0,0])
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, onMarkupChanged)
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointStartInteractionEvent, onMarkupStartInteraction)
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent, onMarkupEndInteraction)
```

## Write Markup Control Point Positions to JSON File

Export control point labels and positions from a markup node to a JSON file:

```python
pointListNode = getNode("F")
outputFileName = "<output_path>/test.json"

# Get markup positions
data = []
for fidIndex in range(pointListNode.GetNumberOfControlPoints()):
  coords=[0,0,0]
  pointListNode.GetNthControlPointPosition(fidIndex,coords)
  data.append({"label": pointListNode.GetNthControlPointLabel(fidIndex), "position": coords})

import json
with open(outputFileName, "w") as outfile:
  json.dump(data, outfile)
```

## Write Markup ROI to JSON File

Export the center and size of a markups ROI node to a JSON file:

```python
roiNode = getNode("R")
outputFileName = "<output_path>/test.json"

# Get ROI data
center = [0,0,0]
size = [0,0,0]
roiNode.GetCenterWorld(center)
roiNode.GetSizeWorld(size)
data = {"center": center, "size": size}

# Write to json file
import json
with open(outputFileName, "w") as outfile:
  json.dump(data, outfile)
```

## Create Markup Plane JSON File - Outside Slicer

Create a markup plane JSON file from scratch (outside of Slicer) by specifying a center, normal, and plane bounds. The plane is defined using the "pointNormal" type with a baseToNode transformation matrix:

```python
outputFileName = "<output_path>/MyPlane.mrk.json"
center = [3.6764886856933536, -52.2593679682938, 41.715845278879044]
normal = [-0.9552783445937983, 0.2957081066696218, 0.0]
plane_bounds = [-50.0, 50.0, -50.0, 50.0]

import numpy as np
import json

normal /= np.linalg.norm(normal)

# Choose an arbitrary vector direction (x) that is not parallel to the normal
axis1 = np.array([1, 0, 0])
if np.linalg.norm(np.cross(normal, axis1)) < 0.1:
  # Almost parallel to the x axis, use another direction (y)
  axis1 = np.array([0, 1, 0])

# Calculate a third axis of the plane coordinate system (orthogonal to the other two)
axis2 = np.cross(normal, axis1)
axis2 /= np.linalg.norm(axis2)

# Get axis1 that is orthogonal to axis2 and normal
axis1 = np.cross(axis2, normal)
axis1 /= np.linalg.norm(axis1)

# Construct the rotation-translation matrix baseToNode
base_to_node_matrix = np.eye(4)
base_to_node_matrix[0:3, 0] = axis1
base_to_node_matrix[0:3, 1] = axis2
base_to_node_matrix[0:3, 2] = normal

data = {
    "@schema": "https://raw.githubusercontent.com/slicer/slicer/master/Modules/Loadable/Markups/Resources/Schema/markups-schema-v1.0.3.json#",
    "markups": [
        {
            "type": "Plane",
            "coordinateSystem": "LPS",
            "coordinateUnits": "mm",
            "planeType": "pointNormal",
            "sizeMode": "auto",
            "baseToNode": list(base_to_node_matrix.reshape(16)),
            "planeBounds": plane_bounds,
            "controlPoints": [{ "id": "1", "position": center }]
        }
    ]
}

with open(outputFileName, "w") as outfile:
  json.dump(data, outfile)
```

## Fit Slice Plane to Markup Control Points

Compute a best-fit plane from three markup control points and orient a slice viewer to that plane:

```python
sliceNode = slicer.mrmlScene.GetNodeByID("vtkMRMLSliceNodeRed")
pointListNode = slicer.mrmlScene.GetFirstNodeByName("F")
# Get markup point positions as numpy arrays
import numpy as np
p1 = np.zeros(3)
p2 = np.zeros(3)
p3 = np.zeros(3)
pointListNode.GetNthControlPointPosition(0, p1)
pointListNode.GetNthControlPointPosition(1, p2)
pointListNode.GetNthControlPointPosition(2, p3)
# Get plane axis directions
n = np.cross(p2-p1, p2-p3) # plane normal direction
n = n/np.linalg.norm(n)
t = np.cross([0.0, 0.0, 1.0], n) # plane transverse direction
t = t/np.linalg.norm(t)
# Set slice plane orientation and position
sliceNode.SetSliceToRASByNTP(n[0], n[1], n[2], t[0], t[1], t[2], p1[0], p1[1], p1[2], 0)
```

## Change Color of a Markups Node

Markups have `Color` and `SelectedColor` properties. `SelectedColor` applies when all control points are in the "selected" state, which is the default. Use `SetSelectedColor` to change the visible color:

```python
markupsNode = getNode("F")
displayNode = markupsNode.GetDisplayNode()
displayNode.SetSelectedColor(0, 1, 0)  # green
```

To set the unselected color:

```python
displayNode.SetColor(1, 0, 0)  # red for unselected state
```

## Display List of Control Points in Module GUI

Use `qSlicerSimpleMarkupsWidget` to integrate a control point list display with placement controls into a module's GUI. See the [qSlicerSimpleMarkupsWidget API documentation](https://apidocs.slicer.org/main/classqSlicerSimpleMarkupsWidget.html) for full details.

You can also programmatically display control point positions in a table:

```python
markupsNode = getNode("F")

for i in range(markupsNode.GetNumberOfControlPoints()):
  pos = [0.0, 0.0, 0.0]
  markupsNode.GetNthControlPointPosition(i, pos)
  label = markupsNode.GetNthControlPointLabel(i)
  print("Point {0}: {1} at ({2:.2f}, {3:.2f}, {4:.2f})".format(i, label, pos[0], pos[1], pos[2]))
```

## Pre-populate the Scene with Measurements

Create measurement markup nodes (lines, angles) with predefined positions and configure their display. This example creates line measurements and binds creation to a keyboard shortcut:

```python
def createMeasurements():
  for nodeName in ['A', 'B', 'C', 'D']:
    lineNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsLineNode", nodeName)
    lineNode.CreateDefaultDisplayNodes()
    dn = lineNode.GetDisplayNode()
    # Use crosshair glyph to allow more accurate point placement
    dn.SetGlyphTypeFromString("CrossDot2D")
    # Hide measurement result while markup up
    lineNode.GetMeasurement('length').SetEnabled(False)

shortcut1 = qt.QShortcut(slicer.util.mainWindow())
shortcut1.setKey(qt.QKeySequence("Ctrl+n"))
shortcut1.connect( 'activated()', createMeasurements)
```

Simple example of creating distance and angle measurements with predefined control points:

```python
# Create distance measurement
lineNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsLineNode", "Distance")
lineNode.CreateDefaultDisplayNodes()
lineNode.AddControlPoint(vtk.vtkVector3d(0, 0, 0))
lineNode.AddControlPoint(vtk.vtkVector3d(10, 10, 10))

# Create angle measurement
angleNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsAngleNode", "Angle")
angleNode.CreateDefaultDisplayNodes()
angleNode.AddControlPoint(vtk.vtkVector3d(0, 0, 0))
angleNode.AddControlPoint(vtk.vtkVector3d(10, 0, 0))
angleNode.AddControlPoint(vtk.vtkVector3d(10, 10, 0))
```

## Copy All Measurements to Clipboard / Excel

Collect all line measurements from the scene and copy them to the clipboard in tab-separated format suitable for pasting into Excel. Bind to a keyboard shortcut:

```python
def copyLineMeasurementsToClipboard():
  measurements = []
  # Collect all line measurements from the scene
  lineNodes = getNodesByClass('vtkMRMLMarkupsLineNode')
  for lineNode in lineNodes:
    if lineNode.GetNumberOfDefinedControlPoints() < 2:
      # incomplete line, skip it
      continue
    # Get node filename that the length was measured on
    try:
      volumeNode = slicer.mrmlScene.GetNodeByID(lineNode.GetNthControlPointAssociatedNodeID(0))
      imagePath = volumeNode.GetStorageNode().GetFileName()
    except:
      imagePath = '(unknown)'
    # Get line node n
    measurementName = lineNode.GetName()
    # Get length measurement
    lineNode.GetMeasurement('length').SetEnabled(True)
    length = str(lineNode.GetMeasurement('length').GetValue())
    # Add fields to results
    measurements.append('\t'.join([imagePath, measurementName, length]))
  # Copy all measurements to clipboard (to be pasted into Excel)
  outputText = "\n".join(measurements) + "\n"
  slicer.app.clipboard().setText(outputText)
  slicer.util.delayDisplay(f"Copied {len(measurements)} length measurements to the clipboard.")

shortcut2 = qt.QShortcut(slicer.util.mainWindow())
shortcut2.setKey(qt.QKeySequence("Ctrl+m"))
shortcut2.connect( 'activated()', copyLineMeasurementsToClipboard)
```

To write to a file instead of copying to clipboard, replace the clipboard line:

```python
with open("<output_path>/results.csv", "a") as f:
  f.write(outputText)
```

## Use Markups JSON Files in Python - Outside Slicer

### Get a table of control point labels and positions using pandas

```python
import pandas as pd
controlPointsTable = pd.DataFrame.from_dict(pd.read_json(input_json_filename)['markups'][0]['controlPoints'])
```

Example result:

```
  label                                        position
0   F-1  [-53.388409961685824, -73.33572796934868, 0.0]
1   F-2     [49.8682950191571, -88.58955938697324, 0.0]
2   F-3   [-25.22749042145594, 59.255268199233726, 0.0]
```

### Access position of control points in separate x, y, z columns

```python
controlPointsTable[['x','y','z']] = pd.DataFrame(controlPointsTable['position'].to_list())
del controlPointsTable['position']
```

### Write control points to a CSV file

```python
controlPointsTable.to_csv(output_csv_filename)
```

Resulting CSV file content:

```
,label,x,y,z
0,F-1,-53.388409961685824,-73.33572796934868,0.0
1,F-2,49.8682950191571,-88.58955938697324,0.0
2,F-3,-25.22749042145594,59.255268199233726,0.0
```

## Assign Custom Actions to Markups

Add custom actions to markups that respond to double-click and keyboard shortcuts. This example assigns toggle label visibility to double-click, and grow/shrink control point glyphs to `q` and `w` keys when hovering over a markup in the 3D view:

```python
# This example adds an action to the default double-click action on a markup
# and defines two new custom actions. It is done for all existing markups in the first 3D view.
#
# How to use:
# 1. Create markups nodes.
# 2. Run the script below.
# 3. Double-click on the markup -> this triggers toggleLabelVisibilty.
# 4. Hover the mouse over a markup then pressing `q` and `w` keys -> this triggers shrinkControlPoints and growControlPoints.

threeDViewNode = slicer.mrmlScene.GetNodeByID("vtkMRMLViewNode1")
appLogic = slicer.app.applicationLogic()
markupsDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(threeDViewNode, "vtkMRMLMarkupsDisplayableManager")

def shrinkControlPoints(caller, eventId):
  markupsDisplayNode = caller
  markupsDisplayNode.SetGlyphScale(markupsDisplayNode.GetGlyphScale()/1.1)

def growControlPoints(caller, eventId):
  markupsDisplayNode = caller
  markupsDisplayNode.SetGlyphScale(markupsDisplayNode.GetGlyphScale()*1.1)

def toggleLabelVisibility(caller, eventId):
  markupsDisplayNode = caller
  markupsDisplayNode.SetPointLabelsVisibility(not markupsDisplayNode.GetPointLabelsVisibility())

observations = []  # store the observations so that later can be removed
markupsDisplayNodes = slicer.util.getNodesByClass("vtkMRMLMarkupsDisplayNode")
for markupsDisplayNode in markupsDisplayNodes:
  # Assign keyboard shortcut to trigger custom actions
  markupsWidget = markupsDisplayableManager.GetWidget(markupsDisplayNode)
  # Left double-click interaction event is translated to markupsWidget.WidgetEventAction by default,
  # therefore we don't need to add an event translation for that. We just add two keyboard event translation for two custom actions
  markupsWidget.SetKeyboardEventTranslation(markupsWidget.WidgetStateOnWidget, vtk.vtkEvent.NoModifier, '\0', 0, "q", markupsWidget.WidgetEventCustomAction1)
  markupsWidget.SetKeyboardEventTranslation(markupsWidget.WidgetStateOnWidget, vtk.vtkEvent.NoModifier, '\0', 0, "w", markupsWidget.WidgetEventCustomAction2)
  # Add observer to custom actions
  observations.append([markupsDisplayNode, markupsDisplayNode.AddObserver(markupsDisplayNode.ActionEvent, toggleLabelVisibility)])
  observations.append([markupsDisplayNode, markupsDisplayNode.AddObserver(markupsDisplayNode.CustomActionEvent1, shrinkControlPoints)])
  observations.append([markupsDisplayNode, markupsDisplayNode.AddObserver(markupsDisplayNode.CustomActionEvent2, growControlPoints)])

# Remove observations when custom actions are not needed anymore by uncommenting these lines:
for observedNode, observation in observations:
  observedNode.RemoveObserver(observation)
```

---

## Quick Reference: Markup Node Types

| Node Class | Description | Key Methods |
|---|---|---|
| `vtkMRMLMarkupsFiducialNode` | Point list (fiducials) | `AddControlPoint()`, `GetNthControlPointPosition()` |
| `vtkMRMLMarkupsLineNode` | Line between two points | `GetMeasurement('length')` |
| `vtkMRMLMarkupsCurveNode` | Open or closed curve | `updateMarkupsControlPointsFromArray()` |
| `vtkMRMLMarkupsAngleNode` | Angle between three points | `GetMeasurement('angle')` |
| `vtkMRMLMarkupsPlaneNode` | Plane defined by points or normal | `GetNormalWorld()`, `SetCenter()`, `SetNormal()` |
| `vtkMRMLMarkupsROINode` | Region of interest (box) | `GetCenterWorld()`, `GetSizeWorld()` |
| `vtkMRMLMarkupsClosedCurveNode` | Closed curve (loop) | Same as curve node |

## Quick Reference: Key Events

| Event | Constant | Description |
|---|---|---|
| Point Modified | `slicer.vtkMRMLMarkupsNode.PointModifiedEvent` | Fired when any control point position changes |
| Point Added | `slicer.vtkMRMLMarkupsNode.PointAddedEvent` | Fired when a new control point is added |
| Point Removed | `slicer.vtkMRMLMarkupsNode.PointRemovedEvent` | Fired when a control point is removed |
| Start Interaction | `slicer.vtkMRMLMarkupsNode.PointStartInteractionEvent` | Fired when user starts dragging a point |
| End Interaction | `slicer.vtkMRMLMarkupsNode.PointEndInteractionEvent` | Fired when user stops dragging a point |
| Position Preview | `slicer.vtkMRMLMarkupsNode.PositionPreview` | Status indicating point position is being previewed |

## Quick Reference: File Formats

| Format | Extension | Description |
|---|---|---|
| Markups JSON | `.mkp.json` | Native Slicer markups format (recommended) |
| FCSV | `.fcsv` | Legacy fiducial CSV format |
| CSV | `.csv` | Control points as comma-separated values |

Source: [3D Slicer Script Repository - Markups](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository/markups.html)
