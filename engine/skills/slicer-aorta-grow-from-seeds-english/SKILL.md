---
name: slicer-aorta-grow-from-seeds-english
description: High-accuracy aorta segmentation on CT using Grow from Seeds effect in 3D Slicer. The more user inputs are provided, the more accurate the results will be. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Aorta Segmentation (High-Accuracy, Using Grow from Seeds)

Source: [3D Slicer Segmentation Recipes - Aorta Grow from Seeds](https://lassoan.github.io/SlicerSegmentationRecipes/AortaMaskedGrowFromSeeds/)
Author: Andras Lasso

## Overview

- Task: Segment aorta on CT. This method can produce high-accuracy results - the more user inputs are provided, the more accurate the results will be. The same method can be used for segmenting other structures that have a good contrast compared to the background but there are other structures with similar intensity nearby.
- Imaging modality: any

## Prerequisites

- SegmentEditorExtraEffects extension is installed.
- Slicer-4.10 or later.

## Recommended Workflow

- Create a segment for aorta and use Paint effect to paint a few strokes inside the aorta.
- Select Threshold effect, set slider to highlight the aorta, and click `Use for masking`.
- Create a segment for all other structures and paint in regions that have similar intensity as the aorta but it is not the aorta (bones, other vessels, etc.).
- Select `Grow from seeds` effect and click `Initialize` to compute segmentation preview.
- Inspect segmentation. If any region is misclassified then paint more strokes using the aorta or the other segment.
- Click `Apply` when segmentation preview is satisfactory to finalize the segmentation.
- Apply `Smoothing` effect, `Median` method to fill in missed voxels and smooth outer surface of the vessel.

## Tips

- To make paint strokes more visible, you can deactivate Paint effect and left-click-and-drag in the slice view to change background volume window/level.
- To see preview in 3D view: Click the down-arrow button on the right side of `Show 3D` button and disable `Surface smoothing` (this will make updates of 3D visualization very fast). Click `Show 3D` button.
- If the segmentation does not extend to the entire aorta then paint strokes in the missing parts and reinitialize (click `Cancel` and then click `Initialize`).
- To quickly activate/deactivate `Paint` effect hit `1` key.
- To quickly switch between segments, hit `q` or `w` key.

## Workflow

### Step 1
Clear the scene. Download the `CTACardio` sample data.

### Step 2
Create a segmentation with a red "Aorta" segment.

### Step 3
Select the Threshold effect. Ask the user to adjust the slider to highlight the aorta, then click Use for masking. Wait for the user to finish.

### Step 4
Set the Aorta segment color to the "aorta" anatomical color (double-click the Color column and type "aorta").

### Step 5
Add a green "Other" segment. Select the Paint effect. Ask the user to paint strokes inside the aorta (Aorta selected) and outside it in bones, vessels, etc. (Other selected). Wait for the user to finish.

### Step 6
Select the Grow from Seeds effect and click Initialize.

### Step 7
Inspect the preview. Ask the user to paint more strokes and re-initialize if any region is misclassified. Wait for the user to finish.

### Step 8
Show the segmentation in 3D.

### Step 9
Ask the user to continue refining seeds if needed. Click Apply when satisfied. Wait for the user to finish.

### Step 10
Apply Smoothing with the Median method.
