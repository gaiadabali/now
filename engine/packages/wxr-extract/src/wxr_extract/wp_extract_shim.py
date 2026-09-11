"""Import bridge to `now-wp-extract`'s PHP-deserialiser.

The ticket for this package is explicit: reuse wp-extract's deserialiser by
importing it rather than rewriting PHP-unserialize logic. wp-extract is a
sibling package (`engine/packages/wp-extract/src/wp_extract`) that is not on
sys.path by default in a plain venv for wxr-extract, so this module locates
its `src/` directory relative to this file and inserts it once, then
re-exports the two functions we need.

This is read-only: we only ever import from wp_extract, never write to it,
and this file lives entirely inside engine/packages/wxr-extract/ (in scope).
"""

from __future__ import annotations

import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
# engine/packages/wxr-extract/src/wxr_extract/wp_extract_shim.py
#   -> engine/packages/wp-extract/src
_WP_EXTRACT_SRC = _THIS_FILE.parents[3] / "wp-extract" / "src"

if not _WP_EXTRACT_SRC.is_dir():
    raise ImportError(
        f"Expected to find now-wp-extract's source at {_WP_EXTRACT_SRC}, "
        "but it does not exist. wxr-extract requires wp-extract as a sibling "
        "package to reuse its PHP deserialiser."
    )

if str(_WP_EXTRACT_SRC) not in sys.path:
    sys.path.insert(0, str(_WP_EXTRACT_SRC))

from wp_extract.phpunserialize import php_unserialize, extract_lat_lng  # noqa: E402
from wp_extract.extract.articles import ARTICLE_META_KEYS  # noqa: E402
from wp_extract.extract.attachments import ATTACHMENT_META_KEYS  # noqa: E402

__all__ = [
    "php_unserialize",
    "extract_lat_lng",
    "ARTICLE_META_KEYS",
    "ATTACHMENT_META_KEYS",
]
