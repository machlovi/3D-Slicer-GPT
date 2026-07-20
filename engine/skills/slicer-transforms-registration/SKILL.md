---
name: slicer-transforms-registration
description: Spatial transforms and image registration including rotation, translation, ITK/Slicer transform conversion, numpy matrix integration, transform animation, grid transforms, displacement visualization, and BRAINSFit registration. Use for spatial transformations and image alignment.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Transforms and Registration

## Overview

This skill covers spatial transform operations and image registration in 3D Slicer. All code examples run inside the 3D Slicer Python environment where the following modules are available by default:

- `slicer` -- Core Slicer Python API (nodes, scene, app, util, modules)
- `vtk` -- VTK classes for matrices, transforms, and data processing
- `qt` -- Qt bindings for UI operations
- `numpy` -- Numerical computing (available after import)

Transforms in Slicer are represented as MRML nodes (`vtkMRMLLinearTransformNode`, `vtkMRMLGridTransformNode`, `vtkMRMLBSplineTransformNode`). A transform node stores a 4x4 homogeneous matrix (for linear transforms) or a displacement field (for non-linear transforms). Transform nodes can be nested in a hierarchy: a transformable node is placed under a transform by calling `SetAndObserveTransformNodeID()`. Since transform nodes are themselves transformable, you can build chains of concatenated transforms.

**Coordinate systems:** Slicer uses the **RAS** (Right-Anterior-Superior) coordinate system. ITK and many file formats (`.tfm`, `.h5`) use **LPS** (Left-Posterior-Superior). Converting between them requires negating the first two rows and columns of the matrix.

**Related skills:**
- `slicer-scene-management` -- Scene loading, saving, and node management
- `slicer-models-meshes` -- Model node creation and display properties
- `slicer-views-layouts` -- View layout management and orientation configuration
- `slicer-vtk-rendering` -- Low-level VTK rendering access

---

## Transforms

### Get a Notification if a Transform is Modified

Attach an observer to a transform node to receive a callback whenever the transform matrix changes. This is useful for updating dependent computations or UI elements in real time.

```python
def onTransformModified(caller, eventid):
    transformMatrix = vtk.vtkMatrix4x4()
    caller.GetMatrixTransformToWorld(transformMatrix)
    print("Transform modified:")
    print(f"  Position: [{transformMatrix.GetElement(0,3):.1f}, "
          f"{transformMatrix.GetElement(1,3):.1f}, "
          f"{transformMatrix.GetElement(2,3):.1f}]")

transformNode = getNode("LinearTransform_3")
transformNode.AddObserver(
    slicer.vtkMRMLTransformNode.TransformModifiedEvent,
    onTransformModified)
```

### Apply a Transform to a Transformable Node

Any MRML node that inherits from `vtkMRMLTransformableNode` (volumes, models, markups, segmentations, etc.) can be placed under a transform. The transform is applied non-destructively -- the original data coordinates are preserved.

```python
transformNode = getNode("LinearTransform_3")
volumeNode = getNode("MRHead")

# Apply the transform (non-destructive)
volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

# Remove a transform from a node
volumeNode.SetAndObserveTransformNodeID(None)
```

### Harden a Transform

Hardening a transform permanently applies the current transform to the node's data, then removes the transform association. The node's coordinates are rewritten to incorporate the transform.

```python
transformNode = getNode("LinearTransform_3")
volumeNode = getNode("MRHead")

# Apply the transform
volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

# Harden (bake) the transform into the node's data
volumeNode.HardenTransform()
```

Alternatively, use the transform logic:

```python
logic = slicer.vtkSlicerTransformLogic()
logic.hardenTransform(volumeNode)
```

### Rotate a Node Around a Specified Point

Create a transform that rotates a node around an arbitrary point in world coordinates. The approach is: translate the center to the origin, apply the rotation, then translate back.

```python
# Get or create nodes
transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "RotationTransform")
modelNode = getNode("MyModel")

# Rotation parameters
center = [100.0, 50.0, -30.0]  # Center of rotation in RAS (mm)
axis = [0, 0, 1]               # Rotation axis (Z-axis)
angleDeg = 45.0                 # Rotation angle in degrees

# Build the composite transform:
#   T(center) * R(angle, axis) * T(-center)
transform = vtk.vtkTransform()
transform.PostMultiply()
transform.Translate(-center[0], -center[1], -center[2])
transform.RotateWXYZ(angleDeg, axis[0], axis[1], axis[2])
transform.Translate(center[0], center[1], center[2])

transformNode.SetMatrixTransformToParent(transform.GetMatrix())
modelNode.SetAndObserveTransformNodeID(transformNode.GetID())
```

