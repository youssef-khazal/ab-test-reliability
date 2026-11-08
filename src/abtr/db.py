"""Load one sample of the Upworthy archive into DuckDB with the project's SQL files.

Analysis is developed on the exploratory sample only. The confirmatory and holdout samples are
opened only by the frozen analysis plan (docs/analysis_plan.md), hence the explicit flag below.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
SAMPLES = {
    "exploratory": "upworthy-archive-exploratory-packages-03.12.2020.csv",
    "confirmatory": "upworthy-archive-confirmatory-packages-03.12.2020.csv",
    "holdout": "upworthy-archive-holdout-packages-03.12.2020.csv",
}


def connect(sample: str = "exploratory", allow_reserved: bool = False) -> duckdb.DuckDBPyConnection:
    """In-memory database with the tables `packages` and `tests` for one sample."""
    if sample != "exploratory" and not allow_reserved:
        raise PermissionError(f"the {sample} sample is reserved for the frozen analysis plan "
                              "(pass allow_reserved=True only from scripts/run_plan.py)")
    csv = RAW / SAMPLES[sample]
    if not csv.exists():
        raise FileNotFoundError(f"{csv} is missing: download it from https://osf.io/jd64p/ (see README)")
    con = duckdb.connect()
    for f in sorted((ROOT / "sql").glob("*.sql")):
        con.execute(f.read_text(encoding="utf-8").replace("{csv}", csv.as_posix()))
    return con


def sample_arg() -> str:
    """The sample to analyse, from `--sample NAME` on the command line (default: exploratory).
    The argument is removed from sys.argv so scripts can parse the rest as usual."""
    import sys
    if "--sample" in sys.argv:
        i = sys.argv.index("--sample")
        name = sys.argv[i + 1]
        del sys.argv[i:i + 2]
        if name not in SAMPLES:
            raise SystemExit(f"--sample must be one of {sorted(SAMPLES)}")
        return name
    return "exploratory"


def open_sample(sample: str) -> duckdb.DuckDBPyConnection:
    """connect() for scripts: the reserved samples open only through scripts/run_plan.py,
    which sets ABTR_PLAN=frozen after checking the plan is committed."""
    import os
    return connect(sample, allow_reserved=os.environ.get("ABTR_PLAN") == "frozen")


def results_dir(sample: str) -> Path:
    d = ROOT / "results" if sample == "exploratory" else ROOT / "results" / sample
    d.mkdir(parents=True, exist_ok=True)
    return d


def figures_dir(sample: str) -> Path:
    d = ROOT / "figures" if sample == "exploratory" else ROOT / "figures" / sample
    d.mkdir(parents=True, exist_ok=True)
    return d
