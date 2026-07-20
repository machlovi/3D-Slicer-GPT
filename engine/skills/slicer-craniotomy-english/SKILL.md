---
name: slicer-craniotomy-english
description: Craniotomy simulation by splitting segments in 3D Slicer. Guides users through cutting a hole on the skull to simulate a craniotomy. The same method can be used anytime a segment has to be partitioned into multiple segments. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Craniotomy (Splitting Segments)

Source: [3D Slicer Segmentation Recipes - Craniotomy](https://lassoan.github.io/SlicerSegmentationRecipes/Craniotomy/)
Author: Andras Lasso

## Overview

- Task: Cut a hole on the skull to simulate a craniotomy. The same method can be used anytime a segment has to be partitioned to multiple segments.
- Imaging modality: any

## Prerequisites

Have a segment that needs to be cut/partitioned into multiple pieces.

## Recommended Workflow

- Create a new segment that will contain the parts separated from the existing segment
- Click `Show 3D` button to see the segment in 3D
- Use `Scissors` effect with `Fill inside` option to cut a hole
- Rotate view, select original segment, and use `Scissors` effect again to add back regions to the original segment that should not have been cut out (e.g., other side of the skull)

## Workflow

### Step 1
Clear the scene. Download the `CT-MR Brain` sample data. Delete the MRBrainT1 and MRBrainT2 volumes — only the CT is needed.

### Step 2
Create a segmentation with a white "Skull" segment.

### Step 3
Apply a Threshold of 100 HU (lower) to segment the bone.

### Step 4
Show the segmentation in 3D.

### Step 5
Add a yellow "BoneFlap" segment.

### Step 6
Select the Scissors effect on the BoneFlap segment. Set Operation to Fill inside, and under Masking set Editable area to Inside all segments. Ask the user to draw the craniotomy boundary in the 3D view. Wait for the user to finish.

### Step 7
Deactivate Scissors. Hide the Skull segment and rotate the 3D view about 90 degrees — the scissors cut goes through both sides of the skull.

### Step 8
Select the Skull segment. Activate Scissors (same settings). Ask the user to draw around the unwanted BoneFlap region on the far side to reassign those voxels back to Skull. Wait for the user to finish.

### Step 9
Deactivate Scissors.

### Step 10
Show both segments — the skull with a hole, and the separated bone flap piece.
