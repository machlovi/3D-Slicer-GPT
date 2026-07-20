---
name: slicer-segmentations
description: Segmentation creation, editing, export, and analysis including labelmap/model conversion, segment editor effects, numpy array access, VTK filter processing, quantification (volume, centroid, bounding box), and file operations with slicerio. Use for all segmentation-related operations.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Segmentations

## Overview

This skill covers segmentation operations in 3D Slicer, including creating, loading, exporting, editing, displaying, converting, and quantifying segmentations. All code runs inside Slicer's embedded Python environment where the following modules are available by default:

- `slicer` -- Core Slicer Python API (nodes, scene, app, util, modules)
- `vtk` -- VTK classes for image processing, surface filters, and geometry
- `qt` -- Qt bindings for UI elements (keyboard shortcuts, dialogs)
- `numpy` -- Numerical computing for array-based segment manipulation

Segmentations in Slicer use the MRML node class `vtkMRMLSegmentationNode`. Each segmentation can contain multiple segments, each with multiple representations (binary labelmap, closed surface, etc.). Segments can be created from labelmaps, models, or interactively with the Segment Editor.

**Related skills:**
- `slicer-volumes` -- Volume loading, display, and masking operations (use for volume masking with segments)
- `slicer-models-meshes` -- Model node creation and display properties
- `slicer-vtk-rendering` -- Low-level VTK rendering and display customization
- `slicer-scene-management` -- Scene loading, saving, and node management
- `slicer-markups-measurements` -- Markup points, lines, and measurement tools

---

## Load a 3D Image or Model File as Segmentation

Load segmentation data from various file formats. Slicer supports `.seg.nrrd`, `.nrrd`, `.nii`, `.nii.gz`, `.stl`, and other 3D image or model formats.

```python
# Load a segmentation from a .seg.nrrd file (preserves segment names and colors)
segmentationNode = slicer.util.loadSegmentation("<path/to/Segmentation.seg.nrrd>")

# Create segmentation from a NIFTI file with a color table for label names
colorNode = slicer.util.loadColorTable("<path/to/Segmentation-label_ColorTable.ctbl>")
segmentationNode = slicer.util.loadSegmentation("<path/to/Segmentation.nii>", {"colorNodeID": colorNode.GetID()})

# Create segmentation from a STL model file
segmentationNode = slicer.util.loadSegmentation("<path/to/Segment_1.stl>")
```

---

## Create a Segmentation from a Labelmap Volume and Display in 3D

Convert a labelmap volume node to a segmentation node. The labelmap volume can optionally be removed afterward to prevent displaying duplicate data.

```python
labelmapVolumeNode = getNode("label")
seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, seg)
seg.CreateClosedSurfaceRepresentation()
slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

---

## Create Segmentation from a Model Node

Import a VTK model (polydata) into a segmentation node. This example creates a sphere model programmatically and imports it.

```python
# Create a model that will be added to a segmentation node
sphere = vtk.vtkSphereSource()
sphere.SetCenter(-6, 30, 28)
sphere.SetRadius(10)
modelNode = slicer.modules.models.logic().AddModel(sphere.GetOutputPort())

# Create segmentation
segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
segmentationNode.CreateDefaultDisplayNodes()  # only needed for display

# Import the model into the segmentation node
slicer.modules.segmentations.logic().ImportModelToSegmentationNode(modelNode, segmentationNode)
```

---

## Export Labelmap Node from Segmentation Node

Multiple strategies are available for exporting segmentations as labelmap volumes, depending on the desired output geometry.

### Export labelmap matching reference geometry of the segmentation

The output labelmap geometry (origin, spacing, axis directions, and extents) will match the internal binary labelmap representation of the segmentation.

```python
segmentationNode = getNode("Segmentation")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY)
```

### Export smallest possible labelmap

The output labelmap will be cropped to the minimal bounding box that contains all segments.

```python
segmentationNode = getNode("Segmentation")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode)
```

### Export labelmap matching a chosen reference volume geometry

The output labelmap will match the geometry (origin, spacing, axis directions, extents) of a specified reference volume.

```python
segmentationNode = getNode("Segmentation")
referenceVolumeNode = getNode("MRHead")
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, referenceVolumeNode)
```

### Export a selection of segments by name

Export specific segments identified by their segment name.

```python
segmentNames = ["Prostate", "Urethra"]
segmentIds = vtk.vtkStringArray()
for segmentName in segmentNames:
  segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName(segmentName)
  segmentIds.InsertNextValue(segmentId)
