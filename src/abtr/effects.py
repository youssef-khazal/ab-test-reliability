"""Distribution of true differences between headlines (question 1), by empirical Bayes.

Each package's log click rate y = log(clicks / impressions) is measured with sampling variance
v = 1/clicks - 1/impressions. Within one test, the difference between two packages d = y_a - y_b
estimates the true relative lift between them, with variance v_a + v_b. Across tests, the true lifts
come from an unknown distribution G; the observed ones are G blurred by known noise. We recover G:
- normal model: true lift ~ N(0, tau^2), tau^2 = mean(d^2 - var) (method of moments);
- nonparametric maximum likelihood (NPMLE): G as weights on a grid, fitted by EM; no shape assumed.
Every pair of versions in a test is used, in both orders (the sign of a pair is arbitrary, so G is
symmetric), each weighted 1 / (k (k - 1)) so that every test counts once (a composite likelihood).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm


def package_table(con, kept_tests: pd.Series | None = None) -> pd.DataFrame:
    df = con.execute("""select test_id, impressions as n, clicks as c from packages where clicks > 0""").fetchdf()
    if kept_tests is not None:
        df = df[df.test_id.isin(set(kept_tests))]
    df["y"] = np.log(df.c / df.n)
    df["v"] = 1 / df.c - 1 / df.n
    return df


def random_pairs(pk: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """One random ordered pair of packages per test: d = y_a - y_b and its variance."""
    rng = np.random.default_rng(seed)
    rows = []
    for tid, g in pk.groupby("test_id", sort=True):
        if len(g) < 2:
            continue
        a, b = rng.choice(len(g), size=2, replace=False)
        ga, gb = g.iloc[a], g.iloc[b]
        rows.append((tid, ga.y - gb.y, ga.v + gb.v))
    return pd.DataFrame(rows, columns=["test_id", "d", "var"])


def tau_moments(d: np.ndarray, var: np.ndarray, weight: np.ndarray | None = None) -> float:
    weight = np.ones(len(d)) if weight is None else weight
    return float(np.sqrt(max(np.average(d ** 2 - var, weights=weight), 0.0)))


def all_pairs(pk: pd.DataFrame) -> pd.DataFrame:
    """Every ordered pair of distinct versions within each test: d = y_a - y_b, its variance, a weight."""
    pk = pk.sort_values(["test_id", "y"]).reset_index(drop=True)
    rows = []
    for tid, g in pk.groupby("test_id", sort=True):
        k = len(g)
        if k < 2:
            continue
        y, v = g.y.values, g.v.values
        for i in range(k):
            for j in range(k):
                if i != j:
                    rows.append((tid, y[i] - y[j], v[i] + v[j], 1 / (k * (k - 1))))
    return pd.DataFrame(rows, columns=["test_id", "d", "var", "weight"])


def npmle(d: np.ndarray, se: np.ndarray, weight: np.ndarray | None = None, grid: np.ndarray | None = None,
          iters: int = 1500, tol: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """Kiefer-Wolfowitz NPMLE of the distribution of true effects, by EM on a fixed grid (weighted)."""
    grid = np.linspace(-1.0, 1.0, 201) if grid is None else grid
    weight = np.ones(len(d)) if weight is None else weight
    weight = weight / weight.sum()
    lik = (norm.pdf((d[:, None] - grid[None, :]) / se[:, None]) / se[:, None]).astype(np.float32)
    w = np.full(len(grid), 1 / len(grid))
    for _ in range(iters):
        post = lik * w
        post /= post.sum(axis=1, keepdims=True)
        new = weight @ post
        if np.abs(new - w).max() < tol:
            return grid, new
        w = new
    return grid, w


def summarize_g(grid: np.ndarray, w: np.ndarray) -> dict:
    a = np.abs(grid)
    order = np.argsort(a)
    cdf = np.cumsum(w[order])
    q = lambda p: float(a[order][np.searchsorted(cdf, p)])  # noqa: E731
    return {"sd": float(np.sqrt(np.sum(w * grid ** 2))),
            "median_abs": q(0.5), "p90_abs": q(0.9),
            "share_abs_below_1pct": float(w[a < np.log(1.01)].sum()),
            "share_abs_below_5pct": float(w[a < np.log(1.05)].sum()),
            "share_abs_above_20pct": float(w[a > np.log(1.20)].sum())}


def posterior_positive(d: np.ndarray, se: np.ndarray, grid: np.ndarray, w: np.ndarray) -> np.ndarray:
    """P(true lift > 0 | observed d) under the fitted distribution G (weights w on grid)."""
    lik = norm.pdf((d[:, None] - grid[None, :]) / se[:, None]) * w[None, :]
    return lik[:, grid > 0].sum(axis=1) / lik.sum(axis=1)


def aa_pairs(con) -> pd.DataFrame:
    """Pairs of packages in the same test with the same headline, image AND excerpt: what viewers saw
    before clicking was identical (share text and square appear only after the click, per the archive's
    paper), so any difference is noise: an accidental A/A test. Outside the flagged window."""
    return con.execute("""
        select a.test_id, a.impressions na, a.clicks ca, b.impressions nb, b.clicks cb
        from packages a join packages b
          on a.test_id = b.test_id and a.headline = b.headline
         and coalesce(a.image_id, '') = coalesce(b.image_id, '')
         and coalesce(a.excerpt, '') = coalesce(b.excerpt, '')
         and (a.created_at, a.impressions, a.clicks) < (b.created_at, b.impressions, b.clicks)
        join tests t on t.test_id = a.test_id
        where not t.in_flagged_window and a.clicks > 0 and b.clicks > 0""").fetchdf()
