"""How `Settings` reads the environment, for the one field where it matters.

`extra_allowed_origins` is the only complex-typed setting this service reads
from an environment variable, and it is temporary by design: it exists until
the DNS cutover and is then meant to be deleted (DEPLOY.md section 8). So
"someone empties it and redeploys" is the normal end of its life rather than
an edge case, and these tests pin the behaviour that makes that safe.

Why it needs pinning at all: pydantic-settings decodes a complex field from
the environment as JSON *before* validators run, so with the plain annotation
a blank value is not "unset" — it is malformed JSON, and the app dies at
import. A compose `${VAR:-}` default or a `.env` line left as `VAR=` produces
exactly that. Verified against the real `Settings` before the fix:

    SettingsError: error parsing value for field "extra_allowed_origins"
                   from source "EnvSettingsSource"

These run against the real class rather than `make_test_settings`, because the
thing under test is the environment-source decoding that the test helper's
keyword overrides bypass entirely.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

VAR = "ENGINE_API_EXTRA_ALLOWED_ORIGINS"
REAL = '{"jakarta":["https://now-jakarta.gaiada.com"],"bali":["https://now-bali.gaiada.com"]}'


@pytest.mark.parametrize("value", ["", "   ", "{}"], ids=["blank", "whitespace", "empty-json"])
def test_empty_value_means_no_extra_origins(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """Blank is none. The API must boot, not crash, when the variable is emptied."""
    monkeypatch.setenv(VAR, value)
    assert Settings().extra_allowed_origins == {}


def test_unset_means_no_extra_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VAR, raising=False)
    assert Settings().extra_allowed_origins == {}


def test_real_value_parses_per_site(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAR, REAL)
    assert Settings().extra_allowed_origins == {
        "jakarta": ["https://now-jakarta.gaiada.com"],
        "bali": ["https://now-bali.gaiada.com"],
    }


def test_malformed_value_still_refuses_to_boot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tolerant of blank, and of nothing else.

    A misspelt allowlist is a security control that silently does not apply.
    Failing at startup is the correct outcome — it is loud, it is immediate,
    and `deploy.sh` fails the rollout on it rather than leaving a stack up that
    collects nothing and says why to no one.
    """
    monkeypatch.setenv(VAR, "{not json")
    with pytest.raises(ValidationError):
        Settings()
