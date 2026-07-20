---
name: slicer-dicom
description: DICOM import, export, database management, tag access, PACS communication, and format conversion. Use for loading medical images from DICOM, accessing metadata, exporting to DICOM formats, and interacting with PACS servers.
allowed-tools: Read Write Bash WebFetch Grep Glob
argument-hint: "[operation | 'help']"
metadata:
    skill-author: Talk2View
    slicer-version: "5.10"
    source: "3D Slicer Script Repository"
---

# Slicer DICOM Operations

## Overview

This skill covers all DICOM operations available in 3D Slicer's Python environment. Code runs inside Slicer's embedded Python interpreter where the following modules are available by default:

- `slicer` -- Core Slicer Python API (nodes, scene, utilities)
- `vtk` -- Visualization Toolkit for 3D rendering and data processing
- `qt` -- Qt framework bindings for UI and settings
- `numpy` -- Numerical computing
- `DICOMLib` -- Slicer's DICOM utilities (`DICOMUtils`, `DICOMSender`, `DICOMCommand`)
- `ctk` -- Common Toolkit with DICOM networking classes (`ctkDICOMQuery`, `ctkDICOMRetrieve`, `ctkDICOMScheduler`)
- `pydicom` -- DICOM file reading and tag access

All paths in examples use placeholders. Replace with actual paths for your environment. Use `slicer.app.temporaryPath` for temporary file operations.

## Prefer Talk2View's Built-In DICOM Tools

For routine DICOM operations inside Talk2View, use the built-in tools instead of writing raw `DICOMUtils` code:

- `import_dicom_directory(dicom_directory)` — index files into Slicer's persistent DICOM database (data shows up in the DICOM Browser and survives restart).
- `query_dicom_database()` — list patients/studies/series with their UIDs.
- `load_dicom_patient(patient_name|patient_uid)` / `load_dicom_study(study_uid)` / `load_dicom_series(series_uid)` — load specific data into the scene.
- `idc_download(series_instance_uid)` — fetch from IDC and run the full import+load pipeline.

Use the raw `DICOMUtils` patterns below only when you need behavior the built-in tools don't expose: throwaway temporary databases, custom plugin selection, DICOMweb endpoints, PACS networking, etc. Note in particular that `TemporaryDICOMDatabase` *swaps out* the user's database for the duration of the `with` block — it is the correct choice when you explicitly do not want to persist, and the wrong choice for normal "load some files" workflows.

## Load DICOM Files from Folder to Volume

Load all DICOM objects from a file folder into the scene. All registered plugins are evaluated and the one with the highest confidence will be used to load the data. Files are imported into a temporary DICOM database, so the current Slicer DICOM database is not impacted.

```python
dicomDataDir = "/path/to/dicom/folder"  # input folder with DICOM files
loadedNodeIDs = []  # this list will contain the list of all loaded node IDs

from DICOMLib import DICOMUtils
with DICOMUtils.TemporaryDICOMDatabase() as db:
  DICOMUtils.importDicom(dicomDataDir, db)
  patientUIDs = db.patients()
  for patientUID in patientUIDs:
    loadedNodeIDs.extend(DICOMUtils.loadPatientByUID(patientUID))
```

## Import DICOM Files into the Application DICOM Database

Use Slicer's built-in DICOM browser indexer to import DICOM files into the database. Images are not loaded into the scene but they show up in the DICOM browser. They can be loaded using `DICOMUtils` functions afterwards.

```python
# instantiate a new DICOM browser
slicer.util.selectModule("DICOM")
dicomBrowser = slicer.modules.DICOMWidget.browserWidget.dicomBrowser
# use dicomBrowser.ImportDirectoryCopy to make a copy of the files (useful for importing data from removable storage)
dicomBrowser.importDirectory(dicomFilesDirectory, dicomBrowser.ImportDirectoryAddLink)
# wait for import to finish before proceeding (optional, if removed then import runs in the background)
dicomBrowser.waitForImportFinished()
```

## Import DICOM Files from a DICOMweb Server

