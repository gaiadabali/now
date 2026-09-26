# now-place-catalogue — `now-places`

P1.1 and P1.2 of `docs/ITINERARY-AND-READER-PRODUCTS-PLAN.md` §9: find the
junk in each city's `public.places`, rank what is left into a curation
queue, and merge duplicates without ever losing a mention.

Every command is a **dry run** unless given `--apply`, and an `--apply` must
repeat the database it writes to (`--confirm-db <name>`). Prove any apply on
a scratch copy first.

```bash
cd engine/packages/place-catalogue
uv sync --extra dev

uv run now-places triage bali            # report -> bali/site/place-triage-report.md
uv run now-places rank jakarta --csv /tmp/top500.csv
uv run now-places dedupe bali            # queue -> bali/content/extracted/place_dedupe_review_queue.jsonl
uv run now-places merge bali 12593 18321 # one editor-chosen merge (dry run: rolled back)
uv run now-places unmerge bali 12593     # exact reversal

# on a scratch copy
uv run now-places triage bali --db now_bali_p1_scratch --apply --confirm-db now_bali_p1_scratch
uv run now-places untriage bali --db now_bali_p1_scratch --log bali/content/extracted/place_triage_apply_log.jsonl --apply --confirm-db now_bali_p1_scratch
```

## Triage (P1.1)

`junk.py` classifies a name into three tiers, each with a six-word reason:

- **junk**: fragments, events, offers, room types, job titles, addresses,
  award captions, two venues run together, and area names from the
  extractor's own noise list. `triage --apply` writes `status = junk` on
  these, and only on rows still `pending_review`. An editor's `active` or
  `closed` is never overwritten.
- **suspect**: shapes that are doubtful but often real, such as "X at Y",
  "X of Y", a number, or two names joined by "and". These are listed in the
  report and badged in the desk. They are never written.
- no flag.

`region.py` flags names that point outside the site's region, like the
~400 Bali venues in Jakarta's table. Those rows are **kept and flagged,
never moved or junked**. `region_ok` stays false until P1.3 geocodes the
row.

**Measured recall** (`tests/test_junk.py`, four hand-labelled 100-row
samples):

| sample | listed (junk + suspect) | junk tier | junk-tier false positives |
|---|---:|---:|---:|
| Bali, the ticket's fixture (tuning) | 53/55 = 96% | 52/55 = 95% | 0/45 |
| Jakarta (tuning) | 48/51 = 94% | 46/51 = 90% | 0/49 |
| Bali, labelled blind, then tuned on | 52/55 = 95% | 50/55 = 91% | 1/45 |
| **Jakarta, labelled blind, never tuned on** | **36/44 = 82%** | **25/44 = 57%** | 1/56 |

The last row is the honest one. The first version of the rules scored 25%
on the Jakarta tuning set, because it had learned the Bali fixture's
examples and not the shapes. The rules are now shapes, and precision stays
around 98%, but junk has a long tail. Expect roughly one junk row in five to
reach an editor unflagged.

**Queue order** is the plan's §9.1 score:
`3 × featured + articles + 2 × active partnership + recency`. Recency runs
from 0 to 1 and decays linearly over five years. The partnership term reads
`engine.partnerships` in `now_platform`. If that read fails, the term
scores 0 and the report says so.

**Coverage** is reported on two denominators. The featured mentions that sit
on junk rows (Jakarta's "Hotel's" is featured 33 times) can never be
covered by a curated venue.

## Dedupe (P1.2)

`dedupe.py` blocks and scores pairs using the extractor's own
`now_place_extraction.match.similarity` and its thresholds:

- **≥ 0.85**: a merge, unless a guard objects. The guards are: an area
  name, an outlet "at" a venue, two different kinds of venue (a hotel and
  its spa share a name), approved rows, different Google ids, orgs, legacy
  records or regions.
- **0.55–0.85**: queued for an editor and **never merged**.

`merge.py` applies one merge per transaction. It locks both rows, moves the
loser's `place_mentions` to the survivor, re-points anything previously
merged into the loser, and sets `merged_into`. It then appends an audit
entry to the **survivor's `aliases`**, so the survivor keeps both names.
The entry records the loser's name and id, the mention ids moved, the
re-pointed rows, the actor, the time and the score. `unmerge` reverses a
merge exactly from that entry. It works last in, first out. The place desk
writes the same entry shape, so there is one audit format and one reversal.

A full apply-and-reverse was run on scratch copies of both cities: all
junk proposals were written, all proposed merges applied, then every merge
was unmerged and every junk row reverted. The `place_mentions` checksum and
the per-status counts afterwards were identical to before.

## Tests

```bash
uv run pytest -q                                                   # pure: no database
NOW_PLACES_TEST_DB=now_bali_p1_scratch uv run pytest -q tests/test_merge_db.py
```

The DB tests refuse to run against `now_bali`, `now_jakarta` or
`now_platform`, and roll back everything they do.

After any change to `junk.py`, run `uv run python scripts/build_junk_golden.py`
and update the desk's TypeScript port (`engine/apps/web/src/lib/placeJunk.ts`)
until `npm test` in `engine/apps/web` passes again. Both suites assert
against `tests/fixtures/junk_golden.jsonl`.
