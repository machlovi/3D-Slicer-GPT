---
name: slicer-skin-surface-wrap-solidify-english
description: Skin surface extraction using Wrap Solidify effect in 3D Slicer. A simpler method for extracting skin surface without holes, important for 3D printing or surface-based registration. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Skin Surface Extraction (Wrap Solidify Method)

Source: [3D Slicer Segmentation Recipes - Skin Surface 2](https://lassoan.github.io/SlicerSegmentationRecipes/SkinSurface2/)
Author: Andras Lasso

## Overview

- Task: Extract skin surface without holes inside the segment. Important for 3D printing or surface-based registration.
- Imaging modality: CT, MRI

Usually there is strong contrast between tissue and air, therefore segmenting the skin surface should be easy, except there may be air inside body part or some tissues or fluids may have image intensity similar to air. Therefore, simple global thresholding may not always work.

This recipe replaces an earlier recipe that used `Flood filling` effect. This new recipe is much simpler and provides comparable or better results.

## Prerequisites

- SurfaceWrapSolidify extension is installed.

## Recommended Workflow

- Use `Threshold` effect to create a segment that contains the head (skin and internal structures)
- Use `Islands` effect's `Keep largest island` method to remove noise speckles
- Use `Wrap solidify` effect (provided by `SurfaceWrapSolidify` extension) to fill holes inside the segment

## Workflow

### Step 1
Clear the scene. Download the `MRBrainTumor1` sample data.

### Step 2
Create a segmentation with a skin-colored "Skin" segment (RGB 0.9, 0.7, 0.5).

### Step 3
Apply a Threshold from approximately 110 to the maximum.

### Step 4
Use Islands with Keep largest island to remove noise speckles.

### Step 5
Select the Wrap Solidify effect. Set Region to Outer surface. Click Apply. Show the result in 3D.
