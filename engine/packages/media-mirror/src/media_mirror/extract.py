from __future__ import annotations

import re
from urllib.parse import unquote, urljoin, urlsplit

from .config import ALL_SITE_HOSTS

# img src / poster / a-href-to-an-image, and srcset entries. Kept simple and
# permissive on purpose: false positives outside our host allowlist are
# filtered out by resolve(); the risk that matters is missing a real one.
_SRC_RE = re.compile(r'''(?:src|poster)\s*=\s*["']([^"']+)["']''', re.IGNORECASE)
_SRCSET_RE = re.compile(r'''srcset\s*=\s*["']([^"']+)["']''', re.IGNORECASE)
_HREF_IMG_RE = re.compile(
    r'''href\s*=\s*["']([^"']+\.(?:jpe?g|png|gif|webp|svg|bmp|tiff?))["']''',
    re.IGNORECASE,
)

IMAGE_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|svg|bmp|tiff?)$", re.IGNORECASE)


def _split_srcset(value: str) -> list[str]:
    urls = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        url = part.split()[0]
        if url:
            urls.append(url)
    return urls


def raw_urls(html: str) -> list[str]:
    """Every candidate media URL literal found in one article's HTML."""
    if not html:
        return []
    found: list[str] = []
    for m in _SRC_RE.finditer(html):
        found.append(m.group(1))
    for m in _SRCSET_RE.finditer(html):
        found.extend(_split_srcset(m.group(1)))
    for m in _HREF_IMG_RE.finditer(html):
        found.append(m.group(1))
    return found


def resolve(raw: str, base_url: str) -> str | None:
    """Resolve a raw HTML URL literal to an absolute URL, or None to drop it.

    Dropped: non-http(s) schemes (data:, mailto:, javascript:), and anything
    that resolves to a host outside the fixed site-host allowlist (third-party
    embeds, trackers, unrelated subsites) — see config.SITE_HOSTS.
    """
    raw = raw.strip()
    if not raw or raw.startswith(("data:", "mailto:", "javascript:", "#")):
        return None
    absolute = urljoin(base_url + "/", raw)
    parts = urlsplit(absolute)
    if parts.scheme not in ("http", "https"):
        return None
    if parts.netloc not in ALL_SITE_HOSTS:
        return None
    return absolute


def canonical_key(url: str) -> str:
    """Host+path key used to fold www/bare-host duplicates into one asset.

    Query strings and fragments are dropped (WordPress media URLs carry none
    meaningfully); the path is percent-decoded so encoded/unencoded variants
    of the same filename collide too.
    """
    parts = urlsplit(url)
    host = parts.netloc.removeprefix("www.")
    path = unquote(parts.path)
    return f"{host}{path}"


def extract_article_urls(html: str, base_url: str) -> list[str]:
    """Absolute, in-scope media URLs referenced by one article's HTML."""
    out = []
    for raw in raw_urls(html):
        resolved = resolve(raw, base_url)
        if resolved:
            out.append(resolved)
    return out
