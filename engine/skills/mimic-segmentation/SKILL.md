---
name: mimic-segmentation
description: RECORD, LOG, or REPLAY manual clinician/user segmentation cleanup actions (paint, erase, clicks, brush size changes). Use when the user wants to train the chatbot to learn their manual edits and mimic/replicate them on new images.
---

# Mimic Segmentation & Learning Mode Playbook

Goal: Record manual cleanup edits performed by a user in 3D Slicer, and replicate them on a new patient volume, using coordinate registration mapping if needed.

## 1. Learning Phase (Recording)

When the user asks to start a learning session or record cleanup actions:
1. Advise the user that you are entering **Learning Mode** and will log their paint/erase interactions.
2. Call `start_segmentation_recording` with a suitable filename (e.g. `slicer_cleanup_log.json`).
3. Confirm to the user: *"Recording started. Please perform your manual paint/erase edits on the segmentation. Tell me when you are finished."*
4. Stop and wait for the user. Do NOT call any other tools until the user responds that they are done.
5. Once the user says they are finished, call `stop_segmentation_recording` to finalize and save the log file.
6. Summarize the session to the user: *"Recorded N actions. Saved log to disk."*

## 2. Replicate / Mimic Phase (Replaying)

When the user asks to apply the learned edits to a new volume or segment:
1. Identify the recorded trajectory JSON file path.
2. Identify the target segmentation node to modify.
3. Determine if registration is needed:
   - If the new target volume has different coordinate spacing/alignment than the recorded source volume, you **MUST** provide the `source_volume` (fixed) and `target_volume` (moving) parameters.
   - If it is the same patient volume (or identical coordinate systems), you can omit the volume parameters.
4. Call `mimic_segmentation_cleanup` with the appropriate parameters.
5. Verify the results by calling `get_scene_overview` or `list_segments` and show the segmentation in 3D using `show_segmentation_3d`.
