from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def render_report(all_stats: dict[str, dict[str, Any]], verification: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    w = lines.append

    w(f"# E1.1 extraction report — generated {ts}")
    w("")
    w("Source: UpdraftPlus MariaDB dump, table prefix `nb15_`, restored into a")
    w("throwaway container (see `docker/docker-compose.yml`, `scripts/restore.sh`).")
    w("This report is regenerated on every run of `wp-extract run` — it is not")
    w("hand-edited.")
    w("")

    w("## Acceptance criteria")
    w("")
    for name, ok, detail in verification["criteria"]:
        mark = "PASS" if ok else "FAIL"
        w(f"- [{'x' if ok else ' '}] **{mark}** — {name}: {detail}")
    w("")

    w("## Counts in vs out, by entity")
    w("")
    for entity, stats in all_stats.items():
        w(f"### {entity}")
        for k, v in stats.items():
            w(f"- `{k}`: {v}")
        w("")

    w("## Known discrepancies vs ARCHITECTURE.md §6")
    w("")
    for d in verification["discrepancies"]:
        w(f"- {d}")
    w("")

    return "\n".join(lines) + "\n"


def write_report(path: Path, all_stats: dict[str, dict[str, Any]], verification: dict[str, Any]) -> None:
    path.write_text(render_report(all_stats, verification), encoding="utf-8")