slicer.vtkSlicerSegmentationsModuleLogic.ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode, referenceVolumeNode)
```

### Export labelmap to file with keyboard shortcut

Create a keyboard shortcut (Ctrl+Shift+S) that exports visible segments to a labelmap file.

```python
outputPath = "<path/to/output/directory>"

def exportLabelmap():
  segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
  referenceVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
  labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
  slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(segmentationNode, labelmapVolumeNode, referenceVolumeNode)
  filepath = outputPath + "/" + referenceVolumeNode.GetName() + "-label.nrrd"
  slicer.util.saveNode(labelmapVolumeNode, filepath)
  slicer.mrmlScene.RemoveNode(labelmapVolumeNode.GetDisplayNode().GetColorNode())
  slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
  slicer.util.delayDisplay("Segmentation saved to " + filepath)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("Ctrl+Shift+s"))
shortcut.connect( "activated()", exportLabelmap)
```

---

## Import/Export Labelmap Node Using Custom Label Value Mapping

Use a color table node to define custom label value assignments when exporting or importing segmentations as labelmaps.

### Create a color table node for custom label mapping

```python
segment_names_to_labels = [("ribs", 10), ("right lung", 12), ("left lung", 6)]

colorTableNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLColorTableNode")
colorTableNode.SetTypeToUser()
colorTableNode.HideFromEditorsOff()  # make the color table selectable in the GUI outside Colors module
slicer.mrmlScene.AddNode(colorTableNode); colorTableNode.UnRegister(None)
largestLabelValue = max([name_value[1] for name_value in segment_names_to_labels])
colorTableNode.SetNumberOfColors(largestLabelValue + 1)
import random
for segmentName, labelValue in segment_names_to_labels:
    r = random.uniform(0.0, 1.0)
    g = random.uniform(0.0, 1.0)
    b = random.uniform(0.0, 1.0)
    a = 1.0
    success = colorTableNode.SetColor(labelValue, segmentName, r, g, b, a)
```

### Export labelmap from segmentation using custom label mapping

```python
segmentationNode = getNode("Segmentation")  # source segmentation node
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")  # export to new labelmap volume
referenceVolumeNode = None  # it could be set to the master volume
segmentIds = segmentationNode.GetSegmentation().GetSegmentIDs()  # export all segments
# colorTableNode = ...  # created from scratch or loaded from file

slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode, referenceVolumeNode, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY, colorTableNode)
```

### Import labelmap into segmentation using custom label mapping

```python
labelmapVolumeNode = getNode("Volume-label")
segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")  # import into new segmentation node
# colorTableNode = ...  # created from scratch or loaded from file

labelmapVolumeNode.GetDisplayNode().SetAndObserveColorNodeID(colorTableNode.GetID())  # associate the custom color table with the labelmap volume
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode)
```

---

## Export Model Nodes from Segmentation Node

Export all segments as separate model nodes into a subject hierarchy folder.

```python
segmentationNode = getNode("Segmentation")
shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Segments")
slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, exportFolderItemId)
```

---

## Create a Hollow Model from Boundary of Solid Segment

Generate a shell/hollow model from the boundary of a solid segmentation segment. Two approaches are available.

### Using the Dynamic Modeler module

The Dynamic Modeler module provides a `Hollow` tool that creates a shell from a model with configurable thickness.

```python
segmentationNode = getNode("Segmentation")

# Export segments to models
shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
exportFolderItemId = shNode.CreateFolderItem(shNode.GetSceneItemID(), "Segments")
slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, exportFolderItemId)
segmentModels = vtk.vtkCollection()
shNode.GetDataNodesInBranch(exportFolderItemId, segmentModels)
# Get exported model of first segment
modelNode = segmentModels.GetItemAsObject(0)

