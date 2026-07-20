---
name: slicer-sequences-plots-misc
description: Sequences (4D data), plotting, screen capture, subject hierarchy management, web server, batch processing, and external application launching. Use for time-series data, visualization export, data organization, and automation workflows.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Sequences, Plots, and Utilities

## Overview

This skill covers several utility areas in 3D Slicer: working with sequences (4D data), creating plots, capturing screenshots, managing the subject hierarchy, running web servers, batch processing DICOM data, and launching external applications. All code examples run inside the 3D Slicer Python environment where the following modules are available by default:

- `slicer` -- the main Slicer Python API
- `vtk` -- VTK classes for visualization and data processing
- `qt` -- Qt bindings for UI operations
- `numpy` -- numerical computing (available after import)
- `os`, `logging`, `time` -- standard library modules

**Related skills:**
- `slicer-volumes` -- Volume loading, display, and manipulation operations
- `slicer-segmentations` -- Segmentation creation and editing operations
- `slicer-views-layouts` -- View layout management, linking, and orientation
- `slicer-scene-management` -- Scene loading, saving, and node management
- `slicer-dicom` -- DICOM loading and database operations
- `slicer-transforms-registration` -- Transform and registration operations
- `slicer-markups-measurements` -- Markups and measurement operations

---

## Sequences

Sequences in 3D Slicer represent time-varying (4D) data, such as cardiac CT or dynamic contrast-enhanced MRI. A sequence node contains multiple data nodes indexed by a parameter (typically time). A sequence browser node controls playback and provides proxy nodes for display.

### Access Voxels of a 4D Volume as NumPy Array

Access voxels of a specific item (time point) in a volume sequence as a numpy array.

```python
import SampleData
sequenceNode = SampleData.SampleDataLogic().downloadSample("CTPCardioSeq")
# Alternatively, get the first sequence node in the scene:
# sequenceNode = slicer.util.getNodesByClass("vtkMRMLSequenceNode")

itemIndex = 5
voxelArray = slicer.util.arrayFromVolume(sequenceNode.GetNthDataNode(itemIndex))
```

### Access All Voxels of a 4D Volume as a Single NumPy Array

Get all voxels of a 4D volume (3D volume sequence) as a numpy array called `voxelArray`. Dimensions: k, j, i, t.

```python
sequenceNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSequenceNode")

import numpy as np
dims = slicer.util.arrayFromVolume(sequenceNode.GetNthDataNode(0)).shape
voxelArray = np.zeros([dims[0], dims[1], dims[2], sequenceNode.GetNumberOfDataNodes()])

for volumeIndex in range(sequenceNode.GetNumberOfDataNodes()):
    voxelArray[:, :, :, volumeIndex] = slicer.util.arrayFromVolume(sequenceNode.GetNthDataNode(volumeIndex))
```

### Get Index Value

Retrieve index name, value, and unit for a specific item in a sequence.

```python
print("Index value of {0}th item: {1} = {2} {3}".format(
  itemIndex,
  sequenceNode.GetIndexName(),
  sequenceNode.GetNthIndexValue(itemIndex),
  sequenceNode.GetIndexUnit()))
```

### Browse a Sequence and Access Currently Displayed Nodes

Use a sequence browser node to navigate through sequence items and access the currently displayed proxy node.

```python
import SampleData
sequenceNode = SampleData.SampleDataLogic().downloadSample("CTPCardioSeq")

browserNode = slicer.modules.sequences.logic().GetFirstBrowserNodeForSequenceNode(sequenceNode)

print("Number of items in the sequence: {0}".format(browserNode.GetNumberOfItems()))
print("Index name: {0}".format(browserNode.GetMasterSequenceNode().GetIndexName()))

browserNode.SetSelectedItemNumber(5)

volumeNode = browserNode.GetProxyNode(sequenceNode)
voxelArray = slicer.util.arrayFromVolume(volumeNode)
```

### Concatenate All Sequences in the Scene into a New Sequence

Merge multiple sequence nodes into a single sequence with sequential index values.

```python
sequenceNodes = slicer.util.getNodesByClass("vtkMRMLSequenceNode")
mergedSequenceNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSequenceNode", "Merged sequence")

mergedIndexValue = 0
for sequenceNode in sequenceNodes:
  for itemIndex in range(sequenceNode.GetNumberOfDataNodes()):
    dataNode = sequenceNode.GetNthDataNode(itemIndex)
    mergedSequenceNode.SetDataNodeAtValue(dataNode, str(mergedIndexValue))
    mergedIndexValue += 1
  slicer.mrmlScene.RemoveNode(sequenceNode)

mergedSequenceBrowserNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSequenceBrowserNode", "Merged")
mergedSequenceBrowserNode.AddSynchronizedSequenceNode(mergedSequenceNode)
slicer.modules.sequences.toolBar().setActiveBrowserNode(mergedSequenceBrowserNode)

mergedProxyNode = mergedSequenceBrowserNode.GetProxyNode(mergedSequenceNode)
slicer.util.setSliceViewerLayers(background=mergedProxyNode)
```

