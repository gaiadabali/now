from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward looking for the repo marker (ARCHITECTURE.md)."""
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / "ARCHITECTURE.md").is_file():
            return parent
    return here.parents[5]


REPO_ROOT = find_repo_root()

# The only hosts this job is allowed to fetch from. Anything else found in
# content_html (Google Fonts, YouTube embeds, tracking pixels, the unrelated
# best.nowjakarta.co.id "Best Of" microsite, etc.) is a third-party asset,
# not our media, and is left alone — never fetched, never counted.
SITE_HOSTS: dict[str, tuple[str, ...]] = {
    "jakarta": ("www.nowjakarta.co.id", "nowjakarta.co.id"),
    "bali": ("www.nowbali.co.id", "nowbali.co.id"),
}

# Canonical (preferred) host per city — used only to fold www/bare duplicates
# into one storage key. The original URL is always preserved in the manifest.
CANONICAL_HOST: dict[str, str] = {
    "jakarta": "www.nowjakarta.co.id",
    "bali": "www.nowbali.co.id",
}

ALL_SITE_HOSTS: frozenset[str] = frozenset(h for hosts in SITE_HOSTS.values() for h in hosts)


def city_for_host(host: str) -> str | None:
    for city, hosts in SITE_HOSTS.items():
        if host in hosts:
            return city
    return None


@dataclass(frozen=True)
class MirrorConfig:
    concurrency: int = 4
    # Deliberately unhurried — this is a live, revenue-earning site. Slower
    # costs nothing; taking it down is catastrophic. See ticket constraints.
    delay_seconds: float = 0.4
    timeout_seconds: float = 30.0
    max_retries: int = 6
    user_agent: str = (
        "NOWEngineMediaMirror/0.1 (+local archival mirror; read-only GET; "
        "contact ops@gaiada.com)"
    )
    garage_s3_endpoint: str = "http://localhost:3900"
    garage_region: str = "garage"
    garage_bucket: str = "now-media"
    garage_access_key_id: str = ""
    garage_secret_access_key: str = ""
