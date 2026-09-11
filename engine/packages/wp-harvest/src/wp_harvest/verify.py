from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from .client import RestClient


def normalise(url: str, default_host: str = "") -> str:
    """Compare URLs on host+path only, case- and www-insensitively.

    Scheme, ``www.``, the trailing slash and the query string are all things
    that differ between a stored permalink and a sitemap entry without the
    page being any different.

    ``default_host`` supplies the host for a *relative* input. The permalink
    map stores paths (``/some-post/``) while a sitemap stores absolute URLs;
    without this they would share no keys at all and every stored URL would
    read as missing.
    """
    parts = urlsplit(url.strip())
    host = (parts.netloc or default_host).lower().removeprefix("www.")
    path = (parts.path or "/").rstrip("/") or "/"
    return f"{host}{path.lower()}"


def host_of(base_url: str) -> str:
    """The bare, www-less host of a base URL, for use as ``default_host``."""
    return urlsplit(base_url).netloc.lower().removeprefix("www.")


@dataclass
class UrlCheck:
    url: str
    status: int | None
    final_url: str | None
    error: str | None
    seconds: float

    @property
    def outcome(self) -> str:
        if self.error is not None:
            return "error"
        if self.status is None:
            return "error"
        if self.status == 200:
            return "ok"
        if 300 <= self.status < 400:
            return "redirect"
        if self.status == 404:
            return "not_found"
        return "other"

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "outcome": self.outcome,
            "error": self.error,
            "seconds": round(self.seconds, 2),
        }


def check_urls(
    client: RestClient,
    urls: Iterable[str],
    *,
    delay: float | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[UrlCheck]:
    """HEAD-then-GET each URL, throttled.

    HEAD first because it is cheap; a WordPress theme that mishandles HEAD
    (405/501) is retried as a GET so a server quirk is not recorded as a
    broken URL. Redirects are *not* followed — for a redirect audit the first
    hop is the finding.
    """
    pause = client.config.delay_seconds if delay is None else delay
    results: list[UrlCheck] = []
    total = len(list(urls)) if isinstance(urls, (list, tuple)) else None
    sequence = list(urls)
    total = len(sequence)

    for index, url in enumerate(sequence, start=1):
        started = time.monotonic()
        status: int | None = None
        final: str | None = None
        error: str | None = None
        try:
            client.request_count += 1
            response = client._client.request(
                "HEAD", url, follow_redirects=False, timeout=client.config.timeout_seconds
            )
            if response.status_code in (405, 501):
                client.request_count += 1
                response = client._client.request(
                    "GET", url, follow_redirects=False, timeout=client.config.timeout_seconds
                )
            status = response.status_code
            final = response.headers.get("Location")
        except httpx.HTTPError as exc:
            error = f"{type(exc).__name__}: {exc}"

        results.append(
            UrlCheck(url, status, final, error, time.monotonic() - started)
        )
        if progress and (index == 1 or index % 50 == 0 or index == total):
            ok = sum(1 for r in results if r.outcome == "ok")
            progress(f"  checked {index}/{total} ({ok} ok)")
        if index < total:
            time.sleep(pause)

    return results


def summarise(checks: list[UrlCheck]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for check in checks:
        counts[check.outcome] = counts.get(check.outcome, 0) + 1
    counts["total"] = len(checks)
    return counts


def compare_to_sitemap(
    stored_urls: Iterable[str],
    sitemap_urls: Iterable[str],
    default_host: str = "",
) -> dict[str, Any]:
    """Set-compare a stored permalink list against the live sitemap.

    This is the part F16 was missing: an exact comparison over the whole
    corpus, rather than an HTTP sample whose timeouts had to be explained
    away. A stored URL absent from the sitemap is the population worth
    spending real requests on.
    """
    stored_index: dict[str, str] = {}
    for url in stored_urls:
        stored_index.setdefault(normalise(url, default_host), url)
    live_index: dict[str, str] = {}
    for url in sitemap_urls:
        live_index.setdefault(normalise(url, default_host), url)

    stored_keys = set(stored_index)
    live_keys = set(live_index)
    missing = sorted(stored_keys - live_keys)
    extra = sorted(live_keys - stored_keys)

    return {
        "stored": len(stored_keys),
        "live": len(live_keys),
        "matched": len(stored_keys & live_keys),
        "missing_from_sitemap": [stored_index[k] for k in missing],
        "not_in_stored_map": [live_index[k] for k in extra],
    }
