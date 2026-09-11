from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "articles_sample.jsonl"


def _load_fixtures() -> list[dict]:
    with FIXTURES_PATH.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="session")
def articles() -> list[dict]:
    return _load_fixtures()


@pytest.fixture(scope="session")
def articles_by_id(articles) -> dict[int, dict]:
    return {a["wp_id"]: a for a in articles}
