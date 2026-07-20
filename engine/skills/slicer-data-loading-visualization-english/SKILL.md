---
name: slicer-data-loading-visualization-english
description: STC-VIS-101 Basics of Data Loading and Visualization in 3D Slicer. Shows how to load and visualize DICOM images and 3D models. From the 3D Slicer Training Compendium by Sonia Pujol, Ph.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-VIS-101
    application-version: Slicer-5.4
    language: English
---

# STC-VIS-101: Basics of Data Loading and Visualization (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Data Loading and Visualization Tutorial (English)](https://spujol.github.io/SlicerVisualizationTutorial/SlicerVisualizationTutorial_SoniaPujol.pdf)
Website: [SlicerVisualizationTutorial](https://spujol.github.io/SlicerVisualizationTutorial/)
Author: Sonia Pujol, Ph.D.

- **Audience:** First-time users who want to discover basic visualization features of 3D Slicer.
- **Modules:** DICOM, Volume Rendering, Models
- **Application version:** Slicer-5.4

## Overview

The Basics of Data Loading and Visualization tutorial shows how to load and visualize DICOM images and 3D models in 3D Slicer.

## Dataset

Download the tutorial dataset: [3D Visualization dataset](https://www.dropbox.com/s/03emcqnlec4t2s5/3DVisualizationDataset.zip?dl=1)

## Workflow

Suggest the user open the PDF tutorial alongside this skill for detailed screenshots.

---

### Part 1: Loading and Exploring Sample Data

#### Step 1
Point out the main 3D Slicer interface: the 3D view (top-right), three slice views (axial, sagittal, coronal), the module panel (left side), and the data probe (bottom-left, shows voxel values under the cursor). Wait for the user to finish.

#### Step 2
Clear the scene. Download the `MRHead` sample data.

#### Step 3
Ask the user to observe the loaded MRI volume across the three slice views — each shows a different anatomical plane. Scroll through slices using the mouse wheel. Wait for the user to finish.

#### Step 4
Ask the user to try adjusting window/level: press W to activate the tool, drag in a slice view, then press V to return to normal navigation. Wait for the user to finish.

#### Step 5
Ask the user to click the maximize button (small square icon in the top-right corner of a slice view) to fill the screen, then click again to restore. Wait for the user to finish.

#### Step 6
Ask the user to hover over the pin icon at the top-left of a slice view to reveal the slice toolbar, then click >> to expand. Wait for the user to finish.

#### Step 7
Ask the user to enable the ruler in the expanded toolbar and try the Rotate to volume plane button. Wait for the user to finish.

---

### Part 2: Layout and Linked Navigation

#### Step 8
Ask the user to click the layout selector in the toolbar and switch to Conventional layout. Wait for the user to finish.

#### Step 9
Ask the user to click the chain-link icon in any slice view toolbar to link all views. Scrolling or zooming in one view now applies to all. Wait for the user to finish.

#### Step 10
Show all three anatomical slice planes in the 3D view.

#### Step 11
Ask the user to practice navigating the 3D view: left-click drag to rotate, right-click drag to zoom, middle-click drag to pan. Wait for the user to finish.

---

### Part 3: Loading the Tutorial Scene

#### Step 12
Clear the scene.

#### Step 13
Ask the user to load the tutorial dataset file `VisualizationTutorial_HeadScene.mrb` by dragging and dropping it into Slicer, or via File > Add Data. Wait for the user to finish.

#### Step 14
Ask the user to open the Data module (Ctrl+D) and explore the loaded nodes — click eye icons to show/hide items, try hiding the "skin" model. Wait for the user to finish.

---

### Part 4: Visualization Techniques

#### Step 15
Ask the user to overlay two volumes in a slice view: expand the compositing controls, select T2 MRI as the foreground, and use the opacity slider to blend. Wait for the user to finish.

#### Step 16
Ask the user to organize data in the Data module: create a "White matter models" folder and drag the white matter model nodes into it. Wait for the user to finish.

#### Step 17
Enable volume rendering on the MRI data with an MR-Default preset.

#### Step 18
Set the skull model opacity to about 30% to make it semi-transparent.

#### Step 19
Show the anatomical slice planes in the 3D view alongside the models.

#### Step 20
Ask the user to explore model clipping: open the Models module, select a brain model, enable Clipping in 3D Display, and experiment with clipping plane directions. Wait for the user to finish.

---

### Part 5: Saving and Reloading

#### Step 21
Ask the user to save the scene: click Save in the toolbar, set the filename to `myNewScene.mrb`, choose a location, and click Save. Wait for the user to finish.

#### Step 22
Ask the user to close the scene and reload it from File > Recent to verify the save worked. Wait for the user to finish.
