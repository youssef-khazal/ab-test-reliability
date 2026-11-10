"""Post-hoc check (deviation 2): which fields of a package change clicks, and what is the noise on
packages that are identical in every recorded field?

    python scripts/check_identical_versions.py [--sample NAME]

Not part of the pre-registered plan: written after the audit described in docs/deviations.md.
For every pair of packages in a test, the fields that differ are noted (headline, image, excerpt, lede,
share text, square). For each group of pairs, the script reports the mean squared z-score of the
difference in click rates (1 = pure binomial noise; every test counts once) and the share of pairs a
5% test calls significant (5% = pure noise), with 95% bootstrap intervals over tests.
Writes results/<sample>/field_effects.json and figures/<sample>/field_effects.png.
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
from abtr.db import figures_dir, open_sample, results_dir, sample_arg  # noqa: E402
from abtr.effects import ANOMALOUS_AA_TESTS  # noqa: E402

Z = norm.ppf(0.975)
FIELDS = {"headline": "h", "image": "i", "excerpt": "e", "lede": "l", "share_text": "s", "square": "q"}


def summary(g, rng) -> dict:
    per_test = g.assign(sig=g.z2 > Z ** 2).groupby("test_id", sort=True)[["z2", "sig", "excess"]].mean()
    n = len(per_test)
    boot = np.array([per_test.values[rng.integers(0, n, n)].mean(axis=0) for _ in range(2000)])
    lo, hi = np.quantile(boot, [0.025, 0.975], axis=0)
    return {"tests": n, "pairs": len(g),
            "mean_z2": round(float(per_test.z2.mean()), 3), "mean_z2_ci95": [round(float(lo[0]), 3), round(float(hi[0]), 3)],
            "share_significant_5pct": round(float(per_test.sig.mean()), 4),
            "share_significant_ci95": [round(float(lo[1]), 4), round(float(hi[1]), 4)],
            # sd of the true log-difference implied by the excess over binomial noise (0 if none)
            "true_difference_sd": round(float(np.sqrt(max(per_test.excess.mean(), 0.0))), 3)}


def main() -> None:
    sample = sample_arg()
    con = open_sample(sample)
    t = con.execute("select * from tests order by test_id").fetchdf()
    kept = set(t[~t.in_flagged_window & (chi2.sf(t.srm_chisq, t.n_packages - 1) >= 0.001)].test_id)
    same = ", ".join(f"coalesce(a.{c}::varchar, '') = coalesce(b.{c}::varchar, '') as {k}"
                     for c, k in (("headline", "h"), ("image_id", "i"), ("excerpt", "e"), ("lede", "l"),
                                  ("share_text", "s"), ("square", "q")))
    x = con.execute(f"""
        with p as (select *, row_number() over (order by test_id, created_at, impressions, clicks, headline) rid
                   from packages where clicks > 0)
        select a.test_id, a.impressions na, a.clicks ca, b.impressions nb, b.clicks cb, {same}
        from p a join p b on a.test_id = b.test_id and a.rid < b.rid
        order by a.rid, b.rid""").fetchdf()
    x = x[x.test_id.isin(kept)].reset_index(drop=True)
    d = np.log(x.ca / x.na) - np.log(x.cb / x.nb)
    v = 1 / x.ca - 1 / x.na + 1 / x.cb - 1 / x.nb
    x["z2"], x["excess"] = d ** 2 / v, d ** 2 - v
    keys = list(FIELDS.values())
    rng = np.random.default_rng(0)
    out = {"sample": sample, "tests_kept": len(kept), "pairs": len(x), "groups": {}}
    identical = x[keys].all(axis=1)
    out["groups"]["identical_in_every_field"] = summary(x[identical & ~x.test_id.isin(ANOMALOUS_AA_TESTS)], rng)
    if (identical & x.test_id.isin(ANOMALOUS_AA_TESTS)).any():
        out["groups"]["identical_in_every_field_with_anomalous_test"] = summary(x[identical], rng)
    for name, k in FIELDS.items():
        only = ~x[k] & x[[c for c in keys if c != k]].all(axis=1)
        if only.sum() >= 20:
            out["groups"][f"only_{name}_differs"] = summary(x[only], rng)
    # the definition used before the audit: same headline, image and excerpt, anything else may differ
    old = x.h & x.i & x.e
    out["groups"]["same_headline_image_excerpt_(first_definition)"] = summary(x[old], rng)
    out["first_definition_pairs_that_differ_in_share_text"] = round(float((~x.s[old]).mean()), 4)
    (results_dir(sample) / "field_effects.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))

    labels = [("identical_in_every_field", "nothing\n(identical)"), ("only_lede_differs", "lede"),
              ("only_excerpt_differs", "excerpt"), ("only_share_text_differs", "share text"),
              ("only_image_differs", "image"), ("only_headline_differs", "headline")]
    rows = [(lab, out["groups"][k]) for k, lab in labels if k in out["groups"]]
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    vals = [100 * g["share_significant_5pct"] for _, g in rows]
    err = [[v - 100 * g["share_significant_ci95"][0] for v, (_, g) in zip(vals, rows)],
           [100 * g["share_significant_ci95"][1] - v for v, (_, g) in zip(vals, rows)]]
    ax.bar([lab for lab, _ in rows], vals, yerr=err, capsize=3,
           color=["#2e86c1"] + ["#5d6d7e"] * (len(rows) - 1))
    ax.axhline(5, color="#c0392b", lw=1.5, ls="--", label="what pure chance gives (5%)")
    ax.set_ylabel("pairs called significant (%)")
    ax.set_xlabel("the only thing that differs between the two versions")
    ax.set_title("Identical versions differ as chance predicts; any visible change does more")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(figures_dir(sample) / "field_effects.png", dpi=150)


if __name__ == "__main__":
    main()
