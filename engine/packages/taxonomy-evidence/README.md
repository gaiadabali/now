# now-taxonomy-evidence — the taxonomy evidence pack (blocker #3 / F50)

**Status (0.2.0, 2026-09-10): RESOLVED.** Hansel answered all 27 decisions;
the answers live in `src/now_taxonomy_evidence/resolutions.py` and are applied
on top of the E2.0 evidence at build time. The rendered packs are now E2.1's
input: zero categories are `decision-needed`, every decision carries its
`resolution`, and the vocabulary change the answers imply is emitted as a
reviewed delta for the seed ticket (F20). See "Resolved" below.

**What it is.** Analysis tooling that turns "110 legacy WordPress categories
and a blank page" into a short list of evidenced decisions -- and, once those
are answered, into the resolved category prior. It reads the extracted
archives of both cities, E1.4's Jakarta draft and the seed vocabulary, and
writes the review surfaces from one in-memory model:

```
jakarta/site/taxonomy-review.md     human surface: decisions (with answers) first, resolved mappings in the appendix
jakarta/site/taxonomy-review.json   machine twin, consumed by E2.1 as the category prior + rules
bali/site/taxonomy-review.md
bali/site/taxonomy-review.json
vocabulary-delta.md                 the reviewed seed change (D14/D15/D16/D22 + approvals) -- input to the seed ticket
vocabulary-delta.json               machine twin of the delta (same model)
```

**What it is not.** It never writes to a database, never touches
`engine/packages/taxonomy/seed/` (vocabulary changes are *emitted as a delta*,
not applied), and ships no migration.

## Run

```bash
cd engine/packages/taxonomy-evidence
uv sync
.venv/Scripts/python -X utf8 -m now_taxonomy_evidence.cli build            # both cities, LLM on if the key is present
.venv/Scripts/python -X utf8 -m now_taxonomy_evidence.cli build --no-llm   # heuristic path only
.venv/Scripts/python -X utf8 -m now_taxonomy_evidence.cli build --no-db    # TF-IDF proxy for both cities
```

No env vars are needed. The city DB is reached through `now_db.settings`
(reads the project `.env`, F31). The LLM key is read from
`~/.claude/secrets/ollama-cloud.env` (override with `NOW_LLM_ENV_FILE`) or
`OLLAMA_CLOUD_API_KEY` in the environment; it is never logged, cached or
written to any output. Per-article features and LLM responses are cached in
`.cache/` (gitignored) so a re-render is seconds and costs zero LLM calls.

Full build from cold: ~8 minutes (3 min cue features, 2 min vocabulary scan,
~4 min LLM at 4 workers). With warm caches: ~20 seconds.

## Inputs (all read-only, none owned here)

| Input | Path | Used for |
|---|---|---|
| Articles | `<city>/content/extracted/articles.jsonl` | titles, dates, categories, Yoast primary, cleaned body |
| Category registry | `<city>/content/harvested/categories.jsonl` (REST) | term ids, parents, editor descriptions; published counts recomputed from articles |
| Editor tags | `<city>/content/extracted/terms.jsonl` (`post_tag`) | the editors' own vocabulary, checked against the seed |
| E1.4 draft | `jakarta/site/taxonomy-mapping.json` | carried as the Jakarta prior; amended where evidence changes the call |
| Seed vocabulary | `engine/packages/taxonomy/seed/` | terms + aliases for the vocabulary scan and the location gazetteer |
| Embeddings | `now_jakarta.engine.embeddings`, `model = 'BAAI/bge-small-en-v1.5'` | Jakarta coherence (always filtered by model — F42) |

Bali has no embeddings yet (`now_bali.engine.embeddings` is empty, verified),
so Bali coherence uses a TF-IDF/LSA proxy. The report says so wherever a
proxy number appears; it is a weaker, lexical instrument.

## Instruments, and how much to trust them

1. **Cue instrument** (`text.py`) — title-weighted regex cue scores per
   type and per format, abstaining on no signal or a tie, plus first-person
   density (routed to `review` only when a venue is the subject). Its
   agreement with undisputed categories is printed in §5 of every report
   (roughly: venue types 60–96%, `offer` 45–88%, `event` ~50–60%, `news`
   25–40%; `feature` has no cue at all and is never contradicted).
2. **Coherence** (`coherence.py`) — per category: cohesion vs a random
   baseline of the same size, leakage to other categories' centroids (with a
   *cross-type* variant that ignores siblings sharing the same proposed type),
   and k-means k∈{2,3} with cosine silhouette. Clusters are labelled with
   their dominant cue type/format, top title words and the titles nearest
   the centroid so a split is visible on sight.
3. **Vocabulary** (`vocabulary.py`, `lexicons.py`) — every seed term and
   alias counted as distinct articles mentioning it (both cities, title and
   body), a curated candidate lexicon per facet counted the same way, and
   the editors' post_tag vocabulary listed where the seed has no term.
4. **LLM second opinion** (`llm.py`, optional) — one structured-JSON call per
   category with 20 time-spread titles and the proposal. Contract: it can
   only *add* flags (a disagreement on a venue type or a decay class); it
   never auto-accepts anything, so the pack degrades cleanly without it.

## Flagging rules (`decide.py`)

