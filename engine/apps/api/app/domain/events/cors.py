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

from collections.abc import Sequence

from now_config import SiteConfig


def allowed_origins_for_site(
    site: SiteConfig, extra: Sequence[str] | None = None
) -> tuple[str, ...]:
    """The origins this site's own front end is served from.

    `hostname` is the site's CANONICAL host, which is not always the host it
    is currently served from. Before a cutover the engine runs on a staging
    domain while `hostname` still names the domain the legacy site holds — and
    then this allowlist rejects the site's own front end, 403, silently, and
    the beacon collects nothing. That is not hypothetical: it is what
    production did, for a week.

    `extra` is that gap, supplied per site from
    `ENGINE_API_EXTRA_ALLOWED_ORIGINS` (see `app/config.py` for why it is
    configuration rather than a change to `hostname`). It is normally empty,
    and becomes empty again once the cutover makes it redundant.
    """
    origins = [f"https://{site.hostname}", f"https://www.{site.hostname}"]
    if extra:
        # Deduplicated, order preserved — an operator listing an origin the
        # registry already covers should be a no-op, not a doubled entry in a
        # rejection log.
        origins.extend(o for o in extra if o and o not in origins)
    return tuple(origins)


def _is_local_dev_origin(origin: str) -> bool:
    """`http://localhost:<port>` (any port) -- covers the beacon's own
    `demo/` page and local API development. Never allowed when
    `settings.env == "production"`."""
    return origin == "http://localhost" or origin.startswith("http://localhost:")


def origin_is_allowed(
    origin: str, site: SiteConfig, *, env: str, extra: Sequence[str] | None = None
) -> bool:
    if origin in allowed_origins_for_site(site, extra):
        return True
    if env != "production" and _is_local_dev_origin(origin):
        return True
    return False
