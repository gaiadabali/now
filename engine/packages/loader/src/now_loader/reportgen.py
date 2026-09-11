"""Renders the E1.8 load report (counts in vs out, every discrepancy named)
as Markdown, and a machine-readable JSON sibling."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def render(city: str, sections: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# E1.8 load report — {city}")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    for title, data in sections.items():
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| field | value |")
        lines.append("|---|---|")
        for key, value in data.items():
            lines.append(f"| {key} | {value} |")
        lines.append("")

    return "\n".join(lines)


def write_report(city: str, sections: dict[str, Any], reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_city = "".join(c if c.isalnum() else "_" for c in city)
    md_path = reports_dir / f"{safe_city}-load-report.md"
    json_path = reports_dir / f"{safe_city}-load-report.json"

    md_path.write_text(render(city, sections), encoding="utf-8")

    json_serializable = {
        title: {k: (asdict(v) if hasattr(v, "__dataclass_fields__") else v) for k, v in data.items()}
        for title, data in sections.items()
    }
    json_path.write_text(json.dumps(json_serializable, indent=2, default=str), encoding="utf-8")

    return md_path, json_path
