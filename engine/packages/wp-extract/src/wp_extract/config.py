from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from this file looking for the repo marker (ARCHITECTURE.md).

    Falls back to the fixed package-depth offset if the marker isn't found
    (e.g. package vendored/copied elsewhere), so this never hard-crashes.
    """
    here = (start or Path(__file__)).resolve()
    for parent in here.parents:
        if (parent / "ARCHITECTURE.md").is_file():
            return parent
    # engine/packages/wp-extract/src/wp_extract/config.py -> repo root
    return here.parents[5]


REPO_ROOT = find_repo_root()

# Table prefix is fixed for this one-shot extraction (nb15_) — see
# ARCHITECTURE.md §6. Not made configurable: there is exactly one source dump.
TABLE_PREFIX = "nb15_"


@dataclass(frozen=True)
class Config:
    db_host: str = os.environ.get("WP_EXTRACT_DB_HOST", "127.0.0.1")
    db_port: int = int(os.environ.get("WP_EXTRACT_DB_PORT", "13306"))
    db_name: str = os.environ.get("WP_EXTRACT_DB_NAME", "nowjakarta_wp")
    db_user: str = os.environ.get("WP_EXTRACT_DB_USER", "root")
    db_password: str = os.environ.get("WP_EXTRACT_DB_ROOT_PASSWORD", "wpextract_root")

    site_home: str = os.environ.get("WP_EXTRACT_SITE_HOME", "https://www.nowjakarta.co.id")

    output_dir: Path = Path(
        os.environ.get("WP_EXTRACT_OUTPUT_DIR", str(REPO_ROOT / "jakarta" / "content" / "extracted"))
    )

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir
