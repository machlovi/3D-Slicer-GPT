---
name: slicer-models-meshes
description: 3D model and mesh operations including surface mesh creation, VTK filter application, texture mapping, scalar coloring, distance measurement, cell selection, and export to glTF/VRML/PLY formats. Use for model visualization, manipulation, and export.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Models and Meshes

## Overview

This skill covers 3D model and mesh operations in 3D Slicer. All code examples run in Slicer's built-in Python environment where the following modules are available by default:

- `slicer` -- Core Slicer Python API for scene management, node access, and utilities
- `vtk` -- Visualization Toolkit for mesh creation, filtering, and processing
- `qt` -- Qt framework bindings for UI interaction
- `numpy` / `np` -- Numerical computing (available after `import numpy as np`)

Models in Slicer are represented as `vtkMRMLModelNode` objects containing VTK polydata (`vtkPolyData`). Each model node has an associated `vtkMRMLModelDisplayNode` that controls visualization properties such as color, opacity, scalar coloring, and texture.

For volume-related operations, see the `slicer-volumes` skill. For segmentation operations, see the `slicer-segmentations` skill.

---

## Show a simple surface mesh as a model node

Create a basic geometric shape and display it as a model node in the scene. The `slicer.modules.models.logic().AddModel()` method provides a convenient way to add a model from a VTK algorithm output.

```python
box = vtk.vtkCubeSource()
box.SetXLength(30)
box.SetYLength(20)
box.SetZLength(15)
box.SetCenter(10,20,5)

boxNode = slicer.modules.models.logic().AddModel(box.GetOutputPort())

boxNode.GetDisplayNode().SetColor(1,0,0)
boxNode.GetDisplayNode().SetOpacity(0.8)
```

You can use any VTK source (e.g., `vtkSphereSource`, `vtkCylinderSource`, `vtkConeSource`, `vtkPlaneSource`) in place of `vtkCubeSource`. The `AddModel()` method creates both the model node and its display node automatically.

---

## Measure distance of points from surface

Measure the signed distance from a set of markup control points to the surface of a model. Positive distance indicates the point is outside the surface; negative distance indicates the point is inside. Results are displayed in a table node with a four-up table view layout.

```python
pointListNode = getNode("F")
modelNode = getNode("mymodel")

# Transform model polydata to world coordinate system
if modelNode.GetParentTransformNode():
  transformModelToWorld = vtk.vtkGeneralTransform()
  slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(modelNode.GetParentTransformNode(), None, transformModelToWorld)
  polyTransformToWorld = vtk.vtkTransformPolyDataFilter()
  polyTransformToWorld.SetTransform(transformModelToWorld)
  polyTransformToWorld.SetInputData(modelNode.GetPolyData())
  polyTransformToWorld.Update()
  surface_World = polyTransformToWorld.GetOutput()
else:
  surface_World = modelNode.GetPolyData()

# Create arrays to store results
indexCol = vtk.vtkIntArray()
indexCol.SetName("Index")
labelCol = vtk.vtkStringArray()
labelCol.SetName("Name")
distanceCol = vtk.vtkDoubleArray()
distanceCol.SetName("Distance")

distanceFilter = vtk.vtkImplicitPolyDataDistance()
distanceFilter.SetInput(surface_World)
nOfControlPoints = pointListNode.GetNumberOfControlPoints()
for i in range(0, nOfControlPoints):
  point_World = [0,0,0]
  pointListNode.GetNthControlPointPositionWorld(i, point_World)
  closestPointOnSurface_World = [0,0,0]
  closestPointDistance = distanceFilter.EvaluateFunctionAndGetClosestPoint(point_World, closestPointOnSurface_World)
  indexCol.InsertNextValue(i)
  labelCol.InsertNextValue(pointListNode.GetNthControlPointLabel(i))
  distanceCol.InsertNextValue(closestPointDistance)

# Create a table from result arrays
resultTableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "Points from surface distance")
resultTableNode.AddColumn(indexCol)
resultTableNode.AddColumn(labelCol)
resultTableNode.AddColumn(distanceCol)

# Show table in view layout
slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpTableView)
slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(resultTableNode.GetID())
slicer.app.applicationLogic().PropagateTableSelection()
```

