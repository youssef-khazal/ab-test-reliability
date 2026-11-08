# Analysis plan (pre-registration)

**Status:** frozen before the confirmatory and holdout samples were opened. The commit that adds this
file is the registration; `scripts/run_plan.py` refuses to run on those samples unless this file and all
analysis code are committed with no changes. Written 8 November 2026.

## 1. Data

- **Development:** exploratory sample only (4,873 tests). Every number in section 4 comes from it.
- **Confirmatory:** `upworthy-archive-confirmatory-packages-03.12.2020.csv` (22,743 tests), opened once
  by `python scripts/run_plan.py confirmatory`.
- **Holdout:** `upworthy-archive-holdout-packages-03.12.2020.csv`, opened once afterwards by
  `python scripts/run_plan.py holdout`, as an independent check.
- **Exclusions, fixed in advance:** packages with 0 impressions; tests started between 25 June 2013 and
  10 January 2014 (randomization problem reported by the archive authors); tests with a sample ratio
  mismatch (chi-square test of equal impressions, p < 0.001). Analyses that need clicks drop versions
  with 0 clicks.
- **Version:** a version is a distinct (headline, image, excerpt) within a test, the elements a viewer
  saw before clicking (archive paper, Matias et al. 2021).

## 2. Questions and predictions

Each prediction is checked with the code as committed; nothing is tuned after the data is opened.

| # | Question | Measure (script) | Prediction from the exploratory sample |
|---|---|---|---|
| H0 | Is the randomization problem visible? | Share of tests with SRM, inside vs outside the flagged period (`check_data.py`) | Much higher inside (exploratory: 70% vs 0.5%) |
| H1 | Is the noise larger than binomial? | Noise factor phi on accidental A/A pairs, each test weighted once, 95% bootstrap CI (`analyze_effects.py`) | phi > 1: CI lower bound above 1 (exploratory: 1.80, CI 1.63 to 1.99); share of A/A pairs significant at 5% above 5% |
| H2 | How big are true differences between versions? | NPMLE of the distribution of true log-lifts, all pairs weighted 1/(k(k-1)), under binomial and measured noise | Median absolute true lift below 10% under measured noise (exploratory: 7%) |
| H3 | How reliable are "significant" results? | Simulation on real test sizes: share of significant results in the wrong direction; median exaggeration | Under measured noise: wrong direction above 10%, exaggeration above 2x (exploratory: 19%, 3.8x) |
| H4 | How reliable were the editors' picks? | Mean posterior probability that the `winner` version truly beats the best other version | Below 70% (exploratory: 55% measured noise, 62% binomial) |
| H5 | What does stopping early cost? | 40,000 simulated tests, 20 looks, rules as in `simulate_stopping.py` | Peeking ships a false winner at least twice as often as one look; corrected noise brings one look close to 2.5% |
| H6 | Does negativity raise clicks (replication)? | Within-test WLS, test fixed effects, clustered SE, VADER lexicon (`reproduce_negativity.py`) | Negative-word share beta > 0 and positive-word share beta < 0 (one-sided 5%) |
| H7 | Can a local LLM pick the winner? | Qwen3-8B on clear pairs (abs z > 2.58 with measured noise), both orders; and rating each headline alone (`llm_pick_winner.py`) | Pairwise accuracy within 45-55% (position bias); rating mode, pairs without ties: above 50% |

## 3. Fixed settings

Random seed 0 everywhere; SRM threshold p < 0.001; NPMLE grid of 201 points on [-1, 1] (log-lift),
EM to tolerance 1e-6 or 1,500 iterations; 2,000 bootstrap resamples of tests; stopping simulation with
40,000 tests, 20 equal batches, one-sided decisions at 5%, mixture SPRT with mixing variance
log(1.10)^2; LLM `qwen3:8b` through Ollama, temperature 0, no reasoning, prompts as in the script.

## 4. Exploratory results (for reference, not evidence)

`results/data_checks.json`, `effects.json`, `stopping.json`, `negativity.json`, `llm_scores.json`,
`llm_rate_scores.json`. Main values: phi 1.80 (CI 1.63 to 1.99); 13% of A/A pairs significant; median
true lift 7% (measured) vs 15% (binomial); significant but wrong direction 19% vs 3%; editors' picks
55%; peeking 22% false winners vs 7.7% one look and 2.7% corrected; negativity +2.27% clicks per
negative word, -1.5% per positive word; LLM pairwise 52% (answers "A" 94% of the time), rating mode
66% on the 150 pairs without ties.

## 5. Deviations

Any change to code or exclusions after the reserved data is opened is reported in a "Deviations"
section of the report, with the reason and the results both before and after the change.
