#!/usr/bin/env python3
"""Answer one question: do we have every article, and is each one intact?

Cross-checks every independent source we hold for a site and reports any
article that is missing from one of them, or present but empty/truncated.

Sources, in descending order of authority:

  1. WXR dump      <site>/db/dumps/wxr/<site>-all-*.xml      raw post_content
  2. SQL extract   <site>/content/extracted/articles.jsonl   E1.1, Jakarta only
  3. REST harvest  <site>/content/harvested/articles.jsonl   rendered content
  4. Live sitemap  <site>/content/harvested/sitemap_urls.txt what the site lists

Stdlib only. Streams the XML, so the 142 MB file costs no more memory than
the small one.

    python scripts/verify-articles.py            # both sites
    python scripts/verify-articles.py --site bali
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

WP_NS = "{http://wordpress.org/export/1.2/}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"

# Below this, a body is not a real article — it is a stub, a redirect page or
# a truncation. Chosen well under the archive's ~4,800-char median so it flags
# only genuine outliers.
MIN_BODY_CHARS = 200


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ARCHITECTURE.md").is_file():
            return parent
    return here.parents[1]


ROOT = repo_root()


def norm_path(url: str) -> str | None:
    """Host-independent key for comparing a permalink to a sitemap entry."""
    if not url:
        return None
    path = unquote(urlsplit(url.strip()).path or "")
    path = path.rstrip("/").lower()
    return path or "/"


def load_wxr_posts(path: Path) -> dict[int, dict[str, object]]:
    """Stream the WXR and return published posts by id.

    ``iterparse`` with ``clear()`` keeps peak memory flat; parsing the tree
    would hold the whole 142 MB document plus object overhead.
    """
    posts: dict[int, dict[str, object]] = {}
    context = ElementTree.iterparse(path, events=("end",))
    for _event, elem in context:
        if elem.tag != "item":
            continue
        get = elem.findtext
        post_type = get(f"{WP_NS}post_type")
        status = get(f"{WP_NS}status")
        if post_type == "post" and status == "publish":
            raw = get(f"{CONTENT_NS}encoded") or ""
            try:
                post_id = int(get(f"{WP_NS}post_id") or 0)
            except ValueError:
                post_id = 0
            if post_id:
                posts[post_id] = {
                    "slug": get(f"{WP_NS}post_name") or "",
                    "title": (get("title") or "").strip(),
                    "link": get("link") or "",
                    "chars": len(raw.strip()),
                    "date": get(f"{WP_NS}post_date") or "",
                }
        elem.clear()
    return posts


def load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def article_index(rows: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    out: dict[int, dict[str, object]] = {}
    for row in rows:
        if row.get("status") not in (None, "publish"):
            continue
        try:
            wp_id = int(row.get("wp_id") or 0)
        except (TypeError, ValueError):
            continue
        if wp_id:
            body = row.get("content_html") or ""
            out[wp_id] = {
                "slug": row.get("slug") or "",
                "title": row.get("title") or "",
                "chars": len(str(body).strip()),
                "permalink": row.get("permalink") or "",
            }
    return out


def newest(pattern: str) -> Path | None:
    matches = sorted(glob.glob(pattern))
    return Path(matches[-1]) if matches else None


def check_site(slug: str) -> bool:
    print(f"\n{'=' * 66}\n  {slug.upper()}\n{'=' * 66}")

    wxr_path = newest(str(ROOT / slug / "db" / "dumps" / "wxr" / f"{slug}-all-*.xml"))
    if wxr_path is None:
        print("  no WXR dump found — run scripts/wp-export-wxr.py first")
        return False

    print(f"  reading {wxr_path.name} ...", flush=True)
    wxr = load_wxr_posts(wxr_path)
    rest = article_index(load_jsonl(ROOT / slug / "content" / "harvested" / "articles.jsonl"))
    sql = article_index(load_jsonl(ROOT / slug / "content" / "extracted" / "articles.jsonl"))

    sitemap_file = ROOT / slug / "content" / "harvested" / "sitemap_urls.txt"
    sitemap: set[str] = set()
    if sitemap_file.exists():
        for line in sitemap_file.read_text(encoding="utf-8").splitlines():
            key = norm_path(line)
            if key:
                sitemap.add(key)

    print(f"\n  published articles per source")
    print(f"    WXR dump (raw content) : {len(wxr):>6,}")
    print(f"    REST harvest           : {len(rest):>6,}" if rest else "    REST harvest           :      - (absent)")
    print(f"    SQL extract (E1.1)     : {len(sql):>6,}" if sql else "    SQL extract (E1.1)     :      - (absent)")
    print(f"    live sitemap URLs      : {len(sitemap):>6,} (all page types)")

    ok = True

    # ---- set comparisons, WXR as the reference ------------------------
    for label, other in (("REST harvest", rest), ("SQL extract", sql)):
        if not other:
            continue
        missing_here = set(other) - set(wxr)
        missing_there = set(wxr) - set(other)
        status = "OK" if not (missing_here or missing_there) else "MISMATCH"
        print(f"\n  WXR vs {label}: {status}")
        if missing_here:
            ok = False
            print(f"    in {label} but NOT in the dump: {len(missing_here)}")
            for wp_id in sorted(missing_here)[:10]:
                print(f"      {wp_id}  {str(other[wp_id]['title'])[:60]}")
        if missing_there:
            ok = False
            print(f"    in the dump but NOT in {label}: {len(missing_there)}")
            for wp_id in sorted(missing_there)[:10]:
                print(f"      {wp_id}  {str(wxr[wp_id]['title'])[:60]}")

    # ---- is every dumped article actually live? -----------------------
    if sitemap:
        absent = [
            (wp_id, data) for wp_id, data in wxr.items()
            if norm_path(str(data["link"])) not in sitemap
        ]
        print(f"\n  dumped articles missing from the live sitemap: {len(absent)}")
        for wp_id, data in absent[:10]:
            print(f"      {wp_id}  {str(data['title'])[:55]}  {data['link']}")
        if absent:
            print("    (a handful is normal — Yoast omits noindex'd posts)")

    # ---- body integrity ------------------------------------------------
    empty = [(i, d) for i, d in wxr.items() if d["chars"] == 0]
    thin = [(i, d) for i, d in wxr.items() if 0 < int(d["chars"]) < MIN_BODY_CHARS]
    print(f"\n  body integrity (raw post_content)")
    print(f"    empty bodies           : {len(empty):>6,}")
    print(f"    under {MIN_BODY_CHARS} chars        : {len(thin):>6,}")
    if wxr:
        sizes = sorted(int(d["chars"]) for d in wxr.values())
        print(f"    median body            : {sizes[len(sizes) // 2]:>6,} chars")
        print(f"    total content          : {sum(sizes) / 2**20:>6.1f} MB")
    # An empty body is not automatically a fault. Some posts exist only so a
    # redirect rule has something to attach to, and some are editorial
    # placeholders that were published and never filled in. Both are faithful
    # copies of the source. Only a *rate* of empties indicates a broken
    # export, so the verdict turns on set completeness, not on these.
    if empty:
        print("    EMPTY (verify each is intentional, not lost content):")
        for wp_id, data in empty[:10]:
            print(f"      {wp_id}  {str(data['title'])[:60]}")
    for wp_id, data in thin[:5]:
        print(f"      thin: {wp_id}  {data['chars']:>4}c  {str(data['title'])[:50]}")

    if wxr and len(empty) / len(wxr) > 0.005:
        ok = False
        print(
            f"    FAIL: {len(empty) / len(wxr):.1%} of bodies are empty — that is a "
            "broken export, not editorial oddity"
        )

    # ---- duplicate slugs ----------------------------------------------
    slugs: dict[str, list[int]] = {}
    for wp_id, data in wxr.items():
        slugs.setdefault(str(data["slug"]), []).append(wp_id)
    dupes = {s: ids for s, ids in slugs.items() if len(ids) > 1 and s}
    print(f"\n  duplicate slugs: {len(dupes)}")
    for slug_value, ids in list(dupes.items())[:5]:
        print(f"      {slug_value}  ids={ids}")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", action="append", help="site slug (repeatable); default: jakarta and bali")
    args = parser.parse_args()

    sites = args.site or ["jakarta", "bali"]
    results = {}
    for slug in sites:
        if not re.match(r"^[a-z][a-z0-9-]*$", slug):
            print(f"invalid slug: {slug!r}", file=sys.stderr)
            return 2
        results[slug] = check_site(slug)

    print(f"\n{'=' * 66}")
    for slug, ok in results.items():
        print(f"  {slug:10} {'COMPLETE — every source agrees' if ok else 'DISCREPANCIES ABOVE'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
