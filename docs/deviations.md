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

## 2. Definition of "identical versions" (audit of 10 November 2026)

- **What happened:** after the plan had been run on both reserved samples and the first report written
  (commits `2918541`, `6fd0e37`, `5f2c7fd`), the whole project was audited before publication. The plan
  measured the noise on "accidental A/A pairs": packages of the same test with the same headline, image
  and excerpt, which it treated as identical for the viewer, following the archive's documentation
  ("share text was not shown in tests"). The audit found that **95% of these pairs differ in their share
  text** (they come from share-text tests run in 2014-2015), and that share text changes clicks:
  pairs that differ only in share text are called significant 14.6% of the time, against 5.7% for pairs
  identical in every recorded field (`results/confirmatory/field_effects.json`). The plan's noise
  factor therefore measured real differences between share texts, not noise.
- **Changes** (commit `2c5657e` for the code, and the commit that adds this section):
  1. *Identical versions* are now packages equal in all six recorded fields: headline, image, excerpt,
     lede, share text and square (`src/abtr/effects.py`). The same six fields define a *version* everywhere
     (before: headline, image and excerpt, so packages with different share texts were merged).
  2. One test (`5535537b646339001c260000`, confirmatory sample) has two identical packages with 29 and
     350 clicks on about 2,000 views each. No noise model produces a 12-fold gap; it is left out of the
     noise estimate, and the estimate with it is reported next to it.
  3. LLM experiment: the two headlines of a pair must now come from versions identical in every other
     field. The "clear winner" threshold is written as a constant, |z| > 3.54 with the binomial formula:
     this is the threshold that was in force when the answers were collected (2.58 x the square root of
     the first noise factor). The stored answers now record the pair they belong to; the few pairs that
     changed were asked again.
  4. `simulate_stopping.py` no longer fails if the noise factor is below 1 (no effect on results).
  5. New post-hoc script `scripts/check_identical_versions.py` (noise and effect of each field).
- **Effect on results** (confirmatory sample; holdout in brackets):

| Result | As registered (first definition) | Corrected |
|---|---|---|
| Identical pairs / tests | 16,350 / 1,905 | 495 / 161 [89 / 32] |
| Noise factor (H1) | 1.88, CI 1.73-2.10 [1.74] | 1.14, CI 0.96-1.34 [1.06, CI 0.73-1.41]; 2.21 with the anomalous test |
| Identical pairs significant at 5% (each test counted once) | 14.0% | 5.7% [1.4%] |
| Median true difference, measured noise (H2) | 6% [7%] | 13% [13%] |
| Significant results in the wrong direction (H3) | 20% [17%] | 5.7% [4.5%] |
| Median exaggeration of significant gains (H3) | x4.3 [x2.8] | x1.5 [x1.4] |
| Editors' picks truly better (H4) | 54% [56%] | 59% [61%] |
| False winners, one look vs peeking (H5) | 8.3% vs 23% [7.4% vs 21%] | 2.9% vs 10.6% [2.5% vs 9.1%] |
| Negativity regression (H6) | unchanged | unchanged |
| LLM pairs (H7) | 2,152 [508] | 2,044 [432] |

- **Effect on the predictions:** H1, H2 and H3 held with the first definition and **do not hold** with the
  corrected one. H0, H4, H5, H6 and H7 hold with both. The first definition gave the same wrong answer on
  all three samples, because all three contain the same share-text tests: an independent sample protects
  against chance findings, not against a measure that does not measure what it should.
- **The first results** remain in the git history at the commits above.

