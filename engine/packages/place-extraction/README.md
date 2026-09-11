# now-place-extraction (E2.3 — place entity extraction + dedup)

Extracts venue mentions from `public.articles.body_blocks`, reconciles them
against each city's existing `public.places`, dedups brand-new candidates
with a precision bias, and upserts `public.place_mentions` idempotently.

## Two findings this ticket surfaced (read before trusting "Jakarta has 177 places")

**Finding #1 — `now_jakarta.public.places` (177 rows) and `now_jakarta.public.events`
(837 rows) are Bali content, not Jakarta content.** Verified live: every one of
the 177 place names is a Bali venue (Seminyak, Canggu, Ubud, Nusa Dua, Jimbaran —
zero Jakarta-area names), and `jakarta/content/extracted/events.jsonl` (the
on-disk source, not just the DB) contains `content_html` with literal
`nowbali.co.id` URLs. `now_bali.public.places`/`public.events` are both
genuinely empty (0 rows), and `bali/content/extracted/venues.jsonl` /
`events.jsonl` are empty files. `public.articles` is NOT affected — Jakarta's
4,772 and Bali's 4,429 articles are both genuinely their own city's content
(spot-checked; e.g. Bali article #7 is literally titled "All Day Easter
Carnival At Potato Head Beach Club", and that same venue is `now_jakarta.
public.places` row 18). This looks like an upstream (E1.x) wp-extract/loader
step that ran the Bali WXR export but targeted `jakarta/content/extracted/`
and `now_jakarta`, while the equivalent Jakarta-source run for events/venues
never happened (or produced nothing).

**Consequence for this ticket:** the brief's premise "reconcile Jakarta
against its 177 existing places" does not hold — those rows are not
Jakarta's real venue seed. This pipeline therefore:
- still checks Jakarta candidates against those 177 rows (an EXACT string
  match against a real name is valid regardless of which city DB row holds
  it — a Jakarta article can genuinely mention a real Bali resort), but
- never auto-merges a Jakarta text-derived FUZZY match into one of those
  177 rows (routed to the review queue instead, flagged with an explicit
  note pointing at this finding), and
- treats Jakarta's real local-venue seed as, in effect, also empty — new
  Jakarta places are created from Jakarta's own article text, the same way
  Bali's are, rather than merged into the contaminated set.

**Not fixed here.** Moving/deleting those 177 rows (and populating
`now_bali`'s real venues/events from the correct source) is a cross-database
data-migration decision, not something to improvise mid-ticket — especially
with a parallel E2.1 agent concurrently reading/reclassifying that exact
table. Recommend a senior-db/architect-scoped follow-up to re-run the
events/venues extraction against the correct per-city WXR sources and decide
whether to move, relabel, or discard the misplaced 177/837 rows.

**Finding #2 — `public.classification_reviews` (E2.8) cannot represent a
place-merge decision**, contrary to this ticket's brief ("reuse it...
coordinate via distinct facet_key/entity_type values"). Read live before
writing any code (`engine/packages/cms/src/collections/
ClassificationReviews.ts`, `reviewQueueHooks.ts`):
1. `facet_key` is a Postgres ENUM with exactly four values — `type`,
   `subtype`, `format`, `location` (`enum_classification_reviews_facet_key`,
   verified live). "Is candidate A the same venue as candidate B" is not a
   fifth value away from working; it is not a classification-facet
   question at all.
2. The collection's `entity` field is a single polymorphic relationship
   (one article-or-place) — there is no second-entity field for "the other
   candidate in a merge pair."
3. `afterChange` writes `finalValue` onto one scalar field of one entity
   the moment `reviewState` leaves `pending`. There is no write-back
   semantic for "merge place B into place A" — an editor clicking the
   existing "accept" affordance on a shoehorned merge row would silently
   write a place name into some unrelated entity's `type`/`subtype`/
   `format`/`location` field.

This instead follows the OTHER review-queue convention already live in this
repo — E2.5's `<city>/content/extracted/geocoded_places_review_queue.jsonl`
(file-based, one JSON object per line) — for the same "uncertain, don't
auto-apply" shape. See `reviewqueue.py`'s docstring. **Flagged as a
contradiction to resolve with an architect/senior-db decision** (a real
second entity-relationship field + a fifth ENUM value, or a dedicated
`place-merge-reviews` collection), not silently worked around without
comment.

## No schema change needed

Verified live before writing any code: `public.places` and
`public.place_mentions` already carry every column this pipeline needs.
Idempotency is enforced in application code (slug lookup for places,
`(article_id, place_id, surface_text)` lookup for mentions) rather than
`ON CONFLICT`, since neither table has a unique constraint shaped for that.
No migration was added.

**Gap noted, not fixed:** `place_mentions` has no `confidence` column in the
shipped schema (matches ARCHITECTURE.md §5's own sketch — this is not a
loader bug, just a gap for this ticket's "linking articles to places with
evidence and a confidence" wording). This pipeline only ever writes a
mention once the ENTITY-level decision has cleared a precision gate (exact
gazetteer match, or membership in an auto-merged ≥0.85 dedup cluster) — so
every written row is implicitly "confident enough to commit" — but there is
nowhere on the row itself to record a graded confidence number. `surface_text`
(the verbatim quote) + `offset` (its location) are the "evidence" the
schema does provide.

## Design

- `textwalk.py` — flattens `body_blocks` to plain text, deterministically
  (byte-identical on every re-run of the same input).
- `extract.py` — deterministic (non-statistical) candidate-phrase regex,
  a venue-keyword heuristic, an area/geography exclusion list drawn from
  the real `enum_places_area_term` vocabulary, and a hand-built noise-word
  list (assembled by running the extractor against real article text and
  inspecting the highest-recurrence false positives — see inline comments
  for exact examples found, e.g. `"bar"` substring-matching inside
  `"Lebaran"`).
- `gazetteer.py` — exact + fuzzy lookup against a city's existing
  `public.places` rows.
- `normalize.py` / `match.py` — name normalization and a three-signal,
  precision-biased similarity score (`core_jaccard` dominates; a name pair
  that differs only by generic words gets a floor of 0.90, but two
  different venues sharing a brand word in different areas, e.g. "Padma
  Resort Ubud" vs "Padma Resort Legian", cannot clear the auto-merge gate).
- `dedup.py` — union-find clustering of brand-new candidates at the
  project's stated 0.85 auto-merge gate; anything from 0.55–0.85 is a
  review pair, left unmerged.
- `llm.py` — OPTIONAL (`--use-llm`), OFF by default. Ollama Cloud
  adjudication for ambiguous pairs, hard call cap enforced in code
  (`BudgetExceeded`), key read from the shared secrets file at call time
  only, never logged.
- `reviewqueue.py` / `pipeline.py` — orchestration, idempotent upserts, and
  a human-sized (capped, evidence-filtered) review-queue file.

## Known precision/recall limitations (v1)

- Single-token new-candidates require an explicit venue keyword (no
  recurrence-based fallback) — a genuine new single-word venue not yet
  seeded and not keyword-bearing (rare in this corpus; most seeded
  single-word places like "Skybar"/"Tropicola" are already in the
  gazetteer) will be missed. Precision-over-recall, as directed.
- Unrecognized acronyms / proper nouns that are neither a person's name
  a regex can rule out nor a venue keyword can hit (e.g. an award-body
  acronym) can still surface as a spurious "new place." These are exactly
  the long tail this ticket says to bias away from guessing on; they are
  cheap for a human to spot in a `public.places` listing sorted by
  `created_at` and low mention count, and are `status='pending_review'`
  like everything else this pipeline creates.
- Run `now-place-extract run --city <city> --dry-run` to see full counts
  with zero DB writes before a real run.
