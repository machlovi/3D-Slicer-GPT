---
name: slicer-dicom-image-visualization-english
description: STC-DICOM-102 DICOM Image Visualization tutorial. Guides through 3D data loading and visualization of DICOM images for Radiology Applications in 3D Slicer. From the 3D Slicer Training Compendium by Sonia Pujol, Ph.D., Kitt Shaffer, M.D., Ph.D., and Ron Kikinis, M.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol, Kitt Shaffer, Ron Kikinis
    source: "https://training.slicer.org/"
    tutorial-id: STC-DICOM-102
    application-version: Slicer-4.10
    language: English
---

# STC-DICOM-102: DICOM Image Visualization (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [DICOM Image Visualization Tutorial (English)](https://www.dropbox.com/s/8pm5mty2c0zwmyk/3DVisualizationDICOM_Slicer4.10_SoniaPujol.pdf?dl=0)
Authors: Sonia Pujol, Ph.D., Kitt Shaffer, M.D., Ph.D., Ron Kikinis, M.D.

- **Audience:** Radiologists and users needing a comprehensive overview of 3D visualization capabilities in Slicer.
- **Modules:** DICOM, Volumes, Volume Rendering, Models
- **Application version:** Slicer-4.10

## Overview

This tutorial guides through 3D data loading and visualization of DICOM images
for Radiology Applications in 3D Slicer. It covers the full workflow from DICOM
import through 2D slice navigation, window/level adjustment, volume rendering,
and 3D model display.

## Workflow

Mention the companion PDF tutorial for detailed screenshots: https://www.dropbox.com/s/8pm5mty2c0zwmyk/3DVisualizationDICOM_Slicer4.10_SoniaPujol.pdf?dl=0

### Step 1
Point out the main application window: the module panel on the left, the 3D viewer at top right, and the three slice viewers (axial, sagittal, coronal) at bottom right. Wait for the user to finish.

### Step 2
Clear the scene. Ask the user to open the DICOM module and import their DICOM data. Wait for the user to finish.

### Step 3
Ask the user to select a series and click Load. Center the view on the loaded data. Wait for the user to finish.

### Step 4
Ask the user to navigate through slices using the scroll wheel and explore all three anatomical planes. Wait for the user to finish.

### Step 5
Ask the user to activate the window/level mouse tool and drag in a slice view. Set a window/level preset appropriate for the data type. Wait for the user to finish.

### Step 6
Ask the user to switch to the Volumes module and explore volume information: dimensions, spacing, origin, and DICOM metadata. Wait for the user to finish.

### Step 7
Enable volume rendering with a preset appropriate for the data type. Center the 3D view. Ask the user to explore the rendering. Wait for the user to finish.

### Step 8
If surface models are available, set model opacity to about 50%. Ask the user to toggle visibility to show/hide models. Wait for the user to finish.

### Step 9
Enable both volume rendering and models. Set model opacity to semi-transparent. Ask the user to rotate and zoom to explore from different angles. Wait for the user to finish.

### Step 10
Save the scene as `visualization.mrb`.
