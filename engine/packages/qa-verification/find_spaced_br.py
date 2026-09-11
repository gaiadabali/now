"""QA.2 verification script: find <br> occurrences in the real corpus that
already have surrounding whitespace (space before AND/OR after the tag),
and check whether apply_render_boundaries / strip_tags_text double-spaces
them.

Usage: python find_spaced_br.py <path-to-articles.jsonl>
"""
import json
import re
import sys

sys.path.insert(0, r"c:/Users/Hansel/Documents/Hansel/Projects/now!/engine/packages/content-clean/src")

from now_content_clean.html_blocks import strip_tags_text  # noqa: E402

# Pattern: some text, whitespace, <br ...>, whitespace, more text — i.e.
# an already-correctly-spaced <br> occurrence in raw content_html.
SPACED_BR_RE = re.compile(r"(\S[ \t\n\r]+)(<br\s*/?>)([ \t\n\r]+\S)", re.IGNORECASE)
# Looser variant: whitespace on EITHER side (not necessarily both)
SPACED_BR_EITHER_RE = re.compile(r"(\S[ \t\n\r]+<br\s*/?>)|(<br\s*/?>[ \t\n\r]+\S)", re.IGNORECASE)

path = sys.argv[1] if len(sys.argv) > 1 else r"c:/Users/Hansel/Documents/Hansel/Projects/now!/jakarta/content/extracted/articles.jsonl"

found = []
total_br = 0
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        html = rec.get("content_html") or rec.get("post_content") or ""
        if not html:
            continue
        total_br += len(re.findall(r"<br\s*/?>", html, re.IGNORECASE))
        for m in SPACED_BR_RE.finditer(html):
            found.append((rec.get("ID") or rec.get("id") or rec.get("post_id"), m.start(), html[max(0, m.start()-40):m.end()+40]))

print(f"Total <br> occurrences in corpus: {total_br}")
print(f"Already-spaced (both sides) <br> occurrences found (regex): {len(found)}")

either_count = 0
with open(path, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        html = rec.get("content_html") or rec.get("post_content") or ""
        if not html:
            continue
        either_count += len(SPACED_BR_EITHER_RE.findall(html))
print(f"Already-spaced (either side) <br> occurrences found (regex): {either_count}")

sample = found[:20]
print(f"\nTesting {len(sample)} samples byte-for-byte through strip_tags_text:\n")

double_space_bugs = 0
for post_id, pos, snippet in sample:
    before = snippet
    after = strip_tags_text(snippet)
    has_double = "  " in after
    if has_double:
        double_space_bugs += 1
    print(f"post_id={post_id}")
    print(f"  BEFORE: {before!r}")
    print(f"  AFTER : {after!r}")
    print(f"  double-space present: {has_double}")
    print()

print(f"SUMMARY: {double_space_bugs}/{len(sample)} samples show a double-space defect.")
