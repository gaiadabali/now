# now-wxr-extract

Streaming WXR (WordPress eXtended RSS) → JSONL extractor. Produces the same
frozen JSONL contract as `now-wp-extract` (the MariaDB-dump extractor),
field-for-field, so downstream consumers (loader, blender, etc.) cannot
tell which extractor produced their input. Built for NOW! Bali, whose only
faithful source is a WXR export (its prior REST harvest is known-inferior —
see PROGRESS.md F37/B1); also run against NOW! Jakarta as a cross-check
against the existing dump-derived extraction.

## Usage

```
cd engine/packages/wxr-extract
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
PYTHONPATH=src ./.venv/Scripts/python.exe -m wxr_extract.cli \
    --input path/to/export1.xml path/to/export2.xml \
    --output-dir path/to/output \
    --site-home https://www.example.com
```

Multiple `--input` files are merged and de-duplicated by `wp_id` (first
occurrence wins) — needed for Jakarta, whose WXR was exported as three
separate files (all/attachment/pages) with overlapping attachment rows.

Writes `articles.jsonl`, `attachments.jsonl`, `terms.jsonl`, `users.jsonl`,
`geo.jsonl`, `events.jsonl`, `venues.jsonl` (the last three are empty for
both NOW! sites — see `extract.py`'s module docstring for why, in detail)
plus `extraction_manifest.json` with row counts, post-type/status census,
and measured peak RSS.

## Diffing against the Jakarta dump extraction

```
python scripts/diff_jakarta.py \
    --dump-dir jakarta/content/extracted \
    --wxr-dir jakarta/content/extracted-wxr
```

Joins both extractions by `wp_id` and reports row-count agreement plus
field-by-field mismatches for articles, characterizing every one found
(not just counting them).

## Design notes

- `wxr_parser.py` streams with `xml.etree.ElementTree.iterparse` and calls
  `elem.clear()` on every finished `<item>`, so a 145 MB file is never held
  as a full DOM. See the final delivery report for measured peak RSS.
- `wp_extract_shim.py` imports `now-wp-extract`'s PHP deserialiser
  (`php_unserialize`, `extract_lat_lng`) and its curated meta-key lists
  (`ARTICLE_META_KEYS`, `ATTACHMENT_META_KEYS`) directly from its `src/`
  tree by path — no vendoring, no reimplementation.
- Every deliberate deviation from a byte-for-byte match with the dump
  extractor (primary-category reordering, attachment MIME inference,
  empty events/venues/geo) is documented in `extract.py`'s module
  docstring, with the concrete evidence that forced each one.