Download and import studies directly from a DICOMweb-compatible PACS such as Kheops, Google Health API, Orthanc, or DCM4CHE.

### Basic Import (No Authentication)

```python
slicer.util.selectModule("DICOM")  # ensure DICOM database is initialized
slicer.app.processEvents()
from DICOMLib import DICOMUtils
DICOMUtils.importFromDICOMWeb(
  dicomWebEndpoint="https://demo.kheops.online/api",
  studyInstanceUID="1.3.6.1.4.1.14519.5.2.1.8421.4009.985792766370191766692237040819")
```

### Authenticate with Access Token

Multiple PACS solutions support remote access authentication via access tokens.

Token sources:
- **Google Cloud**: Execute `gcloud auth print-access-token` once you have logged in.
- **Kheops**: Create an album, create a sharing link (e.g. `https://demo.kheops.online/view/TfYXwbKAW7JYbAgZ7MyISf`), the token is the string after the last slash.

```python
slicer.util.selectModule("DICOM")  # ensure DICOM database is initialized
slicer.app.processEvents()
from DICOMLib import DICOMUtils
DICOMUtils.importFromDICOMWeb(
  dicomWebEndpoint="https://demo.kheops.online/api",
  studyInstanceUID="1.3.6.1.4.1.14519.5.2.1.8421.4009.985792766370191766692237040819",
  accessToken="TfYXwbKAW7JYbAgZ7MyISf")
```

### Authenticate with Username and Password

Authentication types extending Python's `requests.auth.AuthBase` are accepted.

```python
DICOMUtils.importFromDICOMWeb(
  dicomWebEndpoint="https://demo.kheops.online/api",
  studyInstanceUID="1.3.6.1.4.1.14519.5.2.1.8421.4009.985792766370191766692237040819",
  auth=requests.HTTPBasicAuth('<user>','<password>'))
```

### Global DICOMweb Authentication

Set global username and password in the local Slicer application settings for persistence across sessions. `DICOMUtils.getGlobalDICOMAuth` creates `HTTPBasicAuth` instances from the global configuration.

```python
qt.QSettings().setValue(DICOMUtils.GLOBAL_DICOMWEB_USER_KEY, '<user>')
qt.QSettings().setValue(DICOMUtils.GLOBAL_DICOMWEB_PASSWORD_KEY, '<pwd>')
DICOMUtils.importFromDICOMWeb(
  dicomWebEndpoint="https://remote-url/",
  studyInstanceUID="1.3.6.1.4.1.14519.5.2.1.8421.4009.985792766370191766692237040819",
  auth=DICOMUtils.getGlobalDICOMAuth()
)
```

## Access Top-Level DICOM Tags

Retrieve specific DICOM tag values from images imported into the Slicer DICOM database. The `fileValue` method accesses the database of cached top-level tags (nested tags are not included).

```python
db = slicer.dicomDatabase
patientList = db.patients()
studyList = db.studiesForPatient(patientList[0])
seriesList = db.seriesForStudy(studyList[0])
fileList = db.filesForSeries(seriesList[0])
# Note, fileValue accesses the database of cached top level tags
# (nested tags are not included)
print(db.fileValue(fileList[0], "0020,0032"))
# Get tag group,number from dicom dictionary
import pydicom as dicom
tagName = "StudyDate"
tagStr = str(dicom.tag.Tag(tagName))[1:-1].replace(" ","")
print(db.fileValue(fileList[0], tagStr))
```

## Access DICOM Tags Nested in Sequences

To access DICOM tags nested within sequences, use pydicom to re-read the full dataset directly from the file rather than the database cache.

```python
db = slicer.dicomDatabase
patientList = db.patients()
studyList = db.studiesForPatient(patientList[0])
seriesList = db.seriesForStudy(studyList[0])
fileList = db.filesForSeries(seriesList[0])
# Use pydicom to access the full header, which requires
# re-reading the dataset instead of using the database cache
import pydicom
ds = pydicom.dcmread(fileList[0])
ds.CTExposureSequence[0].ExposureModulationType
```

## Access DICOM Tag of a Scalar Volume Loaded from DICOM

