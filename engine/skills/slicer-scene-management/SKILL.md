---
name: slicer-scene-management
description: MRML scene operations including node management, scene saving/loading, module selection, extension management, and Python package installation. Use for operations on the Slicer scene graph, file I/O, and application configuration.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer Scene Management

## Overview

This skill covers 3D Slicer MRML scene operations, node management, scene saving and loading, module selection, extension management, and Python package installation. All code examples run inside the 3D Slicer Python environment where the following modules are available by default:

- `slicer` -- the main Slicer Python API
- `vtk` -- VTK classes for visualization and data processing
- `qt` -- Qt bindings for UI operations
- `numpy` -- numerical computing (available after import)
- `os`, `logging`, `time` -- standard library modules

The central data structure in Slicer is the **MRML scene** (`slicer.mrmlScene`), a directed acyclic graph that holds all data nodes (volumes, models, transforms, markups, etc.), display nodes, and storage nodes. All operations on data in Slicer go through the MRML scene.

## MRML Scene

### Get MRML Node from the Scene

Retrieve nodes from the MRML scene by name, ID, or class. This is the most common starting point for any scene manipulation.

**Get a node by name using the convenience function:**

```python
pointListNode = getNode('F')
pointListNode.RemoveNthControlPoint(0)
```

**Get the first node of a specific class:**

```python
volumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
volumeNode.GetDisplayNode().SetAutoWindowLevel(False)
volumeNode.GetDisplayNode().SetWindowLevelMinMax(100, 200)
```

**Get a node by ID:**

```python
node = slicer.mrmlScene.GetNodeByID("vtkMRMLScalarVolumeNode1")
```

**Get a node by name (MRML API):**

```python
node = slicer.mrmlScene.GetFirstNodeByName("MRHead")
```

**Get all nodes of a specific class:**

```python
volumeNodes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
for volumeNode in volumeNodes:
    print(volumeNode.GetName())
```

**Get a node using slicer.util convenience function:**

```python
volumeNode = slicer.util.getNode("MRHead")
```

### Clone a Node

Create a deep copy of any data node using the Subject Hierarchy. This duplicates the node and all its associated data (display nodes, storage nodes, etc.).

```python
import SampleData
nodeToClone = SampleData.SampleDataLogic().downloadMRHead()

# Get subject hierarchy node
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
itemIDToClone = shNode.GetItemByDataNode(nodeToClone)
clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
clonedNode = shNode.GetItemDataNode(clonedItemID)
```

### Save a Node to File

Save any single MRML node to a file on disk. This creates a storage node if one does not exist and writes the data to the specified path.

```python
myNode = getNode("LinearTransform_3")

myStorageNode = myNode.CreateDefaultStorageNode()
myStorageNode.SetFileName("/path/to/something.tfm")
myStorageNode.WriteData(myNode)
```

You can also use the convenience function:

```python
slicer.util.saveNode(myNode, "/path/to/output.nrrd")
```

### Save the Scene into a Single MRB File

Save the entire MRML scene (all nodes, data, and references) into a single compressed Medical Reality Bundle (.mrb) file. This is the recommended format for sharing complete scenes.

```python
import time
sceneSaveFilename = slicer.app.temporaryPath + "/saved-scene-" + time.strftime("%Y%m%d-%H%M%S") + ".mrb"

if slicer.util.saveScene(sceneSaveFilename):
    logging.info("Scene saved to: {0}".format(sceneSaveFilename))
else:
    logging.error("Scene saving failed")
```

### Save the Scene into a New Directory

Save the scene as a Slicer Data Bundle directory, which contains individual files for each node along with the .mrml scene file. Useful when you need access to individual files.

```python
import os
import time
sceneSaveDirectory = slicer.app.temporaryPath + "/saved-scene-" + time.strftime("%Y%m%d-%H%M%S")
if not os.access(sceneSaveDirectory, os.F_OK):
    os.makedirs(sceneSaveDirectory)

if slicer.app.applicationLogic().SaveSceneToSlicerDataBundleDirectory(sceneSaveDirectory, None):
    logging.info("Scene saved to: {0}".format(sceneSaveDirectory))
else:
    logging.error("Scene saving failed")
```

### Load a Scene

Load a previously saved scene file (.mrml or .mrb) into Slicer. This replaces the current scene contents.

