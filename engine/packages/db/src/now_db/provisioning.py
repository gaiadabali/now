"""`site:create` / `site:migrate` — the migration runner (E0.2 deliverable #3)
plus the taxonomy seed (E1.4).

Design:

  site:create <slug>
      1. CREATE DATABASE now_<slug> if it doesn't already exist (idempotent).
      2. Run every now-db migration against it (idempotent — Alembic no-ops
         once at head).
      3. Seed the shared vocabulary into the platform DB
         (`seed_platform_taxonomy`): `engine.facets` + `engine.terms` from
         the data files in engine/packages/taxonomy/seed/. Idempotent upsert
         keyed by the natural keys (`facets.key`, `terms(facet_id, slug)`);
         never deletes a row.
      4. Seed the city (`seed_city`): make sure `engine.type_relations` has
         a row for every L1 `type` term in the platform vocabulary. Missing
         rows get the §4 default matrix (ON CONFLICT DO NOTHING), so a
         site's own overrides are never clobbered and a brand-new type is
         never left without an exclusion policy.
      5. `ensure_daily_partitions` for interactions/impressions so a brand
         new city can accept beacon traffic immediately, without waiting for
         the first scheduled rotation run.
      6. Upsert the `now_platform.engine.sites` registry row, then write the
         default format→decay policy into `sites.ranking_weights['decay']`
         if — and only if — that key is absent (`seed_site_decay_defaults`).
      7. Scaffold `<slug>/site/`, `<slug>/cms/`, `<slug>/content/` (leaving
         any existing `<slug>/db/` alone — that directory is owned by the
         site-config task, not by this scaffold step).

  site:migrate --all
      Seed the platform vocabulary once, then iterate every non-disabled row
      in the sites registry and run the now-db migrations, `seed_city`,
      partitions and decay defaults against each one. Idempotent by
      construction (same Alembic no-op as above; every seed step is a no-op
      on already-converged data) — this is what CI's second-run check
      exercises.

Every step here is safe to re-run. `site:create` on an existing slug
converges rather than erroring, matching the registry upsert contract.

Taxonomy seed contract (E1.4) — details in engine/packages/taxonomy/README.md:

  * The seed files are the source of truth for the *vocabulary*; the DB rows
    are the runtime copy. Re-running the seed converges the DB onto the
    files (labels, parents, new terms) but never deletes a term and never
    overwrites a non-null `terms.geo` — a geocoder or editor refinement wins
    over the seed's approximate centroid.
  * `engine.type_relations` (city DB) is never updated by the seed, only
    back-filled. Per-site policy edits are made in place and survive.
  * `sites.ranking_weights['decay']` is written once per site and never
    overwritten. Per-site tuning survives.
  * `terms.embedding` is never touched here and no embedding API is called
    from this package. E2.4 owns that column; `TERMS_MISSING_EMBEDDINGS_SQL`
    below is the hand-off query.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from now_db import partitions
from now_db.settings import admin_database_url, city_database_url
from now_db.sites_registry import SiteRow, list_sites, upsert_site
from now_db.facet_sync import FacetDriftGroup, find_facet_drift
from now_db.term_refs import OrphanedTermRef, find_orphaned_term_refs
from now_platform_db.settings import platform_database_url

log = logging.getLogger(__name__)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_PATH = PACKAGE_ROOT / "src" / "now_db" / "migrations"
REPO_ROOT = PACKAGE_ROOT.parents[2]  # engine/packages/db -> engine/packages -> engine -> repo root

# Data-only package: JSON files, no code. Resolved relative to the source
# checkout like `scaffold_site_dirs` already is; `NOW_TAXONOMY_SEED_DIR`
# overrides it for an installed (non-editable) now-db, e.g. inside a
# container image — see the taxonomy README, "Packaging follow-up".
TAXONOMY_SEED_DIR = Path(
    os.environ.get("NOW_TAXONOMY_SEED_DIR") or (REPO_ROOT / "engine" / "packages" / "taxonomy" / "seed")
)

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,62}$")
_TERM_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FACET_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# E2.4 hand-off: every term still lacking an embedding, with enough context
# to build the text to embed (`"{facet}: {label}"`, plus the parent label for
# subtypes/locations so "Kuta" embeds as a Bali neighbourhood, not a
# Lombok one). E2.4 writes `embedding` back by `id`; the partial HNSW index
# `ix_terms_embedding_hnsw (WHERE embedding IS NOT NULL)` picks rows up as
# they are filled. Nothing in this package executes this query.
TERMS_MISSING_EMBEDDINGS_SQL = """
    SELECT t.id, f.key AS facet, t.slug, t.label, p.label AS parent_label
      FROM engine.terms t
      JOIN engine.facets f ON f.id = t.facet_id
 LEFT JOIN engine.terms p ON p.id = t.parent_id
     WHERE t.embedding IS NULL
     ORDER BY f.key, t.slug