Volumes loaded by `DICOMScalarVolumePlugin` store SOP Instance UIDs in the volume node's `DICOM.instanceUIDs` attribute. This can be used to access any DICOM tag for the loaded volume, such as patient position.

```python
volumeName = "2: ENT IMRT"
volumeNode = slicer.util.getNode(volumeName)
instUids = volumeNode.GetAttribute("DICOM.instanceUIDs").split()
filename = slicer.dicomDatabase.fileForInstance(instUids[0])
print(slicer.dicomDatabase.fileValue(filename, "0018,5100"))  # patient position
```

## Access DICOM Tags via Subject Hierarchy

Data loaded by various DICOM plugins may not use `DICOM.instanceUIDs` but instead save the Series Instance UID to the Subject Hierarchy item. Retrieve SOP Instance UIDs from the Series Instance UID to access DICOM tags.

### Get Tag by Series Instance UID

```python
volumeName = "2: ENT IMRT"
volumeNode = slicer.util.getNode(volumeName)

# Get series instance UID from subject hierarchy
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
volumeItemId = shNode.GetItemByDataNode(volumeNode)
seriesInstanceUID = shNode.GetItemUID(volumeItemId, 'DICOM')

# Get patient name (0010,0010) from the first file of the series
instUids = slicer.dicomDatabase.instancesForSeries(seriesInstanceUID)
print(slicer.dicomDatabase.instanceValue(instUids[0], '0010,0010')) # patient name
```

### Get Tag Using Referenced Instance UIDs (RT Structure Set)

```python
rtStructName = "3: RTSTRUCT: PROS"
rtStructNode = slicer.util.getNode(rtStructName)
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
rtStructShItemID = shNode.GetItemByDataNode(rtStructNode)
ctSliceInstanceUids = shNode.GetItemAttribute(rtStructShItemID, "DICOM.ReferencedInstanceUIDs").split()
filename = slicer.dicomDatabase.fileForInstance(ctSliceInstanceUids[0])
print(slicer.dicomDatabase.fileValue(filename, "0008,0033"))  # content time
```

## Get Path and Filename of a Loaded DICOM Volume

Retrieve the file path for a scalar volume node loaded from DICOM, handling both drag-drop and DICOM browser loading scenarios.

```python
def pathFromNode(node):
  storageNode = node.GetStorageNode()
  if storageNode is not None: # loaded via drag-drop
    filepath = storageNode.GetFullNameFromFileName()
  else: # Loaded via DICOM browser
    instanceUIDs = node.GetAttribute("DICOM.instanceUIDs").split()
    filepath = slicer.dicomDatabase.fileForInstance(instanceUIDs[0])
  return filepath

# Example:
node = slicer.util.getNode("volume1")
path = pathFromNode(node)
print("DICOM path=%s" % path)
```

## Convert DICOM to NRRD on the Command Line

Convert DICOM files to NRRD format by running Slicer in headless mode from the command line. The same approach works on Windows using the top-level `Slicer.exe`. Use forward slashes in pathnames within quotes on the command line.

```bash
/Applications/Slicer-4.6.2.app/Contents/MacOS/Slicer --no-main-window --python-code "node=slicer.util.loadVolume('/tmp/series/im0.dcm'); slicer.util.saveNode(node, '/tmp/output.nrrd'); exit()"
```

On Linux, the equivalent would be:

```bash
/path/to/Slicer --no-main-window --python-code "node=slicer.util.loadVolume('/path/to/dicom/im0.dcm'); slicer.util.saveNode(node, '/path/to/output.nrrd'); exit()"
```

## Export a Volume to DICOM File Format

Convert a volume node to DICOM format by creating a Subject Hierarchy organization (patient/study) and using the `DICOMScalarVolumePlugin` exporter with customizable DICOM tags.