```python
slicer.util.loadScene("/path/to/scene.mrb")
```

Load from command line:

```
Slicer.exe --python-code "slicer.util.loadScene('/path/to/2013-08-23-Scene.mrb')"
```

### Override Default Scene Save Dialog

Replace the default scene save dialog with custom save behavior. This is useful for modules that need to implement auto-save or simplified save workflows.

```python
class MyModuleFileDialog():
    """This specially named class is detected by the scripted loadable
    module and is the target for optional drag and drop operations.
    See: Base/QTGUI/qSlicerScriptedFileDialog.h.

    This class is used for overriding default scene save dialog
    with simple saving the scene without asking anything.
    """

    def __init__(self, qSlicerFileDialog):
        self.qSlicerFileDialog = qSlicerFileDialog
        qSlicerFileDialog.fileType = "NoFile"
        qSlicerFileDialog.description = "Save scene"
        qSlicerFileDialog.action = slicer.qSlicerFileDialog.Write

    def execDialog(self):
        # Implement custom scene save operation here.
        # Return True if saving completed successfully,
        # return False if saving was cancelled.
        ...
        return saved
```

### Override Application Close Behavior

Install an event filter on the main window to intercept and customize the application close event. Use this to add confirmation dialogs, auto-save, or cleanup logic before Slicer exits.

```python
class CloseApplicationEventFilter(qt.QWidget):
    def eventFilter(self, object, event):
        if event.type() == qt.QEvent.Close:
            event.accept()
            return True
        return False

filter = CloseApplicationEventFilter()
slicer.util.mainWindow().installEventFilter(filter)
```

### Change Default Output File Type for New Nodes

Set the default file format used when saving new nodes. This affects all nodes created after the default is set. For example, change the default model output format from VTK to PLY.

```python
defaultModelStorageNode = slicer.vtkMRMLModelStorageNode()
defaultModelStorageNode.SetDefaultWriteFileExtension("ply")
slicer.mrmlScene.AddDefaultNode(defaultModelStorageNode)
```

### Change File Type for Existing Nodes

Modify the storage settings for nodes that already exist in the scene.

**Remove existing storage nodes to force re-creation with new defaults:**

```python
existingModelStorageNodes = slicer.util.getNodesByClass("vtkMRMLModelStorageNode")
for modelStorageNode in existingModelStorageNodes:
    slicer.mrmlScene.RemoveNode(modelStorageNode)
```

**Update file extensions for volume nodes:**

```python
requiredFileExtension = ".nia"
originalFileExtension = ".nrrd"
volumeNodes = slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode")
for volumeNode in volumeNodes:
    volumeStorageNode = volumeNode.GetStorageNode()
    if not volumeStorageNode:
        volumeNode.AddDefaultStorageNode()
        volumeStorageNode = volumeNode.GetStorageNode()
        volumeStorageNode.SetFileName(volumeNode.GetName() + requiredFileExtension)
    else:
        volumeStorageNode.SetFileName(volumeStorageNode.GetFileName().replace(originalFileExtension, requiredFileExtension))
```

**Set volumes to save uncompressed by default:**

```python
defaultVolumeStorageNode = slicer.vtkMRMLVolumeArchetypeStorageNode()
defaultVolumeStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultVolumeStorageNode)
logging.info("Volume nodes will be stored uncompressed by default")
```

**Set segmentations to save uncompressed by default:**

```python
defaultSegmentationStorageNode = slicer.vtkMRMLSegmentationStorageNode()
defaultSegmentationStorageNode.SetUseCompression(0)
slicer.mrmlScene.AddDefaultNode(defaultSegmentationStorageNode)
logging.info("Segmentation nodes will be stored uncompressed by default")
```

### Add and Remove Nodes

Programmatically add or remove nodes from the MRML scene.

**Add a new node to the scene:**

```python
# Create and add a new model node
modelNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLModelNode", "MyModel")

# Create and add a new volume node
volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", "MyVolume")
```

**Remove a node from the scene:**

```python
node = slicer.util.getNode("MyModel")
slicer.mrmlScene.RemoveNode(node)
```

**Clear the entire scene:**

```python
slicer.mrmlScene.Clear(0)
```

### Scene Batch Processing

