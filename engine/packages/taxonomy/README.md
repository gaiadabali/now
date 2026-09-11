# now-taxonomy (seed data)

The controlled vocabulary of the NOW! Engine — ARCHITECTURE.md §4 as data.
**This package is data only: JSON files, no code, no `pyproject.toml`.**
It is read by `now_db.provisioning` (`site:create` / `site:migrate`) and is
the single place the vocabulary is authored. Nothing else defines a facet or
a term.

```
seed/
  facets.json            the 11 facets (key, label, cardinality, required)
  terms/<facet>.json     one file per facet; hierarchical facets nest `children`
  type_relations.json    the §4 exclusion + complement matrix (city DB default)
  format_decay.json      the §4 format → half-life table (per-site default)
```

## What persists where

| Seed file | Table | Key | Fields written |
|---|---|---|---|
| `facets.json` | `now_platform.engine.facets` | `key` | `label`, `cardinality`, `required` |
| `terms/*.json` | `now_platform.engine.terms` | `(facet_id, slug)` | `label`, `parent_id`, `geo` |
| `type_relations.json` | `now_<city>.engine.type_relations` | `type` | `exclude_same`, `complements` — **missing rows only** |
| `format_decay.json` | `now_platform.engine.sites.ranking_weights['decay']` | `slug` | the whole `decay` object — **only if the key is absent** |

Every other field in the files (`aliases`, `notes`, `description`,
`ordinal`, `from_spec`, `proposed`, `applies_to`, `required_when`, ...) is
documentation: for the human reviewing the vocabulary and for the E2.1/E2.2
classifier prompts. `engine.terms` has no column for it (see "Proposed DDL").

## Modelling decisions

- **`type` and `subtype` are two facets.** §4 lists them as two required,
  single-cardinality facets, and the exclusion filter (§8.A) must read a
  clean enum. Each `subtype` term's `parent_id` points at its `type` term —
  a cross-facet parent, allowed by the DDL and enforced by the loader.
  `terms/type.json` holds both levels (`children_facet: subtype`).
  §4's own eight L1 types are editorial content; **F49 (PROGRESS.md) adds a
  ninth, `unknown`** — a technical sentinel with no `subtype` children, used
  by the loader/classifier pipeline for a place that has not been
  classified yet (`exclude_same=true`, zero complements in
  `type_relations.json`, so it fails closed regardless of `status`, unlike
  the old `editorial`/`city-guide` loader sentinel it replaces). Nothing
  should carry `type=unknown` at launch — E2.1/E2.3 reclassify every row
  wearing it into a real type.
- **Slugs are unique per facet** (`uq_terms_facet_slug`), so: `stay/boutique`
  is `boutique-hotel` (vs `shop/boutique`); Jakarta and Bali districts are
  `south-jakarta` / `south-bali` (also the clean `/{section}/{area}` URL
  segment); the proposed participatory-sport subtype is `sports-activity`
  (vs `event/sports`).
- **`location` has a real root.** `indonesia` is a term so nationwide pieces
  have a node; `international` is a *proposed* second root for the 115
  World Traveller / Travel articles about destinations abroad (`location`
  is a required facet, so they need one).
- **`price_band` slugs are words** (`budget`, `moderate`, `upscale`,
  `luxury`); labels are `$`..`$$$$`. Ordinal is documented in the file.
- **Dietary needs are amenities, not cuisines** (`halal-certified`,
  `vegetarian-friendly`, `vegan-options`), matching §8.B party constraints.
- **Topics overlap editorial subtypes on purpose.** `type/subtype` says what
  kind of thing an article is about; `topic` tags the subject so a hotel
  article can also carry `sustainability`.
- **Anything beyond §4 is marked `"proposed": true`** and listed for
  sign-off in `jakarta/site/taxonomy-mapping.md`. It is seeded so the
  classifier enum and the review can see the full tree; nothing references
  these terms yet, so striking one before E2.1 runs is a one-line deletion
  in the seed file plus `DELETE FROM engine.terms WHERE ...`.

## Seeding semantics (what `now_db.provisioning` guarantees)

