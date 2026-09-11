# now-loader — E1.8

One-shot JSONL (E1.1 extraction contract, `jakarta/content/extracted/*.jsonl`)
-> city DB `public` loader. Idempotent, legacy-id-keyed where the schema
provides a natural key; a small self-owned SQLite ledger where it doesn't
(`events` — see `now_loader/ledger.py`).

Direct SQL via SQLAlchemy `text()`, not Payload's local API. See "Why
direct SQL" below.

## Usage

```bash
cd engine/packages/loader
uv venv .venv && uv pip install -e ".[dev]" -p .venv/Scripts/python.exe

export NOW_PG_PASSWORD=...   # matches docker-compose's POSTGRES_PASSWORD
export NOW_PG_PORT=15432     # host-mapped port (see docker-compose.yml)

# Full load (idempotent — safe to re-run)
.venv/Scripts/python.exe -m now_loader.cli load \
    --city now_jakarta \
    --input-dir ../../../jakarta/content/extracted

# Just one stage, or a smoke-test subset
.venv/Scripts/python.exe -m now_loader.cli load --city now_bali \
    --input-dir ../../../jakarta/content/extracted --only articles --limit 50

# Round-trip verification (body_blocks field-by-field, facet-NULL guard)
.venv/Scripts/python.exe -m now_loader.cli verify \
    --city now_jakarta --input-dir ../../../jakarta/content/extracted --sample 100
```

