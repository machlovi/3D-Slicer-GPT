---
name: slicer-volumes
description: Volume loading, saving, manipulation, rendering, and analysis including voxel access, numpy integration, SimpleITK filters, volume rendering with custom transfer functions, window/level control, and image processing operations. Use for all volume and image data operations.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Volumes

## Overview

This skill covers all volume (image data) operations in 3D Slicer's Python environment. Code runs inside Slicer's embedded Python interpreter where the following modules are always available:

- `slicer` - Core Slicer Python API (nodes, scene, utilities, module logic)
- `vtk` - Visualization Toolkit classes (image data, transforms, filters)
- `qt` - Qt framework bindings (dialogs, timers, widgets)
- `numpy` (as `np`) - Numerical array operations on voxel data
- `SimpleITK` (as `sitk`) - Image processing filters (may require `pip_install`)
- `SampleData` - Sample dataset downloading module

Volumes in Slicer are represented as MRML nodes (`vtkMRMLScalarVolumeNode`, `vtkMRMLVectorVolumeNode`, `vtkMRMLLabelMapVolumeNode`, `vtkMRMLDiffusionTensorVolumeNode`) containing `vtkImageData` with spatial metadata (origin, spacing, orientation via IJK-to-RAS matrix).

Key conventions:
- Numpy arrays from `slicer.util.arrayFromVolume()` use KJI ordering (z, y, x), not IJK
- RAS (Right-Anterior-Superior) is Slicer's world coordinate system
- IJK are zero-based voxel indices
- Always call `Modified()` on image data or use `slicer.util.updateVolumeFromArray()` after modifying voxel data

## Load Volume from File

Load a volume from a local file path into the scene. Supports NRRD, NIfTI, DICOM, MHA/MHD, and many other formats.

```python
# Basic load - volume is shown in slice views automatically
volumeNode = slicer.util.loadVolume("/path/to/volume.nrrd")
```

```python
# Load with properties to control behavior
properties = {
    "show": True,        # Show in slice views after loading
    "center": True,      # Center volume in views
    "labelmap": False,   # Load as labelmap volume if True
    "singleFile": True,  # Do not try to load neighboring files as slices
    "discardOrientation": False,  # Ignore orientation from file header
    "autoWindowLevel": True,      # Auto-adjust window/level
}
volumeNode = slicer.util.loadVolume("/path/to/volume.nrrd", properties)
```

```python
# Load a labelmap volume
labelmapNode = slicer.util.loadLabelVolume("/path/to/labelmap.nrrd")
```

```python
# Load and specify a color node for display
volumeNode = slicer.util.loadVolume("/path/to/volume.nrrd",
    properties={"colorNodeID": "vtkMRMLColorTableNodeGrey"})
```

## Save Volume to File

Export a volume node to a file on disk. The output format is determined by the file extension.

```python
# Save volume to NRRD format
volumeNode = slicer.util.getNode("MRHead")
slicer.util.saveNode(volumeNode, "/path/to/output.nrrd")
```

```python
# Save with compression
storageNode = volumeNode.CreateDefaultStorageNode()
storageNode.SetFileName("/path/to/output.nrrd")
storageNode.SetUseCompression(True)
storageNode.WriteData(volumeNode)
```

```python
# Export to NIfTI format
slicer.util.saveNode(volumeNode, "/path/to/output.nii.gz")
```

```python
# Save using exportNode (preferred for complex exports)
slicer.util.exportNode(volumeNode, "/path/to/output.nrrd")
```

## Load Volume from .vti File

Load a VTK XML ImageData file (.vti format). Slicer does not natively support .vti, so a custom reader is needed.

```python
# Load .vti file using VTK reader
reader = vtk.vtkXMLImageDataReader()
reader.SetFileName("/path/to/volume.vti")
reader.Update()

volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "VTI_Volume")
volumeNode.SetAndObserveImageData(reader.GetOutput())

# Set up display
volumeNode.CreateDefaultDisplayNodes()
slicer.util.setSliceViewerLayers(background=volumeNode)
```

## Load Volume from a Remote Server (SampleData)

Download and load volumes from remote servers. The SampleData module provides built-in sample datasets.

```python
# Load built-in sample data
import SampleData
volumeNode = SampleData.SampleDataLogic().downloadMRHead()
```

```python
# Load other built-in samples
import SampleData
logic = SampleData.SampleDataLogic()

# MR Brain
mrBrain = logic.downloadSample("MRBrainTumor1")

# CT Chest
ctChest = logic.downloadSample("CTChest")

# CT Abdominal Atlas
ctAbdomen = logic.downloadSample("CTACardio")
```

```python
# Load volume from a URL
volumeNode = slicer.util.loadVolume("https://example.com/volume.nrrd")
```

```python
# Download with checksum validation
import SampleData
volumeNode = SampleData.downloadFromURL(
    nodeNames="MyVolume",
    fileNames="volume.nrrd",
    uris="https://example.com/volume.nrrd",
    checksums="SHA256:abc123def456..."
)[0]
```

## Show Volume Rendering Automatically When a Volume is Loaded

Enable volume rendering display for a volume immediately after loading.

```python
# Load volume and enable volume rendering
volumeNode = slicer.util.loadVolume("/path/to/volume.nrrd")
vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)
```

```python
# Auto-enable volume rendering for any newly loaded volume using an observer
def onNodeAdded(caller, event, calldata):
    node = calldata
    if node.IsA("vtkMRMLScalarVolumeNode"):
        vrLogic = slicer.modules.volumerendering.logic()
        vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(node)
        vrDisplayNode.SetVisibility(True)

slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, onNodeAdded)
```

## Show Volume Rendering Using Maximum Intensity Projection (MIP)

Configure volume rendering to display using maximum intensity projection, which shows the highest intensity value along each viewing ray.

```python
volumeNode = slicer.util.getNode("CTChest")
vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

# Set the rendering technique to MIP
vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty().SetInterpolationType(
    vtk.VTK_LINEAR_INTERPOLATION)

vrPropertyNode = vrDisplayNode.GetVolumePropertyNode()
volumeProperty = vrPropertyNode.GetVolumeProperty()

# For MIP, set a linear opacity ramp
opacityFunction = volumeProperty.GetScalarOpacity()
opacityFunction.RemoveAllPoints()
scalarRange = volumeNode.GetImageData().GetScalarRange()
opacityFunction.AddPoint(scalarRange[0], 0.0)
opacityFunction.AddPoint(scalarRange[1], 1.0)
```

## Show Volume Rendering Making Soft Tissues Transparent

Apply custom opacity transfer functions to make soft tissues transparent while keeping dense structures (like bone) visible.

