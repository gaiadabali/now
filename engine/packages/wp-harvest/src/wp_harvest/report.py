from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Config
from .runner import CollectionResult
from .sink import read_jsonl


def _human_bytes(size: float | None) -> str:
    if not size:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:,.1f} {unit}" if unit != "B" else f"{int(size):,} B"
        size /= 1024
    return f"{size:,.1f} TB"


def media_footprint(path: Path) -> dict[str, Any]:
    """Summarise a harvested media manifest: what a full mirror would cost.

    Originals and derivatives are counted separately because only the
    originals have to be migrated — imgproxy regenerates the rest.
    """
    if not path.exists():
        return {}
    rows = read_jsonl(path)

    original_bytes = sum(r.get("filesize") or 0 for r in rows)
    known = sum(1 for r in rows if r.get("filesize"))
    derivative_bytes = 0
    derivative_count = 0
    for row in rows:
        for size in row.get("sizes") or []:
            if size.get("name") == "full":
                continue  # 'full' is the original, already counted
            derivative_count += 1
            derivative_bytes += size.get("filesize") or 0

    mimes = Counter(r.get("mime") or "unknown" for r in rows)
    years = Counter(
        (r.get("file") or "").split("/")[0] for r in rows if (r.get("file") or "")
    )
    missing_url = [r["wp_id"] for r in rows if not r.get("source_url")]
    guid_mismatch = sum(
        1
        for r in rows
        if r.get("guid")
        and r.get("source_url")
        and r["guid"] != r["source_url"]
    )

    return {
        "items": len(rows),
        "filesize_known": known,
        "original_bytes": original_bytes,
        "original_bytes_human": _human_bytes(original_bytes),
        "derivative_count": derivative_count,
        "derivative_bytes": derivative_bytes,
        "derivative_bytes_human": _human_bytes(derivative_bytes),
        "total_bytes_human": _human_bytes(original_bytes + derivative_bytes),
        "mime_types": dict(mimes.most_common()),
        "by_year": dict(sorted(years.items())),
        "missing_source_url": missing_url,
        "guid_differs_from_source_url": guid_mismatch,
    }


def build(
    config: Config,
    results: list[CollectionResult],
    extras: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    generated = datetime.now(UTC).isoformat(timespec="seconds")
    media_result = next((r for r in results if r.key == "media"), None)
    footprint = media_footprint(media_result.path) if media_result else {}

    payload: dict[str, Any] = {
        "site": config.slug,
        "base_url": config.base_url,
        "generated_at": generated,
        "output_dir": str(config.output_dir),
        "collections": [r.as_dict() for r in results],
        "media_footprint": footprint,
        **(extras or {}),
    }

    lines: list[str] = [
        f"# Live harvest report — {config.slug}",
        "",
        f"**Source:** {config.base_url} (WordPress REST, read-only)  ",
        f"**Generated:** {generated}  ",
        f"**Output:** `{config.output_dir}`",
        "",
        "## Collections",
        "",
        "| Collection | Endpoint | API total | Written | Unique | Pages | Context | Complete |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for result in results:
        lines.append(
            f"| {result.key} | `{result.endpoint}` | "
            f"{result.reported_total if result.reported_total is not None else '?'} | "
            f"{result.written} | {result.unique_ids} | {result.pages} | "
            f"{result.context} | {'✅' if result.complete else '❌'} |"
        )

    if footprint:
        lines += [
            "",
            "## Media footprint",
            "",
            f"- **Items:** {footprint['items']:,} "
            f"({footprint['filesize_known']:,} report a filesize)",
            f"- **Originals:** {footprint['original_bytes_human']}",
            f"- **Derivatives:** {footprint['derivative_count']:,} files, "
            f"{footprint['derivative_bytes_human']}",
            f"- **Full mirror:** {footprint['total_bytes_human']}",
            f"- **`guid` ≠ `source_url`:** {footprint['guid_differs_from_source_url']:,} "
            "items — never fetch by `guid` (F11)",
            "",
            "| MIME | Items |",
            "|---|---:|",
        ]
        for mime, count in list(footprint["mime_types"].items())[:12]:
            lines.append(f"| `{mime}` | {count:,} |")

    incomplete = [r for r in results if not r.complete]
    lines += [
        "",
        "## Acceptance",
        "",
    ]
    if incomplete:
        lines.append("**Incomplete** — these wrote fewer unique rows than the API reported:")
        lines += [
            f"- `{r.key}`: {r.unique_ids} of {r.reported_total} "
            f"(re-run with `--resume`)"
            for r in incomplete
        ]
    else:
        lines.append(
            "Every selected collection wrote at least as many unique rows as the "
            "API reported. Page cursors discarded."
        )

    lines += [
        "",
        "## What this does *not* contain",
        "",
        "Read this before treating the harvest as migration-complete:",
        "",
        "- **Unregistered postmeta.** REST returns only meta that a plugin "
        "registered with `show_in_rest`. Yoast focus keywords, MapPress geo "
        "and most ACF field data live in `postmeta` and do **not** appear "
        "here. Those need a database dump.",
        "- **Non-public statuses.** An anonymous caller sees `publish` only — "
        "no drafts, no `private`, no revisions.",
        "- **Rendered vs raw content.** Under `context=view` the `content_html` "
        "field has been through `the_content` filters (shortcodes expanded, "
        "cache-plugin lazy-load attributes injected). Rows carry "
        "`content_is_raw: false` to say so. Only an authenticated "
        "`context=edit` harvest returns the actual `post_content` column.",
        "- **The files themselves.** This is a manifest of URLs and sizes, not "
        "a copy of `wp-content/uploads`.",
    ]

    return "\n".join(lines) + "\n", payload


def write(
    config: Config,
    results: list[CollectionResult],
    extras: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    markdown, payload = build(config, results, extras)
    out = config.ensure_output_dir()
    md_path = out / "harvest_report.md"
    json_path = out / "harvest_report.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return md_path, json_path