`--city` is a bare `db_ref` (`now_jakarta`, `now_bali`, `now_test`, ...) or
a full DSN. Nothing in this package's code contains a site-name literal —
see the CI lint at `.github/workflows/engine-api-tests.yml` ("Zero
site-name literals..."), which this package passes.

Load order (`STAGES` in `cli.py`): `authors -> media -> articles -> places
-> events` — later stages consume the wp_id maps earlier stages return
(author_id / hero_media_id / place_id foreign keys).

## Why direct SQL, not Payload's local API

1. **Volume.** 4,772 articles + 13,817 media + 82 authors + 177 places +
   837 events, run twice for the idempotency proof plus once against
   `now_bali` for the genericity proof during this ticket alone — Payload's
   per-document local-API overhead (validation, hooks, versions) is the
   wrong tool for a batch backfill at this size.
2. **`enforcePublishRole`** (`engine/packages/cms/src/hooks/enforcePublishRole.ts`)
   requires an authenticated editor/admin `req.user` to move an article to
   `_status = 'published'`. A migration script has no such session; standing
   up a service admin user purely to satisfy this gate is more moving parts
   than the problem warrants.
3. **`publishArticleEvent`** (afterChange hook) would emit `article.published`
   to Redis once per article — semantically wrong for a backfill (nothing
   was "published" by an editor at this moment) and downstream consumers
   (`engine-worker`) aren't part of this wave anyway.
4. **Idempotent upserts are natural in SQL** (`ON CONFLICT ... DO UPDATE`)
   and map directly onto the acceptance criterion ("run twice, second run
   updates rather than duplicating").
5. This loader still respects Payload's schema **exactly** — every column
   name, type, enum, and constraint below comes from reading the actual
   shipped migration
   (`engine/packages/cms/src/migrations/20260908_131927_initial_schema.ts`)
   and cross-checking against a live `\d <table>` on `now_jakarta`, not
   from ARCHITECTURE.md's §5 sketch (which is close but not
   byte-identical — see the places.hours/amenities note, F21).

## Idempotency keys, table by table

| table | key used | why |
|---|---|---|
| `articles` | `legacy_wp_id` | `UNIQUE` index, exactly as the ticket brief says |
| `authors` | `slug` (**not** `legacy_wp_user_id`) | `legacy_wp_user_id` is only a plain (non-unique) index in the schema E1.6 actually shipped — see `load_authors.py` docstring |
| `media` | `filename`, computed as `f"{wp_id}-{basename(file)}"` | bare basenames collide 164x across the 13,817 attachments; even the full relative path still collides 17x. `wp_id` is verified unique. |
| `places` | `slug`, de-duplicated as `f"{slug}-{wp_id}"` on collision | 7 of 177 venues share a slug with another venue in the source (real WP duplication) — E1.8 does not dedupe (that's explicitly E2.3's job), so every source row keeps its own place row |
| `events` | none in the schema — `now_loader/ledger.py` (SQLite, `(city, wp_id) -> events.id`) | `events` has no legacy-id column and no other unique business key at all |

## Two decisions this ticket explicitly authorized the loader to make (and state, not swallow)

### 1. The 508 undated events (F12)

490 `upcoming-events` + 18 `tribe_events` have no occurrence date, only a
publish date. **Decision: load them, don't skip them.** `starts_at`/`ends_at`
are left `NULL` (the column allows it; no date is invented) and `_status`
is forced to `'draft'` regardless of the source WP status, because a
"published" event that can never resolve `ends_at` would silently break
the event-expiry hard filter (ARCHITECTURE.md §8.A) and any listing UI that
assumes a published event has a date. Find them with:

```sql
SELECT id FROM events WHERE starts_at IS NULL;  -- 508 rows
```

### 2. `places.type`/`places.subtype` are `NOT NULL` — in direct conflict with "leave facets NULL"

Confirmed against the live schema: unlike `articles.primary_type`/`format`
(nullable — Articles supports Payload drafts, so required-field validation
is deferred), `Places.ts` deliberately does **not** use `versions.drafts`
(enum collision, per its own code comment), so Postgres enforces
`type`/`subtype` as mandatory on **every** row. There is no NULL available,
and `venues.jsonl` carries no category/type signal at all (name, slug,
address, city/state/province/country, phone, url — nothing else) to
classify from without guessing.

**Decision: insert every venue-derived place with an explicit sentinel** —
`type = 'editorial'`, `subtype = 'city-guide'`, `status = 'pending_review'`
(overriding the column's own `'active'` default). `editorial` is the one
L1 type whose `type_relations.exclude_same = false` (ARCHITECTURE.md §4),
so it can never wrongly assert a venue is a competitor to a real
hotel/restaurant/bar, and `pending_review` keeps it out of anything that
filters on `status = 'active'`. **This is a placeholder, not a
classification — E2.3 must overwrite it before a venue-derived place goes
live.** Find them with:

```sql
SELECT id, name, slug FROM places WHERE status = 'pending_review';  -- 177 rows
```

Re-running the loader after E2.3 (or a human editor) sets a real
type/subtype/status is safe: the `ON CONFLICT` clause for `places` only
touches `name`/`address`/`area_term`/`updated_at` — it never rewrites
`type`/`subtype`/`status` on an existing row, so a reclassified place
cannot be stomped back to the sentinel by a later loader re-run. Verified
directly (see final report).

## A gap this loader found and did not paper over: `events` has no content columns

`events` (ARCHITECTURE.md §5 / `Events.ts`) has exactly five business
columns: `place_id, starts_at, ends_at, rrule, ticket_url`. The 837 source
rows (`events.jsonl`) all carry a title, rich `content_html`, an excerpt
and a thumbnail — none of that has anywhere to go in the current schema,
and there is no FK from `events` back to an `articles` row. This loader
writes every column the schema actually has; the title/body/image content
of all 837 event write-ups is not persisted anywhere in `public` as of
this load. That is a schema decision for an architect/senior-db (add
`events.legacy_wp_id` + either `events.article_id` or title/body columns
directly), not something this loader may improvise — flagged in the final
report, not worked around here.

## Exactly how E1.3 should rewrite `media_ref` once Garage migration lands

Right now `media.url` and every `media_ref` value inside `articles.body_blocks`
point at the original `nowjakarta.co.id` WordPress URLs. The recipe:

1. **Upload.** For each `media` row, fetch `url`, upload it to Garage,
   record the new object key/URL.
2. **Update `media.url`** to the new Garage/imgproxy URL (`UPDATE media SET
   url = :new_url WHERE id = :id`). `filename` should NOT change — it's
   this loader's idempotency key (`{wp_id}-{basename}`) and is unrelated
   to storage location.
3. **Rewrite `body_blocks`.** `media_ref` is an inline URL string inside a
   `jsonb` array, not a foreign key — it must be rewritten with a
   tree-walk-and-replace over every article, not a column UPDATE. Build a
   `dict[old_url, new_url]` from step 1/2, then for each article:
   `blocks = article.body_blocks; walk(blocks, replace media_ref/href
   values found in the map); UPDATE articles SET body_blocks = :blocks
   WHERE id = :id` (the walk must recurse into `gallery.images[]` and
   `columns.columns[][]`, matching how `content-clean` nests those types).

   Do **not** match on the exact original URL string alone — verified
   against the loaded corpus (9,228 inline upload references across 4,772
   articles): only 5,513 (59.7%) exact-match `attachments.jsonl`'s `url`
   field.
     - 183 are the *same* file referenced via a different scheme/host
       (`http://` vs `https://www.`) — recoverable by normalizing
       `re.sub(r'^https?://(www\.)?', '', u)` before matching.
     - 3,359 are same-domain but the **path itself differs** even after
       normalization — spot-checked and traced to attachments whose
       cataloged `file` path (e.g. `2022/07/...`) doesn't match the
       upload-date path baked into the old post content
       (e.g. `2016/12/...`), and to WordPress's own numbered-duplicate
       (`-6`, `-5`) and responsive-size (`-150x150`) filename suffixes
       that don't have their own `attachments.jsonl` entry. **Match by
       basename with the size/number suffix stripped
       (`re.sub(r'-\d+(x\d+)?(?=\.\w+$)', '', basename)`) as a second
       pass**, not by full path or exact URL.
     - 173 are genuinely external domains (other sites' own
       `wp-content/uploads`, e.g. embedded press content) — correctly not
       ours to rewrite; leave as-is.
4. **Verify** with this ticket's `verify` command's approach (field-by-field
   `jsonb` comparison) re-pointed at the new URLs, not a string diff.

## Tests

`tests/` covers the pure-logic pieces (series-key derivation, slug/text
utilities) with `pytest`. The loader's actual correctness claim — upserts
match the live schema, idempotency holds, `body_blocks` round-trips,
facets stay NULL — is verified against real `now_jakarta`/`now_bali`
Postgres instances (two full runs each, `now-db check`, a 100-article
random-sample round-trip) rather than mocked, per this ticket's own
instruction to verify with real SQL output. See the final report for the
transcripts.
