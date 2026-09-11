"""F52 (PROGRESS.md): `now_platform_db.settings` must read the project
`.env` the same way `now_db.settings` does after F31 -- explicit
`NOW_PG_*` env var > `.env` file (`POSTGRES_*` keys) > hardcoded default.

`test_load_env_file_reads_real_dotenv` exercises the real `_load_env_file()`
against a real temp `.env` (monkeypatching `settings.__file__` so the
module's own project-root walk lands on the temp tree). The precedence
tests monkeypatch the already-loaded `_ENV_FILE_VARS` dict directly, which
is exactly what `_load_env_file()` would have produced from a real file --
this keeps them focused on `_get_setting()`'s precedence logic rather than
re-exercising file I/O every time.
"""

from __future__ import annotations

import now_platform_db.settings as settings


def test_load_env_file_reads_real_dotenv(tmp_path, monkeypatch):
    """Real file, real parser -- not a re-description of the code."""
    module_path = tmp_path / "engine" / "packages" / "platform-db" / "src" / "now_platform_db" / "settings.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("# placeholder\n")
    (tmp_path / ".env").write_text("# a comment\nPOSTGRES_USER=filed\nPOSTGRES_PASSWORD=filed-pw\n\n")

    monkeypatch.setattr(settings, "__file__", str(module_path))
    assert settings._load_env_file() == {"POSTGRES_USER": "filed", "POSTGRES_PASSWORD": "filed-pw"}


def test_load_env_file_missing_file_returns_empty(tmp_path, monkeypatch):
    module_path = tmp_path / "engine" / "packages" / "platform-db" / "src" / "now_platform_db" / "settings.py"
    module_path.parent.mkdir(parents=True)
    module_path.write_text("# placeholder\n")
    # No .env written at tmp_path.

    monkeypatch.setattr(settings, "__file__", str(module_path))
    assert settings._load_env_file() == {}


def test_precedence_env_file_used_when_no_explicit_var(monkeypatch):
    """No NOW_PG_* set -> falls back to the .env file's POSTGRES_* values."""
    for key in ("NOW_PG_HOST", "NOW_PG_PORT", "NOW_PG_USER", "NOW_PG_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        settings, "_ENV_FILE_VARS", {"POSTGRES_USER": "filed", "POSTGRES_PASSWORD": "filed-pw", "POSTGRES_PORT": "25432"}
    )
    assert settings.pg_user() == "filed"
    assert settings.pg_password() == "filed-pw"
    assert settings.pg_port() == "25432"
    assert settings.pg_host() == settings.DEFAULT_HOST  # no POSTGRES_HOST in the file -> default


def test_precedence_explicit_env_var_wins_over_env_file(monkeypatch):
    """An explicit NOW_PG_* must override a conflicting .env file value --
    the exact precedence direction F31/F52 promise, and the one QA proved
    in the *failing* direction (a wrong explicit var breaks the connection
    rather than silently falling back to the working .env value)."""
    monkeypatch.setattr(settings, "_ENV_FILE_VARS", {"POSTGRES_USER": "filed", "POSTGRES_PASSWORD": "filed-pw"})
    monkeypatch.setenv("NOW_PG_PASSWORD", "explicit-pw")
    monkeypatch.delenv("NOW_PG_USER", raising=False)
    assert settings.pg_user() == "filed"  # untouched -> still from .env
    assert settings.pg_password() == "explicit-pw"  # explicit env var wins


def test_precedence_default_used_when_neither_present(monkeypatch):
    for key in ("NOW_PG_HOST", "NOW_PG_PORT", "NOW_PG_USER", "NOW_PG_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(settings, "_ENV_FILE_VARS", {})
    assert settings.pg_host() == settings.DEFAULT_HOST
    assert settings.pg_port() == settings.DEFAULT_PORT
    assert settings.pg_user() == settings.DEFAULT_USER
    assert settings.pg_password() == settings.DEFAULT_PASSWORD


def test_platform_database_url_composes_resolved_settings(monkeypatch):
    monkeypatch.delenv("NOW_PLATFORM_DATABASE_URL", raising=False)
    for key in ("NOW_PG_HOST", "NOW_PG_PORT", "NOW_PG_USER", "NOW_PG_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        settings, "_ENV_FILE_VARS", {"POSTGRES_USER": "filed", "POSTGRES_PASSWORD": "filed-pw", "POSTGRES_PORT": "25432"}
    )
    url = settings.platform_database_url()
    assert url == "postgresql+psycopg://filed:filed-pw@localhost:25432/now_platform"


def test_explicit_full_dsn_overrides_everything(monkeypatch):
    monkeypatch.setattr(settings, "_ENV_FILE_VARS", {"POSTGRES_USER": "filed", "POSTGRES_PASSWORD": "filed-pw"})
    monkeypatch.setenv("NOW_PLATFORM_DATABASE_URL", "postgresql+psycopg://x:y@otherhost:1/otherdb")
    assert settings.platform_database_url() == "postgresql+psycopg://x:y@otherhost:1/otherdb"