### Plot Segments Average Intensity Over Time

Plot average intensity in specific regions (designated using segments in a segmentation node) of a volume sequence over time.

```python
volumeSequenceProxyNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
segmentationNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLSegmentationNode")

volumeSequenceBrowserNode = slicer.modules.sequences.logic().GetFirstBrowserNodeForProxyNode(volumeSequenceProxyNode)
volumeSequenceNode = volumeSequenceBrowserNode.GetSequenceNode(volumeSequenceProxyNode)

segmentNames = []
segmentArrays = []
visibleSegmentIds = vtk.vtkStringArray()
segmentationNode.GetDisplayNode().GetVisibleSegmentIDs(visibleSegmentIds)

for segmentIdIndex in range(visibleSegmentIds.GetNumberOfValues()):
    segmentId = visibleSegmentIds.GetValue(segmentIdIndex)
    segmentArrays.append(slicer.util.arrayFromSegmentBinaryLabelmap(segmentationNode, segmentId, volumeSequenceProxyNode))
    segmentNames.append(segmentationNode.GetSegmentation().GetSegment(segmentId).GetName())

import numpy as np
intensityTable = np.zeros([volumeSequenceNode.GetNumberOfDataNodes(), len(segmentArrays)+1])
intensityTableTimeColumn = 0
intensityTableColumnNames = [volumeSequenceNode.GetIndexName()] + segmentNames

for volumeIndex in range(volumeSequenceNode.GetNumberOfDataNodes()):
    intensityTable[volumeIndex, intensityTableTimeColumn] = volumeSequenceNode.GetNthIndexValue(volumeIndex)
    for segmentIndex, segmentArray in enumerate(segmentArrays):
        voxelArray = slicer.util.arrayFromVolume(volumeSequenceNode.GetNthDataNode(volumeIndex))
        intensityTable[volumeIndex, segmentIndex+1] = voxelArray[segmentArray>0].mean()

plotNodes = {}
slicer.util.plot(intensityTable, intensityTableTimeColumn, intensityTableColumnNames, "Intensity", nodes=plotNodes)

for segmentIdIndex in range(visibleSegmentIds.GetNumberOfValues()):
    segment = segmentationNode.GetSegmentation().GetSegment(visibleSegmentIds.GetValue(segmentIdIndex))
    seriesNode = plotNodes['series'][segmentIdIndex]
    seriesNode.SetColor(segment.GetColor())
    seriesNode.SetName(segment.GetName())
```

### Export Nodes Warped by Transform Sequence

Warp a segmentation with a sequence of transforms and write each transformed segmentation to a PLY file.

```python
transformSequenceNode = slicer.util.getNode("OutputTransforms")
segmentationNode = slicer.util.getNode("Segmentation")
segmentIndex = 0
outputFilePrefix = r"/path/to/output/seg"

segmentationNode.CreateClosedSurfaceRepresentation()
segmentModelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode')

for itemIndex in range(transformSequenceNode.GetNumberOfDataNodes()):
  segment = segmentationNode.GetSegmentation().GetNthSegment(segmentIndex)
  slicer.modules.segmentations.logic().ExportSegmentToRepresentationNode(segment, segmentModelNode)
  transform = transformSequenceNode.GetNthDataNode(itemIndex).GetTransformToParent()
  segmentModelNode.ApplyTransform(transform)
  outputFileName = f"{outputFilePrefix}_{itemIndex:03}.ply"
  print(outputFileName)
  slicer.util.saveNode(segmentModelNode, outputFileName)

slicer.mrmlScene.RemoveNode(segmentModelNode)
```

### Create a 4D Volume in Python -- Outside Slicer

Write a `seq.nrrd` file (that Slicer can load as a volume sequence) from an `img` numpy array with dimensions t, i, j, k. Requires the `pynrrd` library.

```python
import nrrd
header = {
    'type': 'int',
    'dimension': 4,
    'space': 'right-anterior-superior',
    'space directions': [[float('nan'), float('nan'), float('nan')], [1.953125, 0., 0.], [0., 1.953125, 0.], [0., 0., 1.953125]],
    'kinds': ['list', 'domain', 'domain', 'domain'],
    'labels': ['frame', '', '', ''],
    'endian': 'little',
    'encoding': 'raw',
    'space origin': [-137.16099548, -36.80649948, -309.71899414],
    'measurement frame': [[1., 0., 0.], [0., 1., 0.], [0., 0., 1.]],
    'axis 0 index type': 'numeric',
    'axis 0 index values': '0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25'
}
nrrd.write("/path/to/output.seq.nrrd", img, header)
```

