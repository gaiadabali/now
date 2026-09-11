"""Deliverable 2 -- the popularity prior, and the trap.

`wpb_post_views_count` (ARCHITECTURE.md Sec.6) is bot-contaminated: zero
articles at 0 views, an interquartile band compressed into ~850-1,400
regardless of what the article actually is, and the top 10% of articles
carrying only ~27% of total views where a real editorial power law would
put 60-80% there. That flat band is the signature of a counter that
increments on every bot/crawler hit almost independent of real traffic.

**Where the real signal starts, measured against the full 4,772-row
corpus** (see the E2.6 report for the actual percentile table):

    percentile (by rank)   views at cutoff
    p75  (top 3,579)       859
    p50  (top 2,386)       1,069
    p25  (top 1,193)       1,332
    p10  (top   477)       1,773
    p5   (top   238)       2,198
    top 300                2,049   <-- chosen default cutoff
    top 200                2,307
    top 100                3,011

The p25-p75 band (859-1,332) is the flat contaminated core the ticket
describes. Counts only start spreading out meaningfully -- gaps of
100-300 views between consecutive ranks instead of near-zero -- above
roughly 1,500-2,000 views, i.e. around rank 300-500. **300** is chosen as
the default head cutoff because it sits just past that inflection (views
>= 2,049) while still being a round, defensible "roughly top 300" per the
ticket's own suggestion, and top-300 captures only 20.8% of total
archive-wide views -- consistent with treating everything below the cutoff
as noise rather than smoothing it into a distribution-wide normalisation
(which the ticket explicitly forbids).

The cutoff is a parameter (`head_n`), not a hardcoded constant, precisely
because "roughly top 300" is a judgment call over noisy data, not a fact --
a future analytics source (Search Console, real GA4) should replace this
entirely rather than requiring a code change to retune it.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HEAD_N = 300


@dataclass(frozen=True)
class PopularityPrior:
    views: int
    rank: int  # 1 = most-viewed
    in_head: bool
    prior_score: float  # 0.0 outside the head; log-scaled within it otherwise
    head_n: int
    head_min_views: int
    head_max_views: int

    def as_components(self) -> dict:
        return {
            "views": self.views,
            "rank": self.rank,
            "in_head": self.in_head,
            "prior_score": self.prior_score,
            "head_cutoff": self.head_n,
            "head_cutoff_views_floor": self.head_min_views,
            "discarded_as_bot_noise": not self.in_head,
        }


def load_views_by_wp_id(articles_jsonl: Path) -> dict[int, int]:
    """Reads `wpb_post_views_count` keyed by the source `wp_id`, exactly as
    it lives in `jakarta/content/extracted/articles.jsonl` (Sec.6 notes
    this is present on all rows in this corpus)."""
    out: dict[int, int] = {}
    with articles_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            wp_id = row.get("wp_id")
            views = (row.get("meta") or {}).get("wpb_post_views_count")
            if wp_id is None or views is None:
                continue
            try:
                out[int(wp_id)] = int(views)
            except (TypeError, ValueError):
                continue
    return out


def compute_priors(views_by_key: dict[int, int], head_n: int = DEFAULT_HEAD_N) -> dict[int, PopularityPrior]:
    """Ranks every key by views desc; only the top `head_n` get a nonzero
    `prior_score` (log-scaled within the head's own min/max so the one
    outlier -- a single 2020 flood story at 306,504 views, ~5% of all
    archive traffic per Sec.6 -- doesn't flatten every other head member
    to near-zero). Everything past `head_n` is explicitly zeroed and
    flagged `discarded_as_bot_noise: true` -- never smoothed or
    interpolated, per the ticket's "do not normalise the whole
    distribution" instruction."""
    ranked = sorted(views_by_key.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return {}

    head = ranked[:head_n]
    head_min = head[-1][1] if head else 0
    head_max = head[0][1] if head else 0
    log_span = math.log(head_max + 1) - math.log(head_min + 1) if head_max > head_min else 0.0

    out: dict[int, PopularityPrior] = {}
    for rank0, (key, views) in enumerate(ranked):
        rank = rank0 + 1
        in_head = rank <= head_n
        if in_head and log_span > 0:
            prior = (math.log(views + 1) - math.log(head_min + 1)) / log_span
        elif in_head:
            prior = 1.0  # degenerate case: every head member has equal views
        else:
            prior = 0.0
        out[key] = PopularityPrior(
            views=views,
            rank=rank,
            in_head=in_head,
            prior_score=round(prior, 4),
            head_n=head_n,
            head_min_views=head_min,
            head_max_views=head_max,
        )
    return out
