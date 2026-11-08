"""Question 4: what does stopping a test early cost? Simulation calibrated on the exploratory sample.

    python scripts/simulate_stopping.py

The archive has only final totals, so stopping rules cannot be replayed on the real tests. Instead,
each simulated test copies a real test (its click rate and its number of viewers per version), draws
a true lift for the new version from the distribution estimated in analyze_effects.py, and lets the
viewers arrive in 20 equal batches. Extra noise is added per batch so that the final noise matches
what the accidental A/A tests showed (results/effects.json, "noise_inflation_phi").

A is the current headline, B the new one; a rule ships B only when it judges B better.
Rules compared:
  ahead      no test: ship B whenever it is ahead at the end
  fixed      one look at the end, z-test p < 0.05 (the textbook test, binomial noise)
  peeking    a look after every batch, stop at the first p < 0.05
  fixed_phi  one look at the end, noise corrected by the measured factor
  msprt      always-valid sequential test (mixture SPRT), looks after every batch, corrected noise
Also run with no true difference at all (A/A world) to measure false alarms.
Writes results/stopping.json and figures/stopping_rules.png.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import chi2, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtr.db import ROOT, figures_dir, open_sample, results_dir, sample_arg  # noqa: E402
from abtr.effects import all_pairs, npmle  # noqa: E402

SEED, N_SIM, LOOKS, ALPHA = 0, 40_000, 20, 0.05
MSPRT_TAU2 = np.log(1.10) ** 2   # mixing variance: lifts of about 10% are expected


def setup(con, phi):
    t = con.execute("select * from tests order by test_id").fetchdf()
    t = t[~t.in_flagged_window & (chi2.sf(t.srm_chisq, t.n_packages - 1) >= 0.001)]
    pk = con.execute("""select test_id, headline, image_id, excerpt, sum(impressions) n, sum(clicks) c
                        from packages group by all order by all""").fetchdf()
    pk = pk[pk.test_id.isin(set(t.test_id)) & (pk.c > 0)]
    per_test = pk.groupby("test_id", sort=True).agg(n=("n", "median"), c=("c", "sum"), N=("n", "sum"))
    per_test["ctr"] = per_test.c / per_test.N
    # true-lift distribution: refit exactly as in analyze_effects.py (all pairs, measured noise)
    pk["y"] = np.log(pk.c / pk.n)
    pk["v"] = 1 / pk.c - 1 / pk.n
    pairs = all_pairs(pk)
    grid, w = npmle(pairs.d.values, np.sqrt(phi * pairs["var"].values), pairs["weight"].values)
    return per_test, grid, w


def simulate(per_test, grid, w, phi, world, rng):
    base = per_test.sample(N_SIM, replace=True, random_state=rng.integers(1 << 31))
    n_arm, p0 = base.n.values, base.ctr.values
    true = np.zeros(N_SIM) if world == "aa" else rng.choice(grid, N_SIM, p=w / w.sum())
    pa, pb = p0, np.minimum(p0 * np.exp(true), 0.5)
    batch = np.maximum((n_arm / LOOKS).astype(int), 1)
    # per-batch multiplicative noise so the final log-rate variance is phi times binomial
    sig2 = LOOKS * (phi - 1) / np.maximum(batch * LOOKS * p0, 1)
    ca = np.zeros(N_SIM); cb = np.zeros(N_SIM); n = np.zeros(N_SIM)
    z_path, v_path, est_path = [], [], []
    for _ in range(LOOKS):
        ea = np.exp(rng.normal(0, np.sqrt(sig2)) - sig2 / 2)
        eb = np.exp(rng.normal(0, np.sqrt(sig2)) - sig2 / 2)
        ca += rng.binomial(batch, np.clip(pa * ea, 0, 1))
        cb += rng.binomial(batch, np.clip(pb * eb, 0, 1))
        n += batch
        est = np.log((cb + 0.5) / n) - np.log((ca + 0.5) / n)
        var = 1 / (ca + 0.5) + 1 / (cb + 0.5) - 2 / n
        z_path.append(est / np.sqrt(var)); v_path.append(var); est_path.append(est)
    z, var, est = np.array(z_path), np.array(v_path), np.array(est_path)
    zc = norm.ppf(1 - ALPHA / 2)
    ship, stop_at = {}, {}
    ship["ahead"] = z[-1] > 0; stop_at["ahead"] = np.full(N_SIM, LOOKS)
    ship["fixed"] = z[-1] > zc; stop_at["fixed"] = np.full(N_SIM, LOOKS)
    hit = z > zc
    first = np.where(hit.any(0), hit.argmax(0) + 1, LOOKS)
    ship["peeking"] = hit.any(0); stop_at["peeking"] = first
    ship["fixed_phi"] = z[-1] / np.sqrt(phi) > zc; stop_at["fixed_phi"] = np.full(N_SIM, LOOKS)
    V = phi * var
    lam = np.sqrt(V / (V + MSPRT_TAU2)) * np.exp(MSPRT_TAU2 * est ** 2 / (2 * V * (V + MSPRT_TAU2)))
    hit = (lam >= 1 / ALPHA) & (est > 0)
    ship["msprt"] = hit.any(0); stop_at["msprt"] = np.where(hit.any(0), hit.argmax(0) + 1, LOOKS)
    out = {}
    for r in ship:
        s = ship[r]
        out[r] = {"share_shipped": round(float(s.mean()), 4),
                  "shipped_but_worse": round(float((true[s] < 0).mean()), 4) if s.any() else None,
                  "avg_true_lift_per_test_pct": round(float(100 * np.where(s, np.exp(true) - 1, 0).mean()), 3),
                  "avg_share_of_viewers_used": round(float((stop_at[r] / LOOKS).mean()), 3)}
    return out


def main() -> None:
    sample = sample_arg()
    con = open_sample(sample)
    res_dir, fig_dir = results_dir(sample), figures_dir(sample)
    phi = json.loads((res_dir / "effects.json").read_text())["aa"]["noise_inflation_phi"]
    per_test, grid, w = setup(con, phi)
    rng = np.random.default_rng(SEED)
    res = {"phi": phi, "simulated_tests": N_SIM, "looks": LOOKS,
           "aa_world": simulate(per_test, grid, w, phi, "aa", rng),
           "realistic_world": simulate(per_test, grid, w, phi, "real", rng)}
    (res_dir / "stopping.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))

    rules = ["ahead", "fixed", "peeking", "fixed_phi", "msprt"]
    names = ["no test:\nship if\nahead", "textbook\ntest,\none look", "peeking,\n20 looks", "corrected\nnoise,\none look", "sequential\ntest,\n20 looks"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fa = [100 * res["aa_world"][r]["share_shipped"] for r in rules]
    axes[0].bar(names, fa, color=["#aab7b8", "#5d6d7e", "#c0392b", "#2e86c1", "#2e86c1"])
    axes[0].axhline(2.5, color="black", lw=1, ls="--")
    axes[0].set_title("No real difference: share of tests\nthat ship a 'winner' anyway (%)")
    wr = [100 * res["realistic_world"][r]["shipped_but_worse"] for r in rules]
    axes[1].bar(names, wr, color=["#aab7b8", "#5d6d7e", "#c0392b", "#2e86c1", "#2e86c1"])
    axes[1].set_title("Realistic differences: shipped 'winners'\nthat are actually worse (%)")
    lift = [res["realistic_world"][r]["avg_true_lift_per_test_pct"] for r in rules]
    axes[2].bar(names, lift, color=["#aab7b8", "#5d6d7e", "#c0392b", "#2e86c1", "#2e86c1"])
    axes[2].set_title("Realistic differences: average real\nclick gain per test run (%)")
    for ax in axes:
        ax.tick_params(axis="x", labelsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "stopping_rules.png", dpi=150)


if __name__ == "__main__":
    main()
