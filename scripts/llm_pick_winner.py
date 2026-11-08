"""Question 5, part 2: can a language model tell which headline will get more clicks?

    python scripts/llm_pick_winner.py              # needs Ollama running with qwen3:8b (about 20-30 min)
    python scripts/llm_pick_winner.py --scores     # scores only, from the saved answers
    python scripts/llm_pick_winner.py --rate       # variant: rate each headline alone, 1-10 (no order effect)

Pairs: two versions of the same article that differ only by their headline (same image and excerpt),
where one clearly beat the other: |z| > 2.58 even after inflating the noise by the factor measured on
the A/A tests (results/effects.json). One pair per test, chosen deterministically, exploratory sample,
same exclusions as elsewhere. The model sees both headlines (no numbers) and answers A or B; every pair
is asked twice with the order swapped, so a model that always answers "A" scores exactly 50%.
Baseline without any model: the published negativity effect (Robertson et al. 2023): predict the
headline with more negative words, then fewer positive words, then more words.
Writes results/llm_answers.jsonl (resumable) and results/llm_scores.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
from scipy.stats import chi2, norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from abtr.db import ROOT, figures_dir, open_sample, results_dir, sample_arg  # noqa: E402
from abtr.sentiment import count, load_lexicon  # noqa: E402

MODEL = "qwen3:8b"
OLLAMA = "http://localhost:11434/api/chat"
PROMPT = """Two headlines were tested for the same article on a news website. Visitors were randomly shown one of them.
Which headline got the higher click rate?

A: {a}
B: {b}

Answer with JSON only: {{"answer": "A"}} or {{"answer": "B"}}"""
RATE_PROMPT = """Here is a headline from a news website.

{h}