```python
volumeNode = getNode("CTChest")
outputFolder = "/path/to/dicom-output"

# Create patient and study and put the volume under the study
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
# set IDs. Note: these IDs are not specifying DICOM tags, but only the names that appear in the hierarchy tree
patientItemID = shNode.CreateSubjectItem(shNode.GetSceneItemID(), "test patient")
studyItemID = shNode.CreateStudyItem(patientItemID, "test study")
volumeShItemID = shNode.GetItemByDataNode(volumeNode)
shNode.SetItemParent(volumeShItemID, studyItemID)

import DICOMScalarVolumePlugin
exporter = DICOMScalarVolumePlugin.DICOMScalarVolumePluginClass()
exportables = exporter.examineForExport(volumeShItemID)
for exp in exportables:
  # set output folder
  exp.directory = outputFolder
  # here we set DICOM PatientID and StudyID tags
  exp.setTag('PatientID', "test patient")
  exp.setTag('StudyID', "test study")

exporter.export(exportables)
```

## Export a Segmentation to DICOM Segmentation Object (SEG)

Export a segmentation node to DICOM Segmentation format (SEG) by associating it with a reference volume node through Subject Hierarchy organization. Requires the `QuantitativeReporting` extension to be installed.

```python
segmentationNode = ...
referenceVolumeNode = ...
outputFolder = "/path/to/dicom-output"

# Associate segmentation node with a reference volume node
shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
referenceVolumeShItem = shNode.GetItemByDataNode(referenceVolumeNode)
studyShItem = shNode.GetItemParent(referenceVolumeShItem)
segmentationShItem = shNode.GetItemByDataNode(segmentationNode)
shNode.SetItemParent(segmentationShItem, studyShItem)

# Export to DICOM
import DICOMSegmentationPlugin
exporter = DICOMSegmentationPlugin.DICOMSegmentationPluginClass()
exportables = exporter.examineForExport(segmentationShItem)
for exp in exportables:
  exp.directory = outputFolder

exporter.export(exportables)
```

## Export an Entire DICOM Series to Research File Format

Export the entire Slicer DICOM database content to research formats (NRRD, NIfTI, etc.) with data-type filtering and output naming based on DICOM tags (PatientID, StudyDate, SeriesNumber, Modality).

```python
outputFolder = "/path/to/export/output/"

from DICOMLib import DICOMUtils
patientUIDs = slicer.dicomDatabase.patients()
for patientUID in patientUIDs:
    loadedNodeIDs = DICOMUtils.loadPatientByUID(patientUID)
    for loadedNodeID in loadedNodeIDs:
        # Check if we want to save this node
        node = slicer.mrmlScene.GetNodeByID(loadedNodeID)
        # Only export images
        if not node or not node.IsA('vtkMRMLScalarVolumeNode'):
            continue
        # Construct filename
        shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        seriesItem = shNode.GetItemByDataNode(node)
        studyItem = shNode.GetItemParent(seriesItem)
        patientItem = shNode.GetItemParent(studyItem)
        filename = shNode.GetItemAttribute(patientItem, 'DICOM.PatientID')
        filename += '_' + shNode.GetItemAttribute(studyItem, 'DICOM.StudyDate')
        filename += '_' + shNode.GetItemAttribute(seriesItem, 'DICOM.SeriesNumber')
        filename += '_' + shNode.GetItemAttribute(seriesItem, 'DICOM.Modality')
        filename = slicer.app.ioManager().forceFileNameValidCharacters(filename) + ".nrrd"
        # Save node
        print(f'Write {node.GetName()} to {filename}')
        success = slicer.util.saveNode(node, outputFolder+filename)
    slicer.mrmlScene.Clear()
```

## Query and Retrieve from a PACS (DIMSE Networking)

Query and retrieve DICOM data from a PACS server using classic DIMSE networking. Supports both C-GET (simple, connection-based retrieval where the data is sent back on the same connection) and C-MOVE (PACS-initiated transfer where the PACS opens a new connection to send data, used by older PACS servers).

### Basic Query and Retrieve

