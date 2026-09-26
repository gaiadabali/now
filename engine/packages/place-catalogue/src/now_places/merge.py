"""P1.2 -- applying and reversing one merge.

A merge of LOSER into SURVIVOR, inside the caller's transaction:

  1. both rows are locked (`FOR UPDATE`) and re-checked: neither already
     merged, not the same row, the loser not approved (`active`);
  2. every `place_mentions` row of the loser is moved to the survivor --
     the ids moved are recorded;
  3. any row that had earlier been merged INTO the loser is re-pointed to
     the survivor (so `merged_into` never points at a merged row) -- ids
     recorded;
  4. `loser.merged_into_id = survivor`;
  5. an entry is appended to `survivor.aliases`.

The alias entry IS the audit record -- it lives on the surviving row, is
versioned by Payload the next time the desk saves that row, and carries
everything needed to reverse the merge exactly:

    {"name": "<loser's name>", "placeId": <loser id>, "mergedAt": "<iso>",
     "by": "<actor>", "score": 0.93 | null,
     "mentionIds": [...], "repointedPlaceIds": [...],
     "inheritedAliases": ["<names the loser itself carried>"]}

So "the survivor keeps both names": its own `name`, plus the loser's in
`aliases` (and any names the loser had absorbed before). The place desk
writes the identical shape when an editor merges from the UI
(engine/apps/web/src/lib/placeDesk.ts) -- one audit format, one `unmerge`.

`unmerge(loser)` is the exact inverse, refused if the survivor has itself
since been merged (unwind the later merge first -- last in, first out).

Each merge and unmerge is also appended as one JSON line to
`<city>/content/extracted/place_merge_log.jsonl` by the CLI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection


class MergeRefused(Exception):
    pass


@dataclass
class MergeRecord:
    action: str  # "merge" | "unmerge"
    loser_id: int
    survivor_id: int
    loser_name: str
    survivor_name: str
    score: float | None
    by: str
    at: str
    mention_ids: list[int] = field(default_factory=list)
    repointed_place_ids: list[int] = field(default_factory=list)

    def as_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def _lock(conn: Connection, ids: list[int]) -> dict[int, dict]:
    rows = conn.execute(
        text(
            "select id, name, status::text as status, merged_into_id, aliases "
            "from public.places where id = any(:ids) order by id for update"
        ),
        {"ids": ids},
    ).mappings().all()
    return {r["id"]: dict(r) for r in rows}


def _alias_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    return list(value) if isinstance(value, list) else []


def _alias_names(entries: list) -> list[str]:
    names: list[str] = []
    for e in entries:
        if isinstance(e, str):
            names.append(e)
        elif isinstance(e, dict) and e.get("name"):
            names.append(e["name"])
            names.extend(n for n in e.get("inheritedAliases", []) if isinstance(n, str))
    return names


def apply_merge(conn: Connection, loser_id: int, survivor_id: int, *, score: float | None, by: str, now: datetime | None = None) -> MergeRecord:
    if loser_id == survivor_id:
        raise MergeRefused("a place cannot be merged into itself")
    rows = _lock(conn, [loser_id, survivor_id])
    if loser_id not in rows or survivor_id not in rows:
        raise MergeRefused(f"place {loser_id if loser_id not in rows else survivor_id} does not exist")
    loser, survivor = rows[loser_id], rows[survivor_id]
    if loser["merged_into_id"] is not None:
        raise MergeRefused(f"place {loser_id} is already merged into {loser['merged_into_id']}")
    if survivor["merged_into_id"] is not None:
        raise MergeRefused(f"place {survivor_id} is itself merged into {survivor['merged_into_id']}; merge into that row instead")
    if loser["status"] == "active":
        raise MergeRefused(f"place {loser_id} is approved; un-approve it before merging it away")

    at = (now or datetime.now(timezone.utc)).isoformat()
    mention_ids = sorted(
        r[0]
        for r in conn.execute(
            text(
                "update public.place_mentions set place_id = :s, updated_at = now() "
                "where place_id = :l returning id"
            ),
            {"s": survivor_id, "l": loser_id},
        ).all()
    )
    repointed = sorted(
        r[0]
        for r in conn.execute(
            text(
                "update public.places set merged_into_id = :s, updated_at = now() "
                "where merged_into_id = :l returning id"
            ),
            {"s": survivor_id, "l": loser_id},
        ).all()
    )
    conn.execute(
        text("update public.places set merged_into_id = :s, updated_at = now() where id = :l"),
        {"s": survivor_id, "l": loser_id},
    )
    entries = _alias_list(survivor["aliases"])
    entries.append(
        {
            "name": loser["name"],
            "placeId": loser_id,
            "mergedAt": at,
            "by": by,
            "score": round(score, 4) if score is not None else None,
            "mentionIds": mention_ids,
            "repointedPlaceIds": repointed,
            "inheritedAliases": _alias_names(_alias_list(loser["aliases"])),
        }
    )
    conn.execute(
        text("update public.places set aliases = cast(:a as jsonb), updated_at = now() where id = :s"),
        {"a": json.dumps(entries, ensure_ascii=False), "s": survivor_id},
    )
    return MergeRecord("merge", loser_id, survivor_id, loser["name"], survivor["name"], score, by, at, mention_ids, repointed)


def unmerge(conn: Connection, loser_id: int, *, by: str, now: datetime | None = None) -> MergeRecord:
    head = conn.execute(text("select merged_into_id from public.places where id = :l"), {"l": loser_id}).scalar()
    if head is None:
        raise MergeRefused(f"place {loser_id} is not merged")
    rows = _lock(conn, [loser_id, head])
    loser, survivor = rows[loser_id], rows[head]
    if survivor["merged_into_id"] is not None:
        raise MergeRefused(
            f"place {head} has since been merged into {survivor['merged_into_id']}; unmerge that first"
        )
    entries = _alias_list(survivor["aliases"])
    idx = next(
        (i for i in range(len(entries) - 1, -1, -1) if isinstance(entries[i], dict) and entries[i].get("placeId") == loser_id),
        None,
    )
    if idx is None:
        raise MergeRefused(f"place {head} carries no merge record for {loser_id}; cannot reverse it exactly")
    entry = entries.pop(idx)
    mention_ids = [int(m) for m in entry.get("mentionIds", [])]
    repointed = [int(p) for p in entry.get("repointedPlaceIds", [])]
    moved_back = sorted(
        r[0]
        for r in conn.execute(
            text(
                "update public.place_mentions set place_id = :l, updated_at = now() "
                "where id = any(:ids) and place_id = :s returning id"
            ),
            {"l": loser_id, "s": head, "ids": mention_ids},
        ).all()
    )
    if repointed:
        conn.execute(
            text("update public.places set merged_into_id = :l, updated_at = now() where id = any(:ids) and merged_into_id = :s"),
            {"l": loser_id, "s": head, "ids": repointed},
        )
    conn.execute(text("update public.places set merged_into_id = null, updated_at = now() where id = :l"), {"l": loser_id})
    conn.execute(
        text("update public.places set aliases = cast(:a as jsonb), updated_at = now() where id = :s"),
        {"a": json.dumps(entries, ensure_ascii=False) if entries else None, "s": head},
    )
    at = (now or datetime.now(timezone.utc)).isoformat()
    return MergeRecord("unmerge", loser_id, head, loser["name"], survivor["name"], entry.get("score"), by, at, moved_back, repointed)