As a reusable function:

```python
def rotateAroundPoint(node, point, axis, angleDeg):
    """Rotate a node around a specified point.

    Args:
        node: MRML transformable node to rotate.
        point: [x, y, z] center of rotation in RAS coordinates.
        axis: [x, y, z] rotation axis (will be normalized).
        angleDeg: Rotation angle in degrees.
    """
    transform = vtk.vtkTransform()
    transform.PostMultiply()
    transform.Translate(-point[0], -point[1], -point[2])
    transform.RotateWXYZ(angleDeg, axis[0], axis[1], axis[2])
    transform.Translate(point[0], point[1], point[2])

    transformNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLinearTransformNode")
    transformNode.SetMatrixTransformToParent(transform.GetMatrix())
    node.SetAndObserveTransformNodeID(transformNode.GetID())
    return transformNode

# Example: rotate a model 45 degrees around the Z-axis at point (100, 50, -30)
modelNode = getNode("MyModel")
rotateAroundPoint(modelNode, [100.0, 50.0, -30.0], [0, 0, 1], 45.0)
```

### Rotate a Node Around a Specified Line

Rotate a node around an arbitrary line in 3D space, defined by a start point and direction vector. This generalizes "rotate around a point" to arbitrary axes.

```python
def rotateAroundLine(node, linePoint, lineDirection, angleDeg):
    """Rotate a node around an arbitrary line in 3D space.

    Args:
        node: MRML transformable node to rotate.
        linePoint: [x, y, z] any point on the rotation axis.
        lineDirection: [x, y, z] direction vector of the axis (will be normalized internally by VTK).
        angleDeg: Rotation angle in degrees.
    """
    transform = vtk.vtkTransform()
    transform.PostMultiply()
    transform.Translate(-linePoint[0], -linePoint[1], -linePoint[2])
    transform.RotateWXYZ(angleDeg, lineDirection[0], lineDirection[1], lineDirection[2])
    transform.Translate(linePoint[0], linePoint[1], linePoint[2])

    transformNode = slicer.mrmlScene.AddNewNodeByClass(
        "vtkMRMLLinearTransformNode")
    transformNode.SetMatrixTransformToParent(transform.GetMatrix())
    node.SetAndObserveTransformNodeID(transformNode.GetID())
    return transformNode

# Example: rotate a model 30 degrees around a line
# Line passes through (10, 20, 30) with direction (1, 1, 0)
modelNode = getNode("MyModel")
rotateAroundLine(modelNode, [10, 20, 30], [1, 1, 0], 30.0)
```

Using markup nodes to define the rotation line:

```python
# Define rotation axis from two markup control points
markupNode = getNode("F")  # A markups fiducial node with 2 points
lineStartPoint = [0, 0, 0]
lineEndPoint = [0, 0, 0]
markupNode.GetNthControlPointPositionWorld(0, lineStartPoint)
markupNode.GetNthControlPointPositionWorld(1, lineEndPoint)

# Compute direction from two points
lineDirection = [
    lineEndPoint[0] - lineStartPoint[0],
    lineEndPoint[1] - lineStartPoint[1],
    lineEndPoint[2] - lineStartPoint[2]
]

modelNode = getNode("MyModel")
rotateAroundLine(modelNode, lineStartPoint, lineDirection, 30.0)
```

### Convert Between ITK and Slicer Linear Transforms

ITK transform files (`.tfm`, `.h5`, `.txt`) store the **resampling transform** (transform from parent) in the **LPS** coordinate system. Slicer uses **RAS**. Converting between them requires negating elements in the first two rows and columns of the matrix.

**Read an ITK transform file and convert to Slicer:**

```python
import numpy as np

# Read the ITK transform file into Slicer
# (Slicer handles the LPS/RAS conversion automatically when loading)
transformNode = slicer.util.loadTransform("/path/to/transform.tfm")
```

**Manual conversion from ITK (LPS) matrix to Slicer (RAS):**

