# now-embeddings (E2.4)

Provider-abstracted embeddings for `engine.embeddings` (ARCHITECTURE.md §7
"Row 3 similar", §10 "cheap model for batch tagging and embeddings"). Owns
`engine/packages/embeddings/**` and, because the shipped provider's
dimension did not match the 1536-dim baseline, one migration:
`engine/packages/db/src/now_db/migrations/versions/0004_embeddings_local_provider_fix.py`.

## Provider investigation (do this before trusting any number below)

The task required checking, in order, for a real embedding provider before
building an offline stand-in.

**1. Ollama Cloud (the configured shared "brain")** — checked directly,
not assumed:

```bash
curl -s https://ollama.com/v1/models -H "Authorization: Bearer $OLLAMA_CLOUD_API_KEY"
# -> chat models only: kimi-k2.7-code, glm-5.x, deepseek-v4-*, gpt-oss, qwen3.5, ...
# no nomic-embed-text, no mxbai-embed-large, nothing embedding-shaped.

curl -s -X POST https://ollama.com/v1/embeddings -H "Authorization: Bearer $OLLAMA_CLOUD_API_KEY" \
  -H "Content-Type: application/json" -d '{"model":"nomic-embed-text","input":"hello world"}'
# -> {"error":"path \"/v1/embeddings\" not found"}
# same result for a real chat-model name. The cloud tier exposes no
# embeddings route at all -- this is not a missing-model error, it's a
# missing-endpoint error.
```

**Verdict: no embeddings endpoint. Ollama Cloud is not usable for this
task**, full stop -- not "usable but rate-limited."

**2. A local model** — available, no key needed. Chose `fastembed`
(ONNX Runtime) over `sentence-transformers` (PyTorch) specifically because
`pip install torch` on Windows without an explicit `--extra-index-url
.../cpu` pulls the CUDA build (multi-GB) even with no GPU present.
`fastembed` is a ~15 MB CPU-only dependency for the same class of model
(HuggingFace weights exported to ONNX, int8-quantized).

**3. Offline/deterministic fallback** — built anyway
(`providers/offline.py`), because it's what CI and unit tests use
regardless of what's available in a given environment. It is **not** a
substitute recommender; see "Honesty about the two providers" below.

## The dimension decision — migration 0004

`engine.embeddings.vec` shipped as `vector(1536)` (an OpenAI-family
assumption baked in before any provider existed). The real provider
(`BAAI/bge-small-en-v1.5`, chosen below) is 384-dimensional. Padding a
384-dim vector to 1536 with zeros, or truncating a hypothetical 1536-dim
vector to 384, would both corrupt cosine similarity -- neither is a
defensible substitute for "the column matches the model that actually
produced the numbers." So migration `0004` changes the column instead:

| Column | Before (0001) | After (0004) | Why |
|---|---|---|---|
| `entity_id` | `uuid NOT NULL` | `text NOT NULL` | `public.articles.id` / `public.places.id` are Payload integer PKs, not uuids -- the *same class of bug* PROGRESS.md's C4 found for `interactions.entity_id`, fixed the same way (widen, don't hash) |
| `vec` | `vector(1536)` | `vector(384)` | matches the real provider; see investigation above |
| `dim` | *(new)* | `integer NOT NULL`, `CHECK (dim = vector_dims(vec))` | explicit, audit-friendly per-row dimension, redundant with `vector_dims(vec)` by design so a future reader never needs to introspect pgvector internals |
| `text_hash` | *(new)* | `text NOT NULL` | idempotent re-embed key, see below |

**Why one column and not a second `vec_1536` column, or a table per
model/dimension**: no second model exists yet. Speculatively adding a
sibling column or a per-dimension table for a dimension nothing writes to
would be schema guesswork. `model` (already part of the primary key) plus
the new `dim` column together make *that* decision, if it's ever needed,
a data-driven migration rather than an archaeology pass — the exact
property the task asked for. **This does mean**: if a second embedding
model at a *different* dimension ever needs to coexist with
`BAAI/bge-small-en-v1.5` (e.g. a real OpenAI-family key eventually
appears), pgvector's one-fixed-dimension-per-column rule means `vec`
cannot hold both — a sibling column or a second table becomes necessary at
that point, and is deliberately not built now. See "Notes for E3.1" below.