```python
# Query
dicomQuery = ctk.ctkDICOMQuery()
dicomQuery.callingAETitle = "SLICER"
dicomQuery.calledAETitle = "ANYAE"
dicomQuery.host = "dicomserver.co.uk"
dicomQuery.port = 11112
dicomQuery.setFilters({"Name":"A", "Modalities":"MR"})
tempDb = ctk.ctkDICOMDatabase()
tempDb.openDatabase("")
dicomQuery.query(tempDb)

# Retrieve
useCGET = True
dicomRetrieve = ctk.ctkDICOMRetrieve()
dicomRetrieve.callingAETitle = dicomQuery.callingAETitle
dicomRetrieve.calledAETitle = dicomQuery.calledAETitle
dicomRetrieve.host = dicomQuery.host
dicomRetrieve.port = dicomQuery.port
dicomRetrieve.setDatabase(slicer.dicomDatabase)
for study, series in dicomQuery.studyAndSeriesInstanceUIDQueried:
  print(f"ctkDICOMRetrieveTest: Retrieving {study} - {series}")
  slicer.app.processEvents()
  if useCGET:
    success = dicomRetrieve.getSeries(study, series)
  else:
    dicomRetrieve.moveDestinationAETitle = dicomQuery.callingAETitle
    success = dicomRetrieve.moveSeries(study, series)
  print(f"  - {'success' if success else 'failed'}")

slicer.dicomDatabase.updateDisplayedFields()
```

### Query and Retrieve with ctkDICOMVisualBrowser

Use the experimental `ctkDICOMVisualBrowser` for a visual interface to PACS server management and filtering.

```python
visualBrowser = slicer.modules.dicom.widgetRepresentation().self().browserWidget.dicomVisualBrowser
dicomDatabase = visualBrowser.dicomDatabase()

# Disable all existing servers
for index in range (0, visualBrowser.serversCount()):
  server = visualBrowser.server(index)
  server.queryRetrieveEnabled = False

# Add a new server
server = ctk.ctkDICOMServer()
server.connectionName = "test"
server.callingAETitle = "SLICER"
server.calledAETitle = "ANYAE"
server.host = "dicomserver.co.uk"
server.port = 104
server.retrieveProtocol = ctk.ctkDICOMServer.CGET

if visualBrowser.addServer(server) == -1:
  raise RuntimeError("Failed to add server")

# Set filters
visualBrowser.filteringPatientID = "PAT020"
visualBrowser.filteringDate = ctk.ctkDICOMPatientItemWidget.LastYear

# Start query
visualBrowser.onQueryRetrieveOptionToggled(True)
visualBrowser.onQueryPatients()
```

### Query and Retrieve with ctkDICOMScheduler (No UI)

Use the experimental `ctkDICOMScheduler` for fully programmatic automation without UI components. Includes callback handlers for job completion and failure states. The scheduler automatically progresses from patient query to study query to retrieval.

