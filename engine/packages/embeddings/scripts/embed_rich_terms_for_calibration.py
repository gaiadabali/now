"""One-off offline tool for PROGRESS.md F118(a) -- the embeddings-based
type/format instrument evaluated in `now_eval.calibration.embed_instrument`.

**Why this exists**: F118's brief flags that bare term labels ("eat",
"stay", "do") likely embed poorly for zero-shot term-similarity
classification, and suggests building richer term text from label +
description + `attrs`. Live-checked: `engine.terms.attrs` is `{}` for
every one of the 9 `type` / 11 `format` rows (see PROGRESS.md F88 -- the
column exists but nothing has ever populated it for this facet), so there
is no description to read from the platform DB. This script hand-authors
one short, editorially-grounded sentence per term (based on how the
category is actually used across the archive, not the bare label) and
embeds it with the exact same model/provider (`now_embeddings.providers
.local.LocalProvider`, `BAAI/bge-small-en-v1.5`, deterministic, offline,
no network) the real pipeline uses for every other vector in
`engine.embeddings` -- so this is a fair like-for-like comparison against
the bare-label vectors already stored there, not a different model.

**Deliberately NOT written to `engine.embeddings`**: these are hand-authored
descriptions for a *measurement*, not the vocabulary's real definitions
(that would need a taxonomy-owner decision, not an agent's guess -- see
CLAUDE.md "schema changes go through the senior-db seat or an
architect-approved migration spec"). Output goes to a plain JSON file in
`now-eval`'s calibration data dir instead, loaded read-only by
`now_eval.calibration.embed_data.load_rich_term_vectors`.

**Run once, in this package's venv (the only one with fastembed
installed)**:
    engine/packages/embeddings> .venv/Scripts/python.exe scripts/embed_rich_terms_for_calibration.py

Deterministic: re-running with the same TERM_TEXT dict reproduces the file
byte-for-byte (same model, same input strings, no randomness).
"""
from __future__ import annotations

import json
from pathlib import Path

from now_embeddings.providers.local import LocalProvider

OUT_PATH = (
    Path(__file__).resolve().parents[2]  # engine/packages
    / "eval" / "data" / "calibration" / "term_vectors_rich.json"
)

# One sentence per term: what the category actually means editorially, not
# just its label. Written from how the archive uses each term (categories.md
# / taxonomy review context), not from `engine.terms.attrs` (empty -- see
# module docstring).
TERM_TEXT: dict[str, dict[str, str]] = {
    "type": {
        "do": "An activity, attraction, sight or experience visitors can do -- tours, landmarks, adventure activities, things to do.",
        "drink": "A bar, cocktail lounge, brewery, cafe or nightlife venue -- a place whose primary purpose is serving drinks.",
        "eat": "A restaurant, cafe or dining venue -- a place whose primary purpose is serving food.",
        "editorial": "General editorial content not centred on one specific venue -- culture, trends, opinion, history or lifestyle writing.",
        "event": "A specific dated happening -- a festival, party, concert, exhibition or one-off gathering, not an ongoing venue.",
        "shop": "A retail venue, boutique, market or shopping experience -- a place whose primary purpose is selling goods.",
        "stay": "A hotel, resort, villa or other accommodation -- a place where visitors sleep overnight.",
        "unknown": "None of the defined venue or activity types apply, or the subject cannot be determined.",
        "wellness": "A spa, gym, yoga studio or wellness retreat -- a place focused on health, fitness or relaxation of the body.",
    },
    "format": {
        "city-guide": "A broad guide to a city, neighbourhood or district covering many venues and things to do at once.",
        "event": "Coverage of one specific dated event -- announcing or recapping a single happening, not an ongoing venue.",
        "feature": "An in-depth editorial feature story exploring a topic, trend or place in detail, not tied to a single transaction.",
        "guide": "A practical how-to or thematic guide -- curated advice or a themed list built around one subject.",
        "heritage": "Historical or cultural heritage writing -- the history of a place, building, tradition or community.",
        "listing": "A compiled list of multiple venues, items or options -- a best-of or round-up style piece.",
        "news": "A timely news announcement or update -- something that just happened or was just announced.",
        "offer": "A promotional deal, discount, package or special offer at a specific venue.",
        "opinion": "An opinion piece or commentary -- a personal viewpoint or argument, not a straight report.",
        "people": "A profile of a person -- an interview, founder story or spotlight on an individual.",
        "review": "An evaluative review of one specific venue, product or experience -- what it's like and whether it's worth it.",
    },
}


def main() -> None:
    provider = LocalProvider()
    out: dict[str, dict[str, list[float]]] = {}
    for facet, by_slug in TERM_TEXT.items():
        slugs = list(by_slug.keys())
        texts = [f"{facet}: {by_slug[s]}" for s in slugs]
        vecs = provider.embed_batch(texts)
        out[facet] = {slug: vec for slug, vec in zip(slugs, vecs)}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out), encoding="utf-8")
    print(f"wrote {sum(len(v) for v in out.values())} rich term vectors -> {OUT_PATH}")


if __name__ == "__main__":
    main()
