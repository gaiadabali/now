"""The E2.6 quality-score blender. ARCHITECTURE.md Sec.7 says every article
needs a `quality_score` with stored components; Sec.6's known-issues call
out "content length, media presence, structural richness ... author
presence, Yoast completeness" as the reasonable components. This module
picks concrete weights for those five and justifies each.

## Weighting (sums to 1.0) -- and why

| component | weight | why this weight |
|---|---|---|
| length    | 0.30 | The single strongest, most attackable-by-stubs signal.
                      Highest weight *and* the one component with a hard
                      penalty override below -- both because a wall of text
                      isn't quality on its own, and because it must be
                      possible to fail regardless of the other four. |
| structure | 0.20 | Sec.6: "a wall of text" vs. headings/lists/quotes is
                      exactly the editorial-quality signal the ticket names
                      separately from raw length. |
| media     | 0.20 | Presence of images/galleries/embeds + a hero image.
                      Editorial articles in this corpus are consistently
                      illustrated; a picture-less article reads as a stub
                      even at moderate length. |
| yoast     | 0.20 | SEO metadata completeness (focus keyword + meta
                      description) is a real, human-authored signal of
                      editorial investment -- an editor filled in Yoast
                      fields for content they cared about. Held at 0.20
                      rather than higher because only 1,136/4,772 articles
                      (24%) have a focus keyword at all (Sec.6), so most of
                      the corpus's real quality variance has to come from
                      the other four components -- overweighting the
                      sparsest one would make quality_score mostly measure
                      "was this recent enough for the SEO plugin to be
                      used", not editorial quality.
| author    | 0.10 | Deliberately the lightest weight. Attribution matters
                      (it is explicitly named in the ticket) but it is a
                      single boolean with no gradation, and the corpus's
                      earliest years are inconsistently attributed for
                      reasons unrelated to content quality (see the
                      `author_id` coverage note in the report). A high
                      weight here would penalize old-but-good content for
                      a metadata gap, not a content gap.

## The stub floor (Deliverable 1's explicit requirement)

A continuous weighted sum alone cannot *guarantee* "sub-500-char stubs
fall below the floor" -- a 400-char stub with a hero image, three yoast
fields and an attributed author could otherwise creep close to the floor
on the other 70% of the weight. So length in [0, 500) chars is treated as
a hard "this is not an article" case: the *final* score is capped at
`STUB_SCORE_CAP` (0.15) regardless of what the other four components say,
independent of and below `QUALITY_FLOOR` (0.35, Sec.8.A's "quality floor"
filter threshold). The two constants have deliberate headroom between them
(0.15 vs 0.35) so the stub cap survives even if the floor is retuned later.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from now_quality.textextract import ArticleTextStats

# --- tunables -------------------------------------------------------------

STUB_CHAR_THRESHOLD = 500  # ticket's own line: "sub-500-char stubs"
STUB_SCORE_CAP = 0.15
QUALITY_FLOOR = 0.35  # Sec.8.A "Quality floor" filter reference value

# A well-developed feature/guide in this corpus (median 4,802 chars per
# ARCHITECTURE.md Sec.6) should comfortably reach 1.0 on length; the curve
# is log-scaled so the marginal value of extra length tapers off past that
# rather than rewarding padding.
_LENGTH_FLOOR_CHARS = STUB_CHAR_THRESHOLD
_LENGTH_CEIL_CHARS = 6000

_MEDIA_COUNT_FOR_FULL_SCORE = 4  # 2 inline images + hero, or a small gallery
_HEADING_COUNT_FOR_FULL_SCORE = 3


@dataclass(frozen=True)
class Weights:
    length: float = 0.30
    structure: float = 0.20
    media: float = 0.20
    yoast: float = 0.20
    author: float = 0.10

    def as_dict(self) -> dict:
        return asdict(self)

    def __post_init__(self) -> None:
        total = self.length + self.structure + self.media + self.yoast + self.author
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


DEFAULT_WEIGHTS = Weights()


def score_length(chars: int) -> float:
    if chars < _LENGTH_FLOOR_CHARS:
        # Still a continuous (if steep) ramp within the stub band itself,
        # so the components jsonb shows *some* gradation for a 50-char vs.
        # 450-char stub -- the hard cap that actually enforces the floor
        # requirement is applied to the final score, not here.
        return round((chars / _LENGTH_FLOOR_CHARS) * 0.3, 4)
    span = math.log(_LENGTH_CEIL_CHARS) - math.log(_LENGTH_FLOOR_CHARS)
    pos = (math.log(chars) - math.log(_LENGTH_FLOOR_CHARS)) / span
    return round(min(1.0, max(0.3, pos)), 4)


def score_media(media_count: int, has_hero: bool) -> float:
    effective = media_count + (1 if has_hero else 0)
    return round(min(1.0, effective / _MEDIA_COUNT_FOR_FULL_SCORE), 4)


def score_structure(stats: ArticleTextStats) -> float:
    rich_type_score = min(1.0, stats.distinct_rich_types / 3)
    heading_score = min(1.0, stats.heading_count / _HEADING_COUNT_FOR_FULL_SCORE)
    return round(0.5 * rich_type_score + 0.5 * heading_score, 4)


def score_author(author_id: int | None) -> float:
    return 1.0 if author_id is not None else 0.0


def score_yoast(has_focuskw: bool, has_metadesc: bool, has_primary_category: bool) -> float:
    signals = [has_focuskw, has_metadesc, has_primary_category]
    return round(sum(1 for s in signals if s) / len(signals), 4)


@dataclass
class QualityResult:
    score: float
    components: dict
    is_stub: bool


def compute_quality(
    *,
    stats: ArticleTextStats,
    author_id: int | None,
    hero_media_id: int | None,
    has_focuskw: bool,
    has_metadesc: bool,
    has_primary_category: bool,
    weights: Weights = DEFAULT_WEIGHTS,
) -> QualityResult:
    """Pure function: no DB access, easy to unit test and to reuse from a
    report/dry-run path without touching Postgres."""
    c_length = score_length(stats.chars)
    c_media = score_media(stats.media_count, hero_media_id is not None)
    c_structure = score_structure(stats)
    c_author = score_author(author_id)
    c_yoast = score_yoast(has_focuskw, has_metadesc, has_primary_category)

    raw = (
        weights.length * c_length
        + weights.media * c_media
        + weights.structure * c_structure
        + weights.author * c_author
        + weights.yoast * c_yoast
    )

    is_stub = stats.chars < STUB_CHAR_THRESHOLD
    final = min(raw, STUB_SCORE_CAP) if is_stub else raw
    final = round(max(0.0, min(1.0, final)), 4)

    components = {
        "weights": weights.as_dict(),
        "length": {"chars": stats.chars, "component": c_length},
        "media": {
            "media_count": stats.media_count,
            "has_hero": hero_media_id is not None,
            "component": c_media,
        },
        "structure": {
            "heading_count": stats.heading_count,
            "distinct_rich_block_types": stats.distinct_rich_types,
            "component": c_structure,
        },
        "author": {"has_author": author_id is not None, "component": c_author},
        "yoast": {
            "has_focus_keyword": has_focuskw,
            "has_meta_description": has_metadesc,
            "has_primary_category": has_primary_category,
            "component": c_yoast,
        },
        "raw_score": round(raw, 4),
        "is_stub": is_stub,
        "stub_char_threshold": STUB_CHAR_THRESHOLD,
        "stub_score_cap": STUB_SCORE_CAP,
        "quality_floor_reference": QUALITY_FLOOR,
    }
    return QualityResult(score=final, components=components, is_stub=is_stub)
