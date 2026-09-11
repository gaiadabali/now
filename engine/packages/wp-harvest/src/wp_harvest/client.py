from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Config


class HarvestError(RuntimeError):
    """A request failed after every retry, or the API answered nonsense."""


@dataclass
class PageResult:
    records: list[dict[str, Any]]
    total: int | None
    total_pages: int | None


# Retried: transient. 429 and 5xx are the rate-limit / overload family that
# F16 ran into. Everything else (401/403/404/400) is a real answer and is
# surfaced immediately rather than hammered.
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 524})


class RestClient:
    """Throttled, retrying, read-only WordPress REST client.

    Every request is a GET. The client has no method that writes, so a bug
    here cannot mutate the live site.
    """

    def __init__(self, config: Config, client: httpx.Client | None = None) -> None:
        self.config = config
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={
                "User-Agent": config.user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self.request_count = 0
        self.retry_count = 0

    def __enter__(self) -> RestClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # ---- single request ------------------------------------------------

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with exponential backoff, honouring Retry-After when present."""
        delay = 1.0
        last: str = "no attempt made"
        for attempt in range(1, self.config.max_retries + 1):
            try:
                self.request_count += 1
                response = self._client.get(url, params=params)
            except httpx.HTTPError as exc:  # timeout, connect error, read error
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in RETRY_STATUS:
                    return response
                last = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, float(retry_after))

            if attempt < self.config.max_retries:
                self.retry_count += 1
                time.sleep(delay)
                delay = min(delay * 2, 60.0)

        raise HarvestError(
            f"GET {url} failed after {self.config.max_retries} attempts ({last})"
        )

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = self.get(url, params)
        if response.status_code != 200:
            raise HarvestError(f"GET {url} -> HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise HarvestError(f"GET {url} returned non-JSON: {exc}") from exc

    # ---- collections ---------------------------------------------------

    def page(self, endpoint: str, page: int, extra: dict[str, Any] | None = None) -> PageResult:
        """Fetch one page of a collection.

        Ordered by ``id asc`` on purpose. The WordPress default is ``date
        desc``, which reshuffles under pagination if anything is published
        mid-harvest; ascending ids are append-only, so a long harvest can
        never skip or duplicate a record because of concurrent editing.
        """
        params: dict[str, Any] = {
            "per_page": self.config.per_page,
            "page": page,
            "orderby": "id",
            "order": "asc",
        }
        if extra:
            params.update(extra)

        url = f"{self.config.api_root}/{endpoint}"
        response = self.get(url, params)

        if response.status_code == 400 and b"rest_post_invalid_page_number" in response.content:
            return PageResult([], None, None)  # walked off the end
        if response.status_code != 200:
            raise HarvestError(f"GET {url} page={page} -> HTTP {response.status_code}")

        try:
            records = response.json()
        except ValueError as exc:
            raise HarvestError(f"GET {url} page={page} returned non-JSON: {exc}") from exc
        if not isinstance(records, list):
            raise HarvestError(f"GET {url} page={page} did not return a list")

        return PageResult(
            records=records,
            total=_int_header(response, "X-WP-Total"),
            total_pages=_int_header(response, "X-WP-TotalPages"),
        )

    def total(self, endpoint: str, extra: dict[str, Any] | None = None) -> int | None:
        """Report a collection's size without downloading it."""
        return self.page(endpoint, 1, {**(extra or {}), "_fields": "id"}).total

    def paginate(
        self,
        endpoint: str,
        start_page: int = 1,
        extra: dict[str, Any] | None = None,
    ) -> Iterator[tuple[int, list[dict[str, Any]], int | None]]:
        """Yield ``(page_number, records, reported_total)`` until exhausted."""
        page = max(1, start_page)
        while True:
            result = self.page(endpoint, page, extra)
            if not result.records:
                return
            yield page, result.records, result.total
            if result.total_pages is not None and page >= result.total_pages:
                return
            page += 1
            time.sleep(self.config.delay_seconds)


def _int_header(response: httpx.Response, name: str) -> int | None:
    raw = response.headers.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