```python
import numpy as np

# The LPS-to-RAS conversion matrix flips the first two axes
lps2ras = np.diag([-1, -1, 1, 1])

# ITK matrix in LPS coordinate system (4x4 homogeneous)
itkMatrix = np.array([
    [1.0, 0.0, 0.0, 10.0],
    [0.0, 0.866, -0.5, 20.0],
    [0.0, 0.5, 0.866, 30.0],
    [0.0, 0.0, 0.0, 1.0]
])

# Convert: ras_matrix = lps2ras @ itk_matrix @ lps2ras
rasMatrix = lps2ras @ itkMatrix @ lps2ras

# Create Slicer transform node from RAS matrix
transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "ConvertedTransform")
vtkMatrix = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        vtkMatrix.SetElement(i, j, rasMatrix[i, j])
transformNode.SetMatrixTransformToParent(vtkMatrix)
```

**Convert Slicer (RAS) transform back to ITK (LPS):**

```python
import numpy as np

# Get the RAS matrix from Slicer
transformNode = getNode("MyTransform")
vtkMatrix = vtk.vtkMatrix4x4()
transformNode.GetMatrixTransformToParent(vtkMatrix)

rasMatrix = np.zeros((4, 4))
for i in range(4):
    for j in range(4):
        rasMatrix[i, j] = vtkMatrix.GetElement(i, j)

# Convert RAS to LPS: itk_matrix = lps2ras @ ras_matrix @ lps2ras
# (lps2ras is its own inverse since it is a diagonal matrix with +/-1)
lps2ras = np.diag([-1, -1, 1, 1])
itkMatrix = lps2ras @ rasMatrix @ lps2ras

print("ITK (LPS) matrix:")
print(itkMatrix)
```

**Using VTK matrix operations (without numpy):**

```python
# Get Slicer transform
transformNode = getNode("MyTransform")
rasMatrix = vtk.vtkMatrix4x4()
transformNode.GetMatrixTransformToParent(rasMatrix)

# Create LPS-to-RAS conversion matrix
lps2ras = vtk.vtkMatrix4x4()
lps2ras.SetElement(0, 0, -1)
lps2ras.SetElement(1, 1, -1)

# Convert: itk_matrix = lps2ras * ras_matrix * lps2ras
temp = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Multiply4x4(lps2ras, rasMatrix, temp)
itkMatrix = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Multiply4x4(temp, lps2ras, itkMatrix)
```

### Set a Transformation Matrix from a Numpy Array

Create or update a transform node using a 4x4 numpy array. This is useful for applying transformations computed with numpy, scipy, or other libraries.

```python
import numpy as np

# Create a new transform node
transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "NumpyTransform")

# Define a 4x4 homogeneous transformation matrix as numpy array
# This example: 30-degree rotation around Z-axis + translation of (10, 20, 30) mm
angle = np.radians(30)
numpyMatrix = np.array([
    [np.cos(angle), -np.sin(angle), 0, 10],
    [np.sin(angle),  np.cos(angle), 0, 20],
    [0,              0,             1, 30],
    [0,              0,             0,  1]
])

# Copy numpy array into VTK matrix
vtkMatrix = vtk.vtkMatrix4x4()
for i in range(4):
    for j in range(4):
        vtkMatrix.SetElement(i, j, numpyMatrix[i, j])

transformNode.SetMatrixTransformToParent(vtkMatrix)
```

**Alternative method using `GetMatrixTransformToParent()` with in-place modification:**

```python
import numpy as np

transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode")

# Get the existing matrix (identity by default)
matrix = transformNode.GetMatrixTransformToParent()

# Set elements from numpy array
numpyMatrix = np.array([
    [0.866, -0.5, 0, 10],
    [0.5,  0.866, 0, 20],
    [0,    0,     1, 30],
    [0,    0,     0,  1]
])

for i in range(4):
    for j in range(4):
        matrix.SetElement(i, j, numpyMatrix[i][j])

# Mark the node as modified to trigger observers and rendering updates
transformNode.Modified()
```

**Read a transform matrix back into numpy:**

```python
import numpy as np

transformNode = getNode("MyTransform")
vtkMatrix = vtk.vtkMatrix4x4()
transformNode.GetMatrixTransformToParent(vtkMatrix)

numpyMatrix = np.zeros((4, 4))
for i in range(4):
    for j in range(4):
        numpyMatrix[i, j] = vtkMatrix.GetElement(i, j)

print("Transform matrix:")
print(numpyMatrix)
```

**Using `slicer.util.arrayFromTransformMatrix` (Slicer 5.2+):**

