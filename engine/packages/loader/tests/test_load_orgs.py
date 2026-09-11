"""E4.1: `load_orgs` against the real platform DB (docker, per the task
brief -- "Docker and Postgres are running; no env vars needed"). A small
synthetic roster exercises exactly the shapes the real 1,562-row
`partner_roster.jsonl` contains -- a synthesized parent whose apex domain
never appears as a direct link (the `intercontinental` case), a
brand-keyword-inferred child at capped confidence, and an ordinary
high-confidence leaf -- without depending on that file's exact contents,
so this suite stays meaningful if the roster is re-extracted.

Every test runs inside a transaction rolled back in `conn`'s teardown
(same pattern as `now_platform_db`'s `test_partnerships_expiry.py`), so
this suite never leaves rows in the shared `now_platform` database.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from now_loader.load_orgs import load_orgs
from now_platform_db.settings import platform_database_url


@pytest.fixture
def conn():
    engine = create_engine(platform_database_url())
    connection = engine.connect()
    trans = connection.begin()
    try:
        yield connection
    finally:
        trans.rollback()
        connection.close()
        engine.dispose()


def _write_roster(tmp_path: Path, rows: list[dict], name: str = "roster.jsonl") -> Path:
    path = tmp_path / name
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    return path


def _unique(slug: str) -> str:
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _sample_rows(child_slug: str, parent_slug: str, grandchild_slug: str) -> list[dict]:
    return [
        {
            "org_slug": parent_slug,
            "name": "Synthesized Test Group",
            "parent_org_slug": None,
            "domains": [],
            "link_count": 0,
            "article_count": 0,
            "first_seen": None,
            "last_seen": None,
            "type_guess": "stay",
            "confidence": 0.35,
            "rel_audit": {"none": 0, "nofollow": 0, "sponsored": 0},
            "notes": ["synthesized group org: no direct outbound link to this apex domain"],
            "synthesized": True,
        },
        {
            "org_slug": child_slug,
            "name": "Test Group Coastal Property",
            "parent_org_slug": parent_slug,
            "domains": ["coastal.testgroup-e2e.example"],
            "link_count": 12,
            "article_count": 9,
            "first_seen": "2019-01-04",
            "last_seen": "2026-03-26",
            "type_guess": "stay",
            "confidence": 0.9,
            "rel_audit": {"none": 12, "nofollow": 0, "sponsored": 0},
            "notes": [],
            "synthesized": False,
        },
        {
            "org_slug": grandchild_slug,
            "name": "Testgroupcoastalresort",
            "parent_org_slug": child_slug,
            "domains": ["testgroupcoastalresort.example"],
            "link_count": 2,
            "article_count": 2,
            "first_seen": "2024-01-01",
            "last_seen": "2024-06-01",
            "type_guess": "stay",
            "confidence": 0.6,
            "rel_audit": {"none": 2, "nofollow": 0, "sponsored": 0},
            "notes": ["parent inferred from brand-keyword in the domain -- not a subdomain relationship; verify manually"],
            "synthesized": False,
        },
    ]


def test_synthesized_parent_and_two_level_nesting(conn, tmp_path):
    """Reproduces the ticket's own example shape: a synthesized apex parent
    (no domain, low confidence) with real children resolving parent_org_id
    correctly, out of file order (child before parent in the source)."""
    parent = _unique("testgroup")
    child = _unique("testgroup-coastal")
    grandchild = _unique("testgroupcoastalresort")

    rows = _sample_rows(child, parent, grandchild)
    # Deliberately out of topological order: child appears before its
    # parent in the file, mirroring the real roster's synthesized-parent
    # placement.
    rows = [rows[1], rows[0], rows[2]]
    roster = _write_roster(tmp_path, rows)

    result = load_orgs(conn, roster, source_tag="test")

    assert result.read == 3
    assert result.inserted_or_updated == 3
    assert result.parent_links_missing == 0
    assert result.parent_links_set == 2  # child->parent, grandchild->child
    assert result.synthesized_count == 1
    assert result.low_confidence_count == 2  # parent @0.35, grandchild @0.6

    fetched = {
        r[0]: r
        for r in conn.execute(
            text(
                "SELECT slug, parent_org_id, synthesized, confidence, type, type_guess, "
                "review_status, website, domains "
                "FROM engine.orgs WHERE slug = ANY(:slugs)"
            ),
            {"slugs": [parent, child, grandchild]},
        ).fetchall()
    }

    parent_id = conn.execute(text("SELECT id FROM engine.orgs WHERE slug = :s"), {"s": parent}).scalar_one()
    child_id = conn.execute(text("SELECT id FROM engine.orgs WHERE slug = :s"), {"s": child}).scalar_one()

    # group -> property nesting resolved correctly despite file order
    assert fetched[child][1] == parent_id
    assert fetched[grandchild][1] == child_id

    # synthesized parent: no domain observed -> no website guessed
    assert fetched[parent][2] is True  # synthesized
    assert fetched[parent][7] is None  # website

    # a real domain -> website derived from it
    assert fetched[child][7] == "https://coastal.testgroup-e2e.example"

    # guesses never promoted: `type` stays NULL, `type_guess` carries the guess
    for slug in (parent, child, grandchild):
        assert fetched[slug][4] is None, f"{slug}.type must stay NULL -- never auto-promoted"
    assert fetched[grandchild][5] == "stay"  # type_guess

    # nothing here is auto-confirmed, regardless of confidence
    assert all(fetched[s][6] == "pending" for s in (parent, child, grandchild))

    # candidate load must never create a partnerships row
    partnerships_count = conn.execute(text("SELECT count(*) FROM engine.partnerships")).scalar_one()
    assert partnerships_count == 0


def test_idempotent_rerun_preserves_human_review_decision(conn, tmp_path):
    slug = _unique("rerun-org")
    rows = [
        {
            "org_slug": slug,
            "name": "Rerun Test Org",
            "parent_org_slug": None,
            "domains": ["rerun-test.example"],
            "link_count": 5,
            "article_count": 4,
            "first_seen": "2020-01-01",
            "last_seen": "2021-01-01",
            "type_guess": "eat",
            "confidence": 0.7,
            "rel_audit": {"none": 5, "nofollow": 0, "sponsored": 0},
            "notes": [],
            "synthesized": False,
        }
    ]
    roster = _write_roster(tmp_path, rows)

    first = load_orgs(conn, roster, source_tag="test")
    assert first.inserted_or_updated == 1
    org_id = uuid.UUID(first.slug_to_id[slug])

    # Simulate a human reviewer confirming this org via the (future) console.
    conn.execute(
        text("UPDATE engine.orgs SET review_status = 'confirmed', type = 'stay' WHERE id = :id"),
        {"id": org_id},
    )

    second = load_orgs(conn, roster, source_tag="test")
    assert second.inserted_or_updated == 1
    assert second.slug_to_id[slug] == str(org_id)  # same row, not a duplicate

    row = conn.execute(
        text("SELECT review_status, type, link_count FROM engine.orgs WHERE id = :id"),
        {"id": org_id},
    ).fetchone()
    assert row[0] == "confirmed"  # human decision survived the reload
    assert row[1] == "stay"  # human-set `type` survived the reload
    assert row[2] == 5  # roster-derived provenance still refreshed

    total_rows = conn.execute(
        text("SELECT count(*) FROM engine.orgs WHERE slug = :slug"), {"slug": slug}
    ).scalar_one()
    assert total_rows == 1  # rerun did not duplicate
