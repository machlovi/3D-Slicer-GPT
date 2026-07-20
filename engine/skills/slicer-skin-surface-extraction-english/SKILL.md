---
name: slicer-skin-surface-extraction-english
description: Skin surface extraction using Flood filling effect in 3D Slicer. Guides users through extracting skin surface without holes, important for 3D printing or surface-based registration. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Skin Surface Extraction (Flood Filling Method)

Source: [3D Slicer Segmentation Recipes - Skin Surface](https://lassoan.github.io/SlicerSegmentationRecipes/SkinSurface/)
Author: Andras Lasso

**Note: This recipe is now obsolete. It is replaced by the newer recipe that uses the Wrap Solidify effect (see slicer-skin-surface-wrap-solidify-english skill). The new recipe is much simpler and provides comparable or better results.**

## Overview

- Task: Extract skin surface without holes inside the segment. Important for 3D printing or surface-based registration.
- Imaging modality: CT, MRI

Usually there is strong contrast between tissue and air, therefore segmenting the skin surface should be easy, except there may be air inside body part or some tissues or fluids may have image intensity similar to air. Therefore, simple global thresholding may not always work.

## Prerequisites

- The `SegmentEditorExtraEffects` extension must be installed (provides the Flood Filling effect).

## Recommended Workflow

- Use `Flood filling` effect (provided by `SegmentEditorExtraEffects` extension) to segment outside air
- Use `Logical operators` effect / `Invert` operation to make the segment contain tissue instead of air
- Use `Scissors` effect and `Smoothing` effect to remove artifacts and noise

## Workflow

### Step 1
Clear the scene. Download the `MRBrainTumor1` sample data.

### Step 2
Create a segmentation with a skin-colored "Skin" segment (RGB 0.9, 0.7, 0.5).

### Step 3
Select the Flood Filling effect.

### Step 4
Ask the user to click in a dark air region (outside the head) in a slice view. Wait for the user to finish.

### Step 5
Increase Intensity tolerance to about 20. Ask the user to click in remaining unfilled air regions. Wait for the user to finish.

### Step 6
Optionally, undo and increase Neighborhood size to 3.0 to prevent leaking. Ask the user to click again in the air region. Wait for the user to finish.

### Step 7
Use Logical operators with the Invert operation to convert the air into a tissue selection.

### Step 8
Show the segmentation in 3D. Select the Scissors effect. Ask the user to remove any incorrectly included regions. Wait for the user to finish.

### Step 9
Use Islands with Keep largest island. Then apply Smoothing with the Median method.
