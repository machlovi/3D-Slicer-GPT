# RadAssistant DeepAgent — Eval Suite 3: Quick-Ask Workbench (100 queries)

*A third variation on the same idea as `EVAL_SUITE.md` and `EVAL_SUITE2.md`, but written the way a
researcher actually fires off a message mid-task — short, casual, sometimes half a sentence — while the
thing being asked for still needs a real multi-step 3D Slicer workflow underneath (loading, segmentation,
registration, transforms, modeling, volume rendering, measurement, radiomics, RT contouring, markups,
scripting, and 4D data). Each line below is a standalone ask; there's no session structure or fixed
sample dataset — treat every line as its own fresh prompt against whatever's appropriate for it.*

---

## Loading, Importing & DICOM

1. can you pull in that PACS folder I dumped on the desktop and tell me what actually came through
2. got a pile of loose dicoms from three different scanners all mixed together, sort out what's what
3. load the cardiac CT but skip the localizer slices, don't need those cluttering the scene
4. there's a multi-frame ultrasound cine buried in that folder somewhere, just grab that one
5. the scanner exported everything as a single series even though it's really three separate phases — split those out
6. grab the T2 series off that MR study, not the T1, and get it loaded
7. a labmate sent me an NRRD file, bring it in and line it up next to my CT
8. dig through the DICOM database for anything with "phantom" in the study description
9. that import earlier died halfway through, tell me what's actually sitting in the scene now
10. this NIfTI mask a colleague sent isn't showing as a real segmentation, just a plain label map — fix that

## Segmentation & Editing

11. carve out the liver on this abdominal scan, rough pass is fine for now
12. need a clean spleen outline, no holes punched through it
13. there's a cyst on the kidney, just grab that piece and nothing else
14. the vertebra seg has a hole right through the middle of it, patch that
15. smooth this segmentation out, it's got a staircase look right now
16. only want the left ventricle blood pool here, not the myocardium wrapped around it
17. combine my three separate rib pieces into one bone structure
18. a chunk of segmentation is floating out in space where it shouldn't be, get rid of it
19. grow this tumor outline out by a few millimeters, need margin
20. shrink that seg back down, went way too aggressive with the threshold
21. the auto seg skipped a slice in the middle, paint that one in by hand
22. duplicate this segment before I start hacking at it, don't want to wreck the original
23. the editor keeps grabbing bits of the table under the patient, mask that off
24. fill the gaps between slices so the surface doesn't look sliced like swiss cheese
25. need gray matter and white matter as two separate segments on this brain scan
26. this mask has more holes than a slice of bread, patch every one of them
27. split the airway out from the lung parenchyma, they're all lumped in one blob right now
28. erase everything on the outline below the diaphragm, went too far south with the threshold

## Registration & Transforms

29. these two scans are from different visits, get them into the same coordinate space
30. the follow-up MRI is tilted compared to the baseline, straighten that out
31. need to fuse the PET onto the CT, they weren't acquired on the same table
32. this volume loaded mirrored somehow, flip it back the right way
33. nudge this volume over a few mm, it's sitting slightly off from where it should
34. apply the transform matrix sitting in my spreadsheet onto this model
35. bake that transform onto the segmentation so it's permanent, not just a display offset
36. rigid alignment isn't cutting it on these two, anatomy's shifted too much — needs something that can bend
37. whatever transform I just applied made it worse, undo that
38. co-register the ultrasound with the CT so I can look at the same lesion on both
39. line up all five timepoints in this series to the first one so drift doesn't wreck my measurements
40. that landmark-based registration barely moved anything, something's off with my point pairs

## Models, Surfaces & 3D

41. turn this segmentation into an actual 3D model I can spin around and look at
42. the surface looks jagged as heck, decimate it down some
43. export the bone model as something I can feed into a 3D printer slicer app
44. want the vessel tree as a solid model, not just the flat segmentation view
45. merge these two separate models into one single mesh
46. there's a weird spike sticking out of the model, clean that artifact up
47. give me a hollow shell version of the skull for printing, not a solid block
48. this mesh is way too heavy to load smoothly, cut the polygon count down
49. wrap a smoother surface around this blocky segmentation
50. show me just the outer skin, hide everything else underneath in the 3D view
51. the model has inverted normals or something, the lighting looks all wrong on it
52. I need the centerline of this vessel model pulled out as its own curve

## Volume Rendering & Visualization

53. give me an actual 3D look at the whole chest, not just a flat segmentation
54. the volume render looks washed out and flat, punch up the contrast on it
55. want to see through the ribcage to the heart sitting underneath
56. set up a proper angiogram-style render for this CTA
57. slice through the 3D view with a clipping plane so I can see inside the volume
58. make the skin see-through so the skeleton shows through in the render
59. set me up with four viewports — axial, sagittal, coronal, and the 3D all together
60. crop the render down, it's still showing the whole table and gantry in the shot

## Measurements & Quantification

61. how big is that mass, eyeballing it on screen isn't good enough anymore
62. give me long axis and short axis on this lesion
63. need the total tumor burden across every lesion I've marked so far
64. what's the average signal in this region compared to the background tissue
65. get me the surface area on this segment too, not just the volume number
66. how much did this structure actually shrink between the two scans
67. need the angle between these two bone axes for the ortho writeup
68. what's the diameter of this vessel at three different spots along its length
69. pull a histogram of the intensities sitting inside this segment
70. calculate the sphericity on this nodule, it's going into a paper
71. what are the centroid coordinates of this segment, need them for a table
72. want per-slice area through the whole structure, not one lump-sum number
73. give me the min, max, and standard deviation inside this ROI, not just the mean
74. how far apart are these two fiducials I dropped earlier, in millimeters please note not voxels

## Radiomics & Research Workflows

75. pull texture features off this lesion for my radiomics cohort
76. need this run with proper IBSI-compliant settings, not whatever the defaults are
77. batch this radiomics extraction across every case sitting in my study folder
78. run a QA check comparing my manual outline against the automated one
79. get me sensitivity and specificity between these two segmentations
80. want reproducibility stats if I rerun the same extraction a second time
81. check whether this radiomics signature survives resampling to a coarser voxel size
82. dump everything into a spreadsheet I can hand off to my stats collaborator
83. need the exact extractor version and parameters logged somewhere, reviewers always ask

## Radiation Therapy Contouring

84. auto contour the organs at risk for this thoracic plan
85. build me a PTV with the standard margin wrapped around this tumor
86. need an anisotropic expansion here, more margin superior-inferior than side to side
87. pull up the dose volume histogram for the cord and esophagus
88. what's the max dose actually hitting the spinal cord in this plan
89. export these contours as DICOM-RT so I can hand them to the planning system
90. check if the heart is picking up more than a sliver of the beam

## Markups & Annotations

91. drop a handful of landmark points on this scan so I can track them across visits
92. draw a line across the fracture line so I can pull the gap distance
93. put an angle marker on this joint for the ortho measurement
94. need a closed curve traced around this region, not just a rough circle
95. label these three points with actual anatomical names, not point-1 point-2 point-3
96. export my markup points to a file so I can reload them in another session later
97. bring back the fiducials I saved from last week's session

## Scripting & Batch Automation

98. don't want to click through the same five steps forty times, script the whole thing
99. loop through every volume currently loaded and slap the same window level on each one
100. automate loading a whole stack of DICOM studies overnight so I'm not babysitting it