Migration 0004 refuses to run against a populated `engine.embeddings`
table (verified empty on all three city DBs before this migration ran —
see "Verification" below) — it is a pre-data schema correction, not a
general-purpose resize.

## Where term embeddings live, and why

`now_platform.engine.terms` already has its own `embedding vector(1536)`
column (`platform-db`'s baseline migration) — but `platform-db` is out of
this task's ownership (`engine/packages/{cms,loader,geocode,eval,quality,
content-clean,qa-verification}/` are listed as off-limits, and
`platform-db` isn't even in that list — it simply isn't in scope either,
and touching another package's Alembic set this wave would violate
PROGRESS.md's "Alembic is single-threaded" rule for a package this task
was never assigned). Writing a 384-dim vector into a `vector(1536)` column
fails outright (pgvector enforces the declared dimension), so that column
cannot be populated without a `platform-db` migration this task does not
own.

**Decision**: term embeddings are written into the *city* DB's
`engine.embeddings` (the table this task does own), keyed
`entity_type='term'`, `entity_id=<platform term uuid>`. This means term
embeddings are currently duplicated per city rather than shared once in
the platform DB — acceptable for the 267-term vocabulary at this wave's
scale, and it keeps every real row this task writes inside the schema this
task actually controls. **Flag for the architect / senior-db seat**:
`now_platform.engine.terms.embedding` is now a stale, always-NULL 1536-dim
column with no writer — either drop it or resize it to 384 (or whatever
model E3.1 standardizes on) in a `platform-db` migration; that decision
belongs to whoever owns that package, not here.

## Why `BAAI/bge-small-en-v1.5` (384-dim), not `bge-base-en-v1.5` (768-dim)

Measured, not guessed, in this sandboxed dev environment:

| Model | Dim | ~time per ~1,200-char article text |
|---|---|---|
| `BAAI/bge-base-en-v1.5` | 768 | ~2.0-2.5s |
| `BAAI/bge-small-en-v1.5` | 384 | ~0.3-0.5s |

Roughly 5x faster for a well-regarded, widely-used small English embedding
model (strong MTEB showing for its size class). At ~5,200 embeddable rows
(4,772 articles + 177 places + 267 terms), that difference is the whole
backfill finishing in well under an hour vs. several hours — and matters
even more for the *recurring* cost: E2.1 will fill facets on every
article, and every article must be re-embedded once it does (this
pipeline is built for that from day one — see "Idempotent re-embedding"
below). Content is English-only for v1 (ARCHITECTURE.md §18 decision 5),
so an English-only model loses nothing relevant.

## Idempotent, resumable re-embedding

`text_hash` (sha256 of the exact string built by `textbuild.py`) is the
whole mechanism:

1. `backfill` fetches every row's current text and hash.
2. It diffs against `engine.embeddings.text_hash` for that `(entity_type,
   model)`.
3. Only rows whose hash differs (new entity, or changed text) go to the
   model at all.
4. Each batch commits independently — killing the process mid-run loses
   at most one in-flight batch; re-running recomputes the diff fresh and
   picks up exactly where it left off, with no separate checkpoint file.

**Facets are NULL today** (E2.1 is blocked on a human taxonomy review).
`textbuild.build_article_text` already accepts `primary_type`/`format`/
`facet_labels` and folds them into the hashed text when present. The day
E2.1 populates them, every affected article's hash changes automatically,
and the next `now-embeddings backfill` run re-embeds exactly those rows —
no code change, no manual "which rows need it" bookkeeping.

Verified directly (see "Verification" below): a second `backfill` run
against already-embedded rows reports `embedded=0`, `skipped_unchanged=N`.

## Re-embed on publish (the worker)

`worker.py` consumes `article.published` / `article.republished` /
`place.published` / `place.republished` off the Redis **Stream**
`now:domain-events:stream` — the exact contract
`engine/packages/cms/src/lib/redis.ts` emits (read-only; not owned or
edited by this task). Stream + a consumer group (`XREADGROUP`/`XACK`),
not pub/sub, because pub/sub only delivers to a subscriber connected *at
publish time* — a restarting/deploying worker loses the message forever.
A consumer group resumes from exactly where it left off, which is this
package's answer to "resumable" for the live path (as `text_hash` is the
answer for the bulk path).

Routing is generic: the event's `site_slug` is looked up against
`now_platform.engine.sites` (`now_db.sites_registry.get_site`) to resolve
which city DB to write to — no `if site == 'jakarta'` anywhere
(ARCHITECTURE.md §3.5).

**Not implemented this wave** (flagging honestly): `XCLAIM`/`XPENDING`
reclaim of a message whose consumer crashed *after* `XREADGROUP` but
*before* `XACK`. `run_once`/`run_forever` ACK unconditionally after
attempting a message (success or logged error) specifically so one
malformed message can't wedge the group forever, but a hard process kill
mid-message would currently leave that one message pending and
unreclaimed until an operator runs a manual `XCLAIM`. Worth adding before
this worker is a hard production dependency; not blocking for E2.4.

## Honesty about the two providers

- **`local` (`BAAI/bge-small-en-v1.5`, via `fastembed`) is the real
  provider.** All acceptance-criteria numbers in the task report use this
  provider. Nearest-neighbour results computed from it are a genuine, if
  v1-scoped, semantic signal.
- **`offline` (`providers/offline.py`) is a deterministic hash-based unit
  vector with zero semantic content**, used only for tests/CI (see
  `tests/`) and to validate the pipeline's wiring before spending real
  model time. Its rows carry `model='offline-deterministic-v1'` and can
  never be confused with real rows (different primary key). **Nearest
  neighbours computed from it are meaningless** and this README does not,
  and must not, present them as evidence of recommender quality.

## Truncation, stated plainly

`BAAI/bge-small-en-v1.5` has a 512-token context window; the archive's
median article is ~4,800 characters. `textbuild.py` embeds
`title + dek + type/format (if present) + body[:1600 chars]` — an explicit,
inspectable truncation point, not whatever the tokenizer happens to cut at.
**Consequence**: content past the first ~1,600 characters of body text
does not influence an article's embedding. For a magazine that
front-loads its topic in the opening paragraphs, this is a reasonable v1
trade-off — but it is a real limitation, not a hidden one. Revisit
(chunk + mean-pool, or a long-context model) if Row 3 "similar" quality
ever looks like it's missing content that only appears deep in an article.

## Usage

```bash
# Backfill everything in one city (idempotent -- safe to re-run)
now-embeddings backfill --city now_jakarta --provider local