Key points:
- Replace `"F"` with the name of your markups fiducial node
- Replace `"mymodel"` with the name of your model node
- The script correctly handles models that have parent transforms applied
- `vtkImplicitPolyDataDistance` computes signed distances (negative = inside, positive = outside)

---

## Add a texture mapped plane to the scene as a model

Add a plane with a texture to the 3D scene. This creates a plane source, attaches texture coordinates, and applies a texture image.

```python
planeSource = vtk.vtkPlaneSource()
planeSource.SetOrigin(-50.0, -50.0, 0.0)
planeSource.SetPoint1(50.0, -50.0, 0.0)
planeSource.SetPoint2(-50.0, 50.0, 0.0)
model = slicer.modules.models.logic().AddModel(planeSource.GetOutputPort())

modelDisplay = model.GetDisplayNode()
modelDisplay.SetColor(1,1,0)
modelDisplay.SetBackfaceCulling(0)

e = vtk.vtkImageEllipsoidSource()
modelDisplay.SetTextureImageDataConnection(e.GetOutputPort())
```

**Note:** Model textures are not exposed in the GUI and are not saved in the scene.

To use a texture from an image file instead of a procedural source, load the image using a VTK reader:

```python
# Example: load texture from a file
textureReader = vtk.vtkJPEGReader()  # or vtkPNGReader for PNG files
textureReader.SetFileName("<path-to-texture-image>")
modelDisplay.SetTextureImageDataConnection(textureReader.GetOutputPort())
```

---

## Get scalar values at surface of a model

Interactively track the mouse position and display scalar values at the closest point on a model surface. Position can be selected by moving the mouse while holding down the Shift key.

```python
modelNode = getNode("sphere")
modelPointValues = modelNode.GetPolyData().GetPointData().GetArray("Normals")
pointListNode = slicer.mrmlScene.GetFirstNodeByName("F")

if not pointListNode:
  pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode","F")

pointsLocator = vtk.vtkPointLocator()
pointsLocator.SetDataSet(modelNode.GetPolyData())
pointsLocator.BuildLocator()

def onMouseMoved(observer,eventid):
  ras=[0,0,0]
  crosshairNode.GetCursorPositionRAS(ras)
  closestPointId = pointsLocator.FindClosestPoint(ras)
  ras = modelNode.GetPolyData().GetPoint(closestPointId)
  closestPointValue = modelPointValues.GetTuple(closestPointId)
  if pointListNode.GetNumberOfControlPoints() == 0:
    pointListNode.AddControlPoint(ras)
  else:
    pointListNode.SetNthControlPointPosition(0,*ras)
  print(f"RAS={ras}  value={closestPointValue}")

crosshairNode=slicer.util.getNode("Crosshair")
observationId = crosshairNode.AddObserver(slicer.vtkMRMLCrosshairNode.CursorPositionModifiedEvent, onMouseMoved)
```

To stop printing values and remove the observer:

```python
crosshairNode.RemoveObserver(observationId)
```

Key points:
- Replace `"sphere"` with the name of your model node
- Replace `"Normals"` with the name of the scalar array you want to query (e.g., `"Curvature"`, `"Thickness"`)
- The crosshair node tracks the mouse position in RAS coordinates
- A `vtkPointLocator` is used for efficient nearest-point lookups

---

## Apply VTK filter on a model node (curvature coloring)

Apply a VTK filter to a model node and color the surface by the computed scalar values. This example computes Gaussian curvature and applies a Viridis color map.

