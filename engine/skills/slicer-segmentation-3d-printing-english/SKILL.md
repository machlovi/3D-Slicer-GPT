---
name: slicer-segmentation-3d-printing-english
description: STC-SEG-102 Segmentation for 3D Printing tutorial. Create a 3D-printable surgical skill training phantom from a CT image using the Segment Editor module. From the 3D Slicer Training Compendium by Csaba Pinter and Attila Nagy.
metadata:
    skill-author: Ben Zwick, Csaba Pinter, Attila Nagy
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/Slicer/SlicerSegmentationFor3DPrintingTutorial"
    tutorial-id: STC-SEG-102
    application-version: Slicer-5.6
    language: English
---

# STC-SEG-102: Segmentation for 3D Printing (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Segmentation for 3D Printing (English)](https://github.com/Slicer/SlicerSegmentationFor3DPrintingTutorial/releases/download/Slicer-5.6/SegmentationFor3DPrinting.pdf)
Repository: [SlicerSegmentationFor3DPrintingTutorial](https://github.com/Slicer/SlicerSegmentationFor3DPrintingTutorial)
Authors: Csaba Pinter (EBATINCA, S.L., Spain), Attila Nagy (University of Szeged)

- **Audience:** Users interested in creating 3D-printed models from 3D images.
- **Application version:** Slicer-5.6

## Material

- Software: 3D Slicer stable release (at least 5.6.1) from http://download.slicer.org/
- Tutorial dataset: Phantom base STL model from https://raw.githubusercontent.com/Slicer/SlicerSegmentationFor3DPrintingTutorial/main/BasePiece.stl

## Overview

1. Load CT image
2. Segment vertebrae to be 3D printed
3. Add phantom base to segmentation
4. Merge and finalize phantom
5. Save phantom segment to STL file for 3D printing

## Part 1: Load CT image

### Step 1/1
Clear the scene. Download the `CTChest` sample data.

### Step 1/2
Set the window/level to a CT bone preset.

### Step 1/3
Center the slice views on the data.

## Part 2: Segment vertebrae

### Step 2/1
Create a segmentation with a white "Bone" segment.

### Step 2/2
Apply a Threshold of 100 HU (lower) to segment all bone.

### Step 2/3
Show the bone segmentation in the 3D view.

### Step 2/4
Select the Islands effect with Keep selected island. Ask the user to click directly on the spine in the 3D or slice view to keep only that connected bone region. Wait for the user to finish.

### Step 2/5
Select the Scissors effect. Ask the user to draw a closed shape around the vertebrae to keep on the coronal view — everything outside is removed. Wait for the user to finish.

### Step 2/6
Ask the user to rotate the 3D view and use Scissors to remove remaining unwanted parts (e.g., ribs on the anterior side). Wait for the user to finish.

### Step 2/7
Deactivate the Segment Editor and center the view.

### Step 2/8
Ask the user to confirm the vertebrae selection looks correct. Wait for the user to finish.

### Step 2/9
Download the phantom base piece STL from: https://raw.githubusercontent.com/Slicer/SlicerSegmentationFor3DPrintingTutorial/main/BasePiece.stl

### Step 2/10
Set the base piece opacity to 0.5 (semi-transparent) and apply a 180-degree rotation (it loads upside-down relative to the spine).

## Part 3: Add phantom base

### Step 3/1
Ask the user to adjust the position of the base piece using the Transforms module so it sits correctly around the vertebrae. Wait for the user to finish.

### Step 3/2
Optionally, ask the user to use Scissors to trim any vertebrae sticking out of the base piece. Wait for the user to finish.

### Step 3/3
Ask the user to import the base piece into the segmentation: in the Data module, right-click BasePiece, convert to segmentation, then drag the BasePiece segment into the main Segmentation node. Wait for the user to finish.

### Step 3/4
Merge the BasePiece segment into the Bone segment using a boolean add operation. Delete the now-empty BasePiece segment.

### Step 3/5
Optionally, ask the user to use Scissors to cut a hole through the phantom for practicing surgical skills. Wait for the user to finish.

## Part 4: Finalize phantom

### Step 4/1
Show the merged result in 3D and center the view.

### Step 4/2
Export the Bone segment as a model.

### Step 4/3
Ask the user where to save the STL file. Wait for the user to finish.

### Step 4/4
Save the model as an STL file for 3D printing.

## Part 5: Summary

### Step 5/1
The phantom STL file is ready for slicing and 3D printing.

### Step 5/2
Summarize what was done: segmented vertebrae from CT, combined with a phantom base, and exported to STL for 3D printing.
