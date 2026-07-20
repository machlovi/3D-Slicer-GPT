---
name: slicer-programming-tutorial-english
description: STC-DEV-102 Slicer Programming tutorial. Introduction to the Python Console and basic Qt widgets in 3D Slicer. From the 3D Slicer Training Compendium by Sonia Pujol, Ph.D. and Steve Pieper, Ph.D.
metadata:
    skill-author: Ben Zwick, Sonia Pujol, Steve Pieper
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/spujol/SlicerProgrammingTutorial"
    tutorial-id: STC-DEV-102
    application-version: Slicer-5.0
    language: English
---

# STC-DEV-102: Slicer Programming (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Slicer Programming Tutorial (English)](https://github.com/spujol/SlicerProgrammingTutorial/releases/latest/download/Slicer5_ProgrammingTutorial_SPujol-SPieper.pdf)
Website: [SlicerProgrammingTutorial](https://spujol.github.io/SlicerProgrammingTutorial/)
Authors: Sonia Pujol, Ph.D., Steve Pieper, Ph.D.

- **Audience:** Users interested in using 3D Slicer with Python scripting.
- **Application version:** Slicer-5.0

## Overview

Introduction to the Python Console and basic Qt widgets in 3D Slicer. This tutorial covers the Python Interactor and the Qt Widget toolkit.

## Workflow

Suggest the user open the PDF tutorial alongside this skill for detailed screenshots: https://github.com/spujol/SlicerProgrammingTutorial/releases/latest/download/Slicer5_ProgrammingTutorial_SPujol-SPieper.pdf

### Step 1
Launch 3D Slicer and familiarize yourself with the application interface — the module panel on the left, the viewers in the center, and the toolbar at the top. Wait for the user to finish.

### Step 2
Open the Python Interactor by going to View > Python Interactor, or use the keyboard shortcut. The Python console appears at the bottom of the Slicer window. Wait for the user to finish.

### Step 3
Try basic Python commands in the interactor. Use the TAB key for auto-completion to discover available functions — for example, type `slicer.` and press TAB. Wait for the user to finish.

### Step 4
Download the `MRHead` sample data.

### Step 5
Access the MRHead volume node from the Python console and explore its properties:
```python
node = slicer.util.getNode('MRHead')
print(node.GetName())
print(node.GetImageData().GetDimensions())
```
Wait for the user to finish.

### Step 6
Create simple Qt GUI elements from the Python console:
```python
button = qt.QPushButton("Click me")
button.show()
```
Wait for the user to finish.

### Step 7
Follow the PDF tutorial's step-by-step guide for creating a first scripted module using the Extension Wizard. Wait for the user to finish.

### Step 8
Make changes to the module code, then use the Reload button in Developer mode to see changes without restarting Slicer. Wait for the user to finish.

The programming tutorial is now complete. For additional Python script examples, visit the [Script Repository](https://slicer.readthedocs.io/en/latest/developer_guide/script_repository.html).