- **Idempotent and countable.** Facets and terms are upserted with a
  guarded `ON CONFLICT ... DO UPDATE ... WHERE <something changed>`, so an
  unchanged row is not rewritten. A second run reports `+0 ~0`.
- **Additive.** The seed never deletes. Renaming a slug in the file creates a
  new term and leaves the old one in place — remove it by hand once nothing
  in any city's `entity_terms` references it (cross-database, so no FK will
  stop you; check first).
- **`geo` is fill-only.** `COALESCE(existing, seed)`: the seed's approximate
  centroid never overwrites a refinement written by E2.5 or an editor.
- **`type_relations` is back-fill-only** (`DO NOTHING`). Every L1 `type`
  term present in the platform gets a row in every city; a type with no
  entry in `type_relations.json` gets the strict default (`exclude_same =
  true`, no complements). To change an existing site's policy, `UPDATE` its
  row. A complement naming a type outside the vocabulary fails the run.
- **Decay defaults are write-once per site.** Tune a site by editing
  `sites.ranking_weights->'decay'`; the seed will not touch it again.
- **`terms.embedding` is never written here** and no embedding API is
  called from this package (E1.4 brief).

Run it: `now-db create <slug> ...` or `now-db migrate --all`. There is no
separate seed command — E0.2's handover asked for one seeding path, and
`site:create` is it. Programmatic entry points, if a later CLI wants them:
`now_db.provisioning.seed_platform_taxonomy()`, `seed_city(dsn)`,
`seed_site_decay_defaults(slug)`, `load_taxonomy_seed()` (validation only).

## Contracts for downstream waves

- **E2.1 classifier** — enums come from the platform DB, not from this
  package: `type` (9, including the `unknown` sentinel added by F49 — the
  classifier should never *output* `unknown`, only replace it),
  `subtype` (grouped by `parent_id`), `format`, `location` (the tree). Use
  the `aliases` in the seed files for the prompt. The WP-category prior is
  `jakarta/site/taxonomy-mapping.json`.
- **E2.4 embeddings** — the hand-off query is
  `now_db.provisioning.TERMS_MISSING_EMBEDDINGS_SQL`
  (`... WHERE embedding IS NULL`, returns facet, slug, label, parent label).
  Suggested text to embed: `"{facet}: {label}"`, with `" ({parent_label})"`
  appended for `subtype` and `location`. Write back by `id`; the partial
  HNSW index `ix_terms_embedding_hnsw` picks rows up as they fill.
- **E3.2 filter pipeline** — exclusion reads `engine.type_relations` in the
  city DB; the L1 type of an entity is its `type`-facet term. Never the
  partnership tier.
- **E3.3 blender** — `SiteConfig.ranking_weights["decay"]["formats"][format]`
  gives `{half_life_days, evergreen, hard_expiry?}`; fall back to
  `["decay"]["default"]`. `half_life_days: null` + `evergreen: true` = no
  decay; `offer` has no half-life and expires at `campaign.ends_at`.
- **E3.5 Row 1** — price-band order is the `ordinal` in
  `terms/price_band.json` (1..4) until a DDL home exists.

## Proposed DDL (for the schema owner — not done here, E1.4 owns no migrations)

1. `engine.terms.attrs jsonb NOT NULL DEFAULT '{}'` — a home for per-term
   attributes that today live only in these files: price ordinal, aliases
   (useful to the classifier at runtime), `proposed` flag, geo provenance.
2. `engine.sites.location_term_id uuid REFERENCES engine.terms(id)` — the
   site's home node in the location tree, so the classifier's "no explicit
   location" fallback is a `sites` column (§3.5), not a slug-equality
   convention (`sites.slug == terms.slug`, which happens to hold for
   `jakarta` and `bali` today).

## Packaging follow-up

`now_db.provisioning` resolves `seed/` relative to the source checkout
(`REPO_ROOT/engine/packages/taxonomy/seed`), exactly as `scaffold_site_dirs`
already does. When `now-db` is installed non-editable (F1 — container
images), either set `NOW_TAXONOMY_SEED_DIR` or turn this directory into a
tiny installable package whose only job is to ship the JSON. One-line change
in `engine/packages/db/pyproject.toml`; not done here because that file is
outside E1.4's ownership.