# Set up Hollow tool
hollowModeler = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLDynamicModelerNode")
hollowModeler.SetToolName("Hollow")
hollowModeler.SetNodeReferenceID("Hollow.InputModel", modelNode.GetID())
hollowedModelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode")  # this node will store the hollow model
hollowModeler.SetNodeReferenceID("Hollow.OutputModel", hollowedModelNode.GetID())
hollowModeler.SetAttribute("ShellThickness", "2.5")  # grow outside
hollowModeler.SetContinuousUpdate(True)  # auto-update output model if input parameters are changed

# Hide inputs, show output
segmentationNode.GetDisplayNode().SetVisibility(False)
modelNode.GetDisplayNode().SetVisibility(False)
hollowedModelNode.GetDisplayNode().SetOpacity(0.5)
```

### Using VTK filters

Use VTK extrusion and normal computation filters to create a shell model directly from the closed surface representation.

```python
# Get closed surface representation of the segment
shellThickness = 3.0  # mm
segmentationNode = getNode("Segmentation")
segmentationNode.CreateClosedSurfaceRepresentation()
polyData = segmentationNode.GetClosedSurfaceInternalRepresentation("Segment_1")

# Create shell
extrude = vtk.vtkLinearExtrusionFilter()
extrude.SetInputData(polyData)
extrude.SetExtrusionTypeToNormalExtrusion()
extrude.SetScaleFactor(shellThickness)

# Compute consistent surface normals
triangle_filter = vtk.vtkTriangleFilter()
triangle_filter.SetInputConnection(extrude.GetOutputPort())
normals = vtk.vtkPolyDataNormals()
normals.SetInputConnection(triangle_filter.GetOutputPort())
normals.FlipNormalsOn()

# Save result into new model node
slicer.modules.models.logic().AddModel(normals.GetOutputPort())
```

---

## Show a Segmentation in 3D

To display a segmentation in the 3D view, a closed surface representation must be created. This converts the internal binary labelmap representation to a surface mesh suitable for 3D rendering.

```python
segmentationNode = getNode("Segmentation")
segmentationNode.CreateClosedSurfaceRepresentation()
```

---

## Modify Segmentation Display Options

Control the visual appearance of segments including opacity, color, and visibility.

```python
segmentationNode = getNode("Segmentation")
segmentID = "Segment_1"

displayNode = segmentationNode.GetDisplayNode()
displayNode.SetOpacity3D(0.4)  # Set overall opacity of the segmentation
displayNode.SetSegmentOpacity3D(segmentID, 0.2)  # Set opacity of a single segment

# Segment color is not just a display property, but it is stored in the segment itself
# (and stored in the segmentation file)
segment = segmentationNode.GetSegmentation().GetSegment(segmentID)
segment.SetColor(1, 0, 0)  # red

# In very special cases (for example, when a segment's color only needs to be changed
# in a specific view) the segment color can be overridden in the display node.
# This is not recommended for general use.
displayNode.SetSegmentOverrideColor(segmentID, 0, 0, 1)  # blue
```

---

## Get a Representation of a Segment

Access the internal representations (binary labelmap or closed surface) of a segment without exporting to a separate node.

### Access binary labelmap representation (without exporting)

```python
image = slicer.vtkOrientedImageData()
segmentationNode.GetBinaryLabelmapRepresentation(segmentID, image)
```

### Get closed surface representation if available

```python
outputPolyData = vtk.vtkPolyData()
segmentationNode.GetClosedSurfaceRepresentation(segmentID, outputPolyData)
```

### Get binary labelmap representation (create if needed)

If the binary labelmap representation does not exist yet, this will create it automatically.

```python
import vtkSegmentationCorePython as vtkSegmentationCore
outputOrientedImageData = vtkSegmentationCore.vtkOrientedImageData()
slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentBinaryLabelmapRepresentation(segmentationNode, segmentID, outputOrientedImageData)
```

### Get closed surface representation (create if needed)

If the closed surface representation does not exist yet, this will create it automatically.

```python
outputPolyData = vtk.vtkPolyData()
slicer.vtkSlicerSegmentationsModuleLogic.GetSegmentClosedSurfaceRepresentation(segmentationNode, segmentID, outputPolyData)
```

---

## Convert All Segments Using Default Path and Conversion Parameters

Create representations using default conversion parameters and path.

```python
segmentationNode = getNode("Segmentation")
segmentationNode.CreateBinaryLabelmapRepresentation()
```

---

## Convert All Segments Using Custom Path or Conversion Parameters

Customize the conversion by specifying reference image geometry or other conversion parameters before creating representations.

### Change reference image geometry based on an existing image

```python
referenceGeometry = slicer.vtkSegmentationConverter.SerializeImageGeometry(referenceImageData)
segmentation = segmentationNode.GetSegmentation()
segmentation.SetConversionParameter(slicer.vtkSegmentationConverter.GetReferenceImageGeometryParameterName(), referenceGeometry)
```

---

## Re-convert Using a Modified Conversion Parameter

When conversion parameters are changed (e.g., smoothing factor), existing representations must be removed and recreated with the new parameters.

```python
import vtkSegmentationCorePython as vtkSegmentationCore
segmentation = getNode("Segmentation").GetSegmentation()

