---
name: slicer-dicom-tutorial-english
description: STC-DICOM-101 DICOM and Slicer tutorial. Provides an introduction to the DICOM standard and shows how to load and visualize DICOM datasets in 3D Slicer. From the 3D Slicer Training Compendium by Sonia Pujol, Ph.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    tutorial-id: STC-DICOM-101
    application-version: Slicer-5.0
    language: English
---

# STC-DICOM-101: DICOM and Slicer (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [DICOM and Slicer Tutorial (English)](https://spujol.github.io/SlicerDICOMTutorial/3DSlicer_DICOMTutorial_SoniaPujol.pdf)
Website: [SlicerDICOMTutorial](https://spujol.github.io/SlicerDICOMTutorial/)
Author: Sonia Pujol, Ph.D.

- **Audience:** First-time users who want to learn about DICOM in Slicer.
- **Modules:** DICOM, Volumes
- **Application version:** Slicer-5.0

## Overview

The DICOM and Slicer tutorial provides an introduction to the DICOM standard and shows how to load and visualize DICOM datasets in 3D Slicer.

## Workflow

Begin by mentioning the companion PDF tutorial for detailed screenshots: https://spujol.github.io/SlicerDICOMTutorial/3DSlicer_DICOMTutorial_SoniaPujol.pdf

### Step 1
Clear the scene. If the user does not have DICOM files, download the `CTChest` sample data to use throughout the tutorial.

### Step 2
Explain the DICOM standard: it defines formats for storing and exchanging medical images along with patient metadata, organized in a Patient > Study > Series hierarchy. Nearly all clinical imaging devices produce DICOM files.

### Step 3
If the user has their own DICOM files, ask them to click Import in the DICOM module and select the folder. If sample data was loaded in Step 1, skip this step. Wait for the user to finish.

### Step 4
Browse the DICOM database panel. Data is organized by Patient > Study > Series — explore the metadata for each series. Wait for the user to finish.

### Step 5
Select a series in the browser and click Load. The volume appears in the slice viewers. Wait for the user to finish.

### Step 6
Ask the user to explore the loaded volume: scroll through slices, click and drag the intersection lines, and adjust window/level by dragging in a slice view. Set a window/level preset appropriate for the data type. Wait for the user to finish.

### Step 7
Switch to the Volumes module to examine volume properties: dimensions, spacing, origin, scalar type, and window/level settings. Wait for the user to finish.

### Step 8
Enable volume rendering with a preset appropriate for the data type. Center the 3D view. Ask the user to explore by rotating, zooming, and panning. Wait for the user to finish.

### Wrap-up

Summarize what was learned: importing and browsing DICOM data, the Patient/Study/Series hierarchy, loading and exploring volumes, examining volume properties, and enabling volume rendering.