```python
import numpy as np

transformNode = getNode("MyTransform")

# Get transform matrix as numpy array
numpyMatrix = slicer.util.arrayFromTransformMatrix(transformNode)
print(numpyMatrix)

# Update the transform from a numpy array
numpyMatrix[0, 3] = 50.0  # change X translation
slicer.util.updateTransformMatrixFromArray(transformNode, numpyMatrix)
```

### Example of Moving a Volume Along a Trajectory Using a Transform

Animate a volume moving along a series of positions by updating a transform's translation at each step. Call `slicer.app.processEvents()` or `slicer.util.forceRenderAllViews()` to render each frame.

```python
import time
import numpy as np

# Create a transform node and apply it to the volume
transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "TrajectoryTransform")
volumeNode = getNode("MRHead")
volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

# Define a trajectory as a list of RAS positions
trajectoryPoints = [
    [0, 0, 0],
    [10, 0, 0],
    [20, 5, 0],
    [30, 10, 0],
    [40, 10, 5],
    [50, 5, 10],
]

# Animate along the trajectory
matrix = vtk.vtkMatrix4x4()
for point in trajectoryPoints:
    matrix.SetElement(0, 3, point[0])
    matrix.SetElement(1, 3, point[1])
    matrix.SetElement(2, 3, point[2])
    transformNode.SetMatrixTransformToParent(matrix)
    slicer.app.processEvents()
    time.sleep(0.5)
```

**Smooth trajectory with interpolation:**

```python
import time
import numpy as np

transformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "SmoothTrajectory")
volumeNode = getNode("MRHead")
volumeNode.SetAndObserveTransformNodeID(transformNode.GetID())

# Define keyframe positions
keyframes = np.array([
    [0, 0, 0],
    [50, 0, 0],
    [50, 50, 0],
    [0, 50, 0],
    [0, 0, 0],
])

# Interpolate between keyframes
numStepsPerSegment = 20
matrix = vtk.vtkMatrix4x4()
for i in range(len(keyframes) - 1):
    for t in np.linspace(0, 1, numStepsPerSegment):
        pos = keyframes[i] * (1 - t) + keyframes[i + 1] * t
        matrix.SetElement(0, 3, pos[0])
        matrix.SetElement(1, 3, pos[1])
        matrix.SetElement(2, 3, pos[2])
        transformNode.SetMatrixTransformToParent(matrix)
        slicer.app.processEvents()
        time.sleep(0.02)
```

### Combine Multiple Transforms

Since a transform node is also a transformable node, transforms can be nested in a hierarchy. When a node is placed under a child transform, and the child is placed under a parent, the effective transform is the concatenation of parent and child.

**Using transform hierarchy (preferred):**

```python
# Create two transform nodes
parentTransform = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "ParentTransform")
childTransform = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "ChildTransform")

# Set up a 10mm X-translation on parent
parentMatrix = vtk.vtkMatrix4x4()
parentMatrix.SetElement(0, 3, 10)
parentTransform.SetMatrixTransformToParent(parentMatrix)

# Set up a 20mm Y-translation on child
childMatrix = vtk.vtkMatrix4x4()
childMatrix.SetElement(1, 3, 20)
childTransform.SetMatrixTransformToParent(childMatrix)

# Nest child under parent (child inherits parent transform)
childTransform.SetAndObserveTransformNodeID(parentTransform.GetID())

# Apply to a volume -- effective transform is parent * child
volumeNode = getNode("MRHead")
volumeNode.SetAndObserveTransformNodeID(childTransform.GetID())

# The volume is now translated by (10, 20, 0) in world coordinates
```

**Combining by matrix multiplication:**

```python
import numpy as np

# Get existing transforms
transform1Node = getNode("Transform_1")
transform2Node = getNode("Transform_2")

# Extract matrices
mat1 = vtk.vtkMatrix4x4()
transform1Node.GetMatrixTransformToParent(mat1)
mat2 = vtk.vtkMatrix4x4()
transform2Node.GetMatrixTransformToParent(mat2)

# Multiply: combined = transform2 * transform1
# This means transform1 is applied first, then transform2
combinedMatrix = vtk.vtkMatrix4x4()
vtk.vtkMatrix4x4.Multiply4x4(mat2, mat1, combinedMatrix)

# Create a new node with the combined transform
combinedTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "CombinedTransform")
combinedTransformNode.SetMatrixTransformToParent(combinedMatrix)
```

**Get the full transform chain to world coordinates:**