```python
volumeNode = slicer.util.getNode("CTChest")
vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

vrPropertyNode = vrDisplayNode.GetVolumePropertyNode()
volumeProperty = vrPropertyNode.GetVolumeProperty()

# Get scalar range for the volume
scalarRange = volumeNode.GetImageData().GetScalarRange()

# Set up opacity function - soft tissues transparent, bone opaque
scalarOpacity = volumeProperty.GetScalarOpacity()
scalarOpacity.RemoveAllPoints()
scalarOpacity.AddPoint(scalarRange[0], 0.0)                                     # Air: fully transparent
scalarOpacity.AddPoint(scalarRange[0] + (scalarRange[1] - scalarRange[0]) * 0.2, 0.0)  # Soft tissue: transparent
scalarOpacity.AddPoint(scalarRange[0] + (scalarRange[1] - scalarRange[0]) * 0.3, 0.0)  # Soft tissue: transparent
scalarOpacity.AddPoint(scalarRange[0] + (scalarRange[1] - scalarRange[0]) * 0.5, 0.3)  # Transition
scalarOpacity.AddPoint(scalarRange[1], 1.0)                                      # Bone: fully opaque

# Set up color function
colorFunction = volumeProperty.GetRGBTransferFunction()
colorFunction.RemoveAllPoints()
colorFunction.AddRGBPoint(scalarRange[0], 0.0, 0.0, 0.0)
colorFunction.AddRGBPoint(scalarRange[0] + (scalarRange[1] - scalarRange[0]) * 0.5, 0.8, 0.4, 0.2)
colorFunction.AddRGBPoint(scalarRange[1], 1.0, 1.0, 0.9)

# Enable gradient opacity for smoother tissue boundaries
gradientOpacity = volumeProperty.GetGradientOpacity()
gradientOpacity.RemoveAllPoints()
gradientOpacity.AddPoint(0, 0.0)
gradientOpacity.AddPoint(90, 0.5)
gradientOpacity.AddPoint(100, 1.0)
```

```python
# Alternative: apply a built-in preset for CT visualization
volumeNode = slicer.util.getNode("CTChest")
vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

# Apply a built-in CT preset (CT-Cardiac3, CT-Bones, etc.)
presetsScene = vrLogic.GetPresetsScene()
presetNode = None
for i in range(presetsScene.GetNumberOfNodes()):
    node = presetsScene.GetNthNode(i)
    if node.GetName() == "CT-Cardiac3":
        presetNode = node
        break

if presetNode:
    vrDisplayNode.GetVolumePropertyNode().Copy(presetNode)
```

## Automatically Load Volumes That Are Copied into a Folder

Monitor a directory for new volume files and automatically load them into Slicer.

```python
import os
import qt

class VolumeAutoLoader:
    def __init__(self, watchFolder, extensions=None):
        self.watchFolder = watchFolder
        self.extensions = extensions or [".nrrd", ".nii", ".nii.gz", ".mha", ".mhd"]
        self.loadedFiles = set()
        self.timer = qt.QTimer()
        self.timer.setInterval(1000)  # Check every second
        self.timer.timeout.connect(self.checkFolder)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()

    def checkFolder(self):
        if not os.path.isdir(self.watchFolder):
            return
        for filename in os.listdir(self.watchFolder):
            filepath = os.path.join(self.watchFolder, filename)
            if filepath in self.loadedFiles:
                continue
            if any(filepath.endswith(ext) for ext in self.extensions):
                try:
                    slicer.util.loadVolume(filepath)
                    self.loadedFiles.add(filepath)
                    print(f"Loaded: {filepath}")
                except Exception as e:
                    print(f"Failed to load {filepath}: {e}")

# Usage
autoLoader = VolumeAutoLoader("/path/to/watch")
autoLoader.start()

# To stop monitoring:
# autoLoader.stop()
```

## Extract a Slice from a Volume Using a Markup Plane

Extract an arbitrarily oriented 2D slice from a 3D volume defined by a markup plane node.

```python
volumeNode = slicer.util.getNode("MRHead")

# Create or get a markup plane node
planeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsPlaneNode", "SlicePlane")

# Use vtkImageReslice to extract the slice along the plane
reslice = vtk.vtkImageReslice()
reslice.SetInputData(volumeNode.GetImageData())

# Get the plane's axes and origin
planeOrigin = [0, 0, 0]
planeNormal = [0, 0, 0]
planeNode.GetOrigin(planeOrigin)
planeNode.GetNormal(planeNormal)

# Set up the reslice axes
resliceAxes = vtk.vtkMatrix4x4()
reslice.SetResliceAxes(resliceAxes)
reslice.SetOutputDimensionality(2)
reslice.SetInterpolationModeToLinear()
reslice.Update()

# Create a new volume from the extracted slice
sliceVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "ExtractedSlice")
sliceVolumeNode.SetAndObserveImageData(reslice.GetOutput())
sliceVolumeNode.CreateDefaultDisplayNodes()
```

```python
# Simpler approach: extract axial/sagittal/coronal slice by index
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Extract axial slice at index 50 (KJI ordering: K=slice, J=row, I=col)
axialSlice = volumeArray[50, :, :]

# Extract sagittal slice
sagittalSlice = volumeArray[:, :, 50]

# Extract coronal slice
coronalSlice = volumeArray[:, 50, :]

# Create a new volume from the extracted slice
sliceNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Axial_Slice_50")
slicer.util.updateVolumeFromArray(sliceNode, np.expand_dims(axialSlice, axis=0))
```

## Extract Randomly Oriented Slabs of Given Shape from a Volume as Numpy Array

Sample rectangular subvolumes with arbitrary orientations for tasks like data augmentation.

```python
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

slabShape = (32, 32, 32)

# Extract a random axis-aligned slab
maxOffset = [volumeArray.shape[i] - slabShape[i] for i in range(3)]
offset = [np.random.randint(0, max(1, m)) for m in maxOffset]

slab = volumeArray[
    offset[0]:offset[0] + slabShape[0],
    offset[1]:offset[1] + slabShape[1],
    offset[2]:offset[2] + slabShape[2]
]
print(f"Extracted slab shape: {slab.shape}")
```

```python
# Extract multiple random slabs for data augmentation
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

slabShape = (64, 64, 10)
numSlabs = 5

slabs = []
for i in range(numSlabs):
    offset = [np.random.randint(0, max(1, volumeArray.shape[d] - slabShape[d]))
              for d in range(3)]
    slab = volumeArray[
        offset[0]:offset[0] + slabShape[0],
        offset[1]:offset[1] + slabShape[1],
        offset[2]:offset[2] + slabShape[2]
    ]
    slabs.append(slab)
    print(f"Slab {i}: offset={offset}, shape={slab.shape}")
```

## Clone a Volume

Create an independent copy of an existing volume node, including its display settings.

```python
# Method 1: Using Subject Hierarchy (recommended - preserves all properties)
volumeNode = slicer.util.getNode("MRHead")

shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
itemIDToClone = shNode.GetItemByDataNode(volumeNode)
clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
clonedVolumeNode = shNode.GetItemDataNode(clonedItemID)
print(f"Cloned volume: {clonedVolumeNode.GetName()}")
```

```python
# Method 2: Using numpy array copy
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)
clonedArray = np.copy(volumeArray)

clonedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MRHead_Clone")
slicer.util.updateVolumeFromArray(clonedNode, clonedArray)

# Copy geometry (origin, spacing, orientation)
ijkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(ijkToRas)
clonedNode.SetIJKToRASMatrix(ijkToRas)

# Copy display settings
clonedNode.CreateDefaultDisplayNodes()
clonedNode.GetDisplayNode().Copy(volumeNode.GetDisplayNode())
```

## Create a New Volume

Create an empty volume with specified dimensions, spacing, and voxel type.

