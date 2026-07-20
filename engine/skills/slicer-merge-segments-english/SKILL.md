---
name: slicer-merge-segments-english
description: Merge selected segments into one segment in 3D Slicer using the Logical operators effect. Covers both two-segment and multi-segment merging workflows. Based on the Slicer Segmentation Recipes by Andras Lasso.
metadata:
    skill-author: Ben Zwick, Andras Lasso
    source: "https://lassoan.github.io/SlicerSegmentationRecipes/"
    source-repository: "https://github.com/lassoan/SlicerSegmentationRecipes"
    language: English
---

# Merge Segments

Source: [3D Slicer Segmentation Recipes - Merge Segments](https://lassoan.github.io/SlicerSegmentationRecipes/MergeSegments/)
Author: Andras Lasso

## Overview

- Task: Merge selected segments into one segment.
- Imaging modality: any

## Prerequisites

Have a segmentation with multiple segments.

## Recommended Workflow

### Merge two segments:

Use `segment_boolean_operation` with operation `add`. This copies the content of the modifier segment into the target segment, combining them.

- Select the target segment (the one that will contain the merged result).
- Run `segment_boolean_operation` with the target segment, the modifier segment, and operation `add`.
- The target segment now contains both segments merged together.

### Merge multiple segments:

To merge N segments into one, run sequential `segment_boolean_operation` add operations. Merge each source segment into the target one at a time.

For example, to merge Segment_1, Segment_2, and Segment_3 into Segment_1:
1. `segment_boolean_operation(segmentation, Segment_1, Segment_2, add)` -- merges Segment_2 into Segment_1
2. `segment_boolean_operation(segmentation, Segment_1, Segment_3, add)` -- merges Segment_3 into Segment_1

**Alternative manual method (using masking):** In Segment Editor, select the target segment, make only the segments to merge visible, click Logical operators, set Editable area to "Inside all visible segments", uncheck "Bypass masking", set Operation to "Fill", and click Apply. This merges all visible segments at once but cannot be automated with current tools.

## Workflow

### Step 1
Clear the scene. Download the `MRHead` sample data. Create a segmentation with four segments: red "Segment_1", green "Segment_2", blue "Segment_3", yellow "Segment_4".

### Step 2
Select the Paint effect. Ask the user to paint a few strokes in each of the four segments. Wait for the user to finish.

### Step 3
Hide Segment_4. Select Segment_1 — this will be the merge target.

### Step 4
Select Logical operators. Set Operation to Fill, Editable area to Inside all visible segments, and uncheck Bypass masking. Click Apply.

### Step 5
Delete Segment_2 and Segment_3 (their content is now in Segment_1). Show Segment_4 again.