```python
# Get the concatenated transform from a node to the world
transformNode = getNode("ChildTransform")
worldMatrix = vtk.vtkMatrix4x4()
transformNode.GetMatrixTransformToWorld(worldMatrix)

print("Full transform to world:")
for i in range(4):
    row = [worldMatrix.GetElement(i, j) for j in range(4)]
    print(f"  {row}")
```

### Convert a Linear Transform to a Grid Transform

A grid (deformation field) transform stores a displacement vector at each point on a regular grid. Converting a linear transform to a grid transform is useful when you need to combine it with non-linear transforms or visualize the displacement field.

```python
# Get the linear transform and a reference volume for grid extent
transformNode = getNode("LinearTransform_3")
referenceVolumeNode = getNode("MRHead")

# Create output grid transform node
gridTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLGridTransformNode", "GridTransform")

# Convert linear to grid using reference volume for extent and spacing
referenceVolumeNode.SetAndObserveTransformNodeID(transformNode.GetID())
referenceVolumeNode.HardenTransform()
```

**Using the Transforms module logic to convert:**

```python
transformNode = getNode("LinearTransform_3")
referenceVolumeNode = getNode("MRHead")

# Use the Transforms module logic to create a displacement field
transformLogic = slicer.modules.transforms.logic()

# Convert to displacement field grid
outputGridTransform = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLTransformNode", "DisplacementField")

# Sample the transform on a regular grid defined by the reference volume
slicer.cli.runSync(
    slicer.modules.transformtogrid,
    None,
    {
        "inputTransform": transformNode.GetID(),
        "referenceVolume": referenceVolumeNode.GetID(),
        "outputTransform": outputGridTransform.GetID(),
    }
)
```

### Export the Displacement Magnitude of the Transform as a Volume

Compute the displacement magnitude (distance each point moves) at every voxel location and save it as a scalar volume. This is useful for quantifying and visualizing the deformation.

```python
transformNode = getNode("LinearTransform_3")
referenceVolumeNode = getNode("MRHead")

# Create output scalar volume for displacement magnitudes
displacementMagnitudeVolume = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLScalarVolumeNode", "DisplacementMagnitude")

# Compute displacement magnitude using the Transforms module logic
transformLogic = slicer.modules.transforms.logic()
transformLogic.CreateDisplacementVolumeFromTransform(
    transformNode, referenceVolumeNode, False,
    displacementMagnitudeVolume)

# Display in slice views
slicer.util.setSliceViewerLayers(background=displacementMagnitudeVolume)
```

**Save the displacement magnitude to file:**

```python
slicer.util.saveNode(
    displacementMagnitudeVolume,
    "/path/to/displacement_magnitude.nrrd")
```

### Visualize the Displacement Magnitude as a Color Volume

Display the displacement magnitude volume with a color lookup table to visualize how much each region moves under the transform.

```python
transformNode = getNode("LinearTransform_3")
referenceVolumeNode = getNode("MRHead")

# Create displacement magnitude volume
displacementMagnitudeVolume = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLScalarVolumeNode", "DisplacementMagnitude")

transformLogic = slicer.modules.transforms.logic()
transformLogic.CreateDisplacementVolumeFromTransform(
    transformNode, referenceVolumeNode, False,
    displacementMagnitudeVolume)

# Configure display with a color table
displayNode = displacementMagnitudeVolume.GetDisplayNode()
displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeFileHotToColdRainbow.txt")
displayNode.SetAutoWindowLevel(False)
displayNode.SetWindowLevelMinMax(0, 10)  # 0-10mm displacement range

# Show in slice views
slicer.util.setSliceViewerLayers(background=displacementMagnitudeVolume)
```

**With auto window/level and a different color table:**

```python
displayNode = displacementMagnitudeVolume.GetDisplayNode()
displayNode.SetAndObserveColorNodeID("vtkMRMLColorTableNodeIron")
displayNode.SetAutoWindowLevel(True)

# Force update of all views
slicer.util.forceRenderAllViews()
```

**Visualize displacement vectors as a color (RGB) volume:**

```python
transformNode = getNode("LinearTransform_3")
referenceVolumeNode = getNode("MRHead")

# Create a vector volume (3-component) for displacement vectors
displacementVectorVolume = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLVectorVolumeNode", "DisplacementVectors")

# Compute displacement vector field
transformLogic = slicer.modules.transforms.logic()
transformLogic.CreateDisplacementVolumeFromTransform(
    transformNode, referenceVolumeNode, True,
    displacementVectorVolume)

# Display as color volume (R=X, G=Y, B=Z displacement)
displayNode = displacementVectorVolume.GetDisplayNode()
displayNode.SetScalarRangeFlag(0)  # Manual range
displayNode.SetAutoWindowLevel(False)

slicer.util.setSliceViewerLayers(background=displacementVectorVolume)
```