```python
# Method 1: Using AddNewNodeByClass and vtkImageData
import numpy as np

imageSize = [256, 256, 128]
imageSpacing = [1.0, 1.0, 2.0]
imageOrigin = [0.0, 0.0, 0.0]
voxelType = vtk.VTK_UNSIGNED_CHAR

imageData = vtk.vtkImageData()
imageData.SetDimensions(imageSize)
imageData.SetSpacing(imageSpacing)
imageData.SetOrigin(imageOrigin)
imageData.AllocateScalars(voxelType, 1)

# Fill with zeros
import vtk.util.numpy_support as vtk_np
narray = vtk_np.vtk_to_numpy(imageData.GetPointData().GetScalars())
narray[:] = 0

volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "NewVolume")
volumeNode.SetAndObserveImageData(imageData)
volumeNode.CreateDefaultDisplayNodes()
```

```python
# Method 2: Using numpy array
import numpy as np

# Create a 100x100x100 volume filled with zeros
volumeArray = np.zeros([100, 100, 100], dtype=np.float32)

volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "EmptyVolume")
volumeNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(volumeNode, volumeArray)

# Set spacing and origin
volumeNode.SetSpacing(1.0, 1.0, 1.0)
volumeNode.SetOrigin(0.0, 0.0, 0.0)
```

```python
# Method 3: Create volume matching geometry of an existing volume
import numpy as np

referenceNode = slicer.util.getNode("MRHead")
referenceArray = slicer.util.arrayFromVolume(referenceNode)

# Create new volume with same geometry but different values
newArray = np.zeros_like(referenceArray)

newNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MatchingVolume")
newNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(newNode, newArray)

# Copy geometry from reference
ijkToRas = vtk.vtkMatrix4x4()
referenceNode.GetIJKToRASMatrix(ijkToRas)
newNode.SetIJKToRASMatrix(ijkToRas)
```

## Create a New Volume from ROI

Extract a subvolume defined by a region-of-interest (ROI) node using the CropVolume module.

```python
# Method 1: Using CropVolume module (recommended)
volumeNode = slicer.util.getNode("MRHead")
roiNode = slicer.util.getNode("ROI")

# Create crop volume parameters
cropVolumeParameterNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLCropVolumeParametersNode")
cropVolumeParameterNode.SetInputVolumeNodeID(volumeNode.GetID())
cropVolumeParameterNode.SetROINodeID(roiNode.GetID())
cropVolumeParameterNode.SetVoxelBased(True)  # Keep original voxel spacing

# Execute cropping
cropVolumeLogic = slicer.modules.cropvolume.logic()
cropVolumeLogic.Apply(cropVolumeParameterNode)

# Get the output volume
croppedVolumeNode = slicer.mrmlScene.GetNodeByID(
    cropVolumeParameterNode.GetOutputVolumeNodeID())
print(f"Cropped volume: {croppedVolumeNode.GetName()}")
```

```python
# Method 2: Using numpy slicing
volumeNode = slicer.util.getNode("MRHead")
roiNode = slicer.util.getNode("ROI")
import numpy as np

# Get ROI bounds in RAS coordinates
bounds = [0] * 6
roiNode.GetBounds(bounds)

# Convert RAS bounds to IJK
rasToIjk = vtk.vtkMatrix4x4()
volumeNode.GetRASToIJKMatrix(rasToIjk)

# Convert min and max corners
point1_ras = [bounds[0], bounds[2], bounds[4], 1]
point2_ras = [bounds[1], bounds[3], bounds[5], 1]
point1_ijk = [0, 0, 0, 1]
point2_ijk = [0, 0, 0, 1]
rasToIjk.MultiplyPoint(point1_ras, point1_ijk)
rasToIjk.MultiplyPoint(point2_ras, point2_ijk)

# Extract subvolume
volumeArray = slicer.util.arrayFromVolume(volumeNode)
i1, i2 = sorted([int(point1_ijk[0]), int(point2_ijk[0])])
j1, j2 = sorted([int(point1_ijk[1]), int(point2_ijk[1])])
k1, k2 = sorted([int(point1_ijk[2]), int(point2_ijk[2])])

roiArray = volumeArray[k1:k2, j1:j2, i1:i2]

roiVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "ROI_Volume")
slicer.util.updateVolumeFromArray(roiVolumeNode, roiArray)
```

## Get Value of a Volume at Specific Voxel Coordinates

Retrieve the scalar intensity value at a given IJK voxel position.

```python
# Method 1: Using numpy array (recommended for batch access)
volumeNode = slicer.util.getNode("MRHead")

volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Note: numpy array uses KJI ordering (z, y, x)
i, j, k = 100, 120, 50
voxelValue = volumeArray[k, j, i]
print(f"Voxel value at IJK [{i}, {j}, {k}]: {voxelValue}")
```

```python
# Method 2: Using vtkImageData directly (good for single voxel access)
volumeNode = slicer.util.getNode("MRHead")
imageData = volumeNode.GetImageData()

i, j, k = 100, 120, 50
value = imageData.GetScalarComponentAsFloat(i, j, k, 0)
print(f"Voxel value at IJK [{i}, {j}, {k}]: {value}")
```

```python
# Get voxel value at a RAS world coordinate
volumeNode = slicer.util.getNode("MRHead")

rasPoint = [0.0, 0.0, 0.0]  # RAS coordinates

# Convert RAS to IJK
rasToIjk = vtk.vtkMatrix4x4()
volumeNode.GetRASToIJKMatrix(rasToIjk)
ijkPoint = [0, 0, 0, 1]
rasToIjk.MultiplyPoint(rasPoint + [1], ijkPoint)

# Round to nearest voxel
i, j, k = [int(round(ijkPoint[n])) for n in range(3)]

volumeArray = slicer.util.arrayFromVolume(volumeNode)
if (0 <= k < volumeArray.shape[0] and
    0 <= j < volumeArray.shape[1] and
    0 <= i < volumeArray.shape[2]):
    value = volumeArray[k, j, i]
    print(f"Voxel value at RAS {rasPoint}: {value}")
```

## Modify Voxels in a Volume

Update voxel values in a volume using numpy arrays or direct vtkImageData access.

### Using Numpy Array (Recommended)

```python
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Set a cubic region to a specific value
volumeArray[50:60, 75:85, 100:110] = 255

# IMPORTANT: Notify Slicer that data has changed
slicer.util.arrayFromVolumeModified(volumeNode)
```

```python
# Threshold: set all voxels below a value to zero
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)
volumeArray[volumeArray < 50] = 0
slicer.util.arrayFromVolumeModified(volumeNode)
```

### Using IJK Loop (Slower, but Works for Complex Per-Voxel Logic)

```python
volumeNode = slicer.util.getNode("MRHead")
imageData = volumeNode.GetImageData()
extent = imageData.GetExtent()

for k in range(extent[4], extent[5] + 1):
    for j in range(extent[2], extent[3] + 1):
        for i in range(extent[0], extent[1] + 1):
            oldValue = imageData.GetScalarComponentAsFloat(i, j, k, 0)
            newValue = oldValue * 2.0  # Example: double all values
            imageData.SetScalarComponentFromDouble(i, j, k, 0, newValue)

imageData.Modified()
slicer.util.forceRenderAllViews()
```

## Get Volume Voxel Coordinates (IJK) from Markup Control Point RAS Coordinates

Convert world RAS coordinates from a markup fiducial to volume voxel IJK indices.

