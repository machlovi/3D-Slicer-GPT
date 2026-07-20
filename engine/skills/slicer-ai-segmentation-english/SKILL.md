---
name: slicer-ai-segmentation-english
description: AI-based Segmentation in 3D Slicer tutorial. Covers AI-based segmentation tasks including prostate, brain glioma, and whole body segmentation. From the 3D Slicer Training Compendium by Sonia Pujol, Ph.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol
    source: "https://training.slicer.org/"
    language: English
---

# AI-based Segmentation in 3D Slicer (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [AI-based Segmentation Tutorial (English)](https://slicerlatinamerica.github.io/public/assets/pdfs/Tutorials/SlicerTutorialAiBasedSegmentationIn3dSlicer-SPujol_en-US.pdf)
Author: Sonia Pujol, Ph.D.

## Overview

This tutorial covers AI-based segmentation tasks in 3D Slicer, including prostate segmentation, brain glioma segmentation, and whole body segmentation using AI extensions such as NVIDIA AIAA, MONAILabel, and TotalSegmentator.

## Workflow

The user can open the PDF tutorial alongside this walkthrough for detailed screenshots: https://slicerlatinamerica.github.io/public/assets/pdfs/Tutorials/SlicerTutorialAiBasedSegmentationIn3dSlicer-SPujol_en-US.pdf

### Step 1
Choose which AI segmentation task to perform:

- **Prostate segmentation** — requires **NVIDIA AIAA** or **MONAILabel**
- **Brain glioma segmentation** — requires **MONAILabel**
- **Whole body segmentation** — requires **TotalSegmentator**

Install the relevant extension and restart Slicer if needed. Wait for the user to finish.

### Step 2
Clear the scene. Load the imaging data to segment. If the user has their own data, load it via File > Add Data or the DICOM module. For a quick demo, download the `CT-MR Brain` sample data.

### Step 3
Run the AI segmentation in the installed extension's module:

- **TotalSegmentator:** Select the input volume, choose the task (e.g., "total" for whole body), and click Apply.
- **MONAILabel:** Connect to a running MONAILabel server, select the model, and click Run.
- **NVIDIA AIAA:** Connect to an AIAA server, select the model, and run.

Wait for the user to finish.

### Step 4
Show the segmentation result in the 3D view. Scroll through the slice views to check segmentation quality.

### Step 5
If refinement is needed, use the Segment Editor to correct the AI result:
- **Paint** / **Erase** — manually add or remove regions
- **Scissors** — cut away large unwanted regions
- **Smoothing** — clean up rough boundaries
- **Islands** — remove small disconnected fragments

Wait for the user to finish.

### Step 6
Save the segmentation results if desired.