```python
modelNode = getNode("tip")

curv = vtk.vtkCurvatures()
curv.SetInputData(modelNode.GetPolyData())
modelNode.SetPolyDataConnection(curv.GetOutputPort())

modelNode.GetDisplayNode().SetActiveScalar("Gauss_Curvature", vtk.vtkAssignAttribute.POINT_DATA)
modelNode.GetDisplayNode().SetAndObserveColorNodeID("Viridis")
modelNode.GetDisplayNode().SetScalarVisibility(True)
```

Key points:
- Replace `"tip"` with the name of your model node
- `vtkCurvatures` can compute different curvature types:
  - `SetCurvatureTypeToGaussian()` -- Gaussian curvature (default, produces `"Gauss_Curvature"` array)
  - `SetCurvatureTypeToMean()` -- Mean curvature (produces `"Mean_Curvature"` array)
  - `SetCurvatureTypeToMaximum()` -- Maximum curvature
  - `SetCurvatureTypeToMinimum()` -- Minimum curvature
- Any VTK filter can be applied using the same pattern: create the filter, set input, connect output to the model node
- Other useful filters include `vtkSmoothPolyDataFilter`, `vtkDecimatePro`, `vtkTriangleFilter`, `vtkPolyDataNormals`
- Available color nodes include `"Viridis"`, `"Magma"`, `"Plasma"`, `"Inferno"`, `"vtkMRMLColorTableNodeRainbow"`, `"vtkMRMLColorTableNodeWarm1"`

---

## Select cells of a model using markups point list

Select and highlight cells of a model that are closest to positions of markup control points. The selection updates automatically when control points are moved.

```python
modelNode = slicer.util.getNode("Segment_1")
pointListNode = slicer.util.getNode("F")

cellScalars = modelNode.GetMesh().GetCellData()
selectionArray = cellScalars.GetArray("selection")
if not selectionArray:
  selectionArray = vtk.vtkIntArray()
  selectionArray.SetName("selection")
  selectionArray.SetNumberOfValues(modelNode.GetMesh().GetNumberOfCells())
  selectionArray.Fill(0)
  cellScalars.AddArray(selectionArray)

modelNode.GetDisplayNode().SetActiveScalar("selection", vtk.vtkAssignAttribute.CELL_DATA)
modelNode.GetDisplayNode().SetAndObserveColorNodeID("vtkMRMLColorTableNodeWarm1")
modelNode.GetDisplayNode().SetScalarVisibility(True)

cell = vtk.vtkCellLocator()
cell.SetDataSet(modelNode.GetMesh())
cell.BuildLocator()

def onPointsModified(observer=None, eventid=None):
  global pointListNode, selectionArray
  selectionArray.Fill(0)
  markupPoints = slicer.util.arrayFromMarkupsControlPoints(pointListNode)
  closestPoint = [0.0, 0.0, 0.0]
  cellObj = vtk.vtkGenericCell()
  cellId = vtk.mutable(0)
  subId = vtk.mutable(0)
  dist2 = vtk.mutable(0.0)
  for markupPoint in markupPoints:
    cell.FindClosestPoint(markupPoint, closestPoint, cellObj, cellId, subId, dist2)
    closestCell = cellId.get()
    if closestCell >=0:
      selectionArray.SetValue(closestCell, 100)
  selectionArray.Modified()

onPointsModified()
pointListNodeObserverTag = pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, onPointsModified)
```

To stop updating the selection and remove the observer:

```python
pointListNode.RemoveObserver(pointListNodeObserverTag)
```

Key points:
- Replace `"Segment_1"` with the name of your model node
- Replace `"F"` with the name of your markups fiducial node
- The `"selection"` cell scalar array is used to highlight selected cells
- `vtkCellLocator` provides efficient spatial lookups for finding the closest cell
- The observer pattern makes the selection interactive -- moving markup points updates the highlighting in real time

---

## Export entire scene as glTF

Export the entire 3D scene (all visible models, markups, etc.) to a glTF file. glTF is a modern, efficient 3D file format supported by many viewers and web applications. The SlicerOpenAnatomy extension provides more comprehensive export options, but this code snippet can be used for a basic export.