```python
class Receiver(qt.QObject):
  def __init__(self, scheduler):
    super().__init__()
    self.scheduler = scheduler
    self.scheduler.progressJobDetail.connect(self.onProgressDetails)
    self.scheduler.jobFinished.connect(self.onJobFinished)
    self.scheduler.jobFailed.connect(self.onJobFailed)

  def startQueryRetrieve(self, parameters):
    self.scheduler.setFilters(parameters)
    self.scheduler.queryPatients()

  def onJobFinished(self, details):
    for detail in details:
      if detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryPatients:
        print ("Query patients success. Connection : ", detail.connectionName())
      elif detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryStudies:
        patientID = detail.patientID()
        print ("Query studies success for patientID: ", patientID, ". Connection : ", detail.connectionName())
      elif detail.jobType() == ctk.ctkDICOMJobResponseSet.RetrieveStudy:
        patientID = detail.patientID()
        studyInstanceUID = detail.studyInstanceUID()
        print ("Retrieve studies success for studyInstanceUID: ", studyInstanceUID, " (patientID: ",patientID, "). Connection : ", detail.connectionName())

  def onJobFailed(self, details):
    for detail in details:
      if detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryPatients:
        print ("Query patients failed. Connection : ", detail.connectionName())
      elif detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryStudies:
        patientID = detail.patientID()
        print ("Query studies failed for patientID: ", patientID, ". Connection : ", detail.connectionName())
      elif detail.jobType() == ctk.ctkDICOMJobResponseSet.RetrieveStudy:
        patientID = detail.patientID()
        studyInstanceUID = detail.studyInstanceUID()
        print ("Retrieve studies failed for studyInstanceUID: ", studyInstanceUID, " (patientID: ", patientID, "). Connection : ", detail.connectionName())

  def onProgressDetails(self, details):
    for detail in details:
      if detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryPatients:
        patientIDs = detail.queriedPatientIDs()
        for patientID in patientIDs:
          print ("Starting studies query for patient: ", patientID, ". Connection : ", detail.connectionName())
          scheduler.queryStudies(patientID)
      elif detail.jobType() == ctk.ctkDICOMJobResponseSet.QueryStudies:
        studyInstanceUIDs = detail.queriedStudyInstanceUIDs()
        for studyInstanceUID in studyInstanceUIDs:
          patientItem = slicer.dicomDatabase.patientForStudy(studyInstanceUID)
          patientID = slicer.dicomDatabase.fieldForPatient("PatientID", patientItem)
          print ("Starting studies retrieve for studyInstanceUID: ", studyInstanceUID, " (patientID: ",patientID, "). Connection : ", detail.connectionName())
          scheduler.retrieveStudy(patientID, studyInstanceUID)

# Configure server
server = ctk.ctkDICOMServer()
server.connectionName = "test"
server.callingAETitle = "SLICER"
server.calledAETitle = "ANYAE"
server.host = "dicomserver.co.uk"
server.port = 104
server.retrieveProtocol = ctk.ctkDICOMServer.CGET

# Create scheduler and connect to database
scheduler = ctk.ctkDICOMScheduler()
scheduler.setDicomDatabase(slicer.dicomDatabase)
scheduler.addServer(server)

# Create receiver with callback handlers
receiver = Receiver(scheduler)

# Set query parameters with date range filter
nDays = 325
endDate = qt.QDate().currentDate()
startDate = endDate.addDays(-nDays)
parameters = {
  "ID": "PAT020",
  "StartDate": startDate.toString("yyyyMMdd"),
  "EndDate": endDate.toString("yyyyMMdd")
}

# Start the query/retrieve workflow
receiver.startQueryRetrieve(parameters)
```

## Send DICOM Data to a PACS (DIMSE)

Transmit DICOM files to a PACS server using classic DIMSE networking via the `DICOMSender` utility.

```python
from DICOMLib import DICOMSender
sender = DICOMSender(
  files=['/path/to/0.dcm', '/path/to/1.dcm'],
  address='dicomserver.co.uk:9999',
  protocol="DIMSE",
  delayed=True
)
sender.send()
```

## Send DICOM Data via DICOMweb

Transmit DICOM files to a PACS server using DICOMweb networking with optional authentication support.

```python
from DICOMLib import DICOMSender
from DICOMLib import DICOMUtils
sender = DICOMSender(
  files=['/path/to/0.dcm', '/path/to/1.dcm'],
  address='dicomserver.co.uk:9999',
  protocol="DICOMweb",
  auth=DICOMUtils.getGlobalDICOMAuth(),
  delayed=True
)
sender.send()
```

## Convert RT Structure Set to Labelmap NRRD Files

Convert radiotherapy (RT) structure sets to labelmap volumes in NRRD format using the SlicerRT extension's batch processing utilities. SlicerRT must be installed via the Extension Manager.

For batch processing of RT structure sets, use the SlicerRT BatchProcessing module:

- **Repository**: https://github.com/SlicerRt/SlicerRT/tree/master/BatchProcessing
- **Module**: `BatchProcessing` (available after installing the SlicerRT extension)

Basic approach for loading an RT structure set and converting to a closed surface representation:

