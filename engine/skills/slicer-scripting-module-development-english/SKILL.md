---
name: slicer-scripting-module-development-english
description: STC-DEV-101 Slicer Scripting and Module Development tutorial. Introduction to Python scripting, the Python console, MRML scene, and creating scripted modules in 3D Slicer. From the 3D Slicer Training Compendium.
metadata:
    skill-author: Ben Zwick, Andras Lasso, Csaba Pinter, Tamas Ungi, Matthew Holden, Kyle Sunderland
    source: "https://training.slicer.org/"
    source-repository: "https://github.com/Slicer/SlicerProgrammingTutorial"
    tutorial-id: STC-DEV-101
    application-version: Slicer-5.6
    language: English
tools:
    - download_sample_data
    - set_window_level_preset
---

# STC-DEV-101: Slicer Scripting and Module Development (English)

Source: [3D Slicer Training Compendium](https://training.slicer.org/)
PDF: [Slicer Programming Tutorial (English)](https://github.com/Slicer/SlicerProgrammingTutorial/releases/download/Slicer-5.6/SlicerProgrammingTutorial.pdf)
Repository: [SlicerProgrammingTutorial](https://github.com/Slicer/SlicerProgrammingTutorial)
Authors: Andras Lasso, Csaba Pinter, Tamas Ungi, Matthew Holden, Kyle Sunderland

- **Audience:** Developers, users with some Python scripting experience.
- **Application version:** Slicer-5.6

## Overview

This tutorial covers:
- Part 1: Software architecture (module types, MRML scene, data model)
- Part 2: Using the Python console and simple scripted module example
- Part 3: Writing a simple scripted module independently

## Part 1: Software Architecture

### Step 1
Review the application architecture diagram in the PDF (Slide 3): Slicer consists of an application core, MRML scene, built-in modules, and extensions, built on Qt, VTK, ITK, CTK, Python, and numpy. Wait for the user to finish.

### Step 2
Slicer has three module types:
- **C++ loadable:** Full Slicer API, for complex or performance-critical components
- **Scripted loadable:** Python, full Slicer API, simplest way to extend Slicer
- **CLI:** Any language, auto-generated GUI from XML, for computational algorithms

Review Slides 4-6 in the PDF. Wait for the user to finish.

### Step 3
Understand the MRML scene — a shared storage of all data objects. Modules communicate by reading and writing MRML nodes (Data, Display, and Storage node types). Review Slides 7-8. Wait for the user to finish.

### Step 4
Study the scripted module implementation pattern: Module, Widget, and Logic classes. Logic must not depend on Widget, and modules communicate through MRML nodes. This is the longest reading section — review Slides 9-19. Wait for the user to finish.

## Part 2: Python Console and Scripted Module

### Step 5
Download the `CTChest` sample data.

### Step 6
Open the Python console from the View menu (or Ctrl+3). Try pressing TAB to explore auto-completion. Wait for the user to finish.

### Step 7
Access MRML nodes from the Python console:
```python
v = slicer.util.getNode('CTChest')
v = slicer.mrmlScene.GetFirstNodeByName('CTChest')
```
Wait for the user to finish.

### Step 8
Explore the node object: type `v` to see its type, `print(v)` for node content, `help(v)` for the full API. Wait for the user to finish.

### Step 9
Manipulate volume display from the Python console — set window/level:
```python
vd = v.GetDisplayNode()
vd.SetAutoWindowLevel(0)
vd.SetWindowLevel(350, 40)
```

### Step 10
Access voxels using numpy:
```python
va = slicer.util.arrayFromVolume(v)
va[100,200,30]  # get voxel value
```
Try thresholding:
```python
vaOriginal = va.copy()
va[va < 200] = -3000
va[va > 200] = 2000
slicer.util.arrayFromVolumeModified(v)
```
Wait for the user to finish.

### Step 11
Load a model and manipulate it from Python:
```python
c = slicer.util.getNode('ModelName')
cd = c.GetDisplayNode()
cd.SetColor(1, 0, 0)
```
Try replacing model geometry with a sphere:
```python
s = vtk.vtkSphereSource()
s.SetRadius(30)
s.SetCenter(30, 40, 60)
s.Update()
c.SetAndObservePolyData(s.GetOutput())
```
Wait for the user to finish.

### Step 12
Create markup points and observe changes:
```python
f = slicer.util.getNode('F')
f.GetNthControlPointPosition(0)

def printPos(caller=None, event=None):
  pos = f.GetNthControlPointPosition(0)
  print(pos)

obsTag = f.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, printPos)
# Drag a point to see position updates
f.RemoveObserver(obsTag)
```
Wait for the user to finish.

### Step 13
Create an extension and module using the Extension Wizard: name it MyFirstExtension, add the module path to settings, enable Developer mode, and restart Slicer. Follow Slides 36-40. Wait for the user to finish.

### Step 14
Customize the module step by step following Slides 42-48: rename it to "Center of Mass", change the input selector to a point list markup, add a center-of-mass function, and display the result. Wait for the user to finish.

### Step 15
Test the module: navigate to it, add markup points, and press Apply to see the computed center of mass. Wait for the user to finish.

### Step 16
Add an auto-update checkbox following Slides 50-53: implement the observer pattern so the center of mass updates automatically when points are moved. Wait for the user to finish.

## Part 3: Independent Exercise

### Step 17
Independent task: position a sphere-shaped model using two markup points. Use the API documentation and examples from earlier. Wait for the user to finish.

The scripting and module development tutorial is now complete.