---

## Plots

Slicer provides built-in plot support through MRML plot nodes displayed in view layouts, as well as support for matplotlib (non-interactive and interactive via wxWidgets).

### Using `slicer.util.plot()` Utility Function

The simplest way to create plots in Slicer. Computes a histogram and displays it.

```python
# Get a volume from SampleData and compute its histogram
import SampleData
import numpy as np
volumeNode = SampleData.SampleDataLogic().downloadMRHead()
histogram = np.histogram(slicer.util.arrayFromVolume(volumeNode), bins=50)

chartNode = slicer.util.plot(histogram, xColumnIndex = 1)
chartNode.SetYAxisRangeAuto(False)
chartNode.SetYAxisRange(0, 4e5)
```

### Using MRML Plot Nodes Directly

Create plots using MRML classes only, with full control over table nodes, plot series, chart configuration, and layout display.

```python
# Get a volume from SampleData
import SampleData
volumeNode = SampleData.SampleDataLogic().downloadMRHead()

# Compute histogram values
import numpy as np
histogram = np.histogram(slicer.util.arrayFromVolume(volumeNode), bins=50)

# Save results to a new table node
tableNode=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode")
slicer.util.updateTableFromArray(tableNode, histogram)
tableNode.GetTable().GetColumn(0).SetName("Count")
tableNode.GetTable().GetColumn(1).SetName("Intensity")

# Create plot
plotSeriesNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", volumeNode.GetName() + " histogram")
plotSeriesNode.SetAndObserveTableNodeID(tableNode.GetID())
plotSeriesNode.SetXColumnName("Intensity")
plotSeriesNode.SetYColumnName("Count")
plotSeriesNode.SetPlotType(plotSeriesNode.PlotTypeScatterBar)
plotSeriesNode.SetColor(0, 0.6, 1.0)

# Create chart and add plot
plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode")
plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode.GetID())
plotChartNode.YAxisRangeAutoOff()
plotChartNode.SetYAxisRange(0, 500000)

# Show plot in layout
slicer.modules.plots.logic().ShowChartInLayout(plotChartNode)
```

### Save Plot as Vector Graphics (.svg)

Export a plot view to SVG format for publication-quality vector graphics.

```python
plotView = slicer.app.layoutManager().plotWidget(0).plotView()
plotView.saveAsSVG("/path/to/output.svg")
```

### Using Matplotlib -- Non-Interactive

The default Tk backend locks up and crashes Slicer. Use the `Agg` backend for non-interactive (file-based) plotting, and display the result using a QLabel widget.

```python
try:
  import matplotlib
except ModuleNotFoundError:
  slicer.util.pip_install("matplotlib")
  import matplotlib

matplotlib.use("Agg")
from pylab import *

t1 = arange(0.0, 5.0, 0.1)
t2 = arange(0.0, 5.0, 0.02)
t3 = arange(0.0, 2.0, 0.01)

subplot(211)
plot(t1, cos(2*pi*t1)*exp(-t1), "bo", t2, cos(2*pi*t2)*exp(-t2), "k")
grid(True)
title("A tale of 2 subplots")
ylabel("Damped")

subplot(212)
plot(t3, cos(2*pi*t3), "r--")
grid(True)
xlabel("time (s)")
ylabel("Undamped")
savefig("MatplotlibExample.png")

# Static image view
pm = qt.QPixmap("MatplotlibExample.png")
imageWidget = qt.QLabel()
imageWidget.setPixmap(pm)
imageWidget.setScaledContents(True)
imageWidget.show()
```

### Using Matplotlib in Slicer Jupyter Notebook

When using Slicer from a Jupyter notebook, use the `JupyterNotebooksLib` display helper.

```python
import JupyterNotebooksLib as slicernb
try:
  import matplotlib
except ModuleNotFoundError:
  slicer.util.pip_install("matplotlib")
  import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

def f(t):
  s1 = np.cos(2*np.pi*t)
  e1 = np.exp(-t)
  return s1 * e1

t1 = np.arange(0.0, 5.0, 0.1)
t2 = np.arange(0.0, 5.0, 0.02)
t3 = np.arange(0.0, 2.0, 0.01)

fig, axs = plt.subplots(2, 1, constrained_layout=True)
axs[0].plot(t1, f(t1), "o", t2, f(t2), "-")
axs[0].set_title("subplot 1")
axs[0].set_xlabel("distance (m)")
axs[0].set_ylabel("Damped oscillation")
fig.suptitle("This is a somewhat long figure title", fontsize=16)

axs[1].plot(t3, np.cos(2*np.pi*t3), "--")
axs[1].set_xlabel("time (s)")
axs[1].set_title("subplot 2")
axs[1].set_ylabel("Undamped")

slicernb.MatplotlibDisplay(matplotlib.pyplot)
```

