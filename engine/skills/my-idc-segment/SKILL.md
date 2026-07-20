---
name: my-idc-segment
description: Automated lung CT analysis pipeline that discovers and downloads chest CT data from NCI Imaging Data Commons, then segments and visualizes thoracic anatomy (lungs, airways, bone, soft tissue) with volume measurements.
required-connectors:
    - SlicerIDCBrowser
    - SlicerTools
metadata:
    skill-author: Talk2View
---

# IDC Lung CT Anatomy Analysis

An end-to-end medical imaging pipeline: find public chest CT data from the
Imaging Data Commons, download it, segment thoracic anatomy, create a 3D
visualization, and measure volumes.

## Data Discovery

Find two chest CT series from the LIDC-IDRI collection (Lung Image Database
Consortium) with different patients. Pick series between 20-150 MB so they
download quickly.

## Segments

For each CT dataset, create these segments in order:

| Name        | Color      | RGB              |
| ----------- | ---------- | ---------------- |
| Lungs       | cyan       | 0.0, 0.85, 0.85 |
| Airways     | yellow     | 1.0, 0.9, 0.2   |
| Bone        | off-white  | 0.95, 0.92, 0.85|
| Soft Tissue | salmon red | 0.9, 0.35, 0.3  |

## How to Segment

### Lungs

1. Set the window/level to the CT lung preset
2. Threshold with lower = -900, upper = -200 (lung parenchyma HU range)
3. Remove small islands with minimum size 1000 voxels
4. Fill holes with hole size 3 mm
5. Smooth with closing method, kernel size 2 mm

### Airways

1. Threshold with lower = -1024, upper = -950 (air-filled structures)
2. Remove small islands with minimum size 500 voxels (keeps trachea and major bronchi)
3. Smooth with median method, kernel size 1.5 mm

### Bone

1. Set the window/level to the CT bone preset
2. Threshold with lower = 200, upper = 3000 (cortical and trabecular bone)
3. Remove small islands with minimum size 200 voxels
4. Smooth with median method, kernel size 1 mm

### Soft Tissue

1. Set the window/level to the CT soft tissue preset
2. Threshold with lower = -100, upper = 200 (muscle, organs, mediastinum)
3. Keep only the largest island (the main body contour)
4. Smooth with closing method, kernel size 3 mm
5. Subtract the Lungs segment from Soft Tissue (carves out the lung cavities)

## 3D Visualization

After all segments are created:

1. Show the segmentation in 3D
2. Set Bone opacity to 0.3 (semi-transparent ribcage reveals lungs inside)
3. Set Soft Tissue opacity to 0.15 (ghostly body outline for context)
4. Set Lungs opacity to 0.7
5. Set Airways opacity to 1.0 (fully opaque bronchial tree)
6. Hide the Soft Tissue segment (it can be noisy; the user can re-enable it)
7. Center and rotate the 3D view to the anterior axis

## Workflow

Ensure that the scene is empty before starting.

For each of the two CT series:

1. Tell the user which patient you are about to process
2. Download the series from IDC
3. Create a segmentation named "Thorax Anatomy" with all four segments
   as described above
4. Jump to the Lungs segment in all slice views
5. Measure the volume of all four segments and report the results in a table
   (healthy adult lungs are typically 2000-3000 cm3 per lung)
6. Set up the 3D visualization as described above
7. Tell the user the analysis is complete and summarize the findings.
   Mention that they can toggle segment visibility, adjust opacity,
   or rotate the view to explore.
8. Wait for the user to say they are done exploring
9. Clear the scene before moving to the next dataset

After both datasets are processed, summarize the volume measurements
from both patients side by side for comparison.
