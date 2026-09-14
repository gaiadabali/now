"""Tests for the parts of engine-worker that carry real logic: the per-site
fan-out, settings parsing, and the heartbeat gate that turns a dead consumer
thread into an unhealthy container."""

from __future__ import annotations

import threading

import pytest

from app import main
from app.config import Settings
from app.sites import Site, for_each_site


def site(slug: str = "alpha", db_ref: str = "now_alpha") -> Site:
    return Site(slug=slug, db_ref=db_ref)


# ---------------------------------------------------------------------------
# Per-site isolation — the property the whole fan-out depends on
# ---------------------------------------------------------------------------


def test_one_failing_site_does_not_stop_the_others():
    """A bad db_ref or a city mid-restore must not stop partition
    maintenance everywhere — that surfaces days later as failed beacon
    inserts on cities that were perfectly healthy."""

    sites = [site("alpha"), site("broken"), site("gamma")]

    def fn(s: Site) -> str:
        if s.slug == "broken":
            raise RuntimeError("database is not accepting connections")
        return f"did {s.slug}"

    report = for_each_site(sites, fn, job="test")

    assert set(report.succeeded) == {"alpha", "gamma"}
    assert "broken" in report.failed
    assert "not accepting connections" in report.failed["broken"]
    assert report.ok is False


def test_all_succeeding_reports_ok():
    report = for_each_site([site("a"), site("b")], lambda s: 1, job="test")
    assert report.ok is True
    assert report.failed == {}


def test_summary_names_the_failures():
    report = for_each_site(
        [site("a"), site("b")],
        lambda s: (_ for _ in ()).throw(ValueError("nope")) if s.slug == "b" else 1,
        job="test",
    )
    assert "1 ok" in report.summary()
    assert "b" in report.summary()


def test_empty_registry_is_not_an_error():
    """No sites means no work, not a crash. A fresh platform DB has an empty
    engine.sites and the worker should idle, not crash-loop."""
    report = for_each_site([], lambda s: 1, job="test")
    assert report.ok is True
    assert report.succeeded == {}


def test_site_dsn_passes_through_a_full_dsn():
    s = Site(slug="x", db_ref="postgresql+psycopg://u:p@host:5432/now_x")
    assert s.dsn == "postgresql+psycopg://u:p@host:5432/now_x"


def test_site_dsn_builds_one_from_a_bare_name(monkeypatch):
    monkeypatch.setenv("NOW_PG_HOST", "postgres")
    monkeypatch.setenv("NOW_PG_USER", "now")
    monkeypatch.setenv("NOW_PG_PASSWORD", "secret")
    monkeypatch.setenv("NOW_PG_PORT", "5432")
    assert Site(slug="x", db_ref="now_bandung").dsn.endswith("@postgres:5432/now_bandung")


def test_no_city_is_named_in_this_app():
    """ARCHITECTURE.md §3.5 bans site-name literals under engine/. The fan-out
    unit is the registry, so adding a city is a row, not a deploy.

    Checked over the AST, not the raw text: docstrings here legitimately
    discuss the rule itself and name Jakarta/Bali timezones, and a substring
    scan flags those. What must not exist is a string *used as a value*.
    """

    import ast
    from pathlib import Path

    banned = {"jakarta", "bali"}
    app_dir = Path(main.__file__).parent

    for path in sorted(app_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                assert node.value.strip().lower() not in banned, (
                    f"{path.name}:{node.lineno} uses a site-name literal"
                )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def test_retention_is_unset_by_default(monkeypatch):
    """Dropping a partition destroys behavioural data permanently, and E7 is
    data-gated on accumulating it. Never-drop must be the default."""
    monkeypatch.delenv("ENGINE_WORKER_INTERACTION_RETENTION_DAYS", raising=False)
    assert Settings.from_env().interaction_retention_days is None


def test_blank_retention_is_treated_as_unset(monkeypatch):
    """An env var set to empty string is how compose passes 'not configured';
    int('') would crash the worker at startup."""
    monkeypatch.setenv("ENGINE_WORKER_INTERACTION_RETENTION_DAYS", "")
    assert Settings.from_env().interaction_retention_days is None


def test_nonsense_integer_fails_loudly(monkeypatch):
    monkeypatch.setenv("ENGINE_WORKER_PARTITION_DAYS_AHEAD", "soon")
    with pytest.raises(ValueError, match="must be an integer"):
        Settings.from_env()


@pytest.mark.parametrize("raw,expected", [("false", False), ("0", False), ("no", False),
                                          ("true", True), ("1", True), ("", True)])
def test_reembed_toggle(monkeypatch, raw, expected):
    monkeypatch.setenv("ENGINE_WORKER_RUN_REEMBED_CONSUMER", raw)
    assert Settings.from_env().run_reembed_consumer is expected


def test_partition_lookahead_exceeds_the_cli_default():
    """14 days, not the CLI's 7, so a worker outage over a holiday still
    leaves runway before inserts start failing."""
    from app import jobs

    assert jobs.PARTITION_DAYS_AHEAD >= 14


# ---------------------------------------------------------------------------
# The heartbeat gate
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self):
        self.sets: list[tuple] = []

    async def set(self, key, value, expire=None):
        self.sets.append((key, value, expire))


async def test_heartbeat_written_when_consumer_is_healthy(monkeypatch):
    monkeypatch.setattr(main, "_reembed_failed", threading.Event())
    alive = threading.Thread(target=lambda: None)
    monkeypatch.setattr(main, "_reembed_thread", None)  # not started == not yet dead

    redis = FakeRedis()
    ctx = {"redis": redis, "settings": Settings(run_reembed_consumer=True)}

    result = await main.heartbeat_or_fail(ctx)

    assert result["heartbeat"] == Settings().heartbeat_key
    assert redis.sets and redis.sets[0][0] == Settings().heartbeat_key
    del alive


async def test_heartbeat_withheld_when_consumer_died(monkeypatch):
    """The whole point of supervising the thread: a dead consumer must make
    the container unhealthy, not leave it running and silently idle."""

    failed = threading.Event()
    failed.set()
    monkeypatch.setattr(main, "_reembed_failed", failed)

    redis = FakeRedis()
    ctx = {"redis": redis, "settings": Settings(run_reembed_consumer=True)}

    result = await main.heartbeat_or_fail(ctx)

    assert result["heartbeat"] == "withheld"
    assert redis.sets == [], "no heartbeat may be written while the consumer is down"


async def test_heartbeat_ignores_consumer_when_it_is_disabled(monkeypatch):
    """Running the consumer as its own service is supported; the gate must
    not then withhold the scheduler's heartbeat."""

    failed = threading.Event()
    failed.set()
    monkeypatch.setattr(main, "_reembed_failed", failed)

    redis = FakeRedis()
    ctx = {"redis": redis, "settings": Settings(run_reembed_consumer=False)}

    result = await main.heartbeat_or_fail(ctx)
    assert result["heartbeat"] == Settings().heartbeat_key


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


async def test_drop_old_partitions_is_a_noop_without_retention():
    from app import jobs

    ctx = {"settings": Settings(interaction_retention_days=None)}
    result = await jobs.drop_old_partitions(ctx)
    assert "skipped" in result
