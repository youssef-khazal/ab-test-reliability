# Deviations from the analysis plan

Changes made after the reserved samples were opened, as required by section 5 of `docs/analysis_plan.md`.

## 1. Versions with no headline text (negativity analysis)

- **What happened:** the frozen plan crashed on the holdout sample at the last step
  (`reproduce_negativity.py`): one version in the holdout sample has no headline text
  (test `51ae9ebe521f031c6c000c65`, 2,846 views, 15 clicks), and the word counter expected text.
- **Change:** `reproduce_negativity.py` skips versions with no headline text.
- **Effect on results:** none on the exploratory and confirmatory samples (they contain no such version;
  their results are unchanged). On the holdout sample there is no "before" result, since the step crashed.
  The other holdout steps (data checks, effects, stopping, LLM) ran with the frozen code before the
  crash point and do not use this script. The holdout plan is re-run in full with the fixed code.
