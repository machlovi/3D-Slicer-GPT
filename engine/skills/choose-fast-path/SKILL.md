---
name: choose-fast-path
description: Pick the cheapest tool that answers the question so a task doesn't blow the time budget. Use whenever a segmentation/measurement could be done either by a quick threshold or by a heavy AI model — "segment the bone", "outline the lung", "grab that bright lesion", "just measure the aorta". Reserve run_total_segmentator / run_monai_auto3dseg for true multi-organ asks, and warn about the wait.
---

# Choose the fast path — don't reach for a heavy model when a threshold answers

A single, well-contrasted structure does **not** need a whole-body AI segmenter. Running
`run_total_segmentator` or `run_monai_auto3dseg` for a one-off structure is what caused a **31-minute
task that timed out** (Q3-044) — the outcome scored 0 not because the answer was wrong but because it
never finished inside the budget.

## The rule
1. Match the ask to the *cheapest* tool that satisfies it. One bright/high-contrast structure →
   `threshold_segmentation`, then clean with `filter_segment_islands` / `smooth_segment`.
2. Reserve the heavy AI segmenters for genuinely **multi-organ / whole-body** requests, or when the
   target has no clean intensity separation (soft-tissue organ boundaries).
3. When a heavy tool *is* the right call, **say it will take a while** before you launch it, so the
   wait is expected rather than a silent stall.

## Fast vs heavy — the decision
| The ask | Fast path (prefer) | Heavy path (only if…) |
|---|---|---|
| Bone on CT | `threshold_segmentation` (~200–3000 HU) | multi-bone atlas / named individual bones |
| Lungs / air | `threshold_segmentation` (very low HU) + islands | lobar or airway breakdown |
| A single bright lesion / contrast vessel | `threshold_segmentation` + `filter_segment_islands` | infiltrative/low-contrast target |
| "Measure the aorta / this structure" | threshold or existing segment → `measure_*` | vessel not separable by intensity |
| "Segment all the organs / OARs for RT" | — | `run_total_segmentator` / `run_monai_auto3dseg` ✅ |

## Guardrails
- Don't invoke `run_total_segmentator` **twice** on the same volume — one run produces all its labels;
  re-running just doubles the wait (this happened in Q3-044).
- If the user explicitly wants the AI model, run it — but set expectations on runtime first.
- This complements `prefer-native-tools`: threshold/measure are native tools; the heavy segmenters are
  native too, just expensive — pick by cost, not by scripting them in `execute_python`.
