"""Provider classification for embeds (`wp:embed` blocks and raw
`<iframe>`s — the corpus has 399 iframes and only 8 `wp:embed` blocks, so
most embeds arrive as bare iframes from the classic editor, not Gutenberg
embed blocks)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_DOMAIN_PROVIDERS = (
    (("youtube.com", "youtu.be"), "youtube"),
    (("vimeo.com",), "vimeo"),
    (("google.com/maps", "maps.google.com"), "google_maps"),
    (("anchor.fm",), "anchor"),
    (("soundcloud.com",), "soundcloud"),
    (("spotify.com",), "spotify"),
    (("instagram.com",), "instagram"),
    (("twitter.com", "x.com"), "twitter"),
    (("facebook.com",), "facebook"),
    (("tiktok.com",), "tiktok"),
    (("jotform.com",), "jotform"),
)


def classify_provider(url: str) -> str:
    if not url:
        return "unknown"
    netloc_and_path = urlparse(url).netloc.lower() + urlparse(url).path.lower()
    for domains, provider in _DOMAIN_PROVIDERS:
        if any(d in netloc_and_path or d in url.lower() for d in domains):
            return provider
    return "other"
