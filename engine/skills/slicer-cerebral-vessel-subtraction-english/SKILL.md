---
name: slicer-cerebral-vessel-subtraction-english
description: Cerebral vasculature segmentation by background subtraction on contrast-enhanced CT in 3D Slicer. Requires baseline and contrast-enhanced images. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Cerebral Vessel Segmentation by Subtraction

Source: [3D Slicer Segmentation Recipes - Vessel Segmentation by Subtraction](https://lassoan.github.io/SlicerSegmentationRecipes/VesselSegmentationBySubtraction/)
Author: Andras Lasso

## Overview

- Task: Segment cerebral vasculature on contrast-enhanced CT by background subtraction.
- Imaging modality: any, with baseline (non-contrasted) and contrasted images available.

## Prerequisites

- SlicerElastix and SlicerVMTK extensions are installed.
- Slicer-4.10 or later.

## Recommended Workflow

- Align baseline (non-contrast) CT and contrast-enhanced CT using `General registration (Elastix)` module to minimize artifacts due to patient motion.
- Subtract the baseline volume from contrast-enhanced volume using `Subtract scalar volumes` module.
- Use `Vesselness filtering` module to remove non-vessel shaped structures (bone plates that have not been fully suppressed by subtraction).
- In `Segment editor` module, use vesselness filtered image as master volume and extract vessels using `Threshold` effect.
- Remove remaining artifacts using `Islands` effect's `Keep largest island` method.
- Optionally compute vessel centerline using `Centerline extraction` module.

## Tips

- If there is only rigid patient motion between baseline and contrast images then `generic rigid (all)` registration preset may be used, which attempts to align the images by applying rigid transform.
- Find a module by hitting Ctrl + F and start typing its name.
- Adjust window/level of the image to improve visibility of vessels in slice viewers: click Window/Level mouse mode in the toolbar and Ctrl + Left-click-and-drag with the mouse (starting from a vessel point) to set optimal window/level automatically.

## Workflow

### Step 1
Clear the scene. Download two CTA brain volumes from the Slicer Data Store and rename them:

- **CTABrainBaseline**: https://github.com/Slicer/SlicerDataStore/releases/download/SHA256/dd3922fb4babe47c49d57674936aac93342296ee3551d2af5b2a9a3b7af916b1 — rename to `CTABrainBaseline.nrrd`
- **CTABrainContrast**: https://github.com/Slicer/SlicerDataStore/releases/download/SHA256/7b8fccab033eac291a4b237b4f99248f337ac6be0c4c8bf87d4f4d75f66214d3 — rename to `CTABrainContrast.nrrd`

Load both files into Slicer. Wait for the user to finish.

### Step 2
Register the contrast volume to the baseline using the General registration (Elastix) module. Set Fixed volume to CTABrainBaseline, Moving volume to CTABrainContrast, Preset to generic (all), and create a new output volume called CTABrainContrastAligned. Wait for the user to finish.

### Step 3
Subtract the baseline from the aligned contrast volume using the Subtract scalar volumes module. Set Input Volume 1 to CTABrainContrastAligned, Input Volume 2 to CTABrainBaseline, and create a new output called CTABrainSubtracted. Wait for the user to finish.

### Step 4
Open the Vesselness filtering module. Set the input to CTABrainSubtracted. Place a seed point on a vessel in the slice view and click Preview. Wait for the user to finish.

### Step 5
Adjust vesselness parameters — try Suppress plates at 35%, then re-preview. Check at different locations if needed. Wait for the user to finish.

### Step 6
Click Start to run the full vesselness filter on the entire volume. Wait for the user to finish.

### Step 7
Create a segmentation with an "Artery" segment. Apply a Threshold of 0.7 (lower) on the vesselness-filtered volume. Show the result in 3D.

### Step 8
Use Islands with Keep largest island to clean up the segmentation.
