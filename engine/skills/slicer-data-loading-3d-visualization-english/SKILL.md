---
name: slicer-data-loading-3d-visualization-english
description: STC-VIS-102 Data Loading and 3D Visualization tutorial for 3D Slicer. Part 1 covers MRI loading and slice navigation. Part 2 covers 3D visualization of surface models, volume rendering, and model clipping. From the 3D Slicer Training Compendium.
metadata:
    skill-author: Ben Zwick, Andras Lasso, Csaba Pinter
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/Slicer/SlicerDataLoadingAndVisualizationTutorial"
    tutorial-id: STC-VIS-102
    application-version: Slicer-5.6
    language: English
---

# STC-VIS-102: Data Loading and 3D Visualization (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Data Loading and 3D Visualization Tutorial (English)](https://github.com/Slicer/SlicerDataLoadingAndVisualizationTutorial/releases/download/Slicer-5.6/SlicerDataLoadingAndVisualizationTutorial.pdf)
Repository: [SlicerDataLoadingAndVisualizationTutorial](https://github.com/Slicer/SlicerDataLoadingAndVisualizationTutorial)
Authors: Andras Lasso, Csaba Pinter

- **Audience:** First-time users who want to discover basic visualization features of 3D Slicer.
- **Modules:** Welcome to Slicer, Models
- **Application version:** Slicer-5.6

## Dataset

Download the tutorial scene: https://github.com/Slicer/SlicerDataLoadingAndVisualizationTutorial/raw/main/VisualizationTutorial_HeadScene.mrb

## Overview

This tutorial has two parts. Part 1 introduces loading MRI data, adjusting window/level, and navigating slice views. Part 2 covers 3D visualization with surface models, volume rendering, opacity, and clipping. Some steps are performed automatically by Talk2View; others require manual interaction with the Slicer UI.

## Part 1: MRI Data Loading and Slice Navigation

### Step 1
Clear the scene. Download the `MRHead` sample data.

### Step 2
Ask the user to activate the window/level mouse mode and adjust brightness/contrast by dragging in a slice view. Wait for the user to finish.

### Step 3
Switch back to the default interaction mode.

### Step 4
Ask the user to click the maximize button (small square icon) on a slice view, then click again to restore. Wait for the user to finish.

### Step 5
Ask the user to hover over the pin icon at the top-left of a slice view to reveal the toolbar, click >> to expand, and enable the ruler display. Wait for the user to finish.

### Step 6
Ask the user to click the Rotate to volume plane button in the expanded slice toolbar. Wait for the user to finish.

### Step 7
Ask the user to switch to the Conventional layout using the layout selector dropdown. Wait for the user to finish.

### Step 8
Ask the user to click the link icon (chain link) in any slice view toolbar to link all views. Wait for the user to finish.

### Step 9
Show all three anatomical slices in the 3D view.

### Step 10
Ask the user to practice navigating the 3D view: left-click drag to rotate, right-click drag to zoom, middle-click drag to pan. Wait for the user to finish.

### Step 11
Clear the scene.

## Part 2: 3D Visualization of Surface Models

### Step 12
Ask the user to load the tutorial scene `VisualizationTutorial_HeadScene.mrb` by dragging and dropping it into Slicer. Download from: https://github.com/Slicer/SlicerDataLoadingAndVisualizationTutorial/raw/main/VisualizationTutorial_HeadScene.mrb Wait for the user to finish.

### Step 13
Center the 3D view on the loaded data.

### Step 14
Ask the user to open the Data module (Ctrl+D), show/hide nodes with eye icons, and try hiding the "skin" model. Wait for the user to finish.

### Step 15
Ask the user to select T2 MRI as the foreground image in a slice view and adjust the foreground opacity slider to blend between volumes. Wait for the user to finish.

### Step 16
Ask the user to right-click the scene in the Data module and create a "White matter models" folder. Wait for the user to finish.

### Step 17
Ask the user to Shift-click to select white matter model nodes, drag them into the folder, then hide non-brain structures using the folder eye icon. Wait for the user to finish.

### Step 18
Enable volume rendering on the MRHead volume with the MR-Default preset.

### Step 19
Turn off volume rendering. Ask the user to show the Models folder again in the Data module. Wait for the user to finish.

### Step 20
Set the skull model to 30% opacity so internal brain structures are visible.

### Step 21
Show the anatomical slice planes in the 3D view.

### Step 22
Ask the user to explore model clipping: right-click a brain model in the Data module, choose "Edit properties...", select all brain models, enable Clipping in 3D Display, and configure the clipping planes. Wait for the user to finish.

### Step 23
Hide the slice planes. Rotate the 3D view to the Anterior orientation.

### Step 24
Save the scene as `myNewScene.mrb`.

### Step 25
Ask the user to close the scene and reload it from File > Recent to verify the save. Wait for the user to finish.

## Completion

The data loading and 3D visualization tutorial is now complete.
