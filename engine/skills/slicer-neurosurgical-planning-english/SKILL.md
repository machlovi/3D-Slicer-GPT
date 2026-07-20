---
name: slicer-neurosurgical-planning-english
description: White Matter Exploration and Neurosurgical Planning tutorial for 3D Slicer. Demonstrates how to generate white matter fiber tracts in the vicinity of a tumor. By Sonia Pujol, Ph.D. and Ron Kikinis, M.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol, Ron Kikinis
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/spujol/NeurosurgicalPlanningTutorial"
    application-version: Slicer-4.10
    language: English
---

# White Matter Exploration / Neurosurgical Planning (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [White Matter Exploration Tutorial (English)](http://spujol.github.io/NeurosurgicalPlanningTutorial/WhiteMatterExplorationTutorial_SoniaPujol-RonKikinis.pdf)
Website: [NeurosurgicalPlanningTutorial](https://spujol.github.io/NeurosurgicalPlanningTutorial/)
Authors: Sonia Pujol, Ph.D., Ron Kikinis, M.D.

- **Application version:** Slicer-4.10

## Overview

This tutorial demonstrates how to generate white matter fiber tracts in the vicinity of a tumor, which is essential for neurosurgical planning. It combines anatomical MRI, diffusion tensor imaging, tumor segmentation, and tractography to visualize the spatial relationship between a tumor and nearby white matter pathways.

## Prerequisites

- The tutorial dataset must be downloaded from the [tutorial website](https://spujol.github.io/NeurosurgicalPlanningTutorial/). The PDF contains download links.
- The **SlicerDMRI** extension should be installed (provides tractography modules).

## Workflow

The user can open the PDF tutorial alongside this walkthrough for detailed screenshots: http://spujol.github.io/NeurosurgicalPlanningTutorial/WhiteMatterExplorationTutorial_SoniaPujol-RonKikinis.pdf

### Step 1
Clear the scene. Ask the user to load the neurosurgical planning dataset via File > Add Data: the anatomical MRI, diffusion tensor volume, and tumor segmentation/label map. Wait for the user to finish.

### Step 2
Center the view. Ask the user to scroll through slices to see the anatomical MRI with the tumor segmentation overlaid. Wait for the user to finish.

### Step 3
Ask the user to open the Tractography Seeding module, set the DTI volume, configure seeding parameters (Minimum FA ~0.2), create an output fiber bundle, and click Apply. Wait for the user to finish.

### Step 4
Ask the user to place an ROI around the tumor using Markups, and position/resize it to encompass the tumor and a margin of surrounding tissue. Wait for the user to finish.

### Step 5
Ask the user to open the Tractography ROI Selection module, set the input fiber bundle and ROI, create a new output bundle, and click Apply. Wait for the user to finish.

### Step 6
Show the tumor segmentation in 3D alongside the filtered fiber tracts. Ask the user to adjust tract color mode, tumor opacity, and rotate to examine the relationship between the tumor and white matter pathways. Wait for the user to finish.

### Step 7
Save the scene.
