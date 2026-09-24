"""Turns raw signals (lexicon zone hits, direct term-embedding cosine,
few-shot centroid cosine) into one `Candidate` per (article, facet, term)
worth a calibration verdict or a write. `calibration.py` measures each
band's precision; this module only assigns bands, it never decides
auto-apply -- that decision lives entirely in `calibration.py`'s measured
table plus `db.py`'s "write only a shipped band" check.

Band precedence (strongest first): a term matched literally in the TITLE
outranks one matched only in the lead, which outranks body-only, which
outranks "no lexical match anywhere, but the embedding says this article
is semantically close to this term". This mirrors
`now_taxonomy_evidence.text`'s title > lead > body trust ordering for
type/format/location -- not a new policy, the same one applied to a wider
set of facets.
"""
from __future__ import annotations

from dataclasses import dataclass

from .embed import CentroidIndex, centroid_similarity, term_similarity
from .lexicon import TermPattern, match_term_zones

BAND_TITLE = "title"
BAND_LEAD = "lead"
BAND_BODY = "body"
BAND_EMBED_ONLY = "embed_only"

LEXICAL_BANDS = (BAND_TITLE, BAND_LEAD, BAND_BODY)
ALL_BANDS = (BAND_TITLE, BAND_LEAD, BAND_BODY, BAND_EMBED_ONLY)

# Below this, an embed-only candidate isn't even worth a calibration
# label -- a cheap pre-filter so the calibration sampler doesn't waste
# labelling budget on obviously-unrelated pairs. It is NOT a calibrated
# cutoff: `calibration.py` measured `embed_only` (bare direct-term cosine,
# no few-shot centroid available at this sample size -- see
# `docs/EDITION-2-PLAN.md`) at 0.00-0.04 precision on every one of the
# five alias-based facets, i.e. everywhere at or above this floor, so
# `embed_only` never ships for any of them (see `calibration.
# MEASURED_PRECISION`) regardless of where this floor sits.
EMBED_ONLY_FLOOR = 0.45


@dataclass(frozen=True)
class Candidate:
    facet: str
    slug: str
    band: str
    lexical_zone: str | None
    direct_sim: float
    centroid_sim: float

    @property
    def embed_score(self) -> float:
        return max(self.direct_sim, self.centroid_sim)


def candidates_for_article(
    facet: str,
    title: str,
    dek_excerpt: str,
    body: str,
    matcher: list[TermPattern],
    article_vec: list[float] | None,
    term_vectors: dict[str, str],           # slug -> term_id (uuid str), for the direct-sim lookup
    term_vec_by_id: dict[str, list[float]],  # term_id (uuid str, lowercased) -> vector
    centroids: CentroidIndex | None,
) -> list[Candidate]:
    """One candidate per term that has EITHER a lexical hit OR a
    minimally-plausible embedding score -- a term with neither is not
    worth carrying (there are 15-44 terms per facet; most articles touch
    only a handful)."""
    zones = match_term_zones(title, dek_excerpt, body, matcher)
    out: list[Candidate] = []
    for tp in matcher:
        slug = tp.slug
        term_id = term_vectors.get(slug)
        term_vec = term_vec_by_id.get(term_id.lower()) if term_id else None
        direct = term_similarity(article_vec, term_vec)
        cent = centroid_similarity(article_vec, slug, centroids)
        zone = zones.get(slug)
        if zone is not None:
            band = {"title": BAND_TITLE, "lead": BAND_LEAD, "body": BAND_BODY}[zone]
            out.append(Candidate(facet, slug, band, zone, direct, cent))
        elif max(direct, cent) >= EMBED_ONLY_FLOOR:
            out.append(Candidate(facet, slug, BAND_EMBED_ONLY, None, direct, cent))
    return out
