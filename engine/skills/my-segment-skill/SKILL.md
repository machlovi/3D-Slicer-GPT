---
name: my-segment-skill
description: Segmentation workflow for brain MRI datasets.
required-connectors:
    - SlicerAdaptiveBrush
    - SlicerSampleData
    - SlicerTools
metadata:
    skill-author: Talk2View
---

# My Segment Skill

## Datasets

Process these datasets from Slicer sample data in order:

- MR Brain Tumor 1
- MR Brain Tumor 2

## Segments

For each dataset, create these segments:

| Name       | Color |
| ---------- | ----- |
| Tumor      | red   |
| Ventricles | blue  |

## How to segment

### Tumor

Adaptive Brush with MRI T1+GD enhancing tumor preset, paint at RAS [-5, 27, 28] with 20 mm radius

### Ventricles

First, jump to RAS [18, 21, 1] in all slice views, which is close to where the ventricles are.
Then use Adaptive Brush with simple threshold algorithm, radius of 7 mm, threshold zone of 30%.

## Workflow

Ensure that the scene is empty before you create a new segmentation.

For each dataset:

1. Download the sample data
2. Create a segmentation with the first segment from the table
3. Activate the tool with the specified preset or algorithm, then apply any extras
4. Show the segmentation in 3D, and if the segment has already been painted and is not empty, jump to the segment in all slice views
5. Tell the user they can now refine the segment, and wait until they are done
6. When the user is finished, add the next segment and repeat from step 3
7. When all segments are done, report the volume of each segment,
   save the scene, and clear the scene before
   moving to the next dataset