A category is **decision-needed** when its proposal is not marked auto
(E1.4's `decision_needed`, or the Bali proposal table) — every such category
is tied to a numbered decision in `proposals.DECISIONS`. An auto-proposed
category becomes **flagged-by-evidence** only when the data contradicts the
proposal in a way that matters:

- cue type disagreement that crosses into or between **venue types**
  (`exclude_same = true`) — the only kind that changes competitor exclusion;
- cue format disagreement across **decay classes** (short / medium /
  evergreen) — the only kind that changes freshness;
- clusters that read as different venue types, or as formats of different
  decay classes, while the proposal fixes one;
- LLM disagreement of the same two kinds.

Everything else is **auto-accepted**, with the status naming the vocabulary
or policy decision it depends on. Print-issue categories are retired by one
decision (D07); Bali's column archive by another (D08).

## Layout

```
src/now_taxonomy_evidence/
  sources.py      loaders (articles, categories, tags, E1.4 mapping, seed)
  text.py         cleaning, cue lexicons, scorer, location gazetteer, first-person density
  features.py     per-article features + disk cache
  vectors.py      embeddings from the city DB, TF-IDF/LSA proxy, numpy fallbacks
  coherence.py    cohesion / leakage / k-means split analysis
  lexicons.py     candidate vocabulary per facet (what to look for that the seed lacks)
  vocabulary.py   seed vs corpus, both directions; uncovered editor tags
  proposals.py    Bali proposals, Jakarta amendments to E1.4, the decision registry (the E2.0 record)
  resolutions.py  Hansel's 27 answers, the mixed-categories policy, per-category overrides, the RULES block
  vocabulary_delta.py  the curated >= 20-mention vocabulary delta (add / alias / merge / skip per candidate) + its renderer
  llm.py          optional second opinion (OpenAI-compatible), cached, key never logged
  decide.py       assemble the model: records, statuses, decision evidence, resolutions, cross-city, calibration
  render.py       Markdown + JSON from the same model
  cli.py          `build`
tests/            unit tests (no DB, no corpus, no network)
```

## Resolved (0.2.0) — how the answers are applied

`proposals.py` stays the **E2.0 record**: the proposal the evidence was
gathered against. Features, coherence, the cached LLM prompts and the Section 2
flags all key off it, so a rebuild after the answers costs zero LLM calls and
changes no instrument reading. `resolutions.py` is the **one place the answers
are written down**:

| table | what |
|---|---|
| `RESOLUTIONS` | one entry per decision id: `answer`, `option`, `source` (`explicit` / `as-recommended`), `rationale`, `conflicts` (with the recommendation -- reported, never silently reconciled), `applies` |
| `EVIDENCE_FLAG_POLICY` | Hansel's "mixed categories -> classify per article" answer and the seven categories it resolves |
| `CATEGORY_RESOLUTIONS` | per-category overrides the answers imply (`per_article`, `type/subtype/format/location`, `facets`, `alternates_prepend`, `decisions_add`, `basis`, `note`) |
| `RULES` | the cross-cutting classifier rules (D01, D02, D06, D07, D08, D09, D10, confidence gate, `international` encoding) -- machine-readable |

`decide.CityBuild.apply_resolutions()` runs after `assign_status()` and
rewrites each record: `proposal` becomes the resolved prior, the E2.0 values
move to `e20_proposal` / `e20_status`, and `resolution.{status, changed,
changes, basis, note, addressed_flags}` records what happened. It fails
loudly on an unknown category or decision id, or on an evidence flag no
override addresses -- a wrong table cannot produce a quietly half-resolved
pack. `assemble()` refuses a registry decision without a resolution.

Rebuild (reproducible; the DB must be up for Jakarta's real embeddings):

```bash
cd engine/packages/taxonomy-evidence
.venv/Scripts/python -X utf8 -m now_taxonomy_evidence.cli build
```

Warm caches: ~20-60 s, `121/121 categories answered` from `.cache/llm`, no
network call. The vocabulary delta is written next to this README.

## JSON contract for E2.1

`taxonomy-review.json` → `categories[]`: one record per legacy category with

- `proposal.{type,subtype,format,location,per_article,facets,series_key}` --
  **the resolved prior** (a facet in `per_article` is decided by the
  classifier; the value shown is the prior);
- `e20_proposal`, `e20_status` -- what the evidence was gathered against;
- `resolution.{status, changed, changes, basis, note, addressed_flags}`;
- `status` -- starts with `resolved` for every category with articles
  (`resolved (as proposed)`, `resolved (D21)`, `resolved — changed (D26,
  mixed-categories)`, `resolved (print issue, D07)`), `empty` otherwise;
- `confidence`, `decisions` (ids into `decisions[]`), `alternates` (the
  classifier's candidate set, evidence-pointed alternates first), the E1.4
  record it carries (`e14`), the cue distributions, samples, coherence and
  the LLM opinion (all against `e20_proposal`).

Top level: `resolution_meta` (decided_by/on, `decisions_resolved`,
`decisions_open` = `[]`, `explicit`, `as_recommended`,
`conflicts_with_recommendation`), `decisions[]` each with `resolution`,
`rules` (read this together with `categories[].proposal`), `evidence_flag_policy`,
`vocabulary_delta` (file paths + counts), `cross_city`, `vocabulary`.

`vocabulary-delta.json`: `approve[]`, `add_term[]` (facet, slug, label,
parent, aliases, geo, mentions, `requires_migration`, `payload_enum`, attrs),
`add_alias[]`, `drop_term[]`, `trim_alias[]`, `match_hints[]`, `merged[]`,
`skipped[]`, `below_threshold[]`, `migration` (F20 sequence). Source of
truth: `vocabulary_delta.py`; the build fails if a candidate at or above the
threshold has no curated action.

The review files and the delta are generated, never hand-edited: change
`resolutions.py` / `vocabulary_delta.py` and rebuild.