How likely are readers to click on it, from 1 (very unlikely) to 10 (very likely)?
Answer with JSON only: {{"score": <number>}}"""


def pairs(con, phi: float):
    t = con.execute("select * from tests order by test_id").fetchdf()
    kept = set(t[~t.in_flagged_window & (chi2.sf(t.srm_chisq, t.n_packages - 1) >= 0.001)].test_id)
    pk = con.execute("""select test_id, headline, image_id, excerpt, sum(impressions) n, sum(clicks) c
                        from packages group by all order by all""").fetchdf()
    pk = pk[pk.test_id.isin(kept) & (pk.c > 0)]
    out = []
    for tid, g in pk.groupby("test_id", sort=True):
        best = None
        for _, grp in g.groupby(["image_id", "excerpt"], dropna=False, sort=True):
            rows = grp.drop_duplicates("headline").to_dict("records")
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    a, b = rows[i], rows[j]
                    d = np.log(a["c"] / a["n"]) - np.log(b["c"] / b["n"])
                    v = 1 / a["c"] - 1 / a["n"] + 1 / b["c"] - 1 / b["n"]
                    z = abs(d) / np.sqrt(phi * v)
                    if z > 2.58 and (best is None or z > best[0]):
                        win, lose = (a, b) if d > 0 else (b, a)
                        best = (z, win["headline"], lose["headline"])
        if best:
            out.append({"test_id": tid, "z": round(float(best[0]), 2), "winner": best[1], "loser": best[2]})
    return out


def _chat(prompt: str) -> str:
    body = {"model": MODEL, "stream": False, "think": False, "format": "json",
            "options": {"temperature": 0, "num_ctx": 2048},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"]


def rate(h: str) -> float | None:
    try:
        v = float(json.loads(_chat(RATE_PROMPT.format(h=h))).get("score"))
        return v if 1 <= v <= 10 else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def ask(a: str, b: str) -> str:
    txt = _chat(PROMPT.format(a=a, b=b))
    try:
        ans = str(json.loads(txt).get("answer", "")).strip().upper()
    except json.JSONDecodeError:
        ans = ""
    return ans if ans in ("A", "B") else "?"


def wilson(k: int, n: int) -> list[float]:
    if n == 0:
        return [0.0, 0.0]
    p, z = k / n, 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(c - h, 4), round(c + h, 4)]


def main() -> None:
    sample = sample_arg()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", action="store_true")
    ap.add_argument("--rate", action="store_true", help="rate each headline alone instead of comparing pairs")
    a = ap.parse_args()
    con = open_sample(sample)
    res_dir = results_dir(sample)
    phi = json.loads((res_dir / "effects.json").read_text())["aa"]["noise_inflation_phi"]
    ps = pairs(con, phi)
    if a.rate:
        return rate_mode(ps, a.scores, res_dir)
    path = res_dir / "llm_answers.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[(r["test_id"], r["order"])] = r
    if not a.scores:
        t0 = time.time()
        with open(path, "a", encoding="utf-8") as f:
            for i, p in enumerate(ps):
                for order in ("winner_first", "winner_second"):
                    if (p["test_id"], order) in done:
                        continue
                    x, y = (p["winner"], p["loser"]) if order == "winner_first" else (p["loser"], p["winner"])
                    ans = ask(x, y)
                    r = {"test_id": p["test_id"], "order": order, "answer": ans,
                         "correct": ans == ("A" if order == "winner_first" else "B")}
                    done[(p["test_id"], order)] = r
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                print(f"[{i + 1}/{len(ps)}] {p['test_id']} {time.time() - t0:.0f} s")

    lex = load_lexicon()
    def score(h):
        w, pos, neg = count(h, lex)
        return (neg, -pos, w)
    base = [score(p["winner"]) > score(p["loser"]) for p in ps]
    ties = [score(p["winner"]) == score(p["loser"]) for p in ps]
    ans = [done[(p["test_id"], o)] for p in ps for o in ("winner_first", "winner_second") if (p["test_id"], o) in done]
    k = sum(r["correct"] for r in ans)
    both = [done[(p["test_id"], "winner_first")]["correct"] and done[(p["test_id"], "winner_second")]["correct"]
            for p in ps if (p["test_id"], "winner_first") in done and (p["test_id"], "winner_second") in done]
    consistent = [done[(p["test_id"], "winner_first")]["answer"] != done[(p["test_id"], "winner_second")]["answer"]
                  for p in ps if (p["test_id"], "winner_first") in done and (p["test_id"], "winner_second") in done]
    res = {"model": MODEL, "pairs": len(ps), "answers": len(ans),
           "llm_accuracy": round(k / max(len(ans), 1), 4), "llm_ci95": wilson(k, len(ans)),
           "llm_unparsed": sum(r["answer"] == "?" for r in ans),
           "llm_answered_A": round(sum(r["answer"] == "A" for r in ans) / max(len(ans), 1), 4),
           "llm_same_headline_in_both_orders": round(float(np.mean(consistent)), 4) if consistent else None,
           "llm_right_in_both_orders": round(float(np.mean(both)), 4) if both else None,
           "baseline_accuracy_counting_ties_as_half": round((sum(base) + 0.5 * sum(ties)) / len(ps), 4),
           "baseline_ties": sum(ties), "chance": 0.5}
    (res_dir / "llm_scores.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


def rate_mode(ps, scores_only: bool, res_dir: Path) -> None:
    path = res_dir / "llm_ratings.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[r["headline"]] = r["score"]
    if not scores_only:
        t0 = time.time()
        with open(path, "a", encoding="utf-8") as f:
            for i, p in enumerate(ps):
                for h in (p["winner"], p["loser"]):
                    if h not in done:
                        done[h] = rate(h)
                        f.write(json.dumps({"headline": h, "score": done[h]}) + "\n")
                        f.flush()
                print(f"[{i + 1}/{len(ps)}] {p['test_id']} {time.time() - t0:.0f} s")
    got = [(done.get(p["winner"]), done.get(p["loser"])) for p in ps]
    got = [(w, l) for w, l in got if w is not None and l is not None]
    wins = sum(w > l for w, l in got)
    ties = sum(w == l for w, l in got)
    res = {"model": MODEL, "mode": "rate each headline 1-10", "pairs": len(ps), "pairs_rated": len(got),
           "accuracy_ties_as_half": round((wins + 0.5 * ties) / max(len(got), 1), 4),
           "ci95_without_ties": wilson(wins, len(got) - ties), "ties": ties,
           "accuracy_without_ties": round(wins / max(len(got) - ties, 1), 4)}
    (res_dir / "llm_rate_scores.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