# Turn off surface smoothing
segmentation.SetConversionParameter("Smoothing factor", "0.0")

# Recreate representation using modified parameters (and default conversion path)
segmentation.RemoveRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
segmentation.CreateRepresentation(vtkSegmentationCore.vtkSegmentationConverter.GetSegmentationClosedSurfaceRepresentationName())
```

---

## Create Keyboard Shortcut for Toggling Sphere Brush for Paint and Erase Effects

Toggle between sphere and circular brush shapes for the Paint and Erase segment editor effects. The `BrushSphere` parameter is a "common" parameter shared between Paint and Erase effects.

```python
def toggleSphereBrush():
  segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
  paintEffect = segmentEditorWidget.effectByName("Paint")
  isSphere = paintEffect.integerParameter("BrushSphere")
  # BrushSphere is "common" parameter (shared between paint and erase)
  paintEffect.setCommonParameter("BrushSphere", 0 if isSphere else 1)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("s"))
shortcut.connect("activated()", toggleSphereBrush)
```

---

## Create Keyboard Shortcut for Toggling Visibility of a Set of Segments

Toggle visibility of segments that have a specific status tag (e.g., "completed", "inprogress", "flagged") using a keyboard shortcut.

```python
slicer.segmentationNode = getNode("Segmentation")
slicer.toggledSegmentState = "completed"  # it could be "inprogress", "completed", "flagged"
slicer.visibility = True

def toggleSegmentVisibility():
    slicer.visibility = not slicer.visibility
    segmentation = slicer.segmentationNode.GetSegmentation()
    for segmentIndex in range(segmentation.GetNumberOfSegments()):
        segmentId = segmentation.GetNthSegmentID(segmentIndex)
        segmentationStatus = vtk.mutable("")
        if not segmentation.GetSegment(segmentId).GetTag("Segmentation.Status", segmentationStatus):
            continue
        if segmentationStatus != slicer.toggledSegmentState:
            continue
        slicer.segmentationNode.GetDisplayNode().SetSegmentVisibility(segmentId, slicer.visibility)

shortcut = qt.QShortcut(slicer.util.mainWindow())
shortcut.setKey(qt.QKeySequence("Ctrl+k"))
shortcut.connect( "activated()", toggleSegmentVisibility)
```

---

## Customize List of Displayed Segment Editor Effects

Control which segment editor effects are shown in the editor widget and their order.

### Show only specific effects

```python
segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
segmentEditorWidget.setEffectNameOrder(["Paint", "Erase"])
segmentEditorWidget.unorderedEffectsVisible = False
```

### List all available effect names

```python
segmentEditorWidget = slicer.modules.segmenteditor.widgetRepresentation().self().editor
print(segmentEditorWidget.availableEffectNames())
```

---

## Center All Views on a Segment

Position all slice views and 3D camera to center on a specific segment's location.

```python
segmentationNode = getNode("Segmentation")
segmentId = "Segment_2"

position = segmentationNode.GetSegmentCenterRAS(segmentId)
print(position)

# Center slice views and cameras on this position
for sliceNode in slicer.util.getNodesByClass("vtkMRMLSliceNode"):
    sliceNode.JumpSliceByCentering(*position)