"""


class InvalidSlugError(ValueError):
    pass


class TaxonomySeedError(ValueError):
    """The seed files are internally inconsistent (bad slug, unknown facet,
    missing parent, a format without a decay entry, type_relations naming a
    type that does not exist, ...). Raised before any database write."""


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        raise InvalidSlugError(
            f"invalid slug {slug!r}: must be lowercase, start with a letter, "
            "and contain only [a-z0-9_] (it becomes part of a Postgres database name)"
        )


def db_name_for_slug(slug: str) -> str:
    return f"now_{slug}"


def alembic_config(url: str) -> Config:
    cfg = Config(str(PACKAGE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(MIGRATIONS_PATH))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def database_exists(conn: Connection, db_name: str) -> bool:
    return (
        conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}).first()
        is not None
    )


def ensure_database(db_name: str) -> bool:
    """CREATE DATABASE if missing. Runs autocommit — Postgres refuses
    CREATE DATABASE inside a transaction block. Returns True if it created
    the database, False if it already existed."""
    engine = create_engine(admin_database_url())
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            if database_exists(conn, db_name):
                return False
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            return True
    finally:
        engine.dispose()


def migrate_city(dsn: str) -> None:
    command.upgrade(alembic_config(dsn), "head")


def ensure_city_partitions(dsn: str, *, days_ahead: int = 7) -> list[str]:
    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            return partitions.ensure_daily_partitions(conn, days_ahead=days_ahead)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# Taxonomy seed — loading (pure, no database)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SeedFacet:
    key: str
    label: str
    cardinality: str
    required: bool


@dataclass(frozen=True)
class SeedTerm:
    facet: str
    slug: str
    label: str
    parent: tuple[str, str] | None  # (facet, slug) of the parent term, if any
    geo: tuple[float, float] | None  # (lat, lng)
    attrs: dict[str, Any] = field(default_factory=dict)  # engine.terms.attrs (migration 0002)

    @property
    def geo_ewkt(self) -> str | None:
        if self.geo is None:
            return None
        lat, lng = self.geo
        return f"SRID=4326;POINT({lng} {lat})"


@dataclass(frozen=True)
class TaxonomySeed:
    facets: list[SeedFacet]
    terms: list[SeedTerm]  # topologically ordered: a parent always precedes its children
    type_relations: dict[str, tuple[bool, list[str]]]  # type -> (exclude_same, complements)
    unknown_type_default: tuple[bool, list[str]]
    decay: dict[str, Any]  # the object written to sites.ranking_weights['decay']

    def terms_of(self, facet: str) -> list[SeedTerm]:
        return [t for t in self.terms if t.facet == facet]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise TaxonomySeedError(f"taxonomy seed file missing: {path}") from None
    except json.JSONDecodeError as exc:
        raise TaxonomySeedError(f"taxonomy seed file is not valid JSON: {path}: {exc}") from None


def load_taxonomy_seed(seed_dir: Path | str | None = None) -> TaxonomySeed:
    """Read and cross-validate every file under the seed directory.

    Fails loudly (TaxonomySeedError) on anything that would leave the runtime
    in an inconsistent state — an unknown facet, a duplicate or malformed
    slug, a child whose parent is missing, a `type_relations` entry naming a
    type that is not in the vocabulary, or a `format` term with no decay
    policy — so a broken seed never half-applies to a database."""
    root = Path(seed_dir) if seed_dir is not None else TAXONOMY_SEED_DIR
    if not root.is_dir():
        raise TaxonomySeedError(
            f"taxonomy seed directory not found: {root} "
            "(set NOW_TAXONOMY_SEED_DIR when now-db is installed outside a source checkout)"
        )

    # facets.json
    facets: list[SeedFacet] = []
    for f in _read_json(root / "facets.json")["facets"]:
        key = f["key"]
        if not _FACET_KEY_RE.match(key):
            raise TaxonomySeedError(f"bad facet key {key!r}")
        if f["cardinality"] not in ("single", "multi"):
            raise TaxonomySeedError(f"facet {key!r}: cardinality must be 'single' or 'multi'")
        facets.append(
            SeedFacet(key=key, label=f["label"], cardinality=f["cardinality"], required=bool(f["required"]))
        )
    facet_keys = {f.key for f in facets}
    if len(facet_keys) != len(facets):
        raise TaxonomySeedError("duplicate facet key in facets.json")
    for required_key in ("type", "format"):
        if required_key not in facet_keys:
            raise TaxonomySeedError(f"facets.json must define the {required_key!r} facet")

    # terms/*.json — one file per facet; hierarchical files nest `children`.
    terms: list[SeedTerm] = []
    seen: set[tuple[str, str]] = set()

    def walk(node: dict[str, Any], facet: str, child_facet: str, parent: tuple[str, str] | None) -> None:
        slug = node["slug"]
        if not _TERM_SLUG_RE.match(slug):
            raise TaxonomySeedError(f"bad term slug {slug!r} in facet {facet!r} (lowercase, digits, single hyphens)")
        key = (facet, slug)
        if key in seen:
            raise TaxonomySeedError(f"duplicate term {facet}/{slug}")
        seen.add(key)
        geo: tuple[float, float] | None = None
        if node.get("geo") is not None:
            lat, lng = float(node["geo"]["lat"]), float(node["geo"]["lng"])
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                raise TaxonomySeedError(f"term {facet}/{slug}: geo out of range ({lat}, {lng})")
            geo = (lat, lng)
        attrs = node.get("attrs") or {}
        if not isinstance(attrs, dict):
            raise TaxonomySeedError(f"term {facet}/{slug}: attrs must be an object")
        terms.append(SeedTerm(facet=facet, slug=slug, label=node["label"], parent=parent, geo=geo, attrs=attrs))
        for child in node.get("children", []):
            walk(child, child_facet, child_facet, key)

    term_files = sorted((root / "terms").glob("*.json"))
    if not term_files:
        raise TaxonomySeedError(f"no term files under {root / 'terms'}")
    for path in term_files:
        doc = _read_json(path)
        facet = doc["facet"]
        if facet not in facet_keys:
            raise TaxonomySeedError(f"{path.name}: facet {facet!r} is not defined in facets.json")
        child_facet = doc.get("children_facet", facet)
        if child_facet not in facet_keys:
            raise TaxonomySeedError(f"{path.name}: children_facet {child_facet!r} is not defined in facets.json")
        for node in doc["terms"]:
            walk(node, facet, child_facet, None)

    empty = facet_keys - {t.facet for t in terms}
    if empty:
        raise TaxonomySeedError(f"facets with no terms: {sorted(empty)}")

    # type_relations.json — must agree with the `type` vocabulary exactly.
    rel_doc = _read_json(root / "type_relations.json")
    type_slugs = {t.slug for t in terms if t.facet == "type"}
    relations: dict[str, tuple[bool, list[str]]] = {}
    for r in rel_doc["relations"]:
        t = r["type"]
        if t not in type_slugs:
            raise TaxonomySeedError(f"type_relations.json: {t!r} is not a `type` term")
        if t in relations:
            raise TaxonomySeedError(f"type_relations.json: duplicate entry for {t!r}")
        complements = list(r["complements"])
        unknown = [c for c in complements if c not in type_slugs]
        if unknown:
            raise TaxonomySeedError(f"type_relations.json: {t!r} complements unknown types {unknown}")
        if t in complements:
            raise TaxonomySeedError(f"type_relations.json: {t!r} cannot complement itself")
        relations[t] = (bool(r["exclude_same"]), complements)
    default = rel_doc.get("unknown_type_default", {"exclude_same": True, "complements": []})
    unknown_default = (bool(default["exclude_same"]), list(default["complements"]))

    # format_decay.json — must list exactly the `format` terms.
    decay = _read_json(root / "format_decay.json")["decay"]
    format_slugs = {t.slug for t in terms if t.facet == "format"}
    listed = set(decay["formats"])
    if listed != format_slugs:
        raise TaxonomySeedError(
            "format_decay.json must list exactly the `format` terms; "
            f"missing={sorted(format_slugs - listed)} extra={sorted(listed - format_slugs)}"
        )
    for slug, policy in decay["formats"].items():
        half_life = policy.get("half_life_days")
        if half_life is not None and (not isinstance(half_life, (int, float)) or half_life <= 0):
            raise TaxonomySeedError(f"format_decay.json: {slug!r} half_life_days must be a positive number or null")
        if half_life is None and not policy.get("evergreen") and not policy.get("hard_expiry"):
            raise TaxonomySeedError(
                f"format_decay.json: {slug!r} has no half-life but is neither evergreen nor hard-expiring"
            )

    # min_format_confidence — F124/F125's decay trust gate (ticket T2). Optional
    # in the file's shape (older seeds/tests may omit it) but must be a real
    # 0..1 probability when present — a typo here (e.g. "85" instead of
    # "0.85") would silently make the gate withhold nothing, or everything.
    if "min_format_confidence" in decay:
        min_conf = decay["min_format_confidence"]
        if not isinstance(min_conf, (int, float)) or not (0.0 <= min_conf <= 1.0):
            raise TaxonomySeedError(
                f"format_decay.json: min_format_confidence must be a number in [0, 1], got {min_conf!r}"
            )

    return TaxonomySeed(
        facets=facets,
        terms=terms,
        type_relations=relations,
        unknown_type_default=unknown_default,
        decay=decay,
    )


# --------------------------------------------------------------------------
# Taxonomy seed — platform DB (facets + terms)
# --------------------------------------------------------------------------

# Both upserts carry a WHERE on the DO UPDATE so an already-converged row is
# not rewritten (no dead tuple, nothing RETURNed). That is what makes "run
# twice, second run is a no-op" literally true and countable.
_UPSERT_FACET = text(
    """
    INSERT INTO engine.facets (key, label, cardinality, required)
    VALUES (:key, :label, :cardinality, :required)
    ON CONFLICT (key) DO UPDATE
       SET label = EXCLUDED.label,
           cardinality = EXCLUDED.cardinality,
           required = EXCLUDED.required
     WHERE (engine.facets.label, engine.facets.cardinality, engine.facets.required)
           IS DISTINCT FROM (EXCLUDED.label, EXCLUDED.cardinality, EXCLUDED.required)
    RETURNING id, (xmax = 0) AS inserted
    """
)

# `geo = COALESCE(existing, seed)`: the seed only ever fills a NULL centroid.
# `attrs` is NOT fill-only like `geo` -- it is structural taxonomy metadata
# (e.g. international's geo_scope=abroad) owned by this seed, not an
# editor/geocoder refinement, so a re-seed converges it like `label`/
# `parent_id` rather than only filling an empty value. `'{}'::jsonb` is the
# column's own DEFAULT (migration 0002 platform-db/0002_terms_attrs_and_site_location_root.py),
# so a term with no `attrs` in the seed file still gets a well-typed empty object.
_UPSERT_TERM = text(
    """
    INSERT INTO engine.terms (facet_id, slug, label, parent_id, geo, attrs)
    VALUES (:facet_id, :slug, :label, :parent_id, CAST(:geo AS geography), CAST(:attrs AS jsonb))
    ON CONFLICT (facet_id, slug) DO UPDATE
       SET label = EXCLUDED.label,
           parent_id = EXCLUDED.parent_id,
           geo = COALESCE(engine.terms.geo, EXCLUDED.geo),
           attrs = EXCLUDED.attrs
     WHERE engine.terms.label IS DISTINCT FROM EXCLUDED.label
        OR engine.terms.parent_id IS DISTINCT FROM EXCLUDED.parent_id
        OR (engine.terms.geo IS NULL AND EXCLUDED.geo IS NOT NULL)
        OR engine.terms.attrs IS DISTINCT FROM EXCLUDED.attrs
    RETURNING id, (xmax = 0) AS inserted
    """
)


@dataclass(frozen=True)
class PlatformSeedReport:
    facets_inserted: int
    facets_updated: int
    terms_inserted: int
    terms_updated: int
    facets_total: int
    terms_total: int

    @property
    def changed(self) -> bool:
        return bool(self.facets_inserted or self.facets_updated or self.terms_inserted or self.terms_updated)


def _seed_platform_taxonomy(conn: Connection, seed: TaxonomySeed) -> PlatformSeedReport:
    f_ins = f_upd = t_ins = t_upd = 0

    for facet in seed.facets:
        row = conn.execute(
            _UPSERT_FACET,
            {
                "key": facet.key,
                "label": facet.label,
                "cardinality": facet.cardinality,
                "required": facet.required,
            },
        ).first()
        if row is not None:
            if row.inserted:
                f_ins += 1
            else:
                f_upd += 1

    facet_ids = {key: fid for key, fid in conn.execute(text("SELECT key, id FROM engine.facets")).fetchall()}

    # Pre-load every existing (facet, slug) -> id so unchanged rows (which the
    # guarded upsert does not RETURN) can still serve as parents.
    term_ids: dict[tuple[str, str], Any] = {
        (fkey, slug): tid
        for fkey, slug, tid in conn.execute(
            text("SELECT f.key, t.slug, t.id FROM engine.terms t JOIN engine.facets f ON f.id = t.facet_id")
        ).fetchall()
    }

    for term in seed.terms:  # parents precede children by construction
        parent_id = None
        if term.parent is not None:
            parent_id = term_ids.get(term.parent)
            if parent_id is None:
                raise TaxonomySeedError(f"term {term.facet}/{term.slug}: parent {term.parent} was not seeded")
        row = conn.execute(
            _UPSERT_TERM,
            {
                "facet_id": facet_ids[term.facet],
                "slug": term.slug,
                "label": term.label,
                "parent_id": parent_id,
                "geo": term.geo_ewkt,
                "attrs": json.dumps(term.attrs, sort_keys=True),
            },
        ).first()
        if row is not None:
            term_ids[(term.facet, term.slug)] = row.id
            if row.inserted:
                t_ins += 1
            else:
                t_upd += 1
        elif (term.facet, term.slug) not in term_ids:
            raise RuntimeError(f"term {term.facet}/{term.slug}: upsert returned nothing and no existing row found")

    facets_total = conn.execute(text("SELECT count(*) FROM engine.facets")).scalar_one()
    terms_total = conn.execute(text("SELECT count(*) FROM engine.terms")).scalar_one()
    report = PlatformSeedReport(
        facets_inserted=f_ins,
        facets_updated=f_upd,
        terms_inserted=t_ins,
        terms_updated=t_upd,
        facets_total=facets_total,
        terms_total=terms_total,
    )
    log.info(
        "taxonomy seed (platform): facets +%d ~%d (total %d), terms +%d ~%d (total %d)",
        f_ins, f_upd, facets_total, t_ins, t_upd, terms_total,
    )
    return report


def seed_platform_taxonomy(
    platform_dsn: str | None = None, *, seed: TaxonomySeed | None = None
) -> PlatformSeedReport:
    """Upsert the shared vocabulary (engine.facets, engine.terms) into the
    platform DB from the seed files. Idempotent; additive; one transaction."""
    seed = seed or load_taxonomy_seed()
    engine = create_engine(platform_dsn or platform_database_url())
    try:
        with engine.begin() as conn:
            return _seed_platform_taxonomy(conn, seed)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# Taxonomy seed — city DB (type_relations)
# --------------------------------------------------------------------------

_INSERT_TYPE_RELATION = text(
    """
    INSERT INTO engine.type_relations (type, exclude_same, complements)
    VALUES (:type, :exclude_same, CAST(:complements AS text[]))
    ON CONFLICT (type) DO NOTHING
    RETURNING type
    """
)


@dataclass(frozen=True)
class CitySeedReport:
    type_relations_inserted: list[str]
    type_relations_total: int
    types_not_in_vocabulary: list[str]  # rows present in the city but absent from the platform `type` facet


def _platform_l1_types(platform_dsn: str | None) -> list[str]:
    engine = create_engine(platform_dsn or platform_database_url())
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT t.slug FROM engine.terms t JOIN engine.facets f ON f.id = t.facet_id "
                    "WHERE f.key = 'type' AND t.parent_id IS NULL ORDER BY t.slug"
                )
            ).fetchall()
    finally:
        engine.dispose()
    return [r[0] for r in rows]


def seed_city(
    dsn: str, *, platform_dsn: str | None = None, seed: TaxonomySeed | None = None
) -> CitySeedReport:
    """Seed a city DB from the platform vocabulary (ARCHITECTURE.md §2:
    "seeds taxonomy from platform").

    Facets/terms are NOT copied into the city — they live only in
    `now_platform.engine` and are referenced by id from `entity_terms`. What
    a city needs is a complete `engine.type_relations`: one row per L1
    `type` term, because competitor exclusion (§8.A) is undefined for a type
    with no row. The baseline migration inserts the §4 matrix; this function
    back-fills any type that has appeared since, using the seed's entry for
    it or — if the seed has none — the strictest policy (`exclude_same =
    true`, no complements). Existing rows are never touched, so per-site
    overrides survive every `site:create` / `site:migrate` run.
    """
    seed = seed or load_taxonomy_seed()
    l1_types = _platform_l1_types(platform_dsn)
    if not l1_types:
        raise RuntimeError(
            "platform vocabulary has no `type` terms — run seed_platform_taxonomy() before seed_city()"
        )

    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            count = conn.execute(text("SELECT count(*) FROM engine.type_relations")).scalar_one()
            if count == 0:
                raise RuntimeError(
                    "engine.type_relations is empty after migration — baseline seed data is missing"
                )

            inserted: list[str] = []
            for type_slug in l1_types:
                exclude_same, complements = seed.type_relations.get(type_slug, seed.unknown_type_default)
                if type_slug not in seed.type_relations:
                    log.warning(
                        "type %r has no entry in type_relations.json; seeding the strict default "
                        "(exclude_same=%s, complements=%s)",
                        type_slug, exclude_same, complements,
                    )
                row = conn.execute(
                    _INSERT_TYPE_RELATION,
                    {"type": type_slug, "exclude_same": exclude_same, "complements": complements},
                ).first()
                if row is not None:
                    inserted.append(type_slug)

            # Commercial policy must be internally consistent: a complement
            # that names a type outside the vocabulary can never match a row
            # and would silently starve Row 1. Fail loudly rather than serve it.
            dangling = conn.execute(
                text(
                    "SELECT tr.type, c FROM engine.type_relations tr, unnest(tr.complements) AS c "
                    "WHERE NOT (c = ANY(CAST(:types AS text[]))) ORDER BY tr.type, c"
                ),
                {"types": l1_types},
            ).fetchall()
            if dangling:
                raise RuntimeError(
                    "engine.type_relations references types missing from the platform vocabulary: "
                    + ", ".join(f"{t} -> {c}" for t, c in dangling)
                )

            orphans = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT type FROM engine.type_relations "
                        "WHERE NOT (type = ANY(CAST(:types AS text[]))) ORDER BY type"
                    ),
                    {"types": l1_types},
                ).fetchall()
            ]
            total = conn.execute(text("SELECT count(*) FROM engine.type_relations")).scalar_one()
    finally:
        engine.dispose()

    if orphans:
        log.warning("engine.type_relations has rows for types not in the platform vocabulary: %s", orphans)
    log.info("taxonomy seed (city %s): type_relations +%s (total %d)", dsn.rsplit("/", 1)[-1], inserted or 0, total)
    return CitySeedReport(
        type_relations_inserted=inserted,
        type_relations_total=total,
        types_not_in_vocabulary=orphans,
    )


# --------------------------------------------------------------------------
# Taxonomy seed — per-site decay defaults (platform DB, sites.ranking_weights)
# --------------------------------------------------------------------------

# Written once: the WHERE makes a re-run a no-op and protects any per-site
# tuning. `jsonb_exists` is the function form of the `?` operator (kept off
# the SQL text so no driver ever mistakes it for a placeholder).
_SET_DECAY_DEFAULTS = text(
    """
    UPDATE engine.sites
       SET ranking_weights = ranking_weights || jsonb_build_object('decay', CAST(:decay AS jsonb)),
           updated_at = now()
     WHERE slug = :slug
       AND NOT jsonb_exists(ranking_weights, 'decay')
    RETURNING slug
    """
)


def _seed_site_decay_defaults(conn: Connection, slug: str, seed: TaxonomySeed) -> bool:
    if conn.execute(text("SELECT 1 FROM engine.sites WHERE slug = :slug"), {"slug": slug}).first() is None:
        raise RuntimeError(f"site {slug!r} is not in engine.sites; register it before seeding decay defaults")
    row = conn.execute(
        _SET_DECAY_DEFAULTS, {"slug": slug, "decay": json.dumps(seed.decay, sort_keys=True)}
    ).first()
    written = row is not None
    log.info("taxonomy seed (site %s): decay defaults %s", slug, "written" if written else "already present")
    return written


def seed_site_decay_defaults(
    slug: str, *, platform_dsn: str | None = None, seed: TaxonomySeed | None = None
) -> bool:
    """Write the format→half-life policy into `sites.ranking_weights['decay']`
    for one site, unless that key already exists. Returns True if written.

    Read path for consumers (E3.3): `SiteConfig.ranking_weights["decay"]`
    — see engine/packages/taxonomy/seed/format_decay.json for the shape.
    """
    seed = seed or load_taxonomy_seed()
    engine = create_engine(platform_dsn or platform_database_url())
    try:
        with engine.begin() as conn:
            return _seed_site_decay_defaults(conn, slug, seed)
    finally:
        engine.dispose()


# F124/F125 (decay trust gate, ticket T2): `min_format_confidence` is a NEW
# key inside the ALREADY-SEEDED `decay` object. `_SET_DECAY_DEFAULTS` above
# only fires `WHERE NOT jsonb_exists(ranking_weights, 'decay')` — every site
# already has a `decay` key (written by an earlier `site:create`/`migrate`),
# so simply adding `min_format_confidence` to `format_decay.json` and
# re-running the ordinary seed is a NO-OP for every existing site: the outer
# `decay` key exists, the guard never fires, the inner key is never written.
# This is the exact trap F122 hit for `type_relations.json` (`ON CONFLICT DO
# NOTHING` protects a site's own tuning from a seed re-run, so a vocabulary
# fix there needed a direct UPDATE too) — named explicitly in this ticket's
# own brief so it isn't rediscovered the hard way a second time.
#
# This is a data backfill, not DDL (`sites.ranking_weights` is plain jsonb,
# no migration needed) — but it still must never clobber a site that has
# already tuned `min_format_confidence` for itself, so it carries the same
# "only if absent" guard as the outer key, just one level deeper via
# `jsonb_set` on the `{decay,min_format_confidence}` path instead of
# replacing the whole `decay` object.
_SET_MIN_FORMAT_CONFIDENCE = text(
    """
    UPDATE engine.sites
       SET ranking_weights = jsonb_set(
               ranking_weights, '{decay,min_format_confidence}', to_jsonb(CAST(:min_conf AS numeric)), true
           ),
           updated_at = now()
     WHERE slug = :slug
       AND jsonb_exists(ranking_weights, 'decay')
       AND NOT (ranking_weights #> '{decay}' ? 'min_format_confidence')
    RETURNING slug
    """
)


def _seed_site_min_format_confidence(conn: Connection, slug: str, seed: TaxonomySeed) -> bool:
    min_conf = seed.decay.get("min_format_confidence")
    if min_conf is None:
        log.info("taxonomy seed (site %s): min_format_confidence not present in seed, skipped", slug)
        return False
    if conn.execute(text("SELECT 1 FROM engine.sites WHERE slug = :slug"), {"slug": slug}).first() is None:
        raise RuntimeError(f"site {slug!r} is not in engine.sites; register it before seeding decay defaults")
    row = conn.execute(_SET_MIN_FORMAT_CONFIDENCE, {"slug": slug, "min_conf": min_conf}).first()
    written = row is not None
    log.info(
        "taxonomy seed (site %s): min_format_confidence %s",
        slug, "written" if written else "already present (or 'decay' key itself missing)",
    )
    return written


def seed_site_min_format_confidence(
    slug: str, *, platform_dsn: str | None = None, seed: TaxonomySeed | None = None
) -> bool:
    """Backfill `sites.ranking_weights['decay']['min_format_confidence']` for
    one already-provisioned site, unless that inner key already exists (see
    module comment above for why the ordinary decay-defaults seed cannot do
    this on its own). Returns True if written."""
    seed = seed or load_taxonomy_seed()
    engine = create_engine(platform_dsn or platform_database_url())
    try:
        with engine.begin() as conn:
            return _seed_site_min_format_confidence(conn, slug, seed)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# site:create / site:migrate
# --------------------------------------------------------------------------


def scaffold_site_dirs(slug: str) -> list[Path]:
    """Create `<slug>/site/`, `<slug>/cms/`, `<slug>/content/` with a
    `.gitkeep` if they don't already exist. Never touches `<slug>/db/`
    (owned by the site-config task) and never overwrites existing files."""
    created: list[Path] = []
    site_root = REPO_ROOT / slug
    for sub in ("site", "cms", "content"):
        d = site_root / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(d)
        keep = d / ".gitkeep"
        if not keep.exists() and not any(d.iterdir()):
            keep.write_text("")
    return created


@dataclass(frozen=True)
class CreateSiteResult:
    slug: str
    db_name: str
    dsn: str
    created_database: bool
    partitions_created: list[str]
    scaffolded_dirs: list[Path]
    platform_seed: PlatformSeedReport | None = None
    city_seed: CitySeedReport | None = None
    decay_defaults_written: bool = False


def create_site(
    slug: str,
    *,
    hostname: str,
    name: str,
    locale: str = "en",
    timezone: str = "Asia/Jakarta",
    currency: str = "IDR",
    enabled_modules: list[str] | None = None,
) -> CreateSiteResult:
    _validate_slug(slug)
    db_name = db_name_for_slug(slug)

    # Validate the seed before touching any database: a broken seed file must
    # never leave a half-provisioned city behind.
    seed = load_taxonomy_seed()

    created_database = ensure_database(db_name)

    dsn = city_database_url(db_name)
    migrate_city(dsn)
    platform_report = seed_platform_taxonomy(seed=seed)
    city_report = seed_city(dsn, seed=seed)
    created_partitions = ensure_city_partitions(dsn)

    platform_engine = create_engine(platform_database_url())
    try:
        with platform_engine.begin() as conn:
            upsert_site(
                conn,
                slug=slug,
                hostname=hostname,
                name=name,
                locale=locale,
                timezone=timezone,
                currency=currency,
                db_ref=db_name,
                enabled_modules=enabled_modules or [],
                status="active",
            )
            decay_written = _seed_site_decay_defaults(conn, slug, seed)
            _seed_site_min_format_confidence(conn, slug, seed)
    finally:
        platform_engine.dispose()

    scaffolded = scaffold_site_dirs(slug)

    return CreateSiteResult(
        slug=slug,
        db_name=db_name,
        dsn=dsn,
        created_database=created_database,
        partitions_created=created_partitions,
        scaffolded_dirs=scaffolded,
        platform_seed=platform_report,
        city_seed=city_report,
        decay_defaults_written=decay_written,
    )


@dataclass(frozen=True)
class MigrateAllResult:
    migrated: list[str]
    partitions_created: dict[str, list[str]]
    platform_seed: PlatformSeedReport | None = None
    city_seeds: dict[str, CitySeedReport] = field(default_factory=dict)
    decay_defaults_written: list[str] = field(default_factory=list)
    # F92: term_id values in this site's engine.entity_terms with no
    # matching now_platform.engine.terms row, keyed by slug. An empty list
    # means clean; `None` means the check itself could not run (platform
    # DB unreachable etc.) — never conflated with "clean". Detection
    # only — see now_db.term_refs module docstring for why this is not a
    # hard failure of migrate_all() itself.
    term_ref_orphans: dict[str, list[OrphanedTermRef] | None] = field(default_factory=dict)
    # F132: articles.primary_type/.format <-> entity_terms drift, per site.
    # Same detection-only, never-fails-migrate contract as term_ref_orphans
    # above -- `None` means "could not check", `[]` means "checked, clean".
    facet_drift: dict[str, list[FacetDriftGroup] | None] = field(default_factory=dict)


def migrate_all() -> MigrateAllResult:
    """Iterate the registry and apply now-db migrations (plus the taxonomy
    seed steps) to every non-disabled city. Idempotent: a second run
    migrates nothing new and seeds nothing new."""
    seed = load_taxonomy_seed()

    platform_engine = create_engine(platform_database_url())
    try:
        with platform_engine.connect() as conn:
            sites: list[SiteRow] = list_sites(conn)
    finally:
        platform_engine.dispose()

    platform_report = seed_platform_taxonomy(seed=seed)

    migrated: list[str] = []
    partitions_created: dict[str, list[str]] = {}
    city_seeds: dict[str, CitySeedReport] = {}
    decay_written: list[str] = []

    for site in sites:
        dsn = city_database_url(site.db_ref)
        migrate_city(dsn)
        city_seeds[site.slug] = seed_city(dsn, seed=seed)
        partitions_created[site.slug] = ensure_city_partitions(dsn)
        if seed_site_decay_defaults(site.slug, seed=seed):
            decay_written.append(site.slug)
        seed_site_min_format_confidence(site.slug, seed=seed)
        migrated.append(site.slug)

    # F92: run AFTER every site has migrated/seeded successfully, and
    # deliberately decoupled from that loop (own try/except, own engine) —
    # a platform-DB hiccup while running this detection check must never
    # be able to fail (or half-run) the migration loop above, which by
    # this point has already committed real DDL/data. `None` for a site
    # means "could not check", kept distinct from `[]` ("checked, clean")
    # by `now_db.cli._echo_term_ref_orphans` / any other caller.
    term_ref_orphans: dict[str, list[OrphanedTermRef] | None] = {}
    try:
        check_platform_engine = create_engine(platform_database_url())
        try:
            with check_platform_engine.connect() as platform_conn:
                for site in sites:
                    dsn = city_database_url(site.db_ref)
                    city_engine = create_engine(dsn)
                    try:
                        with city_engine.connect() as city_conn:
                            term_ref_orphans[site.slug] = find_orphaned_term_refs(city_conn, platform_conn)
                    except Exception as exc:  # noqa: BLE001 - best-effort detection, never fatal
                        log.warning("F92 term-ref check failed for site %s: %s", site.slug, exc)
                        term_ref_orphans[site.slug] = None
                    finally:
                        city_engine.dispose()
        finally:
            check_platform_engine.dispose()
    except Exception as exc:  # noqa: BLE001 - e.g. platform DB unreachable for the check itself
        log.warning("F92 term-ref check skipped entirely (platform DB unreachable): %s", exc)
        for site in sites:
            term_ref_orphans.setdefault(site.slug, None)

    # F132: same best-effort, decoupled, never-fatal shape as the F92 check
    # just above -- a drifted articles/entity_terms row is a pre-existing
    # data problem, never a reason to fail an otherwise-successful migrate.
    facet_drift: dict[str, list[FacetDriftGroup] | None] = {}
    try:
        check_platform_engine = create_engine(platform_database_url())
        try:
            with check_platform_engine.connect() as platform_conn:
                for site in sites:
                    dsn = city_database_url(site.db_ref)
                    city_engine = create_engine(dsn)
                    try:
                        with city_engine.connect() as city_conn:
                            facet_drift[site.slug] = find_facet_drift(city_conn, platform_conn)
                    except Exception as exc:  # noqa: BLE001 - best-effort detection, never fatal
                        log.warning("F132 facet-sync check failed for site %s: %s", site.slug, exc)
                        facet_drift[site.slug] = None
                    finally:
                        city_engine.dispose()
        finally:
            check_platform_engine.dispose()
    except Exception as exc:  # noqa: BLE001 - e.g. platform DB unreachable for the check itself
        log.warning("F132 facet-sync check skipped entirely (platform DB unreachable): %s", exc)
        for site in sites:
            facet_drift.setdefault(site.slug, None)

    return MigrateAllResult(
        migrated=migrated,
        partitions_created=partitions_created,
        platform_seed=platform_report,
        city_seeds=city_seeds,
        decay_defaults_written=decay_written,
        term_ref_orphans=term_ref_orphans,
        facet_drift=facet_drift,
    )
