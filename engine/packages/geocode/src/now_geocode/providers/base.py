"""Provider interface (ARCHITECTURE.md §15: "Google is a resolution
service"). Rungs 2 and 3 of the ladder call this interface, never a
concrete provider directly, so `OfflineProvider` and `GoogleProvider` are
interchangeable and a third provider (e.g. a different geocoder, or a
cached-fixture replay provider for CI) can be swapped in without
touching `ladder.py`.

Two operations, matching the two rungs:
  - `geocode_address`  -> rung 2, structured address in hand
  - `find_place`       -> rung 3, name + loose context (Places Text Search)

Both return `ProviderResult | None` — `None` means "queried, found
nothing" (a stable negative, safe to cache), never a fabricated point.
`ProviderError` (and subclasses) means "the call itself failed" — retryable
(rate limit, transient network) vs. not (bad/missing key, malformed
request) — the caller decides whether to back off and resume or abort.
"""

from __future__ import annotations

from typing import Protocol

from now_geocode.models import ProviderResult


class ProviderError(Exception):
    """Base class for a failed provider call (as opposed to a clean
    zero-result response, which is a normal `None` return)."""


class RetryableProviderError(ProviderError):
    """Rate limit / transient failure — resumable, do not burn the
    candidate's attempt budget as a permanent failure."""


class ProviderConfigError(ProviderError):
    """Missing/invalid API key, request denied — not retryable without a
    human fixing the configuration."""


class GeocodeProvider(Protocol):
    name: str

    def geocode_address(self, address: str) -> ProviderResult | None: ...

    def find_place(self, name: str, context: str | None) -> ProviderResult | None: ...
