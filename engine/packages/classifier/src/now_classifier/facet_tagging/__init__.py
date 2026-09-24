"""WS5 tagging: topic / audience / vibe / cuisine / price_band / occasion.

F137 measured ZERO tagged articles on these six facets in either city
(docs/SURFACES-PLAN.md) -- the preference picker
(`engine/apps/web/src/lib/preferences.ts`) offers all of them, so most of
what a reader picks matches nothing. This package is a re-runnable job that
tags the archive for these facets specifically, using the same evidence
style already established by `now_taxonomy_evidence.text` (a transparent,
inspectable keyword-cue instrument) and `now_taxonomy_evidence.
embed_similarity` (cosine-to-centroid) -- reused, not reinvented -- plus a
direct per-term embedding signal that only exists for these facets because
every platform term already has its own embedding (`engine.embeddings`,
entity_type='term', model BAAI/bge-small-en-v1.5, in EACH city DB).

No LLM is available (the shared Ollama Cloud key is unauthorized, no
Anthropic key exists) -- see `llm_refine.py` for the optional, OFF-by-
default refinement path that uses one IF a valid key ever appears.

Every number this package stamps as `confidence` is MEASURED against a
hand-labelled calibration sample (`calibration.py`'s
`MEASURED_BAND_PRECISION`), never invented -- matching this repo's own
stated discipline (see `now_classifier.confidence`'s module docstring and
the F118/F120 routing work in `embed_routing.py`). A band that does not
measure precision >= 0.80 is NOT shipped: its candidates are simply never
written, not queued for review (this job does not touch
`classification_reviews` at all -- these are exploratory tags, not
category-derived facts, and the review queue (6,442 pending) must not be
flooded by them).
"""
