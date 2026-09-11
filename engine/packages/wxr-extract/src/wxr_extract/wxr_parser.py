"""Streaming WXR (WordPress eXtended RSS) reader.

Uses `xml.etree.ElementTree.iterparse` and calls `elem.clear()` after each
top-level element is consumed, so a 145 MB export never becomes a full DOM
in memory. Verified against real exports under `jakarta/db/dumps/wxr/` and
`bali/db/dumps/wxr/` (see the package README / final report for the actual
element names — WXR versions vary and this was NOT guessed).

Namespaces confirmed by direct inspection of the real files:
  wp:      http://wordpress.org/export/1.2/
  content: http://purl.org/rss/1.0/modules/content/
  excerpt: http://wordpress.org/export/1.2/excerpt/
  dc:      http://purl.org/dc/elements/1.1/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

NS_WP = "{http://wordpress.org/export/1.2/}"
NS_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
NS_EXCERPT = "{http://wordpress.org/export/1.2/excerpt/}"
NS_DC = "{http://purl.org/dc/elements/1.1/}"


def _text(elem, tag: str) -> str | None:
    child = elem.find(tag)
    if child is None:
        return None
    return child.text


@dataclass
class WxrItem:
    """One <item> from a WXR export, fields renamed to plain Python names."""

    wp_id: int
    post_type: str
    status: str | None
    title: str | None
    slug: str | None
    content_html: str | None
    excerpt: str | None
    post_date: str | None
    post_date_gmt: str | None
    post_modified: str | None
    creator_login: str | None
    guid: str | None
    link: str | None
    attachment_url: str | None
    post_parent: int | None
    categories: list[tuple[str, str, str]]  # (domain, nicename, name)
    postmeta: dict[str, str]
    source_file: str


def parse_item(elem, source_file: str) -> WxrItem | None:
    post_id_text = _text(elem, NS_WP + "post_id")
    if post_id_text is None:
        return None

    categories: list[tuple[str, str, str]] = []
    postmeta: dict[str, str] = {}
    for child in elem:
        if child.tag == "category":
            domain = child.attrib.get("domain", "")
            nicename = child.attrib.get("nicename", "")
            name = child.text or ""
            categories.append((domain, nicename, name))
        elif child.tag == NS_WP + "postmeta":
            key = _text(child, NS_WP + "meta_key")
            meta_value_el = child.find(NS_WP + "meta_value")
            # Same empty-CDATA-vs-None issue as content_html/excerpt: a
            # present-but-empty <wp:meta_value> (e.g. Jakarta wp_id 5's
            # `_yoast_wpseo_primary_category`, which is `""` in the DB
            # dump, not absent) must come out as "" here too, or it would
            # spuriously diff against wp-extract's DB-sourced value.
            val = (meta_value_el.text or "") if meta_value_el is not None else None
            if key is not None:
                # WXR duplicates a meta_key only if WordPress itself stored
                # multiple rows for it (rare, e.g. multi-value custom
                # fields); last-write-wins here, matching wp-extract's
                # `fetch_postmeta`, which does the same via dict assignment
                # over a SQL row stream ordered by nothing in particular.
                postmeta[key] = val

    post_parent_text = _text(elem, NS_WP + "post_parent")
    post_parent = int(post_parent_text) if post_parent_text not in (None, "", "0") else None

    content_el = elem.find(NS_CONTENT + "encoded")
    excerpt_el = elem.find(NS_EXCERPT + "encoded")

    return WxrItem(
        wp_id=int(post_id_text),
        post_type=_text(elem, NS_WP + "post_type") or "",
        status=_text(elem, NS_WP + "status"),
        title=_text(elem, "title"),
        slug=_text(elem, NS_WP + "post_name"),
        # ElementTree gives `.text is None` for an empty CDATA section
        # (`<content:encoded><![CDATA[]]></content:encoded>`), but
        # wp-extract's contract — reading straight from the `post_content`
        # DB column, which WordPress never lets be NULL — always has a
        # string here, empty or not (verified: two real empty-body Jakarta
        # posts, wp_id 107626/108105, are `""` in the dump, not null).
        # Coerce to "" when the element is present so both extractors agree.
        content_html=(content_el.text or "") if content_el is not None else None,
        excerpt=(excerpt_el.text or "") if excerpt_el is not None else None,
        post_date=_text(elem, NS_WP + "post_date"),
        post_date_gmt=_text(elem, NS_WP + "post_date_gmt"),
        post_modified=_text(elem, NS_WP + "post_modified"),
        creator_login=_text(elem, NS_DC + "creator"),
        guid=_text(elem, "guid"),
        link=_text(elem, "link"),
        attachment_url=_text(elem, NS_WP + "attachment_url"),
        post_parent=post_parent,
        categories=categories,
        postmeta=postmeta,
        source_file=source_file,
    )


@dataclass
class ChannelMeta:
    """wp:author and wp:term blocks, which live at <channel> level (i.e.
    siblings of <item>, not inside it) and define authors + certain
    taxonomies (event_category/event-tag/nav_menu in the real exports —
    NOT category/post_tag, confirmed by direct inspection: no <wp:term>
    with taxonomy="category" or "post_tag" exists in either export; those
    taxonomies are only ever represented inline on each <item> via
    <category domain="category|post_tag" nicename="...">Name</category>,
    which carries no numeric term_id).
    """

    authors_by_login: dict[str, dict[str, Any]] = field(default_factory=dict)
    terms: list[dict[str, Any]] = field(default_factory=list)


def read_channel_meta(path: Path) -> ChannelMeta:
    """First pass: pull wp:author / wp:term blocks only. Cheap — these are
    small elements and there are at most a few dozen to a few hundred of
    them — done as its own streaming pass for simplicity and to avoid any
    dependence on element order within the channel.
    """
    meta = ChannelMeta()
    for _event, elem in _iterparse(path):
        if elem.tag == NS_WP + "author":
            login = _text(elem, NS_WP + "author_login")
            if login:
                meta.authors_by_login[login] = {
                    "wp_id": int(_text(elem, NS_WP + "author_id") or 0),
                    "login": login,
                    "email": _text(elem, NS_WP + "author_email"),
                    "display_name": _text(elem, NS_WP + "author_display_name"),
                    "first_name": _text(elem, NS_WP + "author_first_name"),
                    "last_name": _text(elem, NS_WP + "author_last_name"),
                }
            elem.clear()
        elif elem.tag == NS_WP + "term":
            meta.terms.append(
                {
                    "term_id": int(_text(elem, NS_WP + "term_id") or 0),
                    "taxonomy": _text(elem, NS_WP + "term_taxonomy"),
                    "slug": _text(elem, NS_WP + "term_slug"),
                    "parent": _text(elem, NS_WP + "term_parent") or None,
                    "name": _text(elem, NS_WP + "term_name"),
                }
            )
            elem.clear()
        elif elem.tag == "item":
            # Items are large; free them immediately in this pass since we
            # only want channel-level metadata here.
            elem.clear()
    return meta


def iter_items(path: Path) -> Iterator[WxrItem]:
    """Second pass: stream <item> elements, yielding one WxrItem at a time.

    Standard bounded-memory ElementTree idiom: only "end" events are
    requested, and each finished <item>'s subtree (its text and children —
    the megabytes-large `content:encoded`/postmeta payloads) is discarded
    via `elem.clear()` the moment it has been converted to a plain WxrItem.
    The empty <item> stub left behind under <channel> is a handful of bytes
    and does not grow with file size, unlike the content it held — this is
    what keeps peak RSS flat against a 145 MB file (measured in the final
    report, not assumed).
    """
    source_file = path.name
    for _event, elem in _iterparse(path):
        if elem.tag == "item":
            item = parse_item(elem, source_file)
            if item is not None:
                yield item
            elem.clear()


def _iterparse(path: Path):
    import xml.etree.ElementTree as ET

    for event, elem in ET.iterparse(str(path), events=("end",)):
        yield event, elem
