# now-content-clean

E1.2 — converts WordPress `content_html` into the structured block array
the rest of the ingest pipeline consumes. One-shot migration tool (see
ARCHITECTURE.md §6); no ongoing WP sync.

## Scope

Consumes the frozen E1.1 contract, `jakarta/content/extracted/articles.jsonl`
(one JSON object per line, `wp_id` + `content_html` at minimum). Produces,
per article: a block array, an outbound-link list (with anchor text +
character offset), an inline `wp-content/uploads` reference list, and a
stats dict (content-loss metrics, dropped/unhandled-construct counts).

This package does **not** touch media (that's E1.3), taxonomy (E1.4), or
the DB (`engine/packages/db/`). It is a pure, offline text transform.

## Install / run

```bash
cd engine/packages/content-clean
uv venv && uv pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/ -q
.venv/Scripts/python -m now_content_clean.cli clean <articles.jsonl> -o blocks.jsonl --report report.json
```

`now-content-clean clean` is idempotent and re-runnable: `clean_html`/
`clean_article` are pure functions of `content_html` with no external
state, so re-running over the same input overwrites the output with
byte-identical content.

## Block schema

```json
[{"type":"heading","level":2,"text":"...","html":"..."},
 {"type":"paragraph","html":"..."},
 {"type":"image","media_ref":"...","alt":"...","caption":"...","href":"..."},
 {"type":"gallery","images":[{"media_ref":"...","alt":"...","caption":"...","href":null}],"caption":null},
 {"type":"list","ordered":false,"items":["<html>", "..."]},
 {"type":"quote","html":"...","cite":"..."},
 {"type":"embed","provider":"youtube","url":"..."},
 {"type":"separator"},
 {"type":"columns","columns":[[<block>, ...], [<block>, ...]]},
 {"type":"raw_html","html":"...","reason":"unhandled_tag:table"}]
```

Full field-by-field rationale lives in `src/now_content_clean/models.py`'s
module docstring. Deviations from the ticket's proposed sketch, and why:

- **`heading.html`** (in addition to `text`) — preserves inline formatting
  (e.g. `<strong>` inside an `<h3>`) that a plain-text `text` field alone
  would silently lose.
- **`image.href`** — set when an image is wrapped in `<a href>` (the
  classic-editor "click through to full size / external site" pattern).
- **`gallery`** (new type, 2,312 occurrences archive-wide — more common
  than several types already in the ticket's sketch) — one entry per
  photo, **each with its own `caption`** (a `wp:gallery` nests one
  `<figure>`+`<figcaption>` per image; grouping them under a single
  gallery-level caption would have silently dropped every caption but
  the first — this was caught and fixed during testing, see below).
- **`separator`** (new type, 1,126 occurrences: `<hr>` / `wp:separator`)
  — a real structural element, not decoration to discard.
- **`columns`** (new type, 251 occurrences: `wp:columns`) — each inner
  array is one column's block sequence. `wp:group` and `wp:media-text`
  are *not* given their own type: they're transparent layout wrappers in
  this archive (verified against every occurrence) and their children
  are spliced directly into the surrounding sequence — nothing is lost,
  there's just no dedicated "group" node in the output.
- **`raw_html.reason`** — always present; a free-text tag naming why this
  escape hatch was used (`unhandled_tag:<tag>`), so the report in
  `stats.unhandled_tags` and a block's own `reason` always agree.
- **`list.items`** are inner-HTML strings, not plain text — list items
  routinely carry `<em>`/`<strong>`/`<a>`; flattening to plain text would
  be silent, avoidable content loss.

`wp:spacer` and empty elements (`<p></p>`, `<p>&nbsp;</p>`) are dropped —
zero visible text — and counted in `stats.dropped_decorative` /
`stats.dropped_empty`, never silently vanished. `<script>`/`<style>`/
`<noscript>`/`<svg>` are dropped (no reader-visible text, and reproducing
inline `<script>` in the new renderer would be an XSS/CSP hazard) and
counted in `stats.dropped_non_visible`.

## Gutenberg handling

**Design decision, verified against the real corpus, not assumed:** every
`<!-- wp:name {json} --> ... <!-- /wp:name -->` block in this archive
wraps HTML that is *already complete and self-describing* — a heading's
level is in its `<h2>` tag, a list's orderedness is in `<ul>` vs `<ol>`, a
gallery is one `<figure>` per photo, an embed's URL is the wrapper's bare
text. There is no block type in the archive whose JSON attrs carry content
not already present in the underlying HTML (confirmed against every
`wp:*` type below). So: `gutenberg.py` tokenizes every comment marker with
a depth-stack walk (real structural parsing — counts block types, flags
unbalanced nesting) purely for the report and for validation, then strips
the markers and hands the underlying HTML to the *same* engine
(`html_blocks.py`) used for classic content. **The literal string
`<!-- wp:` never appears in any output block** — verified by
`test_gutenberg.py::test_no_gutenberg_articles_leak_literal_comment_text`
over every Gutenberg article in the fixture sample.

### Gutenberg block coverage (from a full scan of all 4,772 published articles)

| Block | Count | Handling |
|---|---:|---|
| paragraph | 24,166 | `<p>` → `paragraph` |
| image | 8,926 | `<figure><img>` → `image` |
| gallery | 2,312 | `<figure class="wp-block-gallery">` → `gallery`, per-image caption |
| spacer | 1,831 | dropped (zero text), counted `dropped_decorative` |
| heading | 1,383 | `<h1-6>` → `heading` |
| separator | 1,126 | `<hr>` → `separator` |
| column | 516 | recursed inside `columns` |
| list-item | 326 | `<li>` inside `list.items` |
| columns | 251 | `columns` |
| tadv/classic-paragraph | 191 | inner HTML re-run through the same classic pipeline (may itself contain `[caption]`) |
| list | 82 | `<ul>`/`<ol>` → `list` |
| group | 29 | transparent, children spliced in |
| media-text | 14 | transparent (image figure + content div both recursed) |
| html | 11 | raw passthrough → iframe becomes `embed`, script dropped+counted |
| quote | 11 | `<blockquote>` → `quote`, `<cite>` extracted |
| embed | 8 | bare-URL wrapper → `embed`, provider from URL |
| pullquote | 4 | same as quote |
| cover | 2 | transparent (background `<img>` + inner content both recursed) |
| footnotes | 1 | empty in this archive; no-op |
| table | 1 (+7 via classic `<table>`) | `raw_html`, `reason: unhandled_tag:table` |

## Shortcodes

`[caption]` (17 archive-wide) → `image`/`gallery` block with `caption`.
`[gallery ids="..."]` (0 in the fixture sample, handled defensively per
the ticket) → `gallery` block with `images: []` and an `ids` list — content-
clean cannot resolve WP attachment IDs to URLs on its own; that's a job for
whatever consumes this alongside E1.3's attachment table.

One of the 17 `[caption]` instances (`wp_id 5022`) is genuinely malformed
in the source — HTML-entity-escaped brackets, no matching `[/caption]`,
spanning a broken `<p>` boundary from a historical bad copy/paste.
Content-clean never invents structure it can't verify: it strips the
bracket tokens and lets the intact surrounding HTML flow through normally
— zero visible characters lost, just no dedicated caption grouping for
that one instance. `test_shortcodes.py` asserts this explicitly.

## Links and uploads

Both are extracted directly from the **original** `content_html` string
(regex-based, not from the parsed block tree), so `offset` is exact and
stable regardless of how the block builder groups or flattens markup —
required for E1.5 (partner-roster clustering, needs anchor text +
position) and E4.3 (link → mention conversion), and for E1.3 (media URL
rewrite, needs every inline `wp-content/uploads` reference, not just the
ones that ended up in `image`/`gallery` blocks — `srcset`, background-image
URLs, and bare `<a href>` links to full-size originals are all covered).
`rel` is captured verbatim, unmodified (the archive's ~1,780 external
links have almost no `rel="sponsored"` — that's fixed later by tier-driven
rendering per ARCHITECTURE.md §11, not here).

## Content-loss verification

`stats.content_loss` = `{chars_in, chars_out, delta, loss_pct}`, comparing
normalized *visible* text (tags/entities stripped, whitespace collapsed;
`alt` excluded from both sides since it's an attribute, not rendered text;
`<script>`/`<style>`/`<svg>` excluded from both sides for the same reason).

Full-corpus run (all 4,772 published articles, `now-content-clean clean`):

- **median loss: 0.000%, p95: 0.000%, max: 1.207%**
- **zero articles > 10k chars show any loss** (34 were initially
  flagged during development — all were bugs in this package, fixed; see
  "Bugs found and fixed" below — the current run has zero outliers)
- the 153k-char maximum article (`wp_id 85601`) completes in ~0.08s,
  produces 375 blocks, 62 links, 110 upload references, **0% loss**
- the only 8 articles with any nonzero loss (0.19%–1.2%) are all
  `wp:embed`/bare-`<iframe>` cases: the raw oEmbed URL text
  (e.g. `https://www.youtube.com/watch?v=...`) is intentionally not
  counted as output "visible text" (an `embed` block contributes no text
  to the metric — the URL becomes a player, not prose) while it exists as
  literal text in the WordPress source before oEmbed JS resolves it. This
  is a metric-definition choice, not lost content.

Run it yourself: `now-content-clean clean <articles.jsonl> -o out.jsonl --report report.json`.

### Bugs found and fixed during verification (documented, not just claimed)

1. **Gallery captions**: initially only the first image in a `wp:gallery`
   kept its `<figcaption>` text; every other image's caption was silently
   dropped. Fixed by capturing each image's own wrapping `<figure>`'s
   `<figcaption>`, not the gallery figure's.
2. **Bogus `<figure>`/`<figcaption>` used as a generic paragraph
   wrapper**: a handful of pre-Gutenberg articles nest a real
   image-with-caption inside an outer `<figure>` that *also* has a second,
   unrelated `<figcaption>` holding a full paragraph of body text. The
   original figure handler took the "single image" shortcut and returned
   immediately, dropping that second figcaption's paragraph entirely.
   Fixed: any `<figcaption>` not actually consumed as an image's caption
   is now recursed and appended, never dropped.
3. **Duplicate captions**: after fix #2, a figcaption already used by
   `_image_block_from_img`'s own per-image lookup was *also* being
   re-appended as a leftover, duplicating the text. Fixed by tracking
   consumed `<figcaption>` elements by identity, not by a simple "was any
   caption found" boolean.
4. **Content-loss metric double-counting a dropped `<script>`'s tail
   text**: the metric's own "strip non-visible elements" step used
   `element.remove()`, which (correctly, per lxml/ElementTree semantics)
   also discards that element's *tail* text — but several articles have a
   real bare-text paragraph sitting as an unwrapped `<script>` tag's tail
   (no enclosing element at all). This under-counted `chars_in` versus
   what the real block pipeline correctly captured, manufacturing a false
   "extra content" reading. Fixed by re-homing tail text before removal,
   matching what the main block walker already did correctly.

None of these were block-pipeline correctness bugs that shipped silently
— they were caught precisely because the ticket calls for measuring loss
on every article, not just eyeballing a handful.

## Fixture provenance

`tests/fixtures/articles_sample.jsonl` — 133 real articles extracted
directly from the raw UpdraftPlus MariaDB dump
(`nb15_posts`, `post_type='post'`, `post_status='publish'`), **not
synthetic HTML**. Selected for coverage: all 17 `[caption]`-shortcode
articles, the shortest and longest (153k-char max) articles, several
just over the 10k-char threshold, random samples of Gutenberg-only,
classic-only, iframe-embed, blockquote, list, and inline-`wp-content/
uploads` articles, plus a general random sample. See
`git log`-free extraction notes: the dump uses one `INSERT INTO
\`nb15_posts\`` statement per row with **real, unescaped newlines**
inside `post_content` (Gutenberg content in particular) — a naive
line-based dump parser silently truncates every multi-line row to its
first line; the extraction was written to scan the decompressed dump as
one string and track paren/quote depth instead of line boundaries. (This
extraction script was a one-off, used only to build these fixtures — the
real E1.1 pipeline, built concurrently by another agent, restores into an
actual MariaDB container and is not affected by this.)

Fixture articles carry `categories: []`, `tags: []`, `meta: {}`,
`thumbnail_id: null` — those fields aren't derivable from `nb15_posts`
alone and aren't used by this package; E1.1's real output will populate
them.

## Notes for downstream tickets

- **E1.5 (partner-roster clustering)**: use `links[].offset` to locate
  each outbound link back in `content_html` for context; `links[].text`
  is the decoded anchor text; `links[].is_upload` flags internal-media
  links so they can be excluded from domain clustering.
- **E1.8 (loader)**: `blocks` is ready to store as-is (e.g. a `jsonb`
  column). `image`/`gallery` blocks' `media_ref` is still the *original*
  WP URL — E1.3's URL map must be applied at load time (or in a follow-up
  pass) to rewrite them to Garage URLs; `uploads[]` in this package's
  output gives every inline reference that needs rewriting, including
  ones not captured as a structured `image` block (raw `<a href>` links
  to full-size originals, `srcset` variants). `raw_html` blocks and
  `stats.unhandled_tags` should be spot-checked once against the full
  4,679-article run before considering ingest "clean" — currently only
  `<table>` (8 occurrences archive-wide) falls into that bucket.
