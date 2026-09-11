# now-partner-roster

E1.5 — clusters the archive's outbound links into a candidate partner-org
roster, seeding `orgs` for E4 commerce and quantifying the
`rel="sponsored"`/`nofollow` SEO exposure that feeds the E4.3 audit (see
`ARCHITECTURE.md` §6 and §11).

## Scope

Consumes `jakarta/content/extracted/articles.jsonl` (E1.1 contract) and
E1.2's `now_content_clean.links.extract_links` for byte-accurate outbound
links (`{url, text, offset, rel, is_upload}`). Does **not** parse HTML
itself, does not touch `content-clean`, `wp-extract`, `db`, or `apps/api`.

## Install / run

```bash
cd engine/packages/partner-roster
uv venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/ -q
.venv/Scripts/now-partner-roster build \
    ../../../jakarta/content/extracted/articles.jsonl \
    -o ../../../jakarta/content/extracted/partner_roster.jsonl \
    --report ../../../jakarta/content/extracted/partner_roster_report.json
```

This also writes `partner_roster_exclusions.jsonl` and `partner_roster.md`
next to `-o` (paths overridable via `--exclusions`/`--markdown`).
Re-runnable and idempotent: `run()` is a pure function of the input file's
content plus the static heuristic tables in `domains.py`/`cluster.py` —
re-running over the same input overwrites the outputs byte-for-byte.

## Pipeline

1. `pipeline.run` walks every article, calls E1.2's `extract_links`, and
   buckets every `<a href>` into: internal media (`is_upload`), non-http(s)
   (`mailto:`/`tel:`/relative/malformed), or an absolute external link.
   `domains.repair_href` first undoes a real copy/paste bug found in the
   corpus (`http://https://actual-url`, e.g. wp_id 456/6029/6583) that would
   otherwise show up as a bogus `https:` "domain".
2. Each external netloc is classified (`domains.classify`): our own site
   (`nowjakarta.co.id`/`nowbali.co.id`, any subdomain), social, stock,
   shortener, or utility get excluded **but recorded**, never silently
   dropped — see `partner_roster_exclusions.jsonl`.
3. Surviving netlocs are clustered into orgs (`cluster.build_clusters`):
   - **Domain merge**: `www.` stripped, a small multi-label-suffix table
     (`.co.id`, `.com.au`, ...) applied, then a handful of known corporate
     rebrand aliases (`accorhotels.com` -> `accor`) — `marriott.com` +
     `marriott.co.id` become one org.
   - **Group -> property**: a netloc with a specific (non-generic)
     subdomain of a root that also has an apex cluster in this corpus
     becomes a property of that group, `parent_org_slug` populated with
     confidence 0.85 (`bali.intercontinental.com` under `intercontinental`).
     If the apex domain itself never appears as a direct outbound link, the
     group org is **synthesized** (`synthesized: true`, confidence 0.35,
     zero link evidence, flagged in `notes`) so a human confirms it exists
     before it becomes a real `orgs` row.
   - **Brand-keyword fallback** (weaker, always flagged): a standalone
     domain containing a known brand keyword but not literally a subdomain
     of that brand's domain (`jwmarriottsurabaya.com` containing
     "marriott") gets a lower-confidence `parent_org_slug` guess, always
     with a `notes` entry saying to verify manually.
4. `report.render_markdown` writes `partner_roster.md`: corpus totals, the
   rel-audit SEO-exposure numbers, the top ~60 orgs table, every flagged
   ambiguous cluster, and the full exclusion table.

## Output shape (`partner_roster.jsonl`, one row per org, ranked by `link_count` desc)

```json
{"org_slug": "marriott", "name": "Marriott International", "parent_org_slug": null,
 "domains": ["marriott.com", "marriott.co.id"], "link_count": 66, "article_count": 57,
 "first_seen": "2019-01-04", "last_seen": "2026-07-07", "type_guess": "stay",
 "confidence": 0.9, "sample_articles": [12345, 67890],
 "rel_audit": {"none": 66, "nofollow": 0, "sponsored": 0},
 "notes": [], "synthesized": false}
```

`notes` and `synthesized` are additive beyond the ticket's sketch — they
carry the "flag ambiguous merges rather than guess silently" requirement
without inventing a separate side-channel file that could drift out of
sync with the row it describes.

## Known limitations, left for human review (see `partner_roster.md`)

- Root-domain parsing uses a small hand-maintained multi-label-suffix list,
  not a public-suffix-list library (no new dependency added per ticket
  scope) — a ccTLD suffix outside that list would be mis-split. None
  observed in the real corpus's top domains.
- `book.chope.co` / `chope.co` cluster as a single "Chope" org even though
  Chope is a reservation *platform* used by many distinct restaurants, not
  a single venue — flagged nowhere else because the domain-only signal
  can't disambiguate; call out for E2.3/E4.3 manual handling.
- Brand-keyword parent matches (stage 3 in `cluster.py`) are a substring
  heuristic, not a verified corporate relationship — every one is flagged
  in `notes` and listed in `partner_roster.md`'s "ambiguous clusters"
  section.
- `type_guess` is domain-name-keyword-only and frequently `null` — it is a
  prior for E2.3, never a decision (per ticket).
