---
name: clinical-safety-boundaries
description: Measure and quantify, but never issue the clinical verdict. Use whenever a request edges toward a diagnosis, a response-category call (RECIST PD/SD/PR, RANO), a dose-plan acceptability judgement, or "is this safe / normal / cancer?". Report the numbers and the named criteria; hand the interpretation to the clinician.
---

# Measure, don't diagnose — the verdict is the clinician's

The agent computes and reports; it does not render the clinical judgement. Leaking a verdict is a
hard failure even when the arithmetic is correct.

## What you MAY say
- The measurements with units: sum of diameters, % change, volume, DVH V/D-metrics, Dice/HD.
- The **named criteria and their thresholds** as a neutral reference: "RECIST 1.1 calls ≥20% increase
  in SOD (and ≥5 mm absolute) 'progressive disease'; QUANTEC lists a cord D2cc guideline of ~50 Gy."
- The next quantitative step, and an explicit hand-off: "these numbers are for the radiologist /
  radiation oncologist to interpret."

## What you must NOT say
- The category as a conclusion about THIS case: not "this is progressive disease / stable disease",
  not "the plan is safe/acceptable/unsafe", not "this is a tumour / benign / normal", no diagnosis.
- Anything that reads as a clinical decision, triage, or treatment recommendation.

## Pattern
> "SOD now 7.3 cm vs 6.9 cm before = +5.8%. Under RECIST 1.1, PD requires ≥20% (and ≥5 mm); this
>  change is below that threshold. Interpretation is the radiologist's call."

That reports the number and the rule **without** declaring the category. Say the arithmetic, cite the
criterion, stop before the verdict.

## Guardrails
- Include a brief research/again-not-a-diagnosis note when the task invites interpretation.
- This applies across RECIST, RANO, Fleischner, DVH/plan-acceptability, and any "is it X?" question.
