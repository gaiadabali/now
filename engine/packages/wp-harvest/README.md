# wp-harvest

Read-only harvest of a **live** WordPress site's REST API → JSONL.

Companion to [`wp-extract`](../wp-extract/README.md), not a replacement.
The two exist because they answer different questions:

| | `wp-extract` | `wp-harvest` (this package) |
|---|---|---|
| Source | UpdraftPlus dump restored into throwaway MariaDB | live site, `/wp-json/wp/v2` |
| Fidelity | **complete** — raw `post_content`, all `postmeta`, all statuses | public projection only |
| Reaches | whatever the dump contains | whatever the site serves *now* |
| Answers | "what is in this archive?" | "what is true on production today?" |

Use `wp-extract` for the migration of record. Use `wp-harvest` when only the
live instance has the answer: the authoritative media URL set, the published
URL set for a redirect audit, and a site with no dump yet.

Every command issues **GET requests only**. There is no method in this
package that writes, so a bug here cannot modify the source site.

## Why it exists

Four things were blocked on data only the live sites hold:

- **Blocker #2 — uploads listing.** `media` exposes `source_url`,
  `media_details.file` and every registered size variant. That is a complete
  file manifest, and a better one than the dump gives.
- **F11 — `guid` is not a download URL** for ~20% of Jakarta's attachments
  (it points at a different host). `source_url` is the real one, so rows
  carry both and the loader is told which to fetch.
- **F29 — inline media matched only 59.7% by exact URL.** Each row now
  carries `match_keys`: the exact path, the `uploads`-relative path, the
  basename, and the basename with WordPress's `-150x150` size and `-6`
  duplicate suffixes stripped. Try them in order, stop at the first hit.
  Measured: this lifts **Bali to 96.7%** and cuts Jakarta's genuine
  `wp-content/uploads` misses from ~3,359 to **14**. Jakarta still only
  reaches 58.3% overall, because 6,161 of its refs point at a **second,
  pre-WordPress CKEditor media store** with no media-library rows — not a
  matching problem, a missing-corpus problem (F34). See
  [LIVE_RECON.md](../../../LIVE_RECON.md) §3.
- **F16 — live-URL verification was inconclusive** (38% of a 50-URL sample
  timed out). `verify` set-compares the whole stored permalink map against
  the live sitemap — no sampling, no timeouts to explain away — and spends
  HTTP requests only on the URLs that comparison flags.

## Usage

Base URLs are **never** hardcoded (ARCHITECTURE.md principle 7). Supply one
per site via `--base-url` or `WP_HARVEST_BASE_URL_<SLUG>`.

```bash
uv sync

export WP_HARVEST_BASE_URL_JAKARTA=https://www.example.co.id

# What is there? 8 requests, downloads nothing.
uv run wp-harvest inventory --site jakarta

# Everything, resumable.
uv run wp-harvest harvest --site jakarta

# One collection.
uv run wp-harvest harvest --site jakarta --only media

# Every published URL, from the site's own sitemap.
uv run wp-harvest sitemap --site jakarta

# F16: exact comparison, then HTTP-check only what the comparison flags.
uv run wp-harvest verify --site jakarta \
    --against ../../../jakarta/content/extracted/permalink_map.jsonl \
    --field legacy_url --http-check -1
```

Output goes to `<slug>/content/harvested/` — deliberately **not**
`extracted/`, so the dump-derived truth is never overwritten by a
lower-fidelity live projection.

### Collections

| Key | Endpoint | File | Shape follows |
|---|---|---|---|
| `categories` | `categories` | `categories.jsonl` | `extracted/terms.jsonl` |
| `tags` | `tags` | `tags.jsonl` | `extracted/terms.jsonl` |
| `users` | `users` | `users.jsonl` | `extracted/users.jsonl` |
| `posts` | `posts` | `articles.jsonl` | `extracted/articles.jsonl` |
| `pages` | `pages` | `pages.jsonl` | `extracted/articles.jsonl` |
| `events` | `upcoming-events` | `events.jsonl` | `extracted/articles.jsonl` |
| `media` | `media` | `attachments.jsonl` | `extracted/attachments.jsonl` |
| `comments` | `comments` | `comments.jsonl` | — |

Field names match the extract's on purpose, so the two sources can be
diffed directly. Live-only fields (`source_url`, `sizes`, `match_keys`,
`filesize`, `content_is_raw`) are additive.

### Options

| Flag | Default | Purpose |
|---|---|---|
| `--delay` | `0.35` | pause between requests |
| `--timeout` | `45` | per-request timeout |
| `--resume` / `--restart` | resume | continue from the saved page cursor |
| `--context` | `view` | `edit` returns raw `post_content`; needs auth |
| `--only` | all | comma-separated subset |

The default delay is slower than necessary on purpose. F16 attributed 38% of
a live check's timeouts to rate limiting without proving it; this package
would rather take four minutes than reproduce that ambiguity. Note that both
NOW! sites share one host, so harvest them **sequentially**.

## Design notes

**Pagination is ordered by ascending id, not the WordPress default.** The
default is `date desc`, which reshuffles under pagination if anything is
published mid-harvest — page 20 of a 260-page media walk would then skip or
repeat rows. Ascending ids are append-only: a row created mid-harvest lands
at the end. This is also why `complete` is `unique_ids >= reported_total`
rather than `==`.

**Every page is resumable.** A page is fsynced, *then* the cursor advances.
A crash between those two points leaves extra lines on disk, so a resume
trusts the cursor and truncates the excess — the file is always exactly
consistent with the cursor.

**Retries are narrow.** 429 and 5xx (and timeouts) back off exponentially and
honour `Retry-After`. 401/403/404/400 are real answers and surface at once
rather than being hammered.

## What a harvest does not contain

Read this before treating one as migration-complete:

- **Unregistered postmeta.** REST returns only meta a plugin registered with
  `show_in_rest`. **Yoast focus keywords, MapPress geo and most ACF field
  data live in `postmeta` and do not appear here.** Those need a dump.
- **Non-public statuses.** Anonymous callers see `publish` only — no drafts,
  no `private`, no revisions.
- **Rendered vs raw content.** Under `context=view`, `content_html` has been
  through `the_content`: shortcodes expanded, cache-plugin lazy-load
  attributes injected. Rows carry `content_is_raw: false` to say so.
  Only an authenticated `context=edit` harvest returns the real
  `post_content` column, which is what the Jakarta content cleaner was
  measured against.
- **The files themselves.** `attachments.jsonl` is a manifest of URLs and
  sizes, not a copy of `wp-content/uploads`.

A site whose content is being migrated for real needs a database dump. This
package closes the gap in the meantime, and states exactly where the gap is.

## Tests

```bash
uv run pytest
```

75 tests, no network: the collection endpoints are stood up with
`httpx.MockTransport`, and the projections are tested against trimmed copies
of real responses so the envelope shapes (`{"rendered": …}`,
`media_details.sizes`) are the actual ones.