for camera in slicer.util.getNodesByClass("vtkMRMLCameraNode"):
    camera.SetFocalPoint(position)
```

---

## Read and Write a Segment as a Numpy Array

Access segment data as a numpy array for programmatic manipulation, thresholding, or region filling. This is the most efficient way to read and modify segment contents.

### Read segment, modify, and write back

```python
volumeNode = getNode("MRHead")
segmentationNode = getNode("Segmentation")
segmentId = segmentationNode.GetSegmentation().GetSegmentIdBySegmentName("Segment_1")

# Get segment as numpy array
segmentArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, volumeNode)

# Modify the segmentation
segmentArray[:] = 0  # clear the segmentation
segmentArray[ slicer.util.arrayFromVolume(volumeNode) > 80 ] = 1  # create segment by simple thresholding of an image
segmentArray[20:80, 40:90, 30:70] = 1  # fill a rectangular region using numpy indexing
slicer.util.updateSegmentBinaryLabelmapFromArray(segmentArray, segmentationNode, segmentId, volumeNode)
```

### Get volume voxels within a segment and compute statistics

```python
# Get voxels of a volume within the segmentation and compute some statistics
volumeArray = slicer.util.arrayFromVolume(volumeNode)
volumeVoxelsInSegmentArray = volumeArray[ segmentArray > 0 ]
print(f"Lowest voxel value in segment: {volumeVoxelsInSegmentArray.min()}")
print(f"Highest voxel value in segment: {volumeVoxelsInSegmentArray.max()}")

# Modify the volume
# For example, increase the contrast inside the selected segment by a factor of 4x:
volumeArray[ segmentArray > 0 ] = volumeArray[ segmentArray > 0 ] * 4
# Indicate that we have completed modifications on the volume array
slicer.util.arrayFromVolumeModified(volumeNode)
```

---

## Get Centroid of a Segment in World (RAS) Coordinates

Compute the centroid (center of mass) of a segment in RAS (Right-Anterior-Superior) world coordinates, accounting for the segment's image geometry and any parent transforms.

```python
segmentationNode = getNode("Segmentation")
segmentId = "Segment_1"

# Get array voxel coordinates
import numpy as np
seg = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId)
# numpy array has voxel coordinates in reverse order (KJI instead of IJK)
# and the array is cropped to minimum size in the segmentation
mean_KjiCropped = [coords.mean() for coords in np.nonzero(seg)]

# Get segmentation voxel coordinates
segImage = slicer.vtkOrientedImageData()
segmentationNode.GetBinaryLabelmapRepresentation(segmentId, segImage)
segImageExtent = segImage.GetExtent()
# origin of the array in voxel coordinates is determined by the start extent
mean_Ijk = [mean_KjiCropped[2], mean_KjiCropped[1], mean_KjiCropped[0]] + np.array([segImageExtent[0], segImageExtent[2], segImageExtent[4]])

# Get segmentation physical coordinates
ijkToWorld = vtk.vtkMatrix4x4()
segImage.GetImageToWorldMatrix(ijkToWorld)
mean_World = [0, 0, 0, 1]
ijkToWorld.MultiplyPoint(np.append(mean_Ijk, 1.0), mean_World)
mean_World = mean_World[0:3]

# If segmentation node is transformed, apply that transform to get RAS coordinates
transformWorldToRas = vtk.vtkGeneralTransform()
slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(segmentationNode.GetParentTransformNode(), None, transformWorldToRas)
mean_Ras = transformWorldToRas.TransformPoint(mean_World)

# Show mean position value and jump to it in all slice viewers
print(mean_Ras)
slicer.modules.markups.logic().JumpSlicesToLocation(mean_Ras[0], mean_Ras[1], mean_Ras[2], True)
```

---

## Get Histogram of a Segmented Region

Compute and plot the histogram of voxel values within a segmented region of a volume.

```python
# Generate example input data (volumeNode, segmentationNode, segmentId)
################################################

# Load source volume
import SampleData
sampleDataLogic = SampleData.SampleDataLogic()
volumeNode = sampleDataLogic.downloadMRBrainTumor1()

