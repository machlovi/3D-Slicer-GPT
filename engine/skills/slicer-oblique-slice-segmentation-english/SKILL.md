---
name: slicer-oblique-slice-segmentation-english
description: Segmentation on arbitrarily oriented slices in 3D Slicer. Explains how to handle striping artifacts that may appear when slice view axes are not aligned with segment axes, and provides two approaches to deal with them. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Segmentation on Arbitrarily Oriented Slices

Source: [3D Slicer Segmentation Recipes - Oblique Slice Segmentation](https://lassoan.github.io/SlicerSegmentationRecipes/ObliqueSliceSegmentation/)
Author: Andras Lasso

## Overview

- Task: Segment image on slices that are not aligned with axes of the master volume.
- Imaging modality: any 3D imaging modality (CT, MRI, ...)

Segment Editor allows editing of segmentation on slices of arbitrary orientation. However, since edited segments are stored as binary labelmaps, "striping" artifacts may appear on thin segments or near boundary of any segments.

When slice view axes are aligned with segment axes: segment boundaries may appear "blocky" in slice views, but no other artifacts appear.

When slice view axes are not aligned with segment axes: slice view is filled from voxels of several planes of the segmentation, therefore thin objects or boundary of a solid object may appear to have a striped pattern.

Slicer notifies the user if slice view axes are not aligned with segment axes by showing a warning icon in the Segment Editor, next to the segmentation node selector. If the warning button is clicked, each slice view is automatically aligned to the closest segment axis.

## Recommended Workflow

Depending on the end goal, there are several approaches to deal with stripe artifacts. Present both options to the user and ask which they prefer before proceeding.

### Option A: Ignore stripes

Stripe artifacts can be safely ignored. Correctness of the segmentation near object boundaries can be verified by enabling slice view intersections and reviewing multiple neighboring slices. The probability of seeing stripe artifacts can be greatly reduced by increasing the oversampling factor in Segment Editor (click the grid icon near the segmentation selector).

No further action is needed for Option A.

### Option B: Create resampled volume with rotated axes

#### Step 1
Ask the user to place a Region of Interest (ROI) from the toolbar dropdown and drag the handles to cover the area to be segmented. Wait for the user to finish.

#### Step 2
Create a rotation transform and apply it to the ROI. Ask the user for the desired rotation angles to align with the slice orientation. Wait for the user to finish.

#### Step 3
Open the Crop Volume module. Set the Input Volume and Input ROI, then click Apply to produce a new axis-aligned cropped volume.

#### Step 4
In Segment Editor, select the newly cropped volume as the source volume. Segmentation on this volume will not have striping artifacts.
