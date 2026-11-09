"""Export what the confirmatory tests say about true differences between versions, for the calculator.

    python scripts/export_prior.py     (after scripts/run_plan.py confirmatory)

Refits, exactly as analyze_effects.py does on the confirmatory sample, the distribution of true
log-lifts between two versions (NPMLE on a 201-point grid), under the measured noise and under binomial
noise, and writes demo/prior.json: grid, weights, the noise factor phi and a few reference values.
This is a product step after the frozen analysis, not part of the pre-registered plan.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtr.db import ROOT, connect  # noqa: E402
from abtr.effects import all_pairs, npmle  # noqa: E402


def main() -> None:
    con = connect("confirmatory", allow_reserved=True)
    eff = json.loads((ROOT / "results" / "confirmatory" / "effects.json").read_text())
    phi = eff["aa"]["noise_inflation_phi"]
    t = con.execute("select * from tests order by test_id").fetchdf()
    kept = set(t[~t.in_flagged_window & (chi2.sf(t.srm_chisq, t.n_packages - 1) >= 0.001)].test_id)
    pk = con.execute("""select test_id, headline, image_id, excerpt, sum(impressions) n, sum(clicks) c
                        from packages group by all order by all""").fetchdf()
    pk = pk[pk.test_id.isin(kept) & (pk.c > 0)]
    pk["y"] = np.log(pk.c / pk.n)
    pk["v"] = 1 / pk.c - 1 / pk.n
    pairs = all_pairs(pk)
    out = {"source": "Upworthy Research Archive, confirmatory sample (17,744 tests after exclusions)",
           "phi": phi, "phi_ci95": eff["aa"]["phi_ci95"], "median_ctr": eff["median_ctr"],
           "median_views_per_version": eff["median_views_per_version"]}
    for label, f in (("measured", phi), ("binomial", 1.0)):
        grid, w = npmle(pairs.d.values, np.sqrt(f * pairs["var"].values), pairs["weight"].values)
        out["grid"] = [round(float(g), 4) for g in grid]
        out[f"weights_{label}"] = [float(f"{x:.6g}") for x in w]
    d = ROOT / "demo"
    d.mkdir(exist_ok=True)
    (d / "prior.json").write_text(json.dumps(out), encoding="utf-8")
    print("wrote demo/prior.json")


if __name__ == "__main__":
    main()