# Create segmentation
segmentationNode = slicer.vtkMRMLSegmentationNode()
slicer.mrmlScene.AddNode(segmentationNode)
segmentationNode.CreateDefaultDisplayNodes()  # only needed for display
segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

# Create segment
tumorSeed = vtk.vtkSphereSource()
tumorSeed.SetCenter(-6, 30, 28)
tumorSeed.SetRadius(25)
tumorSeed.Update()
segmentId = segmentationNode.AddSegmentFromClosedSurfaceRepresentation(tumorSeed.GetOutput(), "Segment A", [1.0, 0.0, 0.0])

# Compute histogram
################################################

# Get voxel values of volume in the segmented region
import numpy as np
volumeArray = slicer.util.arrayFromVolume(volumeNode)
segmentArray = slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, volumeNode)
segmentVoxels = volumeArray[segmentArray != 0]

# Compute histogram
import numpy as np
histogram = np.histogram(segmentVoxels, bins=50)

# Plot histogram
################################################

slicer.util.plot(histogram, xColumnIndex=1)
```

---

## Get Segments Visible at a Selected Position

Identify which segments are visible at a given position in a slice view. This uses the `vtkMRMLSegmentationsDisplayableManager2D` to query segments at a world (RAS) coordinate.

```python
segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")
pointListNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsFiducialNode")
sliceViewLabel = "Red"  # any slice view where segmentation node is visible works

def printSegmentNames(unused1=None, unused2=None):

  sliceViewNode = slicer.mrmlScene.GetNodeByID(f"vtkMRMLSliceNode{sliceViewLabel}")
  appLogic = slicer.app.applicationLogic()
  segmentationsDisplayableManager = appLogic.GetViewDisplayableManagerByClassName(sliceViewNode, "vtkMRMLSegmentationsDisplayableManager2D")
  ras = [0, 0, 0]
  pointListNode.GetNthControlPointPositionWorld(0, ras)
  segmentIds = vtk.vtkStringArray()
  segmentationsDisplayableManager.GetVisibleSegmentsForPosition(ras, segmentationNode.GetDisplayNode(), segmentIds)
  for idIndex in range(segmentIds.GetNumberOfValues()):
    segment = segmentationNode.GetSegmentation().GetSegment(segmentIds.GetValue(idIndex))
    print("Segment found at position {0}: {1}".format(ras, segment.GetName()))

# Observe markup node changes
pointListNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, printSegmentNames)
printSegmentNames()
```

---

## Set Default Segmentation Options

Configure default behavior for segmentation editing. By default, editing one segment overwrites other segments in the same region. This can be changed to allow overlap between segments.

```python
defaultSegmentEditorNode = slicer.vtkMRMLSegmentEditorNode()
defaultSegmentEditorNode.SetOverwriteMode(slicer.vtkMRMLSegmentEditorNode.OverwriteNone)
slicer.mrmlScene.AddDefaultNode(defaultSegmentEditorNode)
```

To make these settings persistent, add the above lines to your `.slicerrc.py` startup file.

---

## How to Run Segment Editor Effects from a Script

Segment editor effects are designed for complex interactive editing workflows with support for undo/redo, masking, and source volume changes. The recommended approach is to use a `qMRMLSegmentEditorWidget` instance.

Common scripted workflows include:
- Brain tumor segmentation using Grow from Seeds effect
- Skin surface extraction using Threshold and Smoothing effects
- Masking a volume with segments and computing histograms for each region
- Creating tissue segments by thresholding and reporting volume
- Automatic segmentation of cranial cavity in dry bone skull CT
- Removing patient table from CT images

Effect parameters can be set programmatically. See the Slicer documentation for a description of available effect parameters for each editor effect (Paint, Erase, Threshold, Grow from Seeds, Islands, Smoothing, Margin, Hollow, Scissors, etc.).

---

## Process Segment Using a VTK Filter

Apply VTK image processing filters (such as dilate/erode) to a segment. The segment is exported to a temporary labelmap volume, processed with VTK filters, and imported back.

```python
segmentationNode = getNode("Segmentation")
segmentId = "Segment_1"
kernelSize = [3, 1, 5]

