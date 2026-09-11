from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from .config import MirrorConfig
from .ratelimit import RateLimiter

# Same retry family as wp_harvest.client: 429/5xx family is transient
# overload/rate-limit, everything else is a real answer.
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 524})
TERMINAL_NOT_FOUND = frozenset({404, 410})


@dataclass
class FetchResult:
    status: str  # "ok" | "not_found" | "error"
    http_status: int | None = None
    content_type: str | None = None
    body: bytes | None = None
    error: str | None = None
    attempts: int = 0
    retries: int = 0


class MediaFetcher:
    def __init__(self, config: MirrorConfig, limiter: RateLimiter) -> None:
        self.config = config
        self.limiter = limiter
        self._client = httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            headers={"User-Agent": config.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MediaFetcher":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def fetch(self, url: str) -> FetchResult:
        delay = 2.0
        last_error = "no attempt made"
        retries = 0
        for attempt in range(1, self.config.max_retries + 1):
            self.limiter.wait()
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                response = None

            if response is not None:
                if response.status_code in TERMINAL_NOT_FOUND:
                    return FetchResult(
                        status="not_found",
                        http_status=response.status_code,
                        attempts=attempt,
                        retries=retries,
                    )
                if response.status_code not in RETRY_STATUS:
                    if response.status_code == 200:
                        return FetchResult(
                            status="ok",
                            http_status=200,
                            content_type=response.headers.get("Content-Type"),
                            body=response.content,
                            attempts=attempt,
                            retries=retries,
                        )
                    return FetchResult(
                        status="error",
                        http_status=response.status_code,
                        error=f"HTTP {response.status_code}",
                        attempts=attempt,
                        retries=retries,
                    )
                last_error = f"HTTP {response.status_code}"
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.strip().isdigit():
                    delay = max(delay, float(retry_after))
                # A 429/503 is the site telling us to back off; penalize the
                # *global* limiter too so every worker slows down, not just
                # this one request.
                self.limiter.penalize(delay)

            if attempt < self.config.max_retries:
                retries += 1
                time.sleep(delay)
                delay = min(delay * 2, 90.0)

        return FetchResult(status="error", error=last_error, attempts=self.config.max_retries, retries=retries)
