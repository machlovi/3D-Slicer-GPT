---
name: slicer-skull-stripping-ct-english
description: Skull stripping on CT in 3D Slicer. Removes all skull and other bone and soft tissues around the brain. Can be used whenever a fairly homogeneous region needs to be extracted from an image volume that is mostly surrounded by different intensity regions. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Skull Stripping on CT

Source: [3D Slicer Segmentation Recipes - CT Skull Stripping](https://lassoan.github.io/SlicerSegmentationRecipes/CTSkullStripping/)
Author: Andras Lasso

## Overview

- Task: Skull stripping - remove all skull and all other bone and soft tissues around the brain. Can be used whenever a fairly homogeneous region needs to be extracted from an image volume that is mostly surrounded by different intensity regions.
- Imaging modality: head CT.

## Prerequisites

- SegmentEditorExtraEffects and SurfaceWrapSolidify extensions are installed.
- Head CT image is loaded.

## Recommended Workflow

- Create a new segment that will contain the brain region
- Use `Threshold` effect to create a segment that contains the skull bone
- Use `Wrap solidify` effect (provided by `SurfaceWrapSolidify` extension) to extract the brain cavity
- Use `Mask volume` effect (provided by `SegmentEditorExtraEffects` extension) to blank out all non-brain regions in the image

## Workflow

### Step 1
Clear the scene. Download the `CT-MR Brain` sample data.

### Step 2
Show the CTBrain volume in the slice views.

### Step 3
Create a segmentation with a white "Bone" segment.

### Step 4
Apply a Threshold of approximately 300 HU (lower) to the maximum.

### Step 5
Use Islands with Keep largest island to remove noise speckles.

### Step 6
Select the Wrap Solidify effect. Set Region to Largest cavity, enable Split cavities, set cavity size to approximately 30 mm. Click Apply.

### Step 7
Select the Mask Volume effect. Set Fill value to -1000 and click Apply. Show the output volume.

### Step 8
Hide the segmentation. Set a brain-friendly window/level on the masked volume.