When making many changes to the scene at once, wrap operations in batch processing calls to improve performance. This suppresses individual update events until the batch is complete.

```python
# Start batch processing (suppresses events)
slicer.mrmlScene.StartState(slicer.mrmlScene.BatchProcessState)

# Perform many scene operations here...
for i in range(100):
    node = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", f"Point_{i}")

# End batch processing (triggers a single update)
slicer.mrmlScene.EndState(slicer.mrmlScene.BatchProcessState)
```

### Observe Scene Events

Add observers to the MRML scene to react to changes such as node additions, removals, or scene imports.

```python
def onNodeAdded(caller, event, calldata):
    node = calldata
    if node.IsA("vtkMRMLScalarVolumeNode"):
        print(f"Volume node added: {node.GetName()}")

# Add observer for node added events
observerTag = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, onNodeAdded)

# To remove the observer later:
slicer.mrmlScene.RemoveObserver(observerTag)
```

## Subject Hierarchy

The Subject Hierarchy provides a tree structure for organizing all data nodes in the scene, similar to a file system. It supports creating folders, renaming items, setting attributes, and managing parent-child relationships.

### Get the Subject Hierarchy Node

The subject hierarchy is a singleton node in the MRML scene.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
```

### Create Subject Hierarchy Item

Create folders or organizational items in the hierarchy.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
itemID = shNode.CreateFolderItem(shNode.GetSceneItemID(), "MyFolder")
```

### Get Subject Hierarchy Item for a Data Node

Find the subject hierarchy item associated with a specific data node.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
volumeNode = slicer.util.getNode("MyVolume")
itemID = shNode.GetItemByDataNode(volumeNode)
```

### Traverse Children of a Subject Hierarchy Item

Iterate over all children of an item, for example to process all data under a folder.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
parentItemID = shNode.GetSceneItemID()
childrenIDs = vtk.vtkIdList()
shNode.GetItemChildren(parentItemID, childrenIDs)
for i in range(childrenIDs.GetNumberOfIds()):
    childID = childrenIDs.GetId(i)
    child = shNode.GetItemDataNode(childID)
```

### Manipulate Subject Hierarchy Item

Get and set names and custom attributes on hierarchy items.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
volumeNode = slicer.util.getNode("MyVolume")
itemID = shNode.GetItemByDataNode(volumeNode)

# Get item name
print(shNode.GetItemName(itemID))

# Set item name
shNode.SetItemName(itemID, "NewName")

# Get/set item attributes
print(shNode.GetItemAttribute(itemID, "MyAttribute"))
shNode.SetItemAttribute(itemID, "MyAttribute", "MyValue")
```

### Filter Items in TreeView or ComboBox

Restrict the subject hierarchy tree view to show only specific node types.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
shTreeView = slicer.modules.Data.widgetRepresentation().self().tree

# Show only volume nodes
shTreeView.setRootItem(shNode.GetSceneItemID())
shTreeView.hideAllItems()
for volumeNode in slicer.util.getNodesByClass("vtkMRMLScalarVolumeNode"):
    volumeItemID = shNode.GetItemByDataNode(volumeNode)
    shTreeView.unhideItemAndParents(volumeItemID)
```

### Listen to Subject Hierarchy Item Events

Add observers to be notified when subject hierarchy items are modified.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)

def onSubjectHierarchyItemModified(caller, eventId):
    print("Item was modified!")

shNode.AddObserver(
    slicer.vtkMRMLSubjectHierarchyNode.SubjectHierarchyItemModifiedEvent,
    onSubjectHierarchyItemModified
)
```

### Subject Hierarchy Plugin for View Context Menu

Create a custom plugin that adds actions to the right-click context menu in the subject hierarchy tree view.

```python
import qt

class MySubjectHierarchyPlugin(object):
    def __init__(self, scriptedPlugin):
        self.scriptedPlugin = scriptedPlugin

    def canOwnSubjectHierarchyItem(self, itemID):
        return False  # This plugin doesn't own items

    def roleForPlugin(self):
        return "MyPlugin"

    def helpText(self):
        return "Description of MyPlugin"

    def icon(self, itemID):
        return qt.QIcon()

    def visibilityIcon(self, visible):
        return qt.QIcon()

    def editProperties(self, itemID):
        pass

    def sceneContextMenuActions(self):
        return []

    def itemContextMenuActions(self):
        actions = []
        action = qt.QAction("My custom action", self.scriptedPlugin)
        action.connect("triggered()", self.onMyCustomAction)
        actions.append(action)
        return actions

    def onMyCustomAction(self):
        print("Custom action triggered!")