---

## Registration

### Register Two Images with BRAINSFit

BRAINSFit is a CLI module bundled with Slicer that performs multi-modal, multi-resolution image registration. It supports rigid, affine, BSpline, and composite transforms.

**Basic rigid + affine registration:**

```python
# Load or get the fixed and moving volume nodes
fixedVolumeNode = getNode("FixedVolume")
movingVolumeNode = getNode("MovingVolume")

# Create output transform node
outputTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "RegistrationTransform")

# Set up BRAINSFit parameters
parameters = {}
parameters["fixedVolume"] = fixedVolumeNode.GetID()
parameters["movingVolume"] = movingVolumeNode.GetID()
parameters["outputTransform"] = outputTransformNode.GetID()
parameters["useRigid"] = True
parameters["useAffine"] = True
parameters["initializeTransformMode"] = "useCenterOfHeadAlign"
parameters["numberOfIterations"] = 1500
parameters["numberOfSamples"] = 100000
parameters["minimumStepLength"] = 0.005
parameters["translationScale"] = 1000
parameters["reproportionScale"] = 1
parameters["skewScale"] = 1

# Run registration synchronously
cliNode = slicer.cli.runSync(slicer.modules.brainsfit, None, parameters)

# Check result
if cliNode.GetStatus() & cliNode.CompletedWithErrors:
    print("Registration FAILED")
else:
    print("Registration completed successfully")

# Apply resulting transform to the moving image
movingVolumeNode.SetAndObserveTransformNodeID(outputTransformNode.GetID())
```

**Rigid-only registration:**

```python
fixedVolumeNode = getNode("FixedVolume")
movingVolumeNode = getNode("MovingVolume")

outputTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "RigidTransform")

parameters = {}
parameters["fixedVolume"] = fixedVolumeNode.GetID()
parameters["movingVolume"] = movingVolumeNode.GetID()
parameters["outputTransform"] = outputTransformNode.GetID()
parameters["useRigid"] = True
parameters["initializeTransformMode"] = "useCenterOfHeadAlign"

slicer.cli.runSync(slicer.modules.brainsfit, None, parameters)

movingVolumeNode.SetAndObserveTransformNodeID(outputTransformNode.GetID())
```

**BSpline (deformable) registration:**

```python
fixedVolumeNode = getNode("FixedVolume")
movingVolumeNode = getNode("MovingVolume")

# For BSpline, output is a non-linear transform
outputTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLBSplineTransformNode", "BSplineTransform")

# Optional: provide an initial linear transform
initialTransformNode = getNode("InitialLinearTransform")

parameters = {}
parameters["fixedVolume"] = fixedVolumeNode.GetID()
parameters["movingVolume"] = movingVolumeNode.GetID()
parameters["outputTransform"] = outputTransformNode.GetID()
parameters["useBSpline"] = True
parameters["splineGridSize"] = [14, 10, 12]
parameters["numberOfIterations"] = 1500
parameters["maskProcessingMode"] = "NOMASK"
parameters["numberOfSamples"] = 100000
if initialTransformNode:
    parameters["initialTransform"] = initialTransformNode.GetID()

slicer.cli.runSync(slicer.modules.brainsfit, None, parameters)
movingVolumeNode.SetAndObserveTransformNodeID(outputTransformNode.GetID())
```

**Registration with output resampled volume:**

```python
fixedVolumeNode = getNode("FixedVolume")
movingVolumeNode = getNode("MovingVolume")

outputTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "RegistrationTransform")

# Create an output volume for the resampled (registered) moving image
outputVolumeNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLScalarVolumeNode", "RegisteredVolume")

parameters = {}
parameters["fixedVolume"] = fixedVolumeNode.GetID()
parameters["movingVolume"] = movingVolumeNode.GetID()
parameters["outputTransform"] = outputTransformNode.GetID()
parameters["outputVolume"] = outputVolumeNode.GetID()
parameters["useRigid"] = True
parameters["useAffine"] = True
parameters["initializeTransformMode"] = "useCenterOfHeadAlign"

slicer.cli.runSync(slicer.modules.brainsfit, None, parameters)

# Display the registered volume
slicer.util.setSliceViewerLayers(background=outputVolumeNode)
```