```python
volumeNode = slicer.util.getNode("MRHead")
markupNode = slicer.util.getNode("F")
import numpy as np

# Get RAS position of the first control point
ras = [0, 0, 0]
markupNode.GetNthControlPointPosition(0, ras)

# Convert RAS to IJK
volumeRasToIjk = vtk.vtkMatrix4x4()
volumeNode.GetRASToIJKMatrix(volumeRasToIjk)

point_Ras = [ras[0], ras[1], ras[2], 1]
point_Ijk = [0, 0, 0, 1]
volumeRasToIjk.MultiplyPoint(point_Ras, point_Ijk)
point_Ijk = [int(round(point_Ijk[i])) for i in range(3)]

print(f"RAS: {ras} -> IJK: {point_Ijk}")
```

```python
# Convert all control points to IJK
volumeNode = slicer.util.getNode("MRHead")
markupNode = slicer.util.getNode("F")
import numpy as np

volumeRasToIjk = vtk.vtkMatrix4x4()
volumeNode.GetRASToIJKMatrix(volumeRasToIjk)

for i in range(markupNode.GetNumberOfControlPoints()):
    ras = [0, 0, 0]
    markupNode.GetNthControlPointPositionWorld(i, ras)
    point_Ras = [ras[0], ras[1], ras[2], 1]
    point_Ijk = [0, 0, 0, 1]
    volumeRasToIjk.MultiplyPoint(point_Ras, point_Ijk)
    print(f"Control point {i}: RAS={ras} -> IJK={[int(round(point_Ijk[n])) for n in range(3)]}")
```

## Get Markup Control Point RAS Coordinates from Volume Voxel Coordinates (IJK)

Convert volume voxel IJK indices to world RAS coordinates and optionally place a markup point.

```python
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

# IJK coordinates to convert
point_Ijk = [100, 120, 50]

# Convert IJK to RAS
volumeIjkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(volumeIjkToRas)

point_Ijk_h = [point_Ijk[0], point_Ijk[1], point_Ijk[2], 1]
point_Ras = [0, 0, 0, 1]
volumeIjkToRas.MultiplyPoint(point_Ijk_h, point_Ras)

print(f"IJK: {point_Ijk} -> RAS: {point_Ras[:3]}")
```

```python
# Place a markup fiducial at the RAS position of a voxel
volumeNode = slicer.util.getNode("MRHead")

point_Ijk = [100, 120, 50]

volumeIjkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(volumeIjkToRas)

point_Ras = [0, 0, 0, 1]
volumeIjkToRas.MultiplyPoint(point_Ijk + [1], point_Ras)

# Create markup and add control point at RAS position
markupNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "VoxelPoint")
markupNode.AddControlPoint(point_Ras[0], point_Ras[1], point_Ras[2])
```

## Get the Values of All Voxels for a Label Value

Find all voxel coordinates and values matching a specific label in a labelmap volume.

```python
labelmapNode = slicer.util.getNode("Labelmap")
import numpy as np

labelmapArray = slicer.util.arrayFromVolume(labelmapNode)
labelValue = 1

# Get all voxel indices where label matches (returns tuple of arrays: K, J, I)
voxelCoordinates = np.where(labelmapArray == labelValue)
numVoxels = len(voxelCoordinates[0])
print(f"Found {numVoxels} voxels with label {labelValue}")

# Convert to IJK coordinates
for idx in range(min(5, numVoxels)):
    k, j, i = voxelCoordinates[0][idx], voxelCoordinates[1][idx], voxelCoordinates[2][idx]
    print(f"  Voxel at IJK [{i}, {j}, {k}]")
```

```python
# Get the mean intensity of a volume within a labeled region
volumeNode = slicer.util.getNode("MRHead")
labelmapNode = slicer.util.getNode("Labelmap")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)
labelmapArray = slicer.util.arrayFromVolume(labelmapNode)

labelValue = 1
mask = (labelmapArray == labelValue)
meanIntensity = np.mean(volumeArray[mask])
print(f"Mean intensity in label {labelValue}: {meanIntensity}")
```

## Access Values in a DTI Tensor Volume

Read tensor component values from diffusion tensor imaging (DTI) volumes. DTI volumes store a symmetric 3x3 tensor at each voxel (6 unique components).

```python
dtiVolumeNode = slicer.util.getNode("DTIVolume")
import numpy as np

# Get tensor volume as array
# Shape: (K, J, I, 9) for full tensor or (K, J, I, 6) for symmetric storage
tensorArray = slicer.util.arrayFromVolume(dtiVolumeNode)

# Access tensor at a specific voxel (IJK = [50, 75, 100])
# Note: array indexing is KJI
tensorValue = tensorArray[100, 75, 50, :]
print(f"Tensor at [50, 75, 100]: {tensorValue}")

# For symmetric tensor storage (6 components): Dxx, Dxy, Dxz, Dyy, Dyz, Dzz
if tensorArray.shape[-1] == 6:
    Dxx, Dxy, Dxz, Dyy, Dyz, Dzz = tensorValue
    print(f"  Dxx={Dxx}, Dxy={Dxy}, Dxz={Dxz}")
    print(f"  Dyy={Dyy}, Dyz={Dyz}, Dzz={Dzz}")
```

## Change Window/Level (Brightness/Contrast) or Colormap of a Volume

Adjust the display properties of a volume node to change how intensity values are mapped to screen brightness and color.

```python
# Set window/level directly
volumeNode = slicer.util.getNode("CTChest")
displayNode = volumeNode.GetDisplayNode()

# Disable auto window/level
displayNode.SetAutoWindowLevel(False)

# Set using window (width) and level (center)
displayNode.SetWindow(400)
displayNode.SetLevel(40)
```

```python
# Set using min/max intensity range
volumeNode = slicer.util.getNode("CTChest")
displayNode = volumeNode.GetDisplayNode()
displayNode.SetAutoWindowLevel(False)
displayNode.SetWindowLevelMinMax(-200, 300)
```

```python
# Change the colormap (lookup table)
volumeNode = slicer.util.getNode("MRHead")
displayNode = volumeNode.GetDisplayNode()

# Use a built-in color table
colorNode = slicer.util.getNode("Grey")
displayNode.SetAndObserveColorNodeID(colorNode.GetID())
```

```python
# Apply a volume display preset
volumeNode = slicer.util.getNode("CTChest")
displayNode = volumeNode.GetDisplayNode()
slicer.modules.volumes.logic().ApplyVolumeDisplayPreset(displayNode, "CT-Abdomen")
```

```python
# Reset to auto window/level
volumeNode = slicer.util.getNode("MRHead")
displayNode = volumeNode.GetDisplayNode()
displayNode.SetAutoWindowLevel(True)
```

## Activate Window/Level Adjustment Mode (Mouse Interaction)

Enable interactive window/level adjustment via left-click and drag on slice views.

```python
# Set left-click drag to adjust window/level in Red slice view
sliceViewLabel = "Red"
sliceViewNode = slicer.mrmlScene.GetNodeByID(f"vtkMRMLSliceNode{sliceViewLabel}")
appLogic = slicer.app.applicationLogic()
displayableManager = appLogic.GetViewDisplayableManagerByClassName(
    sliceViewNode, "vtkMRMLScalarBarDisplayableManager")
w = displayableManager.GetWindowLevelWidget()
w.SetEventTranslationClickAndDrag(
    w.WidgetStateIdle,
    vtk.vtkCommand.LeftButtonPressEvent,
    vtk.vtkEvent.NoModifier,
    w.WidgetStateAdjustWindowLevel,
    w.WidgetEventAdjustWindowLevelStart,
    w.WidgetEventAdjustWindowLevelEnd
)
```