```

### Use Allowlist to Customize View Menu

Filter the subject hierarchy tree view to only show certain node types.

```python
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
shTreeView = slicer.modules.Data.widgetRepresentation().self().tree

# Only show volume and segmentation nodes
shTreeView.setNodeTypeToFilterList(["vtkMRMLScalarVolumeNode", "vtkMRMLSegmentationNode"])
```

### Save Files to Directory Structure Matching Subject Hierarchy Folders

Export data to disk with a directory structure that mirrors the subject hierarchy organization.

```python
import os
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
rootPath = "/path/to/output"

def saveItemRecursively(itemID, parentPath):
    item = shNode.GetItemDataNode(itemID)
    if item:
        # Save data node
        itemName = shNode.GetItemName(itemID)
        filePath = parentPath + "/" + itemName + ".nrrd"
        slicer.util.saveNode(item, filePath)

    # Save children
    childrenIDs = vtk.vtkIdList()
    shNode.GetItemChildren(itemID, childrenIDs)
    for i in range(childrenIDs.GetNumberOfIds()):
        childID = childrenIDs.GetId(i)
        childName = shNode.GetItemName(childID)
        childPath = parentPath + "/" + childName
        if not os.path.exists(childPath):
            os.makedirs(childPath)
        saveItemRecursively(childID, childPath)

saveItemRecursively(shNode.GetSceneItemID(), rootPath)
```

## Module Selection

### Switch to a Different Module

Programmatically switch the active Slicer module. This changes the module panel to show the specified module's UI.

```python
slicer.util.selectModule("DICOM")
```

Common module names include: `Data`, `DICOM`, `Volumes`, `Models`, `Segmentations`, `Transforms`, `Markups`, `VolumeRendering`, `SegmentEditor`, `Welcome`.

### Set a New Default Module at Startup

Change which module is shown when Slicer starts. By default, Slicer shows the Welcome module.

```python
qt.QSettings().setValue("Modules/HomeModule", "Data")
```

## Launch Slicer

### Open a File with Slicer at the Command Line

Launch Slicer and immediately open a data file.

On Windows:

```
"c:\Users\myusername\AppData\Local\NA-MIC\Slicer 4.11.20210226\Slicer.exe" c:\some\folder\MRHead.nrrd
```

Windows shortcut:

```
start Slicer c:\some\folder\MRHead.nrrd
```

### Open an .mrb File with Slicer at the Command Line

Load a Medical Reality Bundle file at startup using the Python interface.

```
Slicer.exe --python-code "slicer.util.loadScene('f:/2013-08-23-Scene.mrb')"
```

### Run Python Commands in the Slicer Environment

Execute arbitrary Python code at Slicer startup. Useful for automation and headless processing.

```
Slicer.exe --python-code "doSomething; doSomethingElse; etc." --testing --no-splash --no-main-window
```

### Run a Python Script File in the Slicer Environment

Execute a full Python script file when Slicer launches.

On Windows:

```
Slicer.exe --python-script "/full/path/to/myscript.py" --no-splash --no-main-window
```

On macOS:

```
/Applications/Slicer.app/Contents/MacOS/Slicer --no-splash --no-main-window --python-script "/full/path/to/myscript.py"
```

### Launch Slicer Directly from a Web Browser

Slicer can be launched via custom URL schemes. This allows web applications to open data directly in Slicer.

Download and open a file:

```
slicer://viewer/?download=https%3A%2F%2Fgithub.com%2Frbumm%2FSlicerLungCTAnalyzer%2Freleases%2Fdownload%2FSampleData%2FLungCTAnalyzerChestCT.nrrd
```

Open a DICOM study from a DICOMweb server:

```
slicer://viewer/?studyUID=2.16.840.1.113669.632.20.121711.10000158860&access_token=k0zR6WAPpNbVguQ8gGUHp6&dicomweb_endpoint=http%3A%2F%2Fdemo.kheops.online%2Fapi&dicomweb_uri_endpoint=%20http%3A%2F%2Fdemo.kheops.online%2Fapi%2Fwado
```

## Manage Extensions

### Download and Install an Extension

Install a Slicer extension from the Extensions Server programmatically. This is equivalent to using the Extension Manager GUI.

```python
extensionName = 'SlicerIGT'
em = slicer.app.extensionsManagerModel()
em.interactive = False  # prevent display of popups
restart = True
if not em.installExtensionFromServer(extensionName, restart):
    raise ValueError(f"Failed to install {extensionName} extension")
