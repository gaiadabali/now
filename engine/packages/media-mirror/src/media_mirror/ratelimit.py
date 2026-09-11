from __future__ import annotations

import threading
import time


class RateLimiter:
    """Global (cross-thread) minimum-interval gate.

    Concurrency controls how many requests may be *in flight* at once (i.e.
    how much we overlap network wait); this controls how often a new request
    may *start*, regardless of how many workers are asking. The two combined
    give a hard ceiling on request rate against the live site independent of
    thread count — raising --concurrency alone can never speed up the crawl
    past this gate.
    """

    def __init__(self, min_interval_seconds: float) -> None:
        self.min_interval = max(0.0, min_interval_seconds)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            start_at = max(now, self._next_allowed)
            self._next_allowed = start_at + self.min_interval
            sleep_for = start_at - now
        if sleep_for > 0:
            time.sleep(sleep_for)

    def penalize(self, extra_seconds: float) -> None:
        """Push the next-allowed time out further, e.g. after a 429/503."""
        with self._lock:
            self._next_allowed = max(self._next_allowed, time.monotonic() + extra_seconds)
