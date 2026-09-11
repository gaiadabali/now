from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward looking for the repo marker (ARCHITECTURE.md).

    Mirrors ``wp_extract.config.find_repo_root`` so both packages agree on
    where the repo starts.
    """
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / "ARCHITECTURE.md").is_file():
            return parent
    # engine/packages/wp-harvest/src/wp_harvest/config.py -> repo root
    return here.parents[5]


REPO_ROOT = find_repo_root()

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ConfigError(ValueError):
    """Raised for a site slug or base URL this package refuses to act on."""


def _env_key(slug: str) -> str:
    return "WP_HARVEST_BASE_URL_" + slug.upper().replace("-", "_")


def resolve_base_url(slug: str, explicit: str | None = None) -> str:
    """Resolve a site's public base URL without hardcoding any hostname.

    Order: explicit ``--base-url`` > ``WP_HARVEST_BASE_URL_<SLUG>``. There is
    deliberately no built-in default and no per-site branch anywhere in this
    package (ARCHITECTURE.md principle 7) — a hostname is configuration, and
    the caller supplies it.
    """
    raw = (explicit or os.environ.get(_env_key(slug)) or "").strip()
    if not raw:
        raise ConfigError(
            f"No base URL for site {slug!r}. Pass --base-url or set {_env_key(slug)}."
        )
    if not raw.startswith(("http://", "https://")):
        raise ConfigError(f"Base URL for {slug!r} must be absolute http(s): {raw!r}")
    return raw.rstrip("/")


@dataclass(frozen=True)
class Config:
    """One harvest run against one site."""

    slug: str
    base_url: str
    output_dir: Path
    per_page: int = 100
    # Deliberately unhurried. F16 attributed 38% of a live URL check's timeouts
    # to rate limiting, so this package's default is slower than necessary
    # rather than fast enough to reproduce that.
    delay_seconds: float = 0.35
    timeout_seconds: float = 45.0
    max_retries: int = 5
    user_agent: str = (
        "NOWEngineHarvest/0.1 (+migration; read-only; contact ops@gaiada.com)"
    )

    @classmethod
    def build(
        cls,
        slug: str,
        base_url: str | None = None,
        output_dir: Path | None = None,
        **overrides: object,
    ) -> Config:
        if not SLUG_RE.match(slug or ""):
            raise ConfigError(
                f"Site slug {slug!r} must be lowercase alphanumeric with hyphens."
            )
        resolved = resolve_base_url(slug, base_url)
        out = output_dir or (REPO_ROOT / slug / "content" / "harvested")
        return cls(slug=slug, base_url=resolved, output_dir=Path(out), **overrides)  # type: ignore[arg-type]

    @property
    def api_root(self) -> str:
        return f"{self.base_url}/wp-json/wp/v2"

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir
