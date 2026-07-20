---
name: slicer-aorta-fast-marching-english
description: Aorta segmentation on CT using Fast Marching effect in 3D Slicer. A fast method that produces results quickly without requiring too much user input. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Aorta Segmentation (Fast, Using Fast Marching)

Source: [3D Slicer Segmentation Recipes - Aorta Fast Marching](https://lassoan.github.io/SlicerSegmentationRecipes/AortaFastMarching/)
Author: Andras Lasso

## Overview

- Task: Segment aorta on CT. This method produces results quickly, without requiring too much user input. The same method can be used for segmenting other structures that have a good contrast compared to the background but there are other structures with similar intensity nearby.
- Imaging modality: any

## Prerequisites

- SegmentEditorExtraEffects extension is installed.
- Contrast-enhanced CT volume is loaded.

## Recommended Workflow

- Click Paint effect and paint a few strokes inside the aorta.
- Click Fast Marching effect.
- Set `Maximum volume` to 1% (since volume of the aorta is very small compared to the total volume of the CT image).
- Click `Initialize` to compute segmentation preview.
- Adjust segment volume slider to achieve complete segmentation, but not too high value (to prevent leaking out of the aorta).
- Click `Apply` when segmentation preview is satisfactory to finalize the segmentation.
- Apply `Smoothing` effect, `Median` method to fill in missed voxels and smooth outer surface of the vessel.

## Tips

- If Fast Marching not visible then install SegmentEditorExtraEffects extension and restart the application
- To make paint strokes more visible, you can deactivate Paint effect and left-click-and-drag in the slice view to change background volume window/level.
- To see preview in 3D view: Click the down-arrow button on the right side of `Show 3D` button and disable `Surface smoothing` (this will make updates of 3D visualization very fast). Click `Show 3D` button.
- If a large piece of the aorta is missed then click `Cancel`, use Paint effect to paint inside the area that is missing, then re-initialize Fast Marching effect as described above.

## Workflow

### Step 1
Clear the scene. Download the `CTACardio` sample data.

### Step 2
Create a segmentation with a red "Aorta" segment.

### Step 3
Select the Paint effect. Ask the user to paint a few strokes inside the aorta in the slice views. Wait for the user to finish.

### Step 4
Select the Fast Marching effect. Set Maximum volume to 1%.

### Step 5
Click Initialize to compute the segmentation preview.

### Step 6
Ask the user to adjust the segment volume slider — grow the segmentation until the aorta is complete but not leaking. Wait for the user to finish.

### Step 7
Click Apply to finalize the segmentation.

### Step 8
Apply Smoothing with the Median method. Show the result in 3D.