```python
exporter = vtk.vtkGLTFExporter()
exporter.SetRenderWindow(slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow())
exporter.SetFileName("<output-path>/scene.gltf")
exporter.Write()
```

Key points:
- Use `.gltf` extension for JSON-based format or `.glb` for binary format
- The export captures everything visible in the first 3D view
- For richer export capabilities (segments, hierarchies, etc.), consider the SlicerOpenAnatomy extension

---

## Export entire scene as VRML

Save all surface meshes displayed in the scene (models, markups, etc.) to VRML format. Solid colors and coloring by scalar is preserved. Textures are not supported. VRML is a very old general-purpose scene file format, which is still supported by some software.

```python
exporter = vtk.vtkVRMLExporter()
exporter.SetRenderWindow(slicer.app.layoutManager().threeDWidget(0).threeDView().renderWindow())
exporter.SetFileName("<output-path>/scene.wrl")
exporter.Write()
```

Key points:
- VRML files use the `.wrl` extension
- Colors and scalar coloring are preserved in the export
- Textures are not supported in VRML export
- For modern workflows, prefer glTF export (see section above)

---

## Export model to Blender (PLY with color)

Export a model with scalar coloring to PLY format, which can be imported into Blender and other 3D applications with color information preserved.

```python
modelNode = getNode("Model")
plyFilePath = "<output-path>/model.ply"

modelDisplayNode = modelNode.GetDisplayNode()
triangles = vtk.vtkTriangleFilter()
triangles.SetInputConnection(modelDisplayNode.GetOutputPolyDataConnection())

plyWriter = vtk.vtkPLYWriter()
plyWriter.SetInputConnection(triangles.GetOutputPort())
lut = vtk.vtkLookupTable()
lut.DeepCopy(modelDisplayNode.GetColorNode().GetLookupTable())
lut.SetRange(modelDisplayNode.GetScalarRange())
plyWriter.SetLookupTable(lut)
plyWriter.SetArrayName(modelDisplayNode.GetActiveScalarName())

plyWriter.SetFileName(plyFilePath)
plyWriter.Write()
```

Key points:
- Replace `"Model"` with the name of your model node
- The model must have scalar coloring active (e.g., from curvature computation) for colors to be exported
- `vtkTriangleFilter` ensures the mesh is triangulated, which is required for PLY format
- The lookup table from the display node is used to map scalar values to colors
- PLY files can be imported into Blender via File > Import > Stanford (.ply)

---

## Show comparison view of all model files in a folder

Load all model files from a directory and display each in its own 3D view arranged in a grid layout. This is useful for comparing multiple models side by side.

```python
# Inputs
modelDir = "<path-to-model-directory>"
modelFileExt = "stl"
numberOfColumns = 4

import math
import os
modelFiles = list(f for f in os.listdir(modelDir) if f.endswith("." + modelFileExt))

# Create a custom layout
numberOfRows = int(math.ceil(len(modelFiles)/numberOfColumns))
customLayoutId=567  # we pick a random id that is not used by others
slicer.app.setRenderPaused(True)
customLayout = '<layout type="vertical">'
viewIndex = 0
for rowIndex in range(numberOfRows):
  customLayout += '<item><layout type="horizontal">'
  for colIndex in range(numberOfColumns):
    name = os.path.basename(modelFiles[viewIndex]) if viewIndex < len(modelFiles) else "compare " + str(viewIndex)
    customLayout += '<item><view class="vtkMRMLViewNode" singletontag="'+name
    customLayout += '"><property name="viewlabel" action="default">'+name+'</property></view></item>'
    viewIndex += 1
  customLayout += '</layout></item>'

customLayout += '</layout>'
if not slicer.app.layoutManager().layoutLogic().GetLayoutNode().SetLayoutDescription(customLayoutId, customLayout):
    slicer.app.layoutManager().layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId, customLayout)

slicer.app.layoutManager().setLayout(customLayoutId)

# Load and show each model in a view
for modelIndex, modelFile in enumerate(modelFiles):
  # Show only one model in each view
  name = os.path.basename(modelFile)
  viewNode = slicer.mrmlScene.GetSingletonNode(name, "vtkMRMLViewNode")
  viewNode.LinkedControlOn()
  modelNode = slicer.util.loadModel(modelDir + "/" + modelFile)
  modelNode.GetDisplayNode().AddViewNodeID(viewNode.GetID())

slicer.app.setRenderPaused(False)
```

