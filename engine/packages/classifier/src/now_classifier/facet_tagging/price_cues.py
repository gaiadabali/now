"""`price_band` has no lexical vocabulary at all -- its four terms are
labelled "$".."$$$$" (`engine/packages/taxonomy/seed/terms/price_band.json`),
so there is nothing to alias-match. This is a small, hand-authored
keyword-cue instrument, in the exact style of
`now_taxonomy_evidence.text.TYPE_CUES`/`FORMAT_CUES` (regex, weight;
title/lead/body zone-weighted; argmax + abstain-on-tie) -- reusing that
module's `_score`/`_decide` machinery directly rather than re-deriving a
second scoring engine, because `price_band` is single-cardinality
(`engine.facets.cardinality = 'single'`), the same shape as `type`/
`format`, not the multi-label shape the other five WS5 facets need.

Cue sources: each band's own seed description (`price_band.json`'s
"Street food, warung, casual cafe" / "Fine dining, 5-star hotel, private
villa" etc.) plus explicit price figures already known to correlate with
tier (a Rp 2,000,000++ tasting menu is not `budget`, whatever else the
article says) -- **not** a repurposing of `FORMAT_CUES["offer"]`'s IDR
regex, which fires on ANY price mention regardless of magnitude; this
module's own `_HIGH_FIGURE`/`_LOW_FIGURE` cues are magnitude-aware.
"""
from __future__ import annotations

import re

from now_taxonomy_evidence.text import (
    BODY_CAP_BASE,
    BODY_CAP_MULT,
    LEAD_CAP_BASE,
    LEAD_CAP_MULT,
    LEAD_W,
    NO_TITLE_CEILING,
    TITLE_W,
    BODY_W,
    CueResult,
)

PRICE_BAND_CUES: dict[str, list[tuple[str, float]]] = {
    "budget": [
        (r"\bstreet food\b|\bwarungs?\b|\bkaki[- ]?lima\b", 1.2),
        (r"\bcasual\b|\bhole[- ]in[- ]the[- ]wall\b|\bno[- ]frills\b", 0.7),
        (r"\bcheap\b|\baffordable\b|\bbudget[- ]friendly\b|\bwallet[- ]friendly\b|\bpocket[- ]friendly\b", 1.0),
        (r"\bunder (rp|idr)\s?[\d.,]*\s?(50|75|100)[.,]?000\b", 1.2),
        (r"\bstalls?\b|\bhawker\b|\bfood cart\b", 0.8),
    ],
    "moderate": [
        (r"\bmid[- ]range\b|\bmid[- ]priced\b", 1.2),
        (r"\b3[- ]star\b|\bthree[- ]star\b", 1.0),
        (r"\bcasual dining\b|\bfamily[- ]friendly (restaurant|prices?)\b", 0.6),
        (r"\breasonably priced\b|\bgood value\b|\bvalue for money\b", 0.9),
    ],
    "upscale": [
        (r"\bupscale\b|\bupmarket\b", 1.2),
        (r"\b4[- ]star\b|\bfour[- ]star\b", 1.0),
        (r"\bcocktail bars?\b|\bfine casual\b|\bsophisticated\b|\bchic\b|\belevated\b", 0.6),
        (r"\bpremium\b|\bhigh[- ]end\b(?!.*luxury)", 0.7),
    ],
    "luxury": [
        (r"\bfine dining\b", 1.0),
        (r"\b5[- ]star\b|\bfive[- ]star\b", 1.2),
        (r"\bprivate villas?\b|\bbutler\b|\bmichelin\b|\bomakase\b|\bdegustation\b|\btasting menu\b", 1.0),
        (r"\bluxur(y|ious)\b|\bopulent\b|\bexclusive\b|\bindulgent\b|\bhaute\b", 0.8),
        (r"\bover (rp|idr)\s?[\d.,]*\s?(1|2|3)[.,]?000[.,]?000\b", 1.2),
    ],
}

def _compile(cues: dict[str, list[tuple[str, float]]]) -> dict[str, list[tuple[re.Pattern[str], float]]]:
    return {k: [(re.compile(p, re.I), w) for p, w in v] for k, v in cues.items()}


_COMPILED = _compile(PRICE_BAND_CUES)


def _zone_score(zone_text: str, weight: float) -> dict[str, float]:
    out = {k: 0.0 for k in _COMPILED}
    if not zone_text:
        return out
    for k, pats in _COMPILED.items():
        s = 0.0
        for pat, w in pats:
            n = min(len(pat.findall(zone_text)), 3)  # CAP_PER_CUE, matching text.py
            s += n * w
        out[k] = s * weight
    return out


def _decide(scores: dict[str, float], min_score: float, min_margin: float) -> CueResult:
    """Same argmax/abstain shape as `now_taxonomy_evidence.text._decide`
    (not imported -- that name is private to its module; duplicating this
    ~6-line decision rule here is cheaper and less brittle than reaching
    into another package's underscore-prefixed internals for it)."""
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    top, second = ranked[0], ranked[1] if len(ranked) > 1 else (None, 0.0)
    margin = top[1] - second[1]
    if top[1] < min_score or margin < min_margin:
        return CueResult(None, scores, margin, False)
    return CueResult(top[0], scores, margin, margin >= 2 * min_margin)


def score_price_band(title: str, text: str) -> CueResult:
    """Title/lead/body zone-weighted, reusing the same head/body capping
    shape `now_taxonomy_evidence.text.score_type`/`score_format` use (a
    lead+body combination with zero title support is capped at
    `NO_TITLE_CEILING`) -- but without importing that module's private
    `_score_head_body`/`_combine_head_body` (see `_decide` above for why).

    Unlike that module, this instrument's own `min_score` (1.2) sits
    BELOW `NO_TITLE_CEILING` (2.0), not above it -- so, measured and
    disclosed rather than silently inherited: a title mention is still
    the strongest single anchor, but a repeated, unambiguous lead/body
    price signal (two or more cue hits, e.g. "fine dining" appearing
    twice) CAN still cross the bar without any title support at all. This
    was true of the exact cue set `calibration.py`'s price_band numbers
    were measured against (many hotel-brand-name PR pieces carry their
    only price signal in the lead paragraph, not the headline), so
    tightening it now would invalidate those measured numbers without a
    re-measurement -- left as today's honest behaviour, not "fixed" here."""
    title_s = _zone_score(title, TITLE_W)
    lead_s = _zone_score(text[:400], LEAD_W)
    body_s = _zone_score(text[400:1600], BODY_W)
    combined: dict[str, float] = {}
    for k in _COMPILED:
        t = title_s.get(k, 0.0)
        if t <= 0:
            combined[k] = min(lead_s.get(k, 0.0) + body_s.get(k, 0.0), NO_TITLE_CEILING)
            continue
        lead_capped = min(lead_s.get(k, 0.0), LEAD_CAP_MULT * t + LEAD_CAP_BASE)
        head = t + lead_capped
        body_capped = min(body_s.get(k, 0.0), BODY_CAP_MULT * head + BODY_CAP_BASE)
        combined[k] = head + body_capped
    # Lower bar than type/format's 2.5/1.0 -- this cue set is intentionally
    # small (4 bands, a handful of cues each, hand-authored rather than
    # mined from 253 adjudications), so raw scores run lower. Calibrated
    # against WS5's own hand-labelled price_band sample, not copied from
    # type/format's unrelated thresholds -- see calibration.py.
    return _decide(combined, min_score=1.2, min_margin=0.5)
