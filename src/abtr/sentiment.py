"""Positive and negative word counts in headlines.

Robertson et al. (2023) used the LIWC dictionaries, which are not free. We use the open VADER lexicon
(Hutto & Gilbert 2014) instead: a word is negative if its mean valence is <= -1 and positive if >= 1
(VADER's scale runs from -4 to +4). As in Robertson et al., a word's polarity is flipped when one of the
3 preceding words is a negation.
"""

from __future__ import annotations

import os
import re

import vaderSentiment

NEGATIONS = {"not", "no", "never", "none", "nobody", "nothing", "neither", "nor", "nowhere", "cannot",
             "can't", "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't", "weren't", "won't",
             "wouldn't", "shouldn't", "couldn't", "hasn't", "haven't", "hadn't", "ain't", "without"}
TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?")


def load_lexicon() -> dict[str, float]:
    path = os.path.join(os.path.dirname(vaderSentiment.__file__), "vader_lexicon.txt")
    lex = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2 and TOKEN.fullmatch(parts[0]):
                lex[parts[0]] = float(parts[1])
    return lex


def count(headline: str, lex: dict[str, float]) -> tuple[int, int, int]:
    """(words, positive words, negative words) in one headline."""
    words = TOKEN.findall(headline.lower().replace("’", "'"))
    pos = neg = 0
    for i, w in enumerate(words):
        v = lex.get(w)
        if v is None or abs(v) < 1:
            continue
        if any(p in NEGATIONS for p in words[max(0, i - 3):i]):
            v = -v
        pos += v > 0
        neg += v < 0
    return len(words), pos, neg
