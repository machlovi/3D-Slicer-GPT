---
name: slicer-diffusion-mri-english
description: Diffusion MRI tutorial for 3D Slicer. Introduction to the basics of diffusion MRI analysis including loading diffusion-weighted images, estimating diffusion models, and generating tractography reconstructions of white matter fibers. By Sonia Pujol, Ph.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/spujol/SlicerDiffusionMRITutorial"
    application-version: Slicer-4.10.2
    language: English
---

# Diffusion MRI Tutorial (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Diffusion MRI Tutorial (English)](https://spujol.github.io/SlicerDiffusionMRITutorial/SlicerDiffusionMRITutorial_SoniaPujol.pdf)
Website: [SlicerDiffusionMRITutorial](https://spujol.github.io/SlicerDiffusionMRITutorial/)
Author: Sonia Pujol, Ph.D.

- **Application version:** Slicer-4.10.2

## Overview

Introduction to the basics of diffusion MRI analysis. This tutorial guides through loading diffusion-weighted images (DWI), estimating a diffusion tensor model, and generating tractography reconstructions of white matter fibers.

## Prerequisites

- The tutorial dataset must be downloaded from the [tutorial website](https://spujol.github.io/SlicerDiffusionMRITutorial/). The PDF contains download links and instructions.
- The **SlicerDMRI** extension should be installed (provides diffusion tensor estimation and tractography modules).

## Workflow

The user can open the PDF tutorial alongside this walkthrough for detailed screenshots: https://spujol.github.io/SlicerDiffusionMRITutorial/SlicerDiffusionMRITutorial_SoniaPujol.pdf

### Step 1
Clear the scene. Ask the user to load the DWI dataset via File > Add Data (or the DICOM module for DICOM data). Wait for the user to finish.

### Step 2
Ask the user to explore the loaded diffusion-weighted images: scroll through slices and switch between gradient directions in the Volumes module. Wait for the user to finish.

### Step 3
Ask the user to open the DWI to DTI Estimation module, set the input DWI volume, create output DTI and Baseline volumes, and click Apply. Wait for the user to finish.

### Step 4
Ask the user to visualize diffusion tensor maps in the Volumes module: Fractional Anisotropy (FA), color-coded FA, and tensor glyphs. Wait for the user to finish.

### Step 5
Ask the user to open the Tractography Seeding module, set the DTI volume, configure seeding parameters (Minimum FA ~0.2), create a new output fiber bundle, and click Apply. Wait for the user to finish.

### Step 6
Ask the user to explore the tractography results in 3D: adjust color mode, toggle tube display, change opacity, and rotate. Wait for the user to finish.

### Step 7
Save the scene.
