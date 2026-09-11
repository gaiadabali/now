"""Real Postgres: proves `sites.ranking_weights['blend']` is genuinely
editable-without-deploy, end to end -- the acceptance criterion.
Everything here runs inside a transaction that is rolled back (never
committed), so this test suite never leaves a mutation behind on a
shared dev database."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from now_blender.weights import BlendWeights, load_blend_weights, seed_default_blend_weights

SITE_SLUG = "jakarta"


def test_jakarta_decay_key_is_already_seeded(platform_conn):
    # Sanity check that now-db's site:create/site:migrate has, in fact,
    # already run (F39/E3.3's dependency) -- this package reads, never
    # writes, the decay key.
    row = platform_conn.execute(
        text("SELECT ranking_weights FROM engine.sites WHERE slug = :slug"), {"slug": SITE_SLUG}
    ).first()
    if row is None:
        pytest.skip(f"site {SITE_SLUG!r} not provisioned on this DB")
    assert "decay" in (row[0] or {})


def test_editing_ranking_weights_directly_changes_what_load_blend_weights_returns(platform_conn):
    """The actual proof: write a distinctive value straight into the
    jsonb column (exactly what an ops person editing the row -- or a
    future admin console -- would do), with NO code change and NO
    process restart, and confirm the very next read sees it."""
    trans = platform_conn.begin()
    try:
        distinctive = BlendWeights(w_sem=0.11, w_cf=0.22, w_fresh=0.13, w_qual=0.14, w_geo=0.15, w_promo=0.25)
        platform_conn.execute(
            text(
                "UPDATE engine.sites SET ranking_weights = ranking_weights || "
                "jsonb_build_object('blend', CAST(:blend AS jsonb)) WHERE slug = :slug"
            ),
            {"blend": json.dumps(distinctive.as_dict()), "slug": SITE_SLUG},
        )
        resolved = load_blend_weights(platform_conn, SITE_SLUG)
        assert resolved.weights == distinctive
        assert resolved.source == "sites.ranking_weights['blend']"
    finally:
        trans.rollback()  # never persisted


def test_seed_default_blend_weights_never_overwrites_an_existing_key(platform_conn):
    trans = platform_conn.begin()
    try:
        tuned = BlendWeights(w_sem=0.9, w_cf=0.02, w_fresh=0.02, w_qual=0.02, w_geo=0.02, w_promo=0.02)
        platform_conn.execute(
            text(
                "UPDATE engine.sites SET ranking_weights = ranking_weights || "
                "jsonb_build_object('blend', CAST(:blend AS jsonb)) WHERE slug = :slug"
            ),
            {"blend": json.dumps(tuned.as_dict()), "slug": SITE_SLUG},
        )
        written = seed_default_blend_weights(platform_conn, SITE_SLUG)
        assert written is False  # key already present -> no-op, per-site tuning survives
        resolved = load_blend_weights(platform_conn, SITE_SLUG)
        assert resolved.weights == tuned  # untouched
    finally:
        trans.rollback()


def test_missing_site_falls_back_to_default_and_says_so(platform_conn):
    resolved = load_blend_weights(platform_conn, "definitely-not-a-real-site-slug")
    assert resolved.weights == BlendWeights()
    assert "not found" in resolved.source
