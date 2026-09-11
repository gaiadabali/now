from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def articles_sample_path() -> Path:
    return FIXTURES_DIR / "articles_sample.jsonl"


@pytest.fixture
def taxonomy_sample_path() -> Path:
    return FIXTURES_DIR / "taxonomy_mapping_sample.json"


@pytest.fixture
def gsc_export_sample_path() -> Path:
    return FIXTURES_DIR / "gsc_export_sample.csv"


@pytest.fixture
def permalink_map_sample_path() -> Path:
    return FIXTURES_DIR / "permalink_map_sample.jsonl"
