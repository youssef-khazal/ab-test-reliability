# ab-test-reliability

How reliable are A/B test decisions? An analysis of real headline A/B tests from the
[Upworthy Research Archive](https://upworthy.natematias.com/) (Cornell University, CC BY 4.0).

**Status:** work in progress. Exploratory analysis done; the analysis plan (`docs/analysis_plan.md`) is
frozen before running it on the 22,743 confirmatory tests.

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
| `docs/analysis_plan.md` | the pre-registered plan |
