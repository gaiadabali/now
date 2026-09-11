from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterator

from .config import MirrorConfig
from .fetch import MediaFetcher, FetchResult
from .ledger import Ledger
from .ratelimit import RateLimiter
from .sniff import sniff_image
from .storage import garage_client, object_exists, object_key, put_object


def iter_inventory(path: Path) -> Iterator[dict[str, Any]]:
    import json

    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


class MirrorRun:
    """Drives one (resumable) mirror pass over the inventory.

    Progress model: the ledger (append-only JSONL) is the single source of
    truth for what is already done. On startup we load every 'ok'/'not_found'
    key and skip them — an interrupted run loses at most the handful of
    fetches that were in flight, and picks up exactly where it left off.
    """

    def __init__(
        self,
        config: MirrorConfig,
        ledger_path: Path,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> None:
        self.config = config
        self.limiter = RateLimiter(config.delay_seconds / max(1, config.concurrency))
        self.ledger_path = ledger_path
        self.limit = limit
        self.dry_run = dry_run
        self._hash_lock = threading.Lock()
        self._seen_hashes: dict[str, str] = {}  # sha256 -> key, for in-run dedup
        self.stats = {
            "attempted": 0,
            "ok": 0,
            "not_found": 0,
            "error": 0,
            "skipped_already_done": 0,
            "bytes_downloaded": 0,
            "bytes_uploaded": 0,
            "duplicate_content_reused": 0,
            "invalid_body_rejected": 0,
        }
        self._stats_lock = threading.Lock()

    def _bump(self, **kwargs: int) -> None:
        with self._stats_lock:
            for k, v in kwargs.items():
                self.stats[k] += v

    def run(self, inventory_path: Path) -> dict[str, Any]:
        ledger = Ledger(self.ledger_path)
        try:
            done = ledger.load_done()
            s3 = None if self.dry_run else garage_client(self.config)

            candidates = []
            for entry in iter_inventory(inventory_path):
                if entry["key"] in done:
                    self._bump(skipped_already_done=1)
                    continue
                candidates.append(entry)
                if self.limit and len(candidates) >= self.limit:
                    break

            with MediaFetcher(self.config, self.limiter) as fetcher:
                with ThreadPoolExecutor(max_workers=self.config.concurrency) as pool:
                    futures = {
                        pool.submit(self._process_one, entry, fetcher, s3, ledger): entry
                        for entry in candidates
                    }
                    for fut in as_completed(futures):
                        fut.result()  # re-raise any bug immediately, don't swallow
        finally:
            ledger.close()

        return dict(self.stats)

    def _process_one(self, entry: dict[str, Any], fetcher: MediaFetcher, s3, ledger: Ledger) -> None:
        self._bump(attempted=1)
        url = entry["fetch_url"]
        key = entry["key"]
        city = entry["city"]

        result: FetchResult = fetcher.fetch(url)

        if result.status == "not_found":
            self._bump(not_found=1)
            ledger.record({"key": key, "url": url, "status": "not_found", "http_status": result.http_status})
            return

        if result.status == "error":
            self._bump(error=1)
            ledger.record({"key": key, "url": url, "status": "error", "error": result.error})
            return

        body = result.body or b""
        sniffed = sniff_image(body)
        if sniffed is None:
            # This is exactly the "200 OK but it's an error page" failure
            # mode called out in the ticket: reject rather than store it.
            self._bump(invalid_body_rejected=1, error=1)
            ledger.record(
                {
                    "key": key,
                    "url": url,
                    "status": "error",
                    "error": "body_not_a_recognized_image",
                    "http_content_type": result.content_type,
                    "byte_len": len(body),
                }
            )
            return

        mime, ext = sniffed
        sha256 = hashlib.sha256(body).hexdigest()
        self._bump(bytes_downloaded=len(body))

        with self._hash_lock:
            existing = self._seen_hashes.get(sha256)
            if existing is None:
                self._seen_hashes[sha256] = object_key(city, sha256, ext)
            storage_key = self._seen_hashes[sha256]
            reused = existing is not None

        if reused:
            self._bump(duplicate_content_reused=1)
        elif not self.dry_run:
            already = object_exists(s3, self.config.garage_bucket, storage_key)
            if not already:
                put_object(s3, self.config.garage_bucket, storage_key, body, mime)
                self._bump(bytes_uploaded=len(body))

        self._bump(ok=1)
        ledger.record(
            {
                "key": key,
                "url": url,
                "status": "ok",
                "http_status": 200,
                "garage_bucket": self.config.garage_bucket,
                "garage_key": storage_key,
                "sha256": sha256,
                "mime": mime,
                "bytes": len(body),
                "content_type_reported": result.content_type,
                "dedup_reused": reused,
            }
        )