# Export segment as vtkImageData (via temporary labelmap volume node)
segmentIds = vtk.vtkStringArray()
segmentIds.InsertNextValue(segmentId)
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(segmentationNode, segmentIds, labelmapVolumeNode)

# Process segmentation
segmentImageData = labelmapVolumeNode.GetImageData()
erodeDilate = vtk.vtkImageDilateErode3D()
erodeDilate.SetInputData(segmentImageData)
erodeDilate.SetDilateValue(1)
erodeDilate.SetErodeValue(0)
erodeDilate.SetKernelSize(*kernelSize)
erodeDilate.Update()
segmentImageData.DeepCopy(erodeDilate.GetOutput())

# Import segment from vtkImageData
slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode, segmentIds)

# Cleanup temporary nodes
slicer.mrmlScene.RemoveNode(labelmapVolumeNode.GetDisplayNode().GetColorNode())
slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

---

## Use Segmentation Files in Python -- Outside Slicer

The `slicerio` Python package allows working with Slicer segmentation files (`.seg.nrrd`) in any Python environment, without requiring 3D Slicer to be installed.

### Extract selected segments by standard terminology

Use SNOMED-CT terminology codes to select specific segments from a segmentation file.

```python
# pip install slicerio

import slicerio

input_filename = "<path/to/Segmentation.seg.nrrd>"
output_filename = "<path/to/SegmentationExtracted.seg.nrrd>"
segments_to_labels = [
   ({"category": ["SCT", "123037004", "Anatomical Structure"], "type": ["SCT", "113197003", "Ribs"]}, 1),
   ({"category": ["SCT", "123037004", "Anatomical Structure"], "type": ["SCT", "39607008", "Lung"], "typeModifier": ["SCT", "24028007", "Right"]}, 3)
   ]

segmentation = slicerio.read_segmentation(input_filename)
extracted_segmentation = slicerio.extract_segments(segmentation, segments_to_labels)
slicerio.write_segmentation(output_filename, extracted_segmentation)
```

### Extract selected segments by segment name

Select segments by their user-defined name and assign custom label values.

```python
# pip install slicerio

import slicerio
import nrrd

input_filename = "<path/to/Segmentation.seg.nrrd>"
output_filename = "<path/to/SegmentationExtracted.seg.nrrd>"
segment_names_to_labels = [("ribs", 10), ("right lung", 12), ("left lung", 6)]

# Read voxels and metadata from a .seg.nrrd file
voxels, header = nrrd.read(input_filename)
# Get selected segments in a 3D numpy array and updated segment metadata
extracted_voxels, extracted_header = slicerio.extract_segments(voxels, header, segmentation_info, segment_names_to_labels)
# Write extracted segments and metadata to .seg.nrrd file
nrrd.write(output_filename, extracted_voxels, extracted_header)
```

---

## Clone a Segment

Create a copy of an existing segment within the same segmentation node. The cloned segment includes all representations of the source segment.

```python
segmentationNode = getNode("Segmentation")
sourceSegmentName = "Segment_1"

segmentation = segmentationNode.GetSegmentation()
sourceSegmentId = segmentation.GetSegmentIdBySegmentName(sourceSegmentName)
segmentation.CopySegmentFromSegmentation(segmentation, sourceSegmentId)
```

---

## Resample Segmentation to Higher Resolution

Increase the resolution of the internal binary labelmap representation of a segmentation. Higher oversampling factors provide finer resolution at the cost of increased memory usage and computation time.

```python
# Set inputs
volumeNode = getNode("MRHead")
segmentationNode = getNode("Segmentation")

# The higher the oversampling factor is the finer resolution the segmentation will be,
# at the cost of more memory usage and longer computation times.
# Note that oversampling by a factor of 2 increases memory usage by a factor of 2 * 2 * 2 = 8.
oversamplingFactor = 2.0

# Make spacing value uniform for all axes.
# It is useful for removing staircase artifacts in 3D reconstructions but may increase
# memory usage and computation time.
isotropicSpacing = True

# Update geometry of internal binary labelmap representation in segmentation node
segmentationGeometryLogic = slicer.vtkSlicerSegmentationGeometryLogic()
segmentationGeometryLogic.SetInputSegmentationNode(segmentationNode)
segmentationGeometryLogic.SetSourceGeometryNode(volumeNode)
segmentationGeometryLogic.SetOversamplingFactor(oversamplingFactor)
segmentationGeometryLogic.SetIsotropicSpacing(isotropicSpacing)
segmentationGeometryLogic.CalculateOutputGeometry()
segmentationGeometryLogic.SetReferenceImageGeometryInSegmentationNode()
segmentationGeometryLogic.ResampleLabelmapsInSegmentationNode()
```

