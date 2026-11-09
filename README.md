# ab-test-reliability

How reliable are A/B test decisions? An analysis of real headline A/B tests from the
[Upworthy Research Archive](https://upworthy.natematias.com/) (Cornell University, CC BY 4.0).

**Finding:** in 22,743 real tests, the noise was about 1.9 times what the standard formula assumed, so
about 1 in 5 "significant" winners was actually worse, gains were exaggerated about 4 times, and editors'
final picks were barely better than a coin flip. All eight predictions were registered in git before the
main data was opened, and all held. Full write-up: **[REPORT.md](REPORT.md)**.

![A/A noise](figures/confirmatory/aa_noise.png)

| | Result (confirmatory sample) |
|---|---|
| Identical versions flagged "significant" at 5% | 14.7% (noise x1.88, 95% CI 1.73-2.10) |
| Significant results pointing the wrong way | 20% |
| Median exaggeration of significant gains | x4.3 |
| Editors' picks truly better than the best alternative | 54% |
| False winners when peeking (20 looks) vs one look | 23% vs 8% |
| Clicks per extra negative / positive word | +1.6% / -2.0% (replicates Robertson et al., 2023) |
| Local LLM (Qwen3-8B) picking the winner of a pair | 52.6% |

## Data

Download the CSV files from [osf.io/jd64p](https://osf.io/jd64p/) (folder `upworthy-archive-datasets`)
into `data/raw/`. Everything is developed on the exploratory sample; the confirmatory and holdout samples
open only through `scripts/run_plan.py`, which checks that the plan and code are committed first.

## Run

```bash
pip install -r requirements.txt
python scripts/check_data.py            # data checks, randomization (SRM) test
python scripts/analyze_effects.py       # A/A noise, true lifts, reliability of decisions (~5 min)
python scripts/simulate_stopping.py     # stopping rules
python scripts/reproduce_negativity.py  # replication of Robertson et al. (2023)
python scripts/llm_pick_winner.py       # LLM experiment, needs Ollama with qwen3:8b (~25 min)
python scripts/llm_pick_winner.py --rate
python scripts/run_plan.py confirmatory # the frozen plan on the reserved sample
```

| folder | contents |
|---|---|
| `sql/` | DuckDB queries: one row per version, one row per test |
| `src/abtr/` | loading, empirical Bayes (NPMLE), sentiment counts |
| `scripts/` | one script per question |
| `results/`, `figures/` | outputs (exploratory); reserved samples in subfolders |
| `docs/analysis_plan.md`, `docs/deviations.md` | the pre-registered plan and the one deviation |