## Reset Field of View to Show Background Volume Maximized

Fit the slice view to display the entire background volume.

```python
# Reset a single slice view
layoutManager = slicer.app.layoutManager()
sliceWidget = layoutManager.sliceWidget("Red")
sliceLogic = sliceWidget.sliceLogic()
sliceLogic.FitSliceToAll()
```

```python
# Reset all slice views
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
    sliceWidget = layoutManager.sliceWidget(sliceViewName)
    sliceLogic = sliceWidget.sliceLogic()
    sliceLogic.FitSliceToAll()
```

```python
# Reset using the application logic shortcut
slicer.app.applicationLogic().FitSliceToAll()
```

## Rotate Slice Views to Volume Plane

Align slice views with the acquisition plane orientation of a volume. Useful when volumes are acquired in oblique orientations.

```python
# Rotate all slice views to match the volume's acquisition orientation
volumeNode = slicer.util.getNode("MRHead")

sliceNodes = slicer.util.getNodesByClass("vtkMRMLSliceNode")
for sliceNode in sliceNodes:
    sliceNode.RotateToVolumePlane(volumeNode)

# Fit after rotation
slicer.app.applicationLogic().FitSliceToAll()
```

```python
# Rotate only a specific slice view
volumeNode = slicer.util.getNode("MRHead")

sliceNode = slicer.app.layoutManager().sliceWidget("Red").mrmlSliceNode()
sliceNode.RotateToVolumePlane(volumeNode)
```

## Set Foreground and Background Images in Slice Views

Configure which volumes are displayed as foreground and background layers in slice views.

```python
# Set foreground and background for all visible slice views
backgroundVolumeNode = slicer.util.getNode("CTChest")
foregroundVolumeNode = slicer.util.getNode("PET")

layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
    sliceWidget = layoutManager.sliceWidget(sliceViewName)
    compositeNode = sliceWidget.sliceLogic().GetSliceCompositeNode()
    compositeNode.SetBackgroundVolumeID(backgroundVolumeNode.GetID())
    compositeNode.SetForegroundVolumeID(foregroundVolumeNode.GetID())
    compositeNode.SetForegroundOpacity(0.5)
```

```python
# Set using the convenience function
backgroundVolumeNode = slicer.util.getNode("CTChest")
foregroundVolumeNode = slicer.util.getNode("PET")

slicer.util.setSliceViewerLayers(
    background=backgroundVolumeNode,
    foreground=foregroundVolumeNode,
    foregroundOpacity=0.5
)
```

## Show a Volume in Slice Views

Display a volume as the background layer in all slice viewers.

```python
# Method 1: Using setSliceViewerLayers (simplest)
volumeNode = slicer.util.getNode("MRHead")
slicer.util.setSliceViewerLayers(background=volumeNode)
```

```python
# Method 2: Set on all composite nodes directly
volumeNode = slicer.util.getNode("MRHead")

sliceCompositeNodes = slicer.util.getNodesByClass("vtkMRMLSliceCompositeNode")
for compositeNode in sliceCompositeNodes:
    compositeNode.SetBackgroundVolumeID(volumeNode.GetID())
```

```python
# Method 3: Show volume and fit to view
volumeNode = slicer.util.getNode("MRHead")

slicer.util.setSliceViewerLayers(background=volumeNode)
slicer.app.applicationLogic().FitSliceToAll()
```

## Change Foreground Volume Opacity in Slice Views

Adjust the transparency of the foreground volume layer overlaid on the background.

```python
# Set opacity on all slice views
layoutManager = slicer.app.layoutManager()
for sliceViewName in layoutManager.sliceViewNames():
    compositeNode = layoutManager.sliceWidget(sliceViewName).sliceLogic().GetSliceCompositeNode()
    compositeNode.SetForegroundOpacity(0.5)
```

```python
# Set opacity using the convenience function
slicer.util.setSliceViewerLayers(foregroundOpacity=0.3)
```

```python
# Set opacity on a specific slice view only
layoutManager = slicer.app.layoutManager()
compositeNode = layoutManager.sliceWidget("Red").sliceLogic().GetSliceCompositeNode()
compositeNode.SetForegroundOpacity(0.7)
```

## Turn Off Interpolation

Disable image interpolation to display individual voxels without smoothing. Useful for labelmaps and when examining exact voxel values.

```python
# Turn off interpolation for a specific volume
volumeNode = slicer.util.getNode("MRHead")
displayNode = volumeNode.GetDisplayNode()
displayNode.SetInterpolate(False)
```

```python
# Turn off interpolation for all loaded volumes
for volumeNode in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
    displayNode = volumeNode.GetDisplayNode()
    if displayNode:
        displayNode.SetInterpolate(False)
```

```python
# Turn interpolation back on
volumeNode = slicer.util.getNode("MRHead")
displayNode = volumeNode.GetDisplayNode()
displayNode.SetInterpolate(True)
```

## Run SimpleITK Filters in Python

Apply image processing filters from the SimpleITK library to Slicer volumes. SimpleITK provides a simplified interface to ITK's extensive filter library.

```python
# Apply Gaussian blur
import SimpleITK as sitk
import sitkUtils

volumeNode = slicer.util.getNode("MRHead")

# Pull volume from Slicer into SimpleITK
inputImage = sitkUtils.PullVolumeFromSlicer(volumeNode)

# Apply Gaussian smoothing filter
filter = sitk.SmoothingRecursiveGaussianImageFilter()
filter.SetSigma(2.0)
outputImage = filter.Execute(inputImage)

# Push result back to Slicer
outputVolumeNode = sitkUtils.PushVolumeToSlicer(outputImage, name="Smoothed")
slicer.util.setSliceViewerLayers(background=outputVolumeNode)
```

```python
# Apply median filter for noise reduction
import SimpleITK as sitk
import sitkUtils

volumeNode = slicer.util.getNode("MRHead")
inputImage = sitkUtils.PullVolumeFromSlicer(volumeNode)

# Median filter with 3x3x3 kernel
medianFilter = sitk.MedianImageFilter()
medianFilter.SetRadius(1)
outputImage = medianFilter.Execute(inputImage)

outputVolumeNode = sitkUtils.PushVolumeToSlicer(outputImage, name="MedianFiltered")
```

```python
# Apply Otsu threshold segmentation
import SimpleITK as sitk
import sitkUtils

volumeNode = slicer.util.getNode("MRHead")
inputImage = sitkUtils.PullVolumeFromSlicer(volumeNode)

# Otsu thresholding
otsuFilter = sitk.OtsuThresholdImageFilter()
otsuFilter.SetInsideValue(0)
otsuFilter.SetOutsideValue(1)
thresholdImage = otsuFilter.Execute(inputImage)

# Push as labelmap
labelmapNode = sitkUtils.PushVolumeToSlicer(thresholdImage, name="OtsuMask",
                                             className="vtkMRMLLabelMapVolumeNode")
```

