"""E1.2 — HTML -> blocks cleaner.

Public API:

    clean_article(article: dict) -> CleanResult

See `now_content_clean.pipeline` for the implementation and
`now_content_clean.models` for the block / link / upload shapes.
"""

from now_content_clean.pipeline import clean_article, clean_html
from now_content_clean.models import CleanResult

__all__ = ["clean_article", "clean_html", "CleanResult"]
