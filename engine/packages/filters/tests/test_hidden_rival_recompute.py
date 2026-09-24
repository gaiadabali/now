"""`now_filters.hidden_rival_recompute` -- the pure-logic half (pattern
compilation), no Postgres. The DB-integration half (actually reading
`place_mentions`/`articles` and writing `engine.hidden_rival_flags`) needs
a live city DB and is not covered here -- flagged as a gap in the ticket
report; `test_hidden_rival_lexicon.py` and `test_hidden_rival_guard.py`
cover the matching logic and the consuming predicate respectively, so this
module's only genuinely untested seam is the read/write plumbing itself.
"""

from __future__ import annotations

from now_filters.hidden_rival import default_lexicon
from now_filters.hidden_rival_recompute import _compiled_patterns


def test_compiled_patterns_match_the_same_way_as_the_postgres_pattern():
    lexicon = default_lexicon()
    patterns = _compiled_patterns(["stay", "drink"], lexicon)
    assert patterns["stay"].search("The Westin Resort Nusa Dua, Bali")
    assert not patterns["stay"].search("Celebrate Wellness 2026")
    # The `club` curation must survive the Python-regex translation too.
    assert not patterns["drink"].search("Royale Jakarta Golf Club")
    assert patterns["drink"].search("Potato Head Beach Club")


def test_compiled_patterns_skip_types_with_no_lexicon_entries():
    patterns = _compiled_patterns(["unknown"], default_lexicon())
    assert "unknown" not in patterns