# Just articles, smaller batches
now-embeddings backfill --city now_jakarta --entity-type article --provider local --batch-size 16

# kNN against an already-embedded entity, with measured latency
now-embeddings knn --city now_jakarta --entity-type article --entity-id 13 --k 6 --provider local --runs 10

# Human-readable nearest-neighbour report (5 evenly-spread real articles by default)
now-embeddings sanity-check --city now_jakarta --provider local

# Consume whatever's pending on the domain-events stream, once, then exit
REDIS_URL=redis://:<password>@localhost:16379/0 now-embeddings worker --provider local --once

# Run forever (the real deployment mode)
REDIS_URL=redis://:<password>@localhost:16379/0 now-embeddings worker --provider local
```

Env vars (matching `now-db`'s existing convention, nothing new):
`NOW_PG_HOST`/`NOW_PG_PORT`/`NOW_PG_USER`/`NOW_PG_PASSWORD` (defaults
`localhost`/`5432`/`now`/`now` — this host remaps Postgres to `15432`, see
PROGRESS.md F3), `NOW_PLATFORM_DATABASE_URL` (full DSN override), `REDIS_URL`
(worker only, no default password baked in — must be supplied).
`NOW_EMBEDDING_MODEL` selects the model (below); unset means the default.

## Changing model (WS6)

Which model is live is decided in one place, `now_embeddings/models.py`:
`REGISTRY` lists what this package can run, `DEFAULT_MODEL` is
`BAAI/bge-small-en-v1.5`, and the `NOW_EMBEDDING_MODEL` env var overrides
it. The backfill, the worker (`_provider("local")`), search's query
embedder and the web tier's Read Next query (`apps/web/src/lib/
embeddingModel.ts`, which reads the same env var) all resolve through it;
`tests/test_models.py` fails if the web fallback literal drifts from
`DEFAULT_MODEL`. The classifier's centroid routing and the calibration
measurements are deliberately *pinned* to the model their artifacts were
built with, not switched — see that test file for why.

WS6 measured whether a multilingual or larger model is worth switching to;
the numbers and the decision are in `docs/EDITION-2-PLAN.md`, "WS6 —
Embeddings". The tooling that produced them:

```bash
uv sync --extra dev --extra model-eval
uv run python scripts/measure_corpus_language.py --out report.json --focus-keywords <slug>=<articles.jsonl>
uv run python scripts/compare_embedding_models.py make-slice|dump-texts|embed|eval-search|eval-related|label-pool|score-labels|latency ...
uv run python scripts/bench_embedding_models.py --db-ref <city db> --model <m> [--model <m> ...]
```

To roll a model out (it must be registered and 384-d — `engine.embeddings.vec`
is `vector(384)`; anything wider needs a migration first):

```bash
uv run python scripts/rollout_embedding_model.py backfill --model <m>   # new rows, keyed by model; old rows untouched
uv run python scripts/rollout_embedding_model.py check --model <m>      # exits non-zero on any coverage gap
# then set NOW_EMBEDDING_MODEL=<m> on web, engine-api and worker, and rebuild
# the classifier centroids (see the script's docstring)
```

Rollback is unsetting `NOW_EMBEDDING_MODEL`. One caveat, stated plainly:
while the new model is live the worker embeds new and republished articles
under the new model only, so an article published during that window has no
row under the old one until `now-embeddings backfill --model <old>` is run
after the rollback (its Read Next rail is empty until then, not wrong).

## Notes for E3.1 (hybrid search)

- The HNSW index (`ix_embeddings_hnsw`, `vector_cosine_ops`) is already in
  place and rebuilt at the new 384-dim width by migration 0004. E3.1's
  `pgvector` half of the RRF fusion can query it directly:
  `ORDER BY vec <=> :query_vec LIMIT :k`, filtered by `entity_type` and
  `model` first (both are part of the primary key, so this is a fast
  equality filter before the HNSW scan, not a post-filter).
- `model='BAAI/bge-small-en-v1.5'` must be part of every query — the table
  will, from the moment a second model or dimension is added, hold rows
  from more than one model. Never query `engine.embeddings` without a
  `model =` filter.
- Article embeddings are currently text-only (facets NULL). E3.1's hybrid
  fusion should expect embedding quality to improve materially once E2.1
  lands and the next backfill picks up facets automatically (see
  "Idempotent re-embedding" above) — don't tune RRF weights against
  today's embeddings as if they're final.
- Place embeddings are structured-field-only (no body prose) — see
  `textbuild.build_place_text`. They'll improve once E2.2 facet extraction
  fills `amenities`/`cuisine`/`vibe` for the 177 places currently at F27's
  sentinel type/subtype.

## What re-embedding costs after E2.1

Every article's `text_hash` will change the moment E2.1 writes
`primary_type`/`format`/facets (the hash is computed over the built text,
which includes those fields when present — see `textbuild.py`). That means
**the next backfill run re-embeds all ~4,772 articles again**, at the same
measured throughput as this run (see "Verification" for the real number).
There is no partial-credit path — a hash-based idempotency check is binary
by design (unchanged vs. changed), and "only the facets portion changed"
still changes the whole hashed string. This is a real, recurring cost
(minutes, not hours, at this model/throughput — see the real backfill
timing below) rather than a one-shot job, exactly as the task brief
specified it must be designed for.

## Verification

See the task's final report for real command output: row counts by model,
migration application across all three city DBs, the drift-gate result,
kNN latency measurements, the idempotent-rerun proof, and the 5-article
nearest-neighbour sanity check with an honest read of the results.
