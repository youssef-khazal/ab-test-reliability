"""Questions 1-3 on the exploratory sample.

    python scripts/analyze_effects.py

1. Noise check on accidental A/A tests (packages identical in every recorded field): is the binomial noise model right?
2. Distribution of true lifts between two different versions of a test (empirical Bayes, NPMLE).
3. How often a "significant" result points the wrong way or exaggerates, and how big tests must be.
Every result is given under two noise models: binomial (what Upworthy's p-values assumed) and binomial
inflated by the factor measured on the A/A tests. Writes results/effects.json and two figures.
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
from abtr.effects import (ANOMALOUS_AA_TESTS, aa_pairs, all_pairs, npmle, posterior_positive,  # noqa: E402
                          summarize_g, tau_moments, versions)

RNG_SEED = 0
Z = norm.ppf(0.975)


def kept_tests(con):
    t = con.execute("select * from tests").fetchdf()
    srm = chi2.sf(t.srm_chisq, t.n_packages - 1) < 0.001
    return t[~t.in_flagged_window & ~srm]


def main() -> None:
    sample = sample_arg()
    con = open_sample(sample)
    res_dir, fig_dir = results_dir(sample), figures_dir(sample)
    rng = np.random.default_rng(RNG_SEED)
    tests = kept_tests(con)
    out = {"sample": sample, "tests_kept": len(tests)}

    # 1. accidental A/A tests
    aa = aa_pairs(con).sort_values(["test_id", "na", "ca", "nb", "cb"]).reset_index(drop=True)
    aa = aa[aa.test_id.isin(set(tests.test_id))]
    d = np.log(aa.ca / aa.na) - np.log(aa.cb / aa.nb)
    v = 1 / aa.ca - 1 / aa.na + 1 / aa.cb - 1 / aa.nb
    aa = aa.assign(z=d / np.sqrt(v))
    phi_with_anomalous = float(aa.assign(z2=aa.z ** 2).groupby("test_id", sort=True).z2.mean().mean())
    aa = aa[~aa.test_id.isin(ANOMALOUS_AA_TESTS)]
    z = aa.z
    per_test = aa.assign(z2=z ** 2, sig=np.abs(z) > Z).groupby("test_id", sort=True)[["z2", "sig"]].mean()
    phi = float(per_test.z2.mean())            # every test counts once, all its A/A pairs averaged
    boot = [float(per_test.z2.values[rng.integers(0, len(per_test), len(per_test))].mean()) for _ in range(2000)]
    out["aa"] = {"pairs": len(aa), "tests": int(aa.test_id.nunique()),
                 "share_significant_5pct": round(float(np.mean(np.abs(z) > Z)), 4),
                 "share_significant_5pct_tests_weighted": round(float(per_test.sig.mean()), 4),
                 "noise_inflation_phi": round(phi, 3),
                 "noise_inflation_phi_with_anomalous_test": round(phi_with_anomalous, 3),
                 "phi_ci95": [round(float(np.quantile(boot, 0.025)), 3), round(float(np.quantile(boot, 0.975)), 3)]}

    # 2. distinct versions: identical packages of a test are merged; all pairs, each test counts once
    pk = versions(con)
    pk = pk[pk.test_id.isin(set(tests.test_id)) & (pk.c > 0)]
    pk["y"] = np.log(pk.c / pk.n)
    pk["v"] = 1 / pk.c - 1 / pk.n
    pairs = all_pairs(pk)
    out["pairs"] = len(pairs)
    out["tests_with_two_or_more_versions"] = int(pairs.test_id.nunique())
    out["median_noise_se_binomial"] = round(float(np.median(np.sqrt(pairs["var"]))), 4)
    wts = pairs["weight"].values
    fits = {}
    for label, f in (("binomial", 1.0), ("measured", phi)):
        se = np.sqrt(f * pairs["var"].values)
        grid, w = npmle(pairs.d.values, se, wts)
        fits[label] = (grid, w, f)
        s = summarize_g(grid, w)
        s["tau_moments"] = tau_moments(pairs.d.values, f * pairs["var"].values, wts)
        out[f"G_{label}"] = {k: round(v, 4) for k, v in s.items()}

    # 3. decisions: simulate A/B tests with true lifts from G and the real tests' sizes
    n_sim = 200_000
    idx = rng.choice(len(pairs), n_sim, p=wts / wts.sum())
    var_bin = pairs["var"].values[idx]
    out["decisions"] = {}
    for label, (grid, w, f) in fits.items():
        true = rng.choice(grid, n_sim, p=w / w.sum())
        obs = true + rng.normal(0, np.sqrt(f * var_bin))
        sig = np.abs(obs) / np.sqrt(var_bin) > Z           # Upworthy-style test, binomial variance
        wrong = np.sign(obs) != np.sign(true)
        tiny = np.abs(true) < np.log(1.01)
        ratio = np.abs(obs[sig]) / np.maximum(np.abs(true[sig]), 1e-9)
        out["decisions"][label] = {
            "share_significant": round(float(sig.mean()), 4),
            "significant_but_wrong_direction": round(float(wrong[sig].mean()), 4),
            "significant_but_true_lift_below_1pct": round(float(tiny[sig].mean()), 4),
            "median_exaggeration_when_significant": round(float(np.median(ratio)), 3),
            "pick_higher_always_wrong_direction": round(float(wrong.mean()), 4),
        }
        # editors' picks (`winner`: the version used after the test) vs the best other version
    win = con.execute("""
        with r as (select test_id, headline, image_id, excerpt, lede, share_text, square,
                          sum(impressions) n, sum(clicks) c, bool_or(winner) w
                   from packages group by all),
             s as (select *, row_number() over (partition by test_id order by w desc, c::double/n desc) rk from r)
        select a.test_id, a.n na, a.c ca, b.n nb, b.c cb, a.w from s a join s b on a.test_id=b.test_id and a.rk=1 and b.rk=2
        where a.w and a.c>0 and b.c>0""").fetchdf()
    win = win[win.test_id.isin(set(tests.test_id))]
    dw = np.log(win.ca / win.na) - np.log(win.cb / win.nb)
    vw = 1 / win.ca - 1 / win.na + 1 / win.cb - 1 / win.nb
    out["upworthy_winners"] = {"tests": len(win)}
    for label, (grid, w, f) in fits.items():
        p = posterior_positive(dw.values, np.sqrt(f * vw.values), grid, w)
        out["upworthy_winners"][label] = {"mean_prob_truly_better_than_runner_up": round(float(p.mean()), 4),
                                          "share_below_80pct": round(float((p < 0.8).mean()), 4)}

    # test size needed: per-version views for 80% power, two-sided 5%, at the median click rate
    p0 = float(tests.ctr.median())
    out["median_ctr"] = round(p0, 5)
    out["median_views_per_version"] = int(np.median(pk.n))
    sizes = {}
    for lift in (0.02, 0.05, 0.10, 0.20):
        for label, f in (("binomial", 1.0), ("measured", phi)):
            delta = np.log(1 + lift)
            n = (Z + norm.ppf(0.8)) ** 2 * f * 2 / (p0 * delta ** 2)
            sizes[f"{int(lift * 100)}pct_{label}"] = int(round(n, -2))
    out["views_per_version_for_80pct_power"] = sizes

    (res_dir / "effects.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))

    # figures
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.hist(z, bins=np.linspace(-6, 6, 25), density=True, color="#5d6d7e", label="identical versions (A/A pairs)")
    xs = np.linspace(-6, 6, 400)
    ax.plot(xs, norm.pdf(xs), color="#c0392b", lw=2, label="what pure noise should look like")
    ax.set_xlabel("z-score of the difference between two identical versions")
    ax.set_title(f"Identical versions: noise is x{phi:.2f} the standard formula")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "aa_noise.png", dpi=150)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    for label, color in (("binomial", "#5d6d7e"), ("measured", "#c0392b")):
        grid, w, _ = fits[label]
        lift = 100 * (np.exp(grid) - 1)
        ax.plot(lift, np.cumsum(w), color=color, lw=2,
                label="standard (binomial) noise" if label == "binomial" else "noise as measured on identical versions")
    ax.set_xlim(-60, 60)
    ax.set_xlabel("true click-rate lift of one version over another (%)")
    ax.set_ylabel("share of version pairs")
    ax.set_title("How different are two versions really? (estimated, cumulative)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(fig_dir / "true_lifts.png", dpi=150)


if __name__ == "__main__":
    main()