Key points:
- Replace `<path-to-model-directory>` with the path to your folder of model files
- Change `modelFileExt` to match your file type (`"stl"`, `"ply"`, `"obj"`, `"vtk"`, etc.)
- Adjust `numberOfColumns` to control the grid layout
- `LinkedControlOn()` links camera controls so rotating one view rotates all views
- `AddViewNodeID()` restricts each model to only be visible in its assigned view
- Rendering is paused during setup for performance, then resumed at the end

---

## Rasterize a model and save it to a series of image files

Convert a model (e.g., STL file) to a volumetric labelmap and save it as a series of TIFF image files. This is useful for converting surface meshes to voxel representations.

```python
inputModelFile = "<path-to-input-model>.stl"
outputDir = "<output-directory>"
outputVolumeLabelValue = 100
outputVolumeSpacingMm = [0.5, 0.5, 0.5]
outputVolumeMarginMm = [10.0, 10.0, 10.0]

# Read model
inputModel = slicer.util.loadModel(inputModelFile)

# Determine output volume geometry and create a corresponding reference volume
import math
import numpy as np
bounds = np.zeros(6)
inputModel.GetBounds(bounds)
imageData = vtk.vtkImageData()
imageSize = [ int((bounds[axis*2+1]-bounds[axis*2]+outputVolumeMarginMm[axis]*2.0)/outputVolumeSpacingMm[axis]) for axis in range(3) ]
imageOrigin = [ bounds[axis*2]-outputVolumeMarginMm[axis] for axis in range(3) ]
imageData.SetDimensions(imageSize)
imageData.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
imageData.GetPointData().GetScalars().Fill(0)
referenceVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
referenceVolumeNode.SetOrigin(imageOrigin)
referenceVolumeNode.SetSpacing(outputVolumeSpacingMm)
referenceVolumeNode.SetAndObserveImageData(imageData)
referenceVolumeNode.CreateDefaultDisplayNodes()

# Convert model to labelmap
seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
seg.SetReferenceImageGeometryParameterFromVolumeNode(referenceVolumeNode)
slicer.modules.segmentations.logic().ImportModelToSegmentationNode(inputModel, seg)
seg.CreateBinaryLabelmapRepresentation()
outputLabelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(seg, outputLabelmapVolumeNode, referenceVolumeNode)
outputLabelmapVolumeArray = (slicer.util.arrayFromVolume(outputLabelmapVolumeNode) * outputVolumeLabelValue).astype("int8")

# Install dependencies
try:
  import imageio
except ModuleNotFoundError:
  slicer.util.pip_install("imageio")
  import imageio

# Write labelmap volume to series of TIFF files
for i in range(len(outputLabelmapVolumeArray)):
  imageio.imwrite(f"{outputDir}/image_{i:03}.tiff", outputLabelmapVolumeArray[i])
```

Key points:
- Replace `<path-to-input-model>.stl` with your model file path (supports STL, OBJ, PLY, VTK, etc.)
- Replace `<output-directory>` with the desired output folder
- `outputVolumeSpacingMm` controls the voxel resolution (smaller values = higher resolution but larger files)
- `outputVolumeMarginMm` adds padding around the model bounds
- `outputVolumeLabelValue` sets the intensity value for voxels inside the model
- The `imageio` package is installed automatically if not already available via `slicer.util.pip_install()`
- The conversion pipeline is: Model -> Segmentation -> Binary Labelmap -> Image Series
- For related segmentation operations, see the `slicer-segmentations` skill
