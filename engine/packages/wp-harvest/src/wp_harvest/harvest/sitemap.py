from __future__ import annotations

import re
import time
from typing import Any
from xml.etree import ElementTree

from ..client import HarvestError, RestClient

LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)

# Yoast and core both publish an index that points at child sitemaps; a small
# site may publish a flat urlset instead. Both shapes are handled.
INDEX_CANDIDATES = ("/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml")


def _locs(body: str) -> list[str]:
    """Pull <loc> values, preferring a real XML parse.

    Falls back to a regex because a cache plugin will occasionally prepend a
    comment or whitespace that makes the document technically malformed, and
    a sitemap is too useful to discard over a stray byte.
    """
    try:
        root = ElementTree.fromstring(body.strip())
    except ElementTree.ParseError:
        return LOC_RE.findall(body)
    found = [
        (el.text or "").strip()
        for el in root.iter()
        if el.tag.rsplit("}", 1)[-1] == "loc" and (el.text or "").strip()
    ]
    return found or LOC_RE.findall(body)


def find_index(client: RestClient) -> str | None:
    for path in INDEX_CANDIDATES:
        url = f"{client.config.base_url}{path}"
        try:
            response = client.get(url)
        except HarvestError:
            continue
        if response.status_code == 200 and "<loc>" in response.text.lower():
            return str(response.url)
    return None


def harvest(client: RestClient, progress: Any = None) -> dict[str, Any]:
    """Walk the sitemap index and return every declared URL.

    The result is the site's own statement of what it publishes — the right
    baseline for a redirect audit, and far stronger than sampling live URLs.
    """
    index_url = find_index(client)
    if index_url is None:
        return {"index": None, "children": [], "urls": [], "by_child": {}}

    index_body = client.get(index_url).text
    children = [u for u in _locs(index_body) if u != index_url]

    by_child: dict[str, list[str]] = {}
    urls: list[str] = []
    seen: set[str] = set()

    if not children:  # flat urlset, not an index
        children = [index_url]

    for child in children:
        time.sleep(client.config.delay_seconds)
        try:
            body = client.get(child).text
        except HarvestError:
            by_child[child] = []
            continue
        found = [u for u in _locs(body) if not u.endswith(".xml")]
        by_child[child] = found
        if progress:
            progress(f"  sitemap {child.rsplit('/', 1)[-1]}: {len(found)} urls")
        for url in found:
            if url not in seen:
                seen.add(url)
                urls.append(url)

    return {
        "index": index_url,
        "children": children,
        "urls": urls,
        "by_child": {k: len(v) for k, v in by_child.items()},
    }
