"""Step 1: data checks on the exploratory sample, including the sample ratio mismatch test (question 0).

    python scripts/check_data.py

Writes results/data_checks.json, results/srm_by_month.csv and figures/srm_by_month.png.
A test has a sample ratio mismatch (SRM) when its packages were shown to clearly unequal numbers of
people, although each visitor should have had the same chance of seeing each package: a sign that
randomization failed. Threshold p < 0.001, the usual one for SRM alarms.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtr.db import ROOT, figures_dir, open_sample, results_dir, sample_arg  # noqa: E402

SRM_ALPHA = 0.001


def main() -> None:
    sample = sample_arg()
    con = open_sample(sample)
    res_dir, fig_dir = results_dir(sample), figures_dir(sample)
    tests = con.execute("select * from tests").fetchdf()
    tests["srm_p"] = chi2.sf(tests.srm_chisq, tests.n_packages - 1)
    tests["srm"] = tests.srm_p < SRM_ALPHA
    tests["month"] = tests.started_at.dt.to_period("M").astype(str)

    pk = con.execute("""select count(*) n, sum(impressions) imp, sum(clicks) clk,
                        min(created_at) first, max(created_at) last from packages""").fetchone()
    checks = {
        "sample": sample,
        "packages": pk[0], "tests": len(tests), "impressions": int(pk[1]), "clicks": int(pk[2]),
        "first_package": str(pk[3]), "last_package": str(pk[4]),
        "packages_per_test": tests.n_packages.value_counts().sort_index().to_dict(),
        "median_impressions_per_test": float(tests.impressions.median()),
        "median_ctr": float(tests.ctr.median()),
        "tests_with_a_declared_winner": int((tests.n_winners > 0).sum()),
        "tests_with_several_winners": int((tests.n_winners > 1).sum()),
        "srm_alpha": SRM_ALPHA,
        "srm_rate_flagged_window": round(float(tests[tests.in_flagged_window].srm.mean()), 4),
        "srm_rate_outside_window": round(float(tests[~tests.in_flagged_window].srm.mean()), 4),
        "tests_in_flagged_window": int(tests.in_flagged_window.sum()),
        "tests_kept": int((~tests.in_flagged_window & ~tests.srm).sum()),
    }
    out = res_dir
    (out / "data_checks.json").write_text(json.dumps(checks, indent=1, default=str), encoding="utf-8")

    by_month = tests.groupby("month").agg(tests=("srm", "size"), srm_rate=("srm", "mean")).reset_index()
    by_month.to_csv(out / "srm_by_month.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 3.6))
    colors = ["#c0392b" if m >= "2013-06" and m <= "2014-01" else "#5d6d7e" for m in by_month.month]
    ax.bar(by_month.month, 100 * by_month.srm_rate, color=colors)
    ax.set_ylabel("tests with unequal split (%)")
    ax.set_title("Randomization check: share of tests with a sample ratio mismatch (p < 0.001), by month")
    ax.tick_params(axis="x", rotation=90, labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "srm_by_month.png", dpi=150)
    print(json.dumps(checks, indent=1, default=str))


if __name__ == "__main__":
    main()