```python
# Alternative: using numpy conversion
import SimpleITK as sitk
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Convert numpy to SimpleITK
itkImage = sitk.GetImageFromArray(volumeArray)

# Apply any filter
blurred = sitk.DiscreteGaussian(itkImage, variance=4.0)

# Convert back to numpy and update the volume
resultArray = sitk.GetArrayFromImage(blurred)
outputNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Blurred")
outputNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(outputNode, resultArray)

# Copy geometry from source
ijkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(ijkToRas)
outputNode.SetIJKToRASMatrix(ijkToRas)
```

## Get Axial Slice as Numpy Array

Extract a single 2D axial slice from a 3D volume as a numpy array for external processing.

```python
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Get axial slice at index 50 (first axis = K = slice index)
axialSlice = volumeArray[50, :, :]
print(f"Axial slice shape: {axialSlice.shape}")
print(f"Value range: [{axialSlice.min()}, {axialSlice.max()}]")
```

```python
# Get the middle axial slice
volumeNode = slicer.util.getNode("MRHead")
import numpy as np

volumeArray = slicer.util.arrayFromVolume(volumeNode)
middleIndex = volumeArray.shape[0] // 2
middleSlice = volumeArray[middleIndex, :, :]
print(f"Middle axial slice (index {middleIndex}): shape={middleSlice.shape}")
```

## Get Reformatted Image from a Slice Viewer as Numpy Array

Capture the currently displayed reformatted (arbitrarily oriented) slice from a slice viewer as a numpy array.

```python
# Get the resliced image from Red slice view
layoutManager = slicer.app.layoutManager()
sliceWidget = layoutManager.sliceWidget("Red")
sliceLogic = sliceWidget.sliceLogic()
sliceLayerLogic = sliceLogic.GetBackgroundLayer()

# Get the resliced output
reslicedImage = sliceLayerLogic.GetReslice().GetOutput()

# Convert to numpy array
import vtk.util.numpy_support as vtk_np
import numpy as np

rows, cols, _ = reslicedImage.GetDimensions()
scalars = reslicedImage.GetPointData().GetScalars()
numpyArray = vtk_np.vtk_to_numpy(scalars)
numpyArray = numpyArray.reshape(cols, rows)

print(f"Reformatted slice shape: {numpyArray.shape}")
```

```python
# Alternative: get the slice as a screenshot image
layoutManager = slicer.app.layoutManager()
sliceWidget = layoutManager.sliceWidget("Red")
sliceView = sliceWidget.sliceView()

# Grab the rendered image
renderWindow = sliceView.renderWindow()
windowToImageFilter = vtk.vtkWindowToImageFilter()
windowToImageFilter.SetInput(renderWindow)
windowToImageFilter.Update()

imageData = windowToImageFilter.GetOutput()
```

## Combine Multiple Volumes into One

Merge two or more volumes into a single volume using numpy operations.

```python
# Add two volumes together
import numpy as np

volume1Node = slicer.util.getNode("Volume1")
volume2Node = slicer.util.getNode("Volume2")

array1 = slicer.util.arrayFromVolume(volume1Node)
array2 = slicer.util.arrayFromVolume(volume2Node)

# Ensure same dimensions
assert array1.shape == array2.shape, "Volumes must have the same dimensions"

# Weighted addition
combinedArray = (0.5 * array1.astype(float) + 0.5 * array2.astype(float))
combinedArray = combinedArray.astype(array1.dtype)

combinedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Combined")
combinedNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(combinedNode, combinedArray)

# Copy geometry from first volume
ijkToRas = vtk.vtkMatrix4x4()
volume1Node.GetIJKToRASMatrix(ijkToRas)
combinedNode.SetIJKToRASMatrix(ijkToRas)
```

```python
# Stack volumes along a new axis (e.g., creating a 4D volume from 3D volumes)
import numpy as np

volumeNodes = [slicer.util.getNode(f"Volume{i}") for i in range(1, 4)]
arrays = [slicer.util.arrayFromVolume(node) for node in volumeNodes]

# Stack along axis 0 (concatenate along K dimension)
stackedArray = np.concatenate(arrays, axis=0)

stackedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "Stacked")
stackedNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(stackedNode, stackedArray)
```

```python
# Maximum of two volumes (e.g., fusing PET and CT)
import numpy as np

volume1Node = slicer.util.getNode("Volume1")
volume2Node = slicer.util.getNode("Volume2")

array1 = slicer.util.arrayFromVolume(volume1Node)
array2 = slicer.util.arrayFromVolume(volume2Node)

maxArray = np.maximum(array1, array2)

maxNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MaxCombined")
maxNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(maxNode, maxArray)
```

## Add Noise to Image

Add random noise to a volume for data augmentation or simulation purposes.

```python
# Add Gaussian noise
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

# Generate Gaussian noise with mean=0 and standard deviation=10
noise = np.random.normal(0, 10, volumeArray.shape)
noisyArray = volumeArray.astype(float) + noise

# Clip to valid range and convert back to original dtype
noisyArray = np.clip(noisyArray, volumeArray.min(), volumeArray.max())
noisyArray = noisyArray.astype(volumeArray.dtype)

noisyNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "NoisyVolume")
noisyNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(noisyNode, noisyArray)

# Copy geometry
ijkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(ijkToRas)
noisyNode.SetIJKToRASMatrix(ijkToRas)
```

```python
# Add salt-and-pepper noise
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

noisyArray = volumeArray.copy()
saltPepperRatio = 0.01  # 1% of voxels affected

# Salt (maximum value)
numSalt = int(np.ceil(saltPepperRatio * volumeArray.size))
coords = [np.random.randint(0, i - 1, numSalt) for i in volumeArray.shape]
noisyArray[tuple(coords)] = volumeArray.max()

# Pepper (minimum value)
numPepper = int(np.ceil(saltPepperRatio * volumeArray.size))
coords = [np.random.randint(0, i - 1, numPepper) for i in volumeArray.shape]
noisyArray[tuple(coords)] = volumeArray.min()

noisyNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "SaltPepper")
noisyNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(noisyNode, noisyArray)
```

## Mask Volume Using Segmentation

Apply a segmentation as a mask to a volume, zeroing out regions outside the segmented area. For comprehensive segmentation operations, see the `slicer-segmentations` skill.

```python
# Mask volume using visible segments
volumeNode = slicer.util.getNode("MRHead")
segmentationNode = slicer.util.getNode("Segmentation")
import numpy as np

# Export segmentation to a labelmap aligned with the volume
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", "TempLabelmap")
slicer.modules.segmentations.logic().ExportVisibleSegmentsToLabelmapNode(
    segmentationNode, labelmapVolumeNode, volumeNode)

# Get arrays
volumeArray = slicer.util.arrayFromVolume(volumeNode)
labelmapArray = slicer.util.arrayFromVolume(labelmapVolumeNode)

# Apply mask: keep voxels inside segments, zero outside
maskedArray = volumeArray.copy()
maskedArray[labelmapArray == 0] = 0

# Create masked volume
maskedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MaskedVolume")
maskedNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(maskedNode, maskedArray)

# Copy geometry
ijkToRas = vtk.vtkMatrix4x4()
volumeNode.GetIJKToRASMatrix(ijkToRas)
maskedNode.SetIJKToRASMatrix(ijkToRas)

# Clean up temporary labelmap
slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

```python
# Mask using a specific segment by ID
volumeNode = slicer.util.getNode("MRHead")
segmentationNode = slicer.util.getNode("Segmentation")
segmentID = segmentationNode.GetSegmentation().GetNthSegmentID(0)
import numpy as np

