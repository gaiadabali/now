from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ResumableSink:
    """Append-only JSONL writer with a sidecar page cursor.

    A media harvest is ~260 requests per site; a network blip two thirds of
    the way through should not cost the first two thirds. After every page is
    flushed to disk the cursor advances, so a re-run with ``resume=True``
    restarts at the first page that never landed.
    """

    def __init__(self, path: Path, endpoint: str, resume: bool = False) -> None:
        self.path = Path(path)
        self.state_path = self.path.with_suffix(self.path.suffix + ".state.json")
        self.endpoint = endpoint
        self.records_written = 0
        self.last_completed_page = 0
        self._handle = None

        self.path.parent.mkdir(parents=True, exist_ok=True)
        state = self._read_state() if resume else None

        if state and state.get("endpoint") == endpoint and self.path.exists():
            self.last_completed_page = int(state.get("last_completed_page", 0))
            self.records_written = int(state.get("records_written", 0))
            self._truncate_to(self.records_written)
            self._handle = self.path.open("a", encoding="utf-8")
        else:
            self._handle = self.path.open("w", encoding="utf-8")
            self._write_state()

    # ---- lifecycle -----------------------------------------------------

    def __enter__(self) -> ResumableSink:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    @property
    def start_page(self) -> int:
        return self.last_completed_page + 1

    # ---- writing -------------------------------------------------------

    def write_page(self, page: int, records: list[dict[str, Any]]) -> None:
        """Write one page and advance the cursor, durably, in that order."""
        assert self._handle is not None, "sink is closed"
        for record in records:
            self._handle.write(json.dumps(record, ensure_ascii=False, default=str))
            self._handle.write("\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.records_written += len(records)
        self.last_completed_page = page
        self._write_state()

    def discard_state(self) -> None:
        """Drop the cursor once a harvest has completed cleanly."""
        self.state_path.unlink(missing_ok=True)

    # ---- state ---------------------------------------------------------

    def _read_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write_state(self) -> None:
        payload = {
            "endpoint": self.endpoint,
            "last_completed_page": self.last_completed_page,
            "records_written": self.records_written,
        }
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.state_path)

    def _truncate_to(self, line_count: int) -> None:
        """Cut any partial tail written after the last cursor advance.

        The cursor is written *after* the page is fsynced, so a crash between
        those two points leaves extra lines on disk. Trusting the cursor and
        discarding the excess keeps the file exactly consistent with it.
        """
        with self.path.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        if len(lines) <= line_count:
            return
        with self.path.open("w", encoding="utf-8") as handle:
            handle.writelines(lines[:line_count])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
