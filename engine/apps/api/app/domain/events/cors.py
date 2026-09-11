"""CORS origin allowlist for `POST /v1/{site}/events` -- decision C2.

ARCHITECTURE.md §16 and this API's own README describe API-key auth for the
beacon. PROGRESS.md's C2 supersedes that: a key shipped inside public
client JS served to every visitor of a public website is not a secret, and
the beacon (E0.4) deliberately sends no auth header at all (see its
README's "Notes for E0.5" section). The replacement control is a CORS
origin allowlist, **sourced from the site registry** rather than
hardcoded -- `sites.hostname` is already a real, per-site config column
(E0.2), so no new schema is needed to satisfy "add allowed origins via
config, not hardcoded" (that column, not a literal, is the config).

A disallowed origin cannot forge a *readable* cross-origin response (the
browser withholds it), which is what matters for `fetch(..., {keepalive})`.
`navigator.sendBeacon` -- the beacon's primary transport, used on every
unload -- always sends in `no-cors` mode and never preflights, so this
allowlist cannot stop an arbitrary third-party page from POSTing junk
through it that way; the endpoint still checks `Origin` server-side and
rejects a mismatch outright (`403`) as defense in depth, but this is not
mistaken for a strong anti-forgery boundary -- see the E0.5 report's
blockers/follow-ups for the honest limits of that.
"""

from __future__ import annotations

from now_config import SiteConfig


def allowed_origins_for_site(site: SiteConfig) -> tuple[str, str]:
    """The origins this site's own front end is served from. `nav`/
    `brand_tokens` etc. are jsonb config the schema owner could later use to
    list additional origins (a CDN preview domain, a staging alias) per
    site without another migration -- not needed yet since every registered
    site's `hostname` column alone is sufficient (ARCHITECTURE.md §2/§14
    topology: one production hostname per city, no site literals here)."""
    return (f"https://{site.hostname}", f"https://www.{site.hostname}")


def _is_local_dev_origin(origin: str) -> bool:
    """`http://localhost:<port>` (any port) -- covers the beacon's own
    `demo/` page and local API development. Never allowed when
    `settings.env == "production"`."""
    return origin == "http://localhost" or origin.startswith("http://localhost:")


def origin_is_allowed(origin: str, site: SiteConfig, *, env: str) -> bool:
    if origin in allowed_origins_for_site(site):
        return True
    if env != "production" and _is_local_dev_origin(origin):
        return True
    return False