---

## Quantifying Segments

Use the `SegmentStatistics` module to compute quantitative measurements of segments including volume, centroid, and oriented bounding box.

### Get volume of each segment

```python
segmentationNode = getNode("Segmentation")

# Compute segment statistics
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Display volume of each segment
for segmentId in stats["SegmentIDs"]:
  volume_cm3 = stats[segmentId, "LabelmapSegmentStatisticsPlugin.volume_cm3"]
  segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
  print(f"{segmentName} volume = {volume_cm3} cm3")
```

### Get centroid of each segment and place markup points

```python
segmentationNode = getNode("Segmentation")

# Compute centroids
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.centroid_ras.enabled", str(True))
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Place a markup point in each centroid
pointListNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode")
pointListNode.CreateDefaultDisplayNodes()
for segmentId in stats["SegmentIDs"]:
  centroid_ras = stats[segmentId, "LabelmapSegmentStatisticsPlugin.centroid_ras"]
  segmentName = segmentationNode.GetSegmentation().GetSegment(segmentId).GetName()
  pointListNode.AddControlPoint(centroid_ras, segmentName)
```

### Get oriented bounding box of each segment and visualize with Markups ROI

Compute the oriented bounding box (OBB) of each segment and display it as a Markups ROI node in the scene.

```python
segmentationNode = getNode("Segmentation")

# Compute bounding boxes
import SegmentStatistics
segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_origin_ras.enabled", str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_diameter_mm.enabled", str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_x.enabled", str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_y.enabled", str(True))
segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_z.enabled", str(True))
segStatLogic.computeStatistics()
stats = segStatLogic.getStatistics()

# Draw ROI for each oriented bounding box
import numpy as np
for segmentId in stats["SegmentIDs"]:
  # Get bounding box
  obb_origin_ras = np.array(stats[segmentId, "LabelmapSegmentStatisticsPlugin.obb_origin_ras"])
  obb_diameter_mm = np.array(stats[segmentId, "LabelmapSegmentStatisticsPlugin.obb_diameter_mm"])
  obb_direction_ras_x = np.array(stats[segmentId, "LabelmapSegmentStatisticsPlugin.obb_direction_ras_x"])
  obb_direction_ras_y = np.array(stats[segmentId, "LabelmapSegmentStatisticsPlugin.obb_direction_ras_y"])
  obb_direction_ras_z = np.array(stats[segmentId, "LabelmapSegmentStatisticsPlugin.obb_direction_ras_z"])
  # Create ROI
  segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
  roi = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")
  roi.SetName(segment.GetName() + " OBB")
  roi.GetDisplayNode().SetHandlesInteractive(False)  # do not let the user resize the box
  roi.SetSize(obb_diameter_mm)
  # Position and orient ROI using a transform
  obb_center_ras = obb_origin_ras + 0.5 * (obb_diameter_mm[0] * obb_direction_ras_x + obb_diameter_mm[1] * obb_direction_ras_y + obb_diameter_mm[2] * obb_direction_ras_z)
  boundingBoxToRasTransform = np.row_stack((np.column_stack((obb_direction_ras_x, obb_direction_ras_y, obb_direction_ras_z, obb_center_ras)), (0, 0, 0, 1)))
  boundingBoxToRasTransformMatrix = slicer.util.vtkMatrixFromArray(boundingBoxToRasTransform)
  roi.SetAndObserveObjectToNodeMatrix(boundingBoxToRasTransformMatrix)
```

The complete list of available segment statistics parameters can be obtained by running:

```python
segStatLogic.getParameterNode().GetParameterNames()
```