### Interactive Matplotlib Plot Using wxWidgets

For interactive matplotlib plots (pan, zoom, etc.), use the `WXAgg` backend with `wxPython`.

```python
try:
  import matplotlib
  import wx
except ModuleNotFoundError:
  slicer.util.pip_install("matplotlib wxPython")
  import matplotlib

# Get a volume from SampleData and compute its histogram
import SampleData
import numpy as np
volumeNode = SampleData.SampleDataLogic().downloadMRHead()
histogram = np.histogram(slicer.util.arrayFromVolume(volumeNode), bins=50)

# Set matplotlib to use WXAgg backend
import matplotlib
matplotlib.use("WXAgg")

# Show an interactive plot
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot(histogram[1][1:], histogram[0].astype(float))
ax.grid(True)
ax.set_ylim((0, 4e5))
plt.show(block=False)
```

---

## Screen Capture

Capture screenshots of the full Slicer window, individual views, or series of slice images. Uses the `ScreenCapture` module for advanced captures and `qt.QPixmap` for simple grabs.

### Capture the Full Slicer Screen

Save a screenshot of the entire Slicer main window to a file.

```python
img = qt.QPixmap.grabWidget(slicer.util.mainWindow()).toImage()
img.save("/path/to/screenshot.png")
```

### Capture All Views

Capture all views (3D and slice) with view controllers hidden for a clean image.

```python
import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
cap.showViewControllers(False)
cap.captureImageFromView(None, "/path/to/all_views.png")
cap.showViewControllers(True)
```

### Capture a Single View

Capture a specific view by its MRML view node ID.

```python
viewNodeID = "vtkMRMLViewNode1"
import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
view = cap.viewFromNode(slicer.mrmlScene.GetNodeByID(viewNodeID))
cap.captureImageFromView(view, "/path/to/single_view.png")
```

### Capture a Slice View Sweep into a Series of PNG Files

Sweep through slice offsets and capture an image at each position using the `ScreenCapture` module.

```python
import ScreenCapture
ScreenCapture.ScreenCaptureLogic().captureSliceSweep(
    getNode("vtkMRMLSliceNodeRed"),
    -125.0,  # start offset
    75.0,    # end offset
    30,      # number of steps
    "/path/to/output",
    "image_%05d.png"
)
```

### Capture 3D View with Transparent Background

Capture a 3D view as a PNG image with transparent (alpha) background, useful for compositing.

```python
view = slicer.app.layoutManager().threeDWidget(0).threeDView()
view.mrmlViewNode().SetBackgroundColor(0,0,0)
view.mrmlViewNode().SetBackgroundColor2(0,0,0)
view.forceRender()
renderWindow = view.renderWindow()
renderWindow.SetAlphaBitPlanes(1)
wti = vtk.vtkWindowToImageFilter()
wti.SetInputBufferTypeToRGBA()
wti.SetInput(renderWindow)
writer = vtk.vtkPNGWriter()
writer.SetFileName("/path/to/screenshot_transparent.png")
writer.SetInputConnection(wti.GetOutputPort())
writer.Write()
```

### Capture Slice View with White Background

Capture a slice view with a white background instead of the default black.

```python
sliceViewName = "Red"
filename = "/path/to/screenshot_white.png"
view = slicer.app.layoutManager().sliceWidget(sliceViewName).sliceView()
view.setBackgroundColor(qt.QColor.fromRgbF(1,1,1))
view.forceRender()
import ScreenCapture
cap = ScreenCapture.ScreenCaptureLogic()
cap.captureImageFromView(view, filename)
```

### Save a Series of Images from a Slice View

Sweep through slice positions and capture each frame as an image file.

```python
layoutName = "Green"
imagePathPattern = "/path/to/output/image-%03d.png"
steps = 10

widget = slicer.app.layoutManager().sliceWidget(layoutName)
view = widget.sliceView()
logic = widget.sliceLogic()
bounds = [0,]*6
logic.GetSliceBounds(bounds)

for step in range(steps):
  offset = bounds[4] + step/(1.*steps) * (bounds[5]-bounds[4])
  logic.SetSliceOffset(offset)
  view.forceRender()
  image = qt.QPixmap.grabWidget(view).toImage()
  image.save(imagePathPattern % step)
```

---

## Subject Hierarchy

The Subject Hierarchy provides a tree structure for organizing all data nodes in the MRML scene, similar to a DICOM patient/study/series hierarchy or a file system. It supports creating folders, patient/study items, managing parent-child relationships, setting attributes, and filtering views.

See also the `slicer-scene-management` skill for general scene operations including cloning nodes via the subject hierarchy.

### Get the Subject Hierarchy Node

