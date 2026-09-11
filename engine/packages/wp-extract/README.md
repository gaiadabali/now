# wp-extract

One-shot WordPress (UpdraftPlus/MariaDB dump) → JSONL extraction for the
NOW! Jakarta migration (task **E1.1**). See `ARCHITECTURE.md` §6 for the
source analysis this package implements.

WordPress is a **migration source only** — this package never talks to a
live WP instance, never writes back to it, and is not meant to run more
than a handful of times total.

## What it does

1. Restores the UpdraftPlus dump into a throwaway MariaDB container
   (`docker/`), using MariaDB's own `docker-entrypoint-initdb.d` gunzip
   handling — not a hand-rolled parser. This is deliberate: a naive
   streaming parser desyncs on `nb15_term_relationships` (it sits right
   after ~223MB of `post_content`) and silently returns zero rows for it
   while everything else looks fine. Restoring into a real server and
   querying with SQL sidesteps that failure mode entirely.
2. Extracts articles, attachments, events, venues, taxonomy terms, users,
   redirects, and geo (MapPress + ACF `google_map`, PHP-deserialized) to
   newline-delimited JSON under `jakarta/content/extracted/`.
3. Writes `extraction_report.md` next to the JSONL — counts in vs out per
   entity, acceptance-criteria checks re-verified by direct SQL every run,
   and every known discrepancy against `ARCHITECTURE.md` §6 explained.

## Usage

```bash
# 1. Restore the dump into a throwaway container (port 13306 by default —
#    distinct from the main stack's Postgres on 15432).
SOURCE_DUMP=/path/to/backup.sql.gz scripts/restore.sh --fresh

# 2. Extract to JSONL.
uv sync
uv run wp-extract run
```

`--fresh` tears down the container + volume first. Omit it to re-run
against an existing restored volume (no-op restore, still re-verifies
counts). `scripts/restore.sh` defaults `SOURCE_DUMP` to the path given for
E1.1; override via the env var for a different dump.

Environment variables (all optional, sensible defaults for local dev):

| Var | Default | Purpose |
|---|---|---|
| `SOURCE_DUMP` | the E1.1 dump path in Downloads | dump to restore |
| `WP_EXTRACT_DB_PORT` | `13306` | host port for the throwaway MariaDB |
| `WP_EXTRACT_DB_ROOT_PASSWORD` | `wpextract_root` | throwaway root password |
| `WP_EXTRACT_DB_NAME` | `nowjakarta_wp` | database name |
| `WP_EXTRACT_SITE_HOME` | `https://www.nowjakarta.co.id` | used to build article permalinks and attachment URLs |
| `WP_EXTRACT_OUTPUT_DIR` | `<repo>/jakarta/content/extracted` | JSONL output location |

## Output contract (frozen — do not change without the consuming agent's sign-off)

`articles.jsonl`, `attachments.jsonl`, `events.jsonl`, `venues.jsonl`,
`terms.jsonl`, `users.jsonl`, `redirects.jsonl`, `geo.jsonl` — one JSON
object per line. Field shapes are documented inline in each
`src/wp_extract/extract/*.py` module and demonstrated in
`extraction_report.md`.

Known, investigated discrepancies against the `ARCHITECTURE.md` §6 figures
(e.g. 4,772 real published posts vs the 4,679 documented) are explained in
full in the generated report, not silently reconciled — see
"Known discrepancies" there.

## Teardown

```bash
cd docker && docker compose down -v
```

Removes the throwaway container and its volume. Nothing under
`jakarta/content/extracted/` is affected.