# Export specific segment to labelmap
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
segmentIds = vtk.vtkStringArray()
segmentIds.InsertNextValue(segmentID)
slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(
    segmentationNode, segmentIds, labelmapVolumeNode, volumeNode)

volumeArray = slicer.util.arrayFromVolume(volumeNode)
labelmapArray = slicer.util.arrayFromVolume(labelmapVolumeNode)

maskedArray = volumeArray.copy()
maskedArray[labelmapArray == 0] = 0

maskedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "SegmentMasked")
maskedNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(maskedNode, maskedArray)

slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
```

## Thick Slab Reconstruction and Maximum/Minimum Intensity Volume Projections

Generate maximum intensity projection (MIP), minimum intensity projection (MinIP), or average intensity projection (AIP) images from a volume slab.

```python
# Maximum Intensity Projection (MIP) along the K (axial) axis
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

# MIP: take maximum value along axis 0 (K/slice axis)
mipArray = np.max(volumeArray, axis=0)

# Create 2D result as a thin volume
mipNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MIP")
mipNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(mipNode, np.expand_dims(mipArray, axis=0))
```

```python
# Minimum Intensity Projection (MinIP)
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

minipArray = np.min(volumeArray, axis=0)

minipNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MinIP")
minipNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(minipNode, np.expand_dims(minipArray, axis=0))
```

```python
# Average Intensity Projection (AIP)
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

aipArray = np.mean(volumeArray, axis=0).astype(volumeArray.dtype)

aipNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "AIP")
aipNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(aipNode, np.expand_dims(aipArray, axis=0))
```

```python
# Thick slab MIP over a subset of slices (e.g., 10-slice thick slab)
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
volumeArray = slicer.util.arrayFromVolume(volumeNode)

slabStart = 40
slabThickness = 10
slab = volumeArray[slabStart:slabStart + slabThickness, :, :]

# MIP of the thick slab
slabMipArray = np.max(slab, axis=0)

slabMipNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "SlabMIP")
slabMipNode.CreateDefaultDisplayNodes()
slicer.util.updateVolumeFromArray(slabMipNode, np.expand_dims(slabMipArray, axis=0))
```

## Display Volume Using Volume Rendering

Enable 3D volumetric visualization (direct volume rendering) for a volume node.

### Python

```python
# Basic volume rendering
volumeNode = slicer.util.getNode("CTChest")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)
slicer.util.forceRenderAllViews()
```

```python
# Volume rendering with a specific preset
volumeNode = slicer.util.getNode("CTChest")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)

# Apply a preset (e.g., CT-Bones, CT-Cardiac3, CT-Chest-Contrast-Enhanced, MR-Default)
presetsScene = vrLogic.GetPresetsScene()
for i in range(presetsScene.GetNumberOfNodes()):
    presetNode = presetsScene.GetNthNode(i)
    if presetNode.GetName() == "CT-Bones":
        vrDisplayNode.GetVolumePropertyNode().Copy(presetNode)
        break

vrDisplayNode.SetVisibility(True)
```

### C++

```python
# C++ equivalent (for reference in Slicer module development):
#
# qSlicerAbstractCoreModule* vrModule =
#     qSlicerApplication::application()->moduleManager()->module("VolumeRendering");
# vtkSlicerVolumeRenderingLogic* vrLogic =
#     vtkSlicerVolumeRenderingLogic::SafeDownCast(vrModule->logic());
#
# vtkMRMLVolumeRenderingDisplayNode* vrDisplayNode =
#     vrLogic->CreateDefaultVolumeRenderingNodes(volumeNode);
# vrDisplayNode->SetVisibility(true);
```

## Apply a Custom Volume Rendering Color/Opacity Transfer Function

Define custom color mapping and opacity for volume rendering to highlight specific intensity ranges.

```python
volumeNode = slicer.util.getNode("CTChest")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

volumePropertyNode = vrDisplayNode.GetVolumePropertyNode()
volumeProperty = volumePropertyNode.GetVolumeProperty()

# Custom color transfer function (maps scalar value to RGB)
colorTransferFunction = volumeProperty.GetRGBTransferFunction()
colorTransferFunction.RemoveAllPoints()
colorTransferFunction.AddRGBPoint(-1000, 0.0, 0.0, 0.0)   # Air: black
colorTransferFunction.AddRGBPoint(-500, 0.5, 0.2, 0.1)    # Lung: brown
colorTransferFunction.AddRGBPoint(0, 0.8, 0.5, 0.4)       # Soft tissue: skin tone
colorTransferFunction.AddRGBPoint(200, 1.0, 0.9, 0.8)     # Dense tissue: light
colorTransferFunction.AddRGBPoint(1000, 1.0, 1.0, 1.0)    # Bone: white

# Custom opacity transfer function (maps scalar value to opacity 0-1)
opacityTransferFunction = volumeProperty.GetScalarOpacity()
opacityTransferFunction.RemoveAllPoints()
opacityTransferFunction.AddPoint(-1000, 0.0)    # Air: transparent
opacityTransferFunction.AddPoint(-500, 0.0)     # Lung: transparent
opacityTransferFunction.AddPoint(-100, 0.0)     # Fat: transparent
opacityTransferFunction.AddPoint(0, 0.0)        # Water: transparent
opacityTransferFunction.AddPoint(100, 0.1)      # Soft tissue: slightly visible
opacityTransferFunction.AddPoint(300, 0.3)      # Dense tissue: semi-transparent
opacityTransferFunction.AddPoint(1000, 0.8)     # Bone: mostly opaque

# Optional: gradient opacity for smoother surfaces
gradientOpacity = volumeProperty.GetGradientOpacity()
gradientOpacity.RemoveAllPoints()
gradientOpacity.AddPoint(0, 0.0)
gradientOpacity.AddPoint(90, 0.5)
gradientOpacity.AddPoint(100, 1.0)
```

```python
# Simpler example: binary threshold volume rendering
volumeNode = slicer.util.getNode("MRHead")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

volumeProperty = vrDisplayNode.GetVolumePropertyNode().GetVolumeProperty()

# Simple ramp: everything below threshold is invisible
colorFunc = volumeProperty.GetRGBTransferFunction()
colorFunc.RemoveAllPoints()
colorFunc.AddRGBPoint(0, 0, 0, 0)
colorFunc.AddRGBPoint(100, 1, 1, 1)
colorFunc.AddRGBPoint(255, 1, 1, 1)

opacityFunc = volumeProperty.GetScalarOpacity()
opacityFunc.RemoveAllPoints()
opacityFunc.AddPoint(0, 0.0)
opacityFunc.AddPoint(99, 0.0)
opacityFunc.AddPoint(100, 0.5)
opacityFunc.AddPoint(255, 1.0)
```

## Limit Volume Rendering to a Specific Region (ROI)

Restrict volume rendering to only display within a defined region-of-interest box.

```python
volumeNode = slicer.util.getNode("CTChest")

# Create or get an ROI node
roiNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode", "VR_ROI")