The subject hierarchy is a singleton node in the MRML scene.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
```

Or using the convenience shortcut:

```python
shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
```

### Create Subject Hierarchy Items

Create organizational items (folders, subjects, studies) in the hierarchy.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

# Create a folder item under the scene root
folderItemID = shNode.CreateFolderItem(shNode.GetSceneItemID(), "MyFolder")

# Create a patient (subject) item
patientItemID = shNode.CreateSubjectItem(shNode.GetSceneItemID(), "MyPatient")

# Create a study item under the patient
studyItemID = shNode.CreateStudyItem(patientItemID, "MyStudy")
```

### Get Subject Hierarchy Items

Find items by data node, name, UID, or other criteria.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

# Get the scene root item
sceneItemID = shNode.GetSceneItemID()

# Get item by data node
volumeNode = slicer.util.getNode("MyVolume")
itemID = shNode.GetItemByDataNode(volumeNode)

# Get item by name (child of a specific parent)
subjectItemID = shNode.GetItemChildWithName(sceneItemID, "Subject_1")

# Get item by DICOM UID
itemID = shNode.GetItemByUID(slicer.vtkMRMLSubjectHierarchyConstants.GetDICOMUIDName(), seriesInstanceUid)

# Get item by DICOM instance UID
itemID = shNode.GetItemByUIDList(slicer.vtkMRMLSubjectHierarchyConstants.GetDICOMInstanceUIDName(), instanceUID)

# Check for invalid item ID
invalidItemID = slicer.vtkMRMLSubjectHierarchyNode.GetInvalidItemID()
```

### Traverse Children of a Subject Hierarchy Item

Iterate over all children of an item to process data under a folder or study.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
parentItemID = shNode.GetSceneItemID()

children = vtk.vtkIdList()
shNode.GetItemChildren(parentItemID, children)
for i in range(children.GetNumberOfIds()):
  child = children.GetId(i)
  dataNode = shNode.GetItemDataNode(child)
  print(shNode.GetItemName(child))
```

### Manipulate Subject Hierarchy Items

Get and set names, parents, visibility, and custom attributes on hierarchy items.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
volumeNode = slicer.util.getNode("MyVolume")
itemID = shNode.GetItemByDataNode(volumeNode)

# Get item name
print(shNode.GetItemName(itemID))

# Set item name
shNode.SetItemName(itemID, "NewName")

# Change parent
newParentItemID = shNode.CreateFolderItem(shNode.GetSceneItemID(), "NewParent")
shNode.SetItemParent(itemID, newParentItemID)

# Set visibility
shNode.SetItemDisplayVisibility(itemID, 1)

# Set folder visibility using the Folder plugin
pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
folderPlugin = pluginHandler.pluginByName("Folder")
folderPlugin.setDisplayVisibility(newParentItemID, 1)

# Get/set item attributes
shNode.SetItemAttribute(itemID, "MyAttribute", "MyValue")
print(shNode.GetItemAttribute(itemID, "MyAttribute"))
```

### Filter Items in TreeView or ComboBox

Filter which items are displayed in the subject hierarchy tree view using attribute filters.

```python
# Assuming shTreeView is a reference to the subject hierarchy tree view widget
# For example: shTreeView = slicer.modules.Data.widgetRepresentation().self().tree

# Show count of currently displayed items
print(shTreeView.displayedItemCount())

# Filter by attribute existence
shTreeView.setAttributeFilter("DICOM.Modality")
print(shTreeView.displayedItemCount())

# Filter by attribute value
shTreeView.setAttributeFilter("DICOM.Modality", "CT")
print(shTreeView.displayedItemCount())

# Remove attribute filter
shTreeView.removeAttributeFilter()
print(shTreeView.displayedItemCount())
```

### Listen to Subject Hierarchy Item Events

Add observers to be notified when subject hierarchy items are modified.

```python
class MyListenerClass(VTKObservationMixin):
  def __init__(self):
    VTKObservationMixin.__init__(self)
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    self.addObserver(shNode, shNode.SubjectHierarchyItemModifiedEvent, self.shItemModifiedEvent)

  @vtk.calldata_type(vtk.VTK_LONG)
  def shItemModifiedEvent(self, caller, eventId, callData):
    print("SH Node modified")
    print("SH item ID: {0}".format(callData))
```

### Subject Hierarchy Plugin Offering View Context Menu Action

Create a custom subject hierarchy plugin that adds actions to the right-click context menu in the subject hierarchy tree view. This is implemented as a scripted Slicer module.

```python
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from SubjectHierarchyPlugins import AbstractScriptedSubjectHierarchyPlugin