```

### Install a Module Directly from a Git Repository

Install a module from a git repository without requiring a Slicer restart. This is useful for sharing code during development. See the [complete code snippet](https://gist.github.com/pieper/a9c0ba57de3833c9f5aea68247bda597) for a full implementation.

### Install a Python Package

Install Python packages at runtime using pip. Always check if the package is already available before installing, and consider asking the user for confirmation.

```python
try:
    import flywheel
except ModuleNotFoundError:
    if slicer.util.confirmOkCancelDisplay("This module requires 'flywheel-sdk' Python package. Click OK to install it now."):
        slicer.util.pip_install("flywheel-sdk")
        import flywheel
```

**Install without user confirmation (use for required dependencies):**

```python
slicer.util.pip_install("numpy>=1.21")
```

**Install multiple packages:**

```python
slicer.util.pip_install("pandas scikit-learn matplotlib")
```

## Common Patterns

### List All Nodes in the Scene

Enumerate all nodes currently in the MRML scene, optionally filtering by class.

```python
# List all node types and counts
nodeCount = slicer.mrmlScene.GetNumberOfNodes()
for i in range(nodeCount):
    node = slicer.mrmlScene.GetNthNode(i)
    print(f"{node.GetClassName()}: {node.GetName()}")
```

**List specific node types with counts:**

```python
for className in ["vtkMRMLScalarVolumeNode", "vtkMRMLModelNode", "vtkMRMLSegmentationNode",
                   "vtkMRMLMarkupsFiducialNode", "vtkMRMLTransformNode"]:
    nodes = slicer.util.getNodesByClass(className)
    if nodes:
        print(f"{className}: {len(nodes)} nodes")
        for node in nodes:
            print(f"  - {node.GetName()} (ID: {node.GetID()})")
```

### Load Data Files

Load various file types into the Slicer scene.

```python
# Load a volume
volumeNode = slicer.util.loadVolume("/path/to/volume.nrrd")

# Load a model
modelNode = slicer.util.loadModel("/path/to/model.vtk")

# Load a segmentation
segmentationNode = slicer.util.loadSegmentation("/path/to/segmentation.seg.nrrd")

# Load a transform
transformNode = slicer.util.loadTransform("/path/to/transform.tfm")

# Load markups
markupsNode = slicer.util.loadMarkups("/path/to/markups.mrk.json")

# Load a color table
colorNode = slicer.util.loadColorTable("/path/to/colors.ctbl")
```

### Force Render Updates

After making changes to display properties, force all views to re-render.

```python
slicer.util.forceRenderAllViews()
```

### Get Application Paths

Access standard application directories for file operations.

```python
# Temporary directory (safe for scratch files)
tempPath = slicer.app.temporaryPath

# Application home directory
homePath = slicer.app.slicerHome

# Settings file location
settingsPath = slicer.app.slicerUserSettingsFilePath

# Extensions install path
extensionsPath = slicer.app.extensionsInstallPath
```

## Related Skills

- See the **slicer-volumes** skill for volume loading, display, and manipulation operations.
- See the **slicer-segmentations** skill for segmentation creation and editing operations.
- See the **slicer-models** skill for 3D model display and manipulation.
- See the **slicer-transforms** skill for spatial transform operations.
- See the **slicer-markups** skill for markup/annotation operations.

## Resources

- [3D Slicer Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html) -- comprehensive code examples for all Slicer operations
- [MRML Overview](https://slicer.readthedocs.io/en/latest/developer_guide/mrml_overview.html) -- core concepts for the Medical Reality Markup Language scene graph
- [Slicer Developer Guide](https://slicer.readthedocs.io/en/latest/developer_guide/slicer.html) -- main API reference and development guidelines
- [Slicer Python API](https://slicer.readthedocs.io/en/latest/developer_guide/slicer.html#slicer-module-api) -- module-level Python API documentation