```python
# Load RT structure set (requires SlicerRT extension)
# The DICOM RT plugin will automatically create a segmentation node
from DICOMLib import DICOMUtils

dicomDataDir = "/path/to/dicom/rt-struct-folder"
with DICOMUtils.TemporaryDICOMDatabase() as db:
  DICOMUtils.importDicom(dicomDataDir, db)
  patientUIDs = db.patients()
  for patientUID in patientUIDs:
    loadedNodeIDs = DICOMUtils.loadPatientByUID(patientUID)

# Access the loaded segmentation (RT structure set is loaded as a segmentation node)
segmentationNode = slicer.util.getNodesByClass('vtkMRMLSegmentationNode')[0]

# Convert to closed surface representation
segmentationNode.CreateClosedSurfaceRepresentation()

# Export as labelmap if needed
labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLLabelMapVolumeNode')
slicer.modules.segmentations.logic().ExportAllSegmentsToLabelmapNode(
  segmentationNode, labelmapVolumeNode)

# Save the labelmap as NRRD
slicer.util.saveNode(labelmapVolumeNode, "/path/to/output/rt_labelmap.nrrd")
```

## Run DCMTK Command-Line Tools

Execute DCMTK command-line tools (such as `img2dcm`) as separate processes from within Slicer. The `DICOMCommand` class manages synchronous execution, blocking until the command completes.

```python
from DICOMLib import DICOMCommand
command = DICOMCommand('img2dcm', ['image.png', 'output.dcm'])
stdout = command.start()
```

## Customize DICOM Browser Table Columns

Modify the DICOM browser table columns by changing column order, visibility, names, and widths using the `dicomDatabase` object and table manager settings.

```python
dicomBrowser = slicer.modules.dicom.widgetRepresentation().self().browserWidget.dicomBrowser
dicomDatabase = dicomBrowser.database()

# List available field names for each level
print(dicomDatabase.patientFieldNames)
print(dicomDatabase.studyFieldNames)
print(dicomDatabase.seriesFieldNames)

# Change column order by setting weight (higher weight = shown first)
dicomDatabase.setWeightForField("Series", "SeriesDescription", 7)
dicomDatabase.setWeightForField("Studies", "StudyDescription", 6)

# Change visibility of columns
dicomDatabase.setVisibilityForField("Patients", "PatientsBirthDate", False)
dicomDatabase.setVisibilityForField("Patients", "PatientsComments", True)
dicomDatabase.setWeightForField("Patients", "PatientsComments", 8)

# Change displayed column name
dicomDatabase.setDisplayedNameForField("Series", "DisplayedCount", "Number of images")

# Set column resize mode
dicomDatabase.setFormatForField("Series", "SeriesDescription", '{"resizeMode":"interactive"}')

# Change selection mode and auto-select behavior
dicomTableManager = dicomBrowser.dicomTableManager()
dicomTableManager.selectionMode = qt.QAbstractItemView.SingleSelection
dicomTableManager.autoSelectSeries = False

# Apply changes by closing and reopening the database
dicomDatabase.closeDatabase()
dicomDatabase.openDatabase(dicomBrowser.database().databaseFilename)
```

Documentation of methods for changing DICOM browser columns: https://github.com/commontk/CTK/blob/master/Libs/DICOM/Core/ctkDICOMDatabase.h#L354

## Common DICOM Tag Reference

Frequently used DICOM tags for quick reference:

| Tag | Name | Description |
|-----|------|-------------|
| `0008,0018` | SOPInstanceUID | Unique identifier for each DICOM instance |
| `0008,0033` | ContentTime | Time the content was created |
| `0008,0060` | Modality | Type of imaging (CT, MR, PT, etc.) |
| `0010,0010` | PatientName | Patient's full name |
| `0010,0020` | PatientID | Primary patient identifier |
| `0018,5100` | PatientPosition | Patient position (HFS, FFS, etc.) |
| `0020,000D` | StudyInstanceUID | Unique study identifier |
| `0020,000E` | SeriesInstanceUID | Unique series identifier |
| `0020,0032` | ImagePositionPatient | Image position in patient coordinates |

## Related Skills

- **imaging-data-commons** -- Query and download public cancer imaging data from NCI Imaging Data Commons. Use for accessing DICOM datasets from public repositories before loading into Slicer.