**Asynchronous registration with progress callback:**

```python
fixedVolumeNode = getNode("FixedVolume")
movingVolumeNode = getNode("MovingVolume")

outputTransformNode = slicer.mrmlScene.AddNewNodeByClass(
    "vtkMRMLLinearTransformNode", "AsyncRegistrationTransform")

parameters = {}
parameters["fixedVolume"] = fixedVolumeNode.GetID()
parameters["movingVolume"] = movingVolumeNode.GetID()
parameters["outputTransform"] = outputTransformNode.GetID()
parameters["useRigid"] = True
parameters["useAffine"] = True
parameters["initializeTransformMode"] = "useCenterOfHeadAlign"

def onRegistrationComplete(cliNode, event):
    if cliNode.GetStatus() & cliNode.Completed:
        if cliNode.GetStatus() & cliNode.CompletedWithErrors:
            print("Registration failed")
        else:
            print("Registration completed")
            movingVolumeNode.SetAndObserveTransformNodeID(
                outputTransformNode.GetID())
    elif cliNode.GetStatus() & cliNode.Cancelling:
        print("Registration cancelled")

# Run asynchronously (does not block Slicer UI)
cliNode = slicer.cli.run(slicer.modules.brainsfit, None, parameters)
cliNode.AddObserver("ModifiedEvent", onRegistrationComplete)
```

---

## Common Transform Operations Quick Reference

| Operation | Code |
|-----------|------|
| Create linear transform | `slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLinearTransformNode")` |
| Apply transform to node | `node.SetAndObserveTransformNodeID(transformNode.GetID())` |
| Remove transform from node | `node.SetAndObserveTransformNodeID(None)` |
| Harden (bake) transform | `node.HardenTransform()` |
| Get matrix to parent | `transformNode.GetMatrixTransformToParent(matrix)` |
| Set matrix to parent | `transformNode.SetMatrixTransformToParent(matrix)` |
| Get full transform to world | `transformNode.GetMatrixTransformToWorld(matrix)` |
| Load transform from file | `slicer.util.loadTransform("/path/to/file.tfm")` |
| Save transform to file | `slicer.util.saveNode(transformNode, "/path/to/file.tfm")` |
| Nest transforms | `childTransform.SetAndObserveTransformNodeID(parentTransform.GetID())` |
| Invert a transform | `transformNode.Inverse()` |
| Identity matrix | `vtk.vtkMatrix4x4()` (identity by default) |

## Troubleshooting

**Issue: Transform has no visible effect on the node**
- Ensure the transform is applied: check `node.GetTransformNodeID()` returns a valid ID
- Call `slicer.util.forceRenderAllViews()` to force a display update
- Check if another transform higher in the hierarchy is overriding the effect

**Issue: Hardening a transform produces unexpected results**
- Verify the transform is correct before hardening: inspect the matrix with `GetMatrixTransformToParent()`
- For volumes, hardening resamples the image data which may change resolution or extent
- For models, hardening transforms vertex coordinates directly

**Issue: ITK/Slicer transform conversion produces incorrect results**
- Remember: ITK stores the **resampling** (inverse) transform, while Slicer's `TransformToParent` is the **modeling** (forward) transform
- Double-check coordinate system: ITK=LPS, Slicer=RAS
- Use `slicer.util.loadTransform()` which handles the conversion automatically

**Issue: BRAINSFit registration fails or produces poor results**
- Try different initialization: `useCenterOfHeadAlign`, `useMomentsAlign`, `useGeometryAlign`
- Increase `numberOfIterations` (default is often sufficient, but complex cases may need more)
- Adjust `numberOfSamples` -- more samples improve accuracy at the cost of speed
- Check that fixed and moving volumes have sufficient overlap
- Try a simpler transform model first (rigid only) before adding affine or BSpline

## Resources

- **3D Slicer Script Repository - Transforms**: https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html#transforms
- **3D Slicer Transforms Module**: https://slicer.readthedocs.io/en/latest/user_guide/modules/transforms.html
- **BRAINSFit Documentation**: https://slicer.readthedocs.io/en/latest/user_guide/modules/brainsfit.html
- **MRML Overview**: https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html
- **VTK Transform Classes**: https://vtk.org/doc/nightly/html/classvtkTransform.html
