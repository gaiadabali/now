# Data provenance: what's on disk but not in git (F48)

Written during the F48 pre-init audit (2026-09-09). Explains why the tree
under `jakarta/` and `bali/` has directories full of data that `git status`
will never show as untracked-and-worrying — they're gitignored on purpose,
and this is the reasoning plus the regen path.

## The pipeline

```
jakarta/db/dumps/wxr/*.xml   (raw WordPress export — production data)
        │  wp-extract / wp-harvest (engine/packages/wp-extract, wp-harvest)
        ▼
jakarta/content/extracted/*.jsonl   (parsed, normalized records)
jakarta/content/harvested/*.jsonl   (harvested via WP REST API, alt path)
        │  downstream packages (cms, blender, taxonomy, search, ...) read
        │  these JSONL files as their input
        ▼
engine/packages/cms, search, taxonomy, ...
```

Same shape under `bali/`, minus the `extracted/` stage (bali only has
`harvested/` today).

## What's ignored and why

| Path | Size (2026-09-09) | Ignored by | Why |
|---|---|---|---|
| `*/db/dumps/` | jakarta 87M+45M+, bali 145M | `.gitignore` (pre-existing) | Full copy of production WordPress content, including anything non-public in it. Never belongs in git history — history is forever, a scrub after the fact doesn't remove it from clones already made. |
| `*/content/extracted/` | jakarta 42M | `.gitignore` (added by this audit) | Derived from the dumps above. Regenerable, not source. |
| `*/content/harvested/` | jakarta 78M, bali 123M | `.gitignore` (added by this audit) | Same reasoning — derived, regenerable, and large. |

Combined, the derived JSONL alone is ~240MB. Added to the 280MB of raw
dumps, that's over half a gigabyte that would otherwise sit in the first
commit and in every clone thereafter.

## Why derived data is excluded, not just the raw dumps

The extracted/harvested JSONL is *not* a secret — it's already public
content published on jakarta/bali's live sites. The case against tracking
it is purely about repo hygiene:

- **Regenerable.** Every downstream package's README describes running the
  extractor/harvester against the dumps. Losing this data means re-running
  a documented command, not losing work.
- **Git doesn't shrink.** Once a 240MB blob lands in history, every future
  clone pays for it forever, even after the file is later deleted or
  replaced — unless someone does a history rewrite, which is its own
  can of worms on a shared repo.
- **It changes on every re-run.** As wp-extract/wp-harvest gets fixed
  (there is active work on exactly this — see PROGRESS.md F-series on
  wxr-extract/blender/taxonomy), the JSONL will be regenerated repeatedly.
  Tracking it would mean a 240MB diff-churn file in git blame for every
  extraction bugfix, which defeats the purpose of using git at all here.

**Counter-consideration, recorded for whoever revisits this:** every
downstream package (cms, search, taxonomy, blender, ...) reads this JSONL
as its actual input, and there is currently no committed fixture/sample
version for local dev or CI to run against without first running the full
extraction pipeline locally. If CI or a fresh clone needs to exercise those
packages end-to-end without network access to production WordPress, that's
a gap — the fix should be a *small, curated fixture* (a few dozen records)
checked into each package's `tests/fixtures/`, not committing the full
production-sized JSONL. Several packages already do this correctly (see
`engine/packages/content-clean/tests/fixtures/articles_sample.jsonl`,
`engine/packages/eval/tests/fixtures/*`) — extend that pattern rather than
un-ignoring the full files.

## Regenerating

See each package's README for the exact command; as of this audit:
- `engine/packages/wp-extract/README.md` — dumps → `content/extracted/`
- `engine/packages/wp-harvest/README.md` — WP REST API → `content/harvested/`

## Scope note

This file documents a DevOps/repo-hygiene decision made as part of F48
(git init). It does not change, own, or comment on the correctness of the
extraction/harvest pipelines themselves — that's wxr-extract/blender/
taxonomy territory, actively being worked by other agents per PROGRESS.md.