class ViewContextMenu(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Context menu example"
    self.parent.categories = ["Examples"]
    self.parent.contributors = ["Steve Pieper (Isomics, Inc.)"]
    slicer.app.connect("startupCompleted()", self.onStartupCompleted)

  def onStartupCompleted(self):
    import SubjectHierarchyPlugins
    from ViewContextMenu import ViewContextMenuSubjectHierarchyPlugin
    scriptedPlugin = slicer.qSlicerSubjectHierarchyScriptedPlugin(None)
    scriptedPlugin.setPythonSource(ViewContextMenuSubjectHierarchyPlugin.filePath)
    pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
    pluginHandler.registerPlugin(scriptedPlugin)
    print("ViewContextMenuSubjectHierarchyPlugin loaded")


class ViewContextMenuSubjectHierarchyPlugin(AbstractScriptedSubjectHierarchyPlugin):
  filePath = __file__

  def __init__(self, scriptedPlugin):
    self.viewAction = qt.QAction("CUSTOM VIEW...", scriptedPlugin)
    self.viewAction.objectName = "CustomViewAction"
    slicer.qSlicerSubjectHierarchyAbstractPlugin.setActionPosition(
        self.viewAction,
        slicer.qSlicerSubjectHierarchyAbstractPlugin.SectionNode+5
    )
    self.viewAction.connect("triggered()", self.onViewAction)

  def viewContextMenuActions(self):
    return [self.viewAction]

  def showViewContextMenuActionsForItem(self, itemID, eventData=None):
    print(f"itemID: {itemID}")
    print(f"eventData: {eventData}")
    self.viewAction.visible = True

  def onViewAction(self):
    print("Custom view action is called")
    slicer.util.messageBox("This works!")
```

### Use Allowlist to Customize View Menu

Restrict which context menu actions are available in the subject hierarchy view.

```python
pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler.instance()
pluginLogic = pluginHandler.pluginLogic()

# List all registered view context menu action names
print(pluginLogic.registeredViewContextMenuActionNames)

# Set allowlist to only show specific actions
pluginLogic.allowedViewContextMenuActionNames = ["RenamePointAction"]
```

### Save Files to Directory Structure Matching Subject Hierarchy Folders

Export data nodes to disk with a directory structure that mirrors the subject hierarchy organization. Recursively traverses the hierarchy and saves each storable node.

```python
def exportNodes(shFolderItemId, outputFolder):
    childIds = vtk.vtkIdList()
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    shNode.GetItemChildren(shFolderItemId, childIds)
    if childIds.GetNumberOfIds() == 0:
        return
    import os
    os.makedirs(outputFolder, exist_ok=True)
    for itemIdIndex in range(childIds.GetNumberOfIds()):
        shItemId = childIds.GetId(itemIdIndex)
        dataNode = shNode.GetItemDataNode(shItemId)
        if dataNode and dataNode.IsA("vtkMRMLStorableNode") and dataNode.GetStorageNode():
            storageNode = dataNode.GetStorageNode()
            filename = os.path.basename(storageNode.GetFileName())
            filepath = outputFolder + "/" + filename
            slicer.util.exportNode(dataNode, filepath)
        grandChildIds = vtk.vtkIdList()
        shNode.GetItemChildren(shItemId, grandChildIds)
        if grandChildIds.GetNumberOfIds() > 0:
            exportNodes(shItemId, outputFolder+"/"+shNode.GetItemName(shItemId))

shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
outputFolder = "/path/to/output"
slicer.app.ioManager().addDefaultStorageNodes()
exportNodes(shNode.GetSceneItemID(), outputFolder)
```

---

## WebServer

Slicer includes a `WebServer` module that can serve static content and handle custom HTTP request endpoints. This is useful for integrating Slicer with web-based tools and dashboards.

**Note:** Hosting web content has security implications. Use this feature with caution and only on trusted networks. See the `WebServerLib` for more complete examples.

### Serve Static Content

Create a web server instance that serves static files from a directory.

```python
import WebServer
import WebServerLib
# serve content from the temp directory on port 9916 and print all messages
handler = WebServerLib.StaticPagesRequestHandler(docroot=b"/tmp", logMessage=print)
logic = WebServer.WebServerLogic(port=9916, requestHandlers=[handler], logMessage=print)
logic.start()
print(f"Open 'http://localhost:{logic.port}'")
# stop later with logic.stop()
```

### Custom Request Handler

Create a web server with custom endpoint handlers that can access the full Slicer Python environment.

```python
import urllib
import WebServer
import WebServerLib

class ExampleRequestHandler(WebServerLib.BaseRequestHandler):

    def __init__(self, logMessage = None):
        """
        Initialize a new Example request handler instance.
        :param logMessage: An optional external handle for message logging.
        """
        self.logMessage = logMessage

    def canHandleRequest(self, uri: bytes, **_kwargs) -> float:
        """
        Whether the given request is a Example request.
        :param uri: The request URI to parse.
        :return: 0.5 confidence if the request is an Example request, else 0.0
        """
        parsedURL = urllib.parse.urlparse(uri)
        return 0.5 if parsedURL.path.startswith(b"/example") else 0.0

    def handleRequest(self, method: str, uri: bytes, requestBody: bytes, **_kwargs) -> tuple[bytes, bytes]:
        """
        Dispatches various example requests.
        :param method: The HTTP request method. 'GET', 'POST', etc.
        :param uri: The request URI to parse.
        :param requestBody: the binary that came with the request
        :return: tuple of content type (based on file ext) and request body binary (contents of file)
        """
        parsedURL = urllib.parse.urlparse(uri)
        contentType = b"text/plain"
        responseBody = None
        splitPath = parsedURL.path.split(b"/")
        if len(splitPath) > 2 and splitPath[2] == b"ping":
            self.logMessage("handling collections")
            responseBody = b"pong"
        else:
            self.logMessage("Unhandled Example request path: %s" % parsedURL.path)
            responseBody = b"Unhandled Example request path"

        return contentType, responseBody

# create a server with a custom handler class - here it does nothing, but it
# can access and use anything from the Slicer python environment
PORT = 2042
import WebServer
logMessage = WebServer.WebServerLogic.defaultLogMessage
requestHandlers = [ExampleRequestHandler()]
logic = WebServer.WebServerLogic(port=PORT, logMessage=logMessage, enableSlicer=False, enableStaticPages=False, enableDICOM=False, requestHandlers=requestHandlers)

logic.start()
print(f"Open 'http://localhost:{logic.port}/example/ping'")
# stop later with logic.stop()
```

---

## Batch Processing

Automate operations across multiple DICOM series or data files. Useful for research pipelines, data conversion, and bulk analysis.

See also the `slicer-dicom` skill for DICOM loading and database operations.

### Iterate Through DICOM Series

Process each DICOM series in the database, loading volumes and saving them with descriptive filenames based on DICOM metadata.

```python
outputFolder = "/path/to/output/"

from DICOMLib import DICOMUtils
patientUIDs = slicer.dicomDatabase.patients()
for patientUID in patientUIDs:
    loadedNodeIDs = DICOMUtils.loadPatientByUID(patientUID)
    for loadedNodeID in loadedNodeIDs:
        node = slicer.mrmlScene.GetNodeByID(loadedNodeID)
        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            continue
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        seriesItem = shNode.GetItemByDataNode(node)
        studyItem = shNode.GetItemParent(seriesItem)
        patientItem = shNode.GetItemParent(studyItem)
        filename = shNode.GetItemAttribute(patientItem, 'DICOM.PatientID')
        filename += '_' + shNode.GetItemAttribute(studyItem, 'DICOM.StudyDate')
        filename += '_' + shNode.GetItemAttribute(seriesItem, 'DICOM.SeriesNumber')
        filename += '_' + shNode.GetItemAttribute(seriesItem, 'DICOM.Modality')
        filename = slicer.app.ioManager().forceFileNameValidCharacters(filename) + ".nrrd"
        print(f'Write {node.GetName()} to {filename}')
        success = slicer.util.saveNode(node, outputFolder+filename)
    slicer.mrmlScene.Clear()
```

### Iterate Through DICOM Series with Directory Processing

An alternative approach that copies DICOM files to a temporary directory for processing.

```python
db = slicer.dicomDatabase
patients = db.patients()
patientCount = 0
for patient in patients:
  patientCount += 1
  print(f"Patient {patient} ({patientCount} of {len(patients)})")
  for study in db.studiesForPatient(patient):
    print(f"Study {study}")
    for series in db.seriesForStudy(study):
      print(f"Series {series}")
      temporaryDir = qt.QTemporaryDir()
      for instanceUID in db.instancesForSeries(series):
        qt.QFile.copy(db.fileForInstance(instanceUID), f"{temporaryDir.path()}/{instanceUID}.dcm")
      patientID = slicer.dicomDatabase.instanceValue(instanceUID, '0010,0020')
      outputPath = os.path.join(convertedPath, patientID, study, series, "BatchResult")
      if not os.path.exists(outputPath):
        os.makedirs(outputPath)
      # do an operation here that processes the series into the outputPath
```

Running a batch processing script from the Slicer Python console:

```python
filePath = "/path/to/myscript.py"
exec(open(filePath).read())
```

### Extracting Volume Patches Around Segments

Extract segmentation subsets and their oriented bounding boxes for machine learning applications (e.g., MONAI Label). Uses `SegmentStatistics` to compute oriented bounding boxes and `CropVolume` to extract patches.

```python
import glob
import os

def segROI(segmentationNode):
  import SegmentStatistics
  segStatLogic = SegmentStatistics.SegmentStatisticsLogic()
  segStatLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
  segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_origin_ras.enabled",str(True))
  segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_diameter_mm.enabled",str(True))
  segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_x.enabled",str(True))
  segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_y.enabled",str(True))
  segStatLogic.getParameterNode().SetParameter("LabelmapSegmentStatisticsPlugin.obb_direction_ras_z.enabled",str(True))
  segStatLogic.computeStatistics()
  stats = segStatLogic.getStatistics()

  import numpy as np
  for segmentId in stats["SegmentIDs"]:
    obb_origin_ras = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_origin_ras"])
    obb_diameter_mm = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_diameter_mm"])
    obb_direction_ras_x = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_x"])
    obb_direction_ras_y = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_y"])
    obb_direction_ras_z = np.array(stats[segmentId,"LabelmapSegmentStatisticsPlugin.obb_direction_ras_z"])
    segment = segmentationNode.GetSegmentation().GetSegment(segmentId)
    roi=slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsROINode")
    roi.SetName(segment.GetName() + " OBB")
    roi.GetDisplayNode().SetHandlesInteractive(False)
    roi.SetSize(obb_diameter_mm * 2)
    obb_center_ras = obb_origin_ras+0.5*(obb_diameter_mm[0] * obb_direction_ras_x + obb_diameter_mm[1] * obb_direction_ras_y + obb_diameter_mm[2] * obb_direction_ras_z)
    boundingBoxToRasTransform = np.row_stack((np.column_stack(((1,0,0), (0,1,0), (0,0,1), obb_center_ras)), (0, 0, 0, 1)))
    boundingBoxToRasTransformMatrix = slicer.util.vtkMatrixFromArray(boundingBoxToRasTransform)
    roi.SetAndObserveObjectToNodeMatrix(boundingBoxToRasTransformMatrix)
    return roi

labelFiles = glob.glob("/path/to/imagesTr/labels/final/*.nii.gz")

for labelFile in labelFiles:
  slicer.mrmlScene.Clear()
  print(labelFile)
  baseName = os.path.basename(labelFile)
  ctFile = os.path.join("/path/to/imagesTr", baseName)
  print(ctFile)
  ct = slicer.util.loadVolume(ctFile)
  seg = slicer.util.loadSegmentation(labelFile)
  roi = segROI(seg)
  cropVolumeParameters = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLCropVolumeParametersNode")
  cropVolumeParameters.SetInputVolumeNodeID(ct.GetID())
  cropVolumeParameters.SetROINodeID(roi.GetID())
  slicer.modules.cropvolume.logic().Apply(cropVolumeParameters)
  croppedCT = cropVolumeParameters.GetOutputVolumeNode()
  seg.SetReferenceImageGeometryParameterFromVolumeNode(croppedCT)
  segLogic = slicer.modules.segmentations.logic()
  labelmap = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
  segLogic.ExportAllSegmentsToLabelmapNode(seg, labelmap, slicer.vtkSegmentation.EXTENT_REFERENCE_GEOMETRY)
  slicer.util.saveNode(croppedCT, f"/path/to/crops/{baseName}")
  slicer.util.saveNode(labelmap, f"/path/to/crops/labels/final/{baseName}")
  slicer.app.processEvents()
```

---

## Launch External Applications

Launch external processes from within Slicer while avoiding library conflicts. When Slicer runs, it modifies environment variables (PATH, LD_LIBRARY_PATH, etc.) to include its own ITK, VTK, Qt, and other libraries. External applications with their own versions of these libraries may crash due to conflicts. Use `slicer.util.startupEnvironment()` to restore the original environment.

### Launch External Process in Startup Environment

Run an external application using the environment that was present when Slicer was first launched, avoiding library conflicts.

```python
command_to_execute = ["/usr/bin/python3", "-c", "print('hola')"]
from subprocess import check_output
check_output(
  command_to_execute,
  env=slicer.util.startupEnvironment()
  )
```

On certain systems, the `shell=True` parameter may be required as well:

```python
from subprocess import check_output
result = check_output(
  ["/usr/bin/python3", "-c", "print('hello')"],
  env=slicer.util.startupEnvironment(),
  shell=True
)
print(result.decode())
```

---

## Resources

- [3D Slicer Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html) -- comprehensive code examples for all Slicer operations
- [Sequences Module Documentation](https://slicer.readthedocs.io/en/latest/user_guide/modules/sequences.html) -- user guide for the Sequences module
- [Plots Module Documentation](https://slicer.readthedocs.io/en/latest/user_guide/modules/plots.html) -- user guide for the Plots module
- [Screen Capture Module](https://slicer.readthedocs.io/en/latest/user_guide/modules/screencapture.html) -- user guide for the Screen Capture module
- [Subject Hierarchy Documentation](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html#subject-hierarchy) -- MRML overview of subject hierarchy
- [WebServer Extension](https://github.com/pieper/SlicerWeb) -- SlicerWeb extension for web server functionality
- [MRML Overview](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html) -- core MRML scene graph concepts