# Set ROI size and center (in RAS coordinates)
roiNode.SetCenter(0, 0, 0)
roiNode.SetSize(100, 100, 100)

# Set up volume rendering
vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

# Enable ROI cropping
vrDisplayNode.SetAndObserveROINodeID(roiNode.GetID())
vrDisplayNode.SetCroppingEnabled(True)
```

```python
# Fit ROI to the volume bounds
volumeNode = slicer.util.getNode("CTChest")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)
vrDisplayNode.SetVisibility(True)

# Create ROI and fit to volume
roiNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode", "VR_ROI")
cropVolumeParameters = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
cropVolumeParameters.SetInputVolumeNodeID(volumeNode.GetID())
cropVolumeParameters.SetROINodeID(roiNode.GetID())
slicer.modules.cropvolume.logic().SnapROIToVoxelGrid(cropVolumeParameters)
slicer.modules.cropvolume.logic().FitROIToInputVolume(cropVolumeParameters)
slicer.mrmlScene.RemoveNode(cropVolumeParameters)

# Assign ROI to volume rendering
vrDisplayNode.SetAndObserveROINodeID(roiNode.GetID())
vrDisplayNode.SetCroppingEnabled(True)
```

## Register a Custom Volume Rendering Mapper

Register custom volume rendering backends or switch between available rendering methods.

```python
# List available volume rendering methods
vrLogic = slicer.modules.volumerendering.logic()

# Get available rendering method class names
renderingMethods = vrLogic.GetRenderingMethods()
print(f"Available rendering methods: {renderingMethods}")
```

```python
# Switch to a specific rendering method
volumeNode = slicer.util.getNode("CTChest")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)

# Use GPU ray casting (default on supported hardware)
vrDisplayNode.SetClassName("vtkMRMLGPURayCastVolumeRenderingDisplayNode")

# Or use CPU ray casting (fallback)
# vrDisplayNode.SetClassName("vtkMRMLCPURayCastVolumeRenderingDisplayNode")

vrDisplayNode.SetVisibility(True)
```

## Register Custom Volume Rendering Presets

Define and register custom transfer function presets for quick reuse.

```python
# Create a custom preset
vrLogic = slicer.modules.volumerendering.logic()

# Create a new volume property node as a preset
presetNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLVolumePropertyNode", "MyCustomPreset")

volumeProperty = presetNode.GetVolumeProperty()

# Define color transfer function
colorFunc = volumeProperty.GetRGBTransferFunction()
colorFunc.RemoveAllPoints()
colorFunc.AddRGBPoint(-1000, 0.0, 0.0, 0.0)
colorFunc.AddRGBPoint(-500, 0.6, 0.3, 0.1)
colorFunc.AddRGBPoint(0, 0.9, 0.6, 0.5)
colorFunc.AddRGBPoint(500, 1.0, 0.9, 0.8)
colorFunc.AddRGBPoint(1000, 1.0, 1.0, 1.0)

# Define opacity transfer function
opacityFunc = volumeProperty.GetScalarOpacity()
opacityFunc.RemoveAllPoints()
opacityFunc.AddPoint(-1000, 0.0)
opacityFunc.AddPoint(-500, 0.0)
opacityFunc.AddPoint(0, 0.0)
opacityFunc.AddPoint(200, 0.2)
opacityFunc.AddPoint(500, 0.5)
opacityFunc.AddPoint(1000, 1.0)

# Define gradient opacity
gradientOpacity = volumeProperty.GetGradientOpacity()
gradientOpacity.RemoveAllPoints()
gradientOpacity.AddPoint(0, 0.0)
gradientOpacity.AddPoint(90, 0.5)
gradientOpacity.AddPoint(100, 1.0)
```

```python
# Apply a saved preset to a volume
volumeNode = slicer.util.getNode("CTChest")
presetNode = slicer.util.getNode("MyCustomPreset")

vrLogic = slicer.modules.volumerendering.logic()
vrDisplayNode = vrLogic.CreateDefaultVolumeRenderingNodes(volumeNode)

# Copy the preset properties to the display node
vrDisplayNode.GetVolumePropertyNode().Copy(presetNode)
vrDisplayNode.SetVisibility(True)
```

```python
# List all available presets
vrLogic = slicer.modules.volumerendering.logic()
presetsScene = vrLogic.GetPresetsScene()

print("Available volume rendering presets:")
for i in range(presetsScene.GetNumberOfNodes()):
    node = presetsScene.GetNthNode(i)
    print(f"  {node.GetName()}")
```

## Apply Random Deformations to Image

Apply elastic deformations to volumes for data augmentation in machine learning workflows.

```python
# Using SimpleITK for elastic deformation
import SimpleITK as sitk
import sitkUtils
import numpy as np

volumeNode = slicer.util.getNode("MRHead")
inputImage = sitkUtils.PullVolumeFromSlicer(volumeNode)

# Create a random displacement field
size = inputImage.GetSize()
spacing = inputImage.GetSpacing()

# Create B-spline transform with random parameters
bsplineTransform = sitk.BSplineTransformInitializer(inputImage, [5, 5, 5])

# Randomize parameters
params = np.array(bsplineTransform.GetParameters())
params += np.random.normal(0, 3.0, len(params))
bsplineTransform.SetParameters(params.tolist())

# Apply deformation
resampler = sitk.ResampleImageFilter()
resampler.SetReferenceImage(inputImage)
resampler.SetTransform(bsplineTransform)
resampler.SetInterpolator(sitk.sitkLinear)
resampler.SetDefaultPixelValue(0)
deformedImage = resampler.Execute(inputImage)

# Push result back to Slicer
deformedNode = sitkUtils.PushVolumeToSlicer(deformedImage, name="Deformed")
slicer.util.setSliceViewerLayers(background=deformedNode)
```

```python
# Using VTK thin plate spline transform
import numpy as np

volumeNode = slicer.util.getNode("MRHead")

# Create source and target landmarks
numPoints = 8
sourcePoints = vtk.vtkPoints()
targetPoints = vtk.vtkPoints()

bounds = [0] * 6
volumeNode.GetBounds(bounds)

for i in range(numPoints):
    x = np.random.uniform(bounds[0], bounds[1])
    y = np.random.uniform(bounds[2], bounds[3])
    z = np.random.uniform(bounds[4], bounds[5])
    sourcePoints.InsertNextPoint(x, y, z)
    targetPoints.InsertNextPoint(
        x + np.random.uniform(-5, 5),
        y + np.random.uniform(-5, 5),
        z + np.random.uniform(-5, 5)
    )

# Create thin plate spline transform
tps = vtk.vtkThinPlateSplineTransform()
tps.SetSourceLandmarks(sourcePoints)
tps.SetTargetLandmarks(targetPoints)
tps.SetBasisToR()

# Apply to volume using vtkImageReslice
reslice = vtk.vtkImageReslice()
reslice.SetInputData(volumeNode.GetImageData())
reslice.SetResliceTransform(tps)
reslice.SetInterpolationModeToLinear()
reslice.Update()

deformedNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "TPS_Deformed")
deformedNode.SetAndObserveImageData(reslice.GetOutput())
deformedNode.CreateDefaultDisplayNodes()
```

## Related Skills

- **slicer-segmentations**: For segmentation creation, editing, import/export, and segment statistics. Use when masking volumes with segmentations or working with labelmaps derived from segmentation nodes.
