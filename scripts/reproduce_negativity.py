"""Question 5, part 1: reproduce Robertson et al. (2023), "Negativity drives online news consumption".

    python scripts/reproduce_negativity.py

They found, on the confirmatory sample with LIWC dictionaries, that each additional negative word in a
~15-word headline raises the click rate by about 2.3%, and each positive word lowers it by about 1.0%
(standardized: +0.015 and -0.008 in log-odds). We re-estimate this on the exploratory sample with an
open dictionary, as a check that our pipeline finds a known effect.

Model: within-test regression (test fixed effects, so only versions of the same article are compared)
of the log-odds of a click on the share of negative words, the share of positive words and the word
count, all standardized, weighted by clicks x (1 - click rate) (the inverse variance of a log-odds),
with standard errors clustered by test. Same exclusions as elsewhere (flagged period, SRM).
Writes results/negativity.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtr.db import ROOT, figures_dir, open_sample, results_dir, sample_arg  # noqa: E402
from abtr.sentiment import count, load_lexicon  # noqa: E402


def main() -> None:
    sample = sample_arg()
    con = open_sample(sample)
    res_dir, fig_dir = results_dir(sample), figures_dir(sample)
    t = con.execute("select * from tests order by test_id").fetchdf()
    kept = set(t[~t.in_flagged_window & (chi2.sf(t.srm_chisq, t.n_packages - 1) >= 0.001)].test_id)
    df = con.execute("""select test_id, headline, sum(impressions) n, sum(clicks) c
                        from packages group by all order by all""").fetchdf()
    df = df[df.test_id.isin(kept) & (df.c > 0)].copy()
    lex = load_lexicon()
    counts = np.array([count(h, lex) for h in df.headline])
    df["words"], df["pos"], df["neg"] = counts[:, 0], counts[:, 1], counts[:, 2]
    df = df[df.words > 0]
    df["pos_share"], df["neg_share"] = df.pos / df.words, df.neg / df.words
    # keep tests with at least two different headlines (others carry no headline contrast)
    df = df[df.groupby("test_id").headline.transform("nunique") >= 2]
    p = df.c / df.n
    df["y"] = np.log(p / (1 - p))
    df["w"] = df.c * (1 - p)
    xs = ["neg_share", "pos_share", "words"]
    sd = {x: float(df[x].std()) for x in xs}
    for x in xs:
        df[x + "_z"] = (df[x] - df[x].mean()) / sd[x]
    cols = ["y"] + [x + "_z" for x in xs]
    wmean = df.groupby("test_id")[cols].transform(lambda s: np.average(s, weights=df.loc[s.index, "w"]))
    dm = df[cols] - wmean
    fit = sm.WLS(dm["y"], dm[[x + "_z" for x in xs]], weights=df["w"]).fit(
        cov_type="cluster", cov_kwds={"groups": df["test_id"].astype("category").cat.codes})
    words = float(df.words.mean())
    res = {"sample": sample, "dictionary": "VADER (|valence| >= 1), negation window 3",
           "tests": int(df.test_id.nunique()), "headlines": len(df),
           "mean_words": round(words, 2),
           "share_headlines_with_negative_word": round(float((df.neg > 0).mean()), 3),
           "share_headlines_with_positive_word": round(float((df.pos > 0).mean()), 3)}
    for x in xs:
        b, se = float(fit.params[x + "_z"]), float(fit.bse[x + "_z"])
        res[x] = {"beta_standardized": round(b, 4), "se": round(se, 4),
                  "ci95": [round(b - 1.96 * se, 4), round(b + 1.96 * se, 4)]}
    for x, label in (("neg_share", "negative"), ("pos_share", "positive")):
        b = res[x]["beta_standardized"]
        # one extra word of that kind in an average-length headline raises its share by 1 / words
        res[f"one_more_{label}_word_ctr_change_pct"] = round(100 * (np.exp(b / sd[x] / words) - 1), 2)
    res["robertson_2023"] = {"negative_beta": 0.015, "positive_beta": -0.008,
                             "one_more_negative_word_pct": 2.3, "one_more_positive_word_pct": -1.0}
    (res_dir / "negativity.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
