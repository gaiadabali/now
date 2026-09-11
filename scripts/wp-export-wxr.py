#!/usr/bin/env python3
"""Pull a full-fidelity WXR export from a live NOW! WordPress site.

Why this exists
---------------
``scripts/wp-dump.sh`` is the better tool — a real ``mysqldump`` — but it
needs SSH, which on Hostinger must be enabled per-account and uses a password
separate from the hPanel login. This script needs only the wp-admin
credentials, and it reaches the two things the REST harvest cannot:

* **raw ``post_content``** — the actual column, not ``the_content`` output
* **every ``postmeta`` row** — Yoast focus keywords, ACF fields, MapPress geo

That is precisely the gap recorded as F37 / blocker B1.

What it still does not reach (only mysqldump does):

* the ``options`` table
* plugin tables — notably Redirection's, which holds the legacy redirect map
* users' password hashes (which you do not want anyway)
* the files in ``wp-content/uploads``

Usage
-----
    export WP_ADMIN_USER=...
    export WP_ADMIN_PASSWORD=...
    export WP_BASE_URL_BALI=https://www.example.co.id

    python scripts/wp-export-wxr.py --site bali
    python scripts/wp-export-wxr.py --site bali --chunk-years
    python scripts/wp-export-wxr.py --site bali --content posts,attachment

Output lands in ``<site>/db/dumps/wxr/`` (gitignored) with a manifest.

Read-only: it logs in and issues GETs. WordPress generates the export on the
fly and writes nothing persistent.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from http.cookiejar import CookieJar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    Request,
    build_opener,
)
from xml.etree import ElementTree

# Stdlib only, deliberately: this is a standalone script in scripts/, so it
# has to run with whatever Python is on the machine — no venv, no install.

# A Windows console defaults to cp1252 and would turn every em dash in the
# messages below into a replacement character.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

UA = "NOWEngineMigration/0.1 (+migration tooling; read-only)"
DENIED = ("Sorry, you are not allowed", "You do not have sufficient permissions")


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "ARCHITECTURE.md").is_file():
            return parent
    return here.parents[1]


def env_base_url(slug: str) -> str | None:
    key = "WP_BASE_URL_" + slug.upper().replace("-", "_")
    value = os.environ.get(key)
    return value.rstrip("/") if value else None


class AdminSession:
    """A logged-in wp-admin session. Issues GETs only, after the login POST."""

    def __init__(self, base_url: str, user: str, password: str) -> None:
        self.base = base_url.rstrip("/")
        self.jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.jar), HTTPRedirectHandler())
        self.opener.addheaders = [("User-Agent", UA)]
        self._login(user, password)

    # ---- transport -----------------------------------------------------

    def _open(self, url: str, data: bytes | None = None, referer: str | None = None):
        request = Request(url, data=data, method="POST" if data else "GET")
        if referer:
            request.add_header("Referer", referer)
        if data:
            request.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            return self.opener.open(request, timeout=180)
        except HTTPError as exc:
            return exc  # a 4xx/5xx body is informative; read it rather than raise
        except URLError as exc:
            raise SystemExit(f"network error for {url}: {exc.reason}") from exc

    def _get_text(self, path: str, params: dict[str, str] | None = None) -> tuple[int, str]:
        url = f"{self.base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        response = self._open(url)
        body = response.read().decode("utf-8", "replace")
        return response.status if hasattr(response, "status") else response.code, body

    def _logged_in(self) -> bool:
        return any(c.name.startswith("wordpress_logged_in") for c in self.jar)

    # ---- login ---------------------------------------------------------

    def _login(self, user: str, password: str) -> None:
        payload = urlencode(
            {
                "log": user,
                "pwd": password,
                "wp-submit": "Log In",
                "redirect_to": f"{self.base}/wp-admin/",
                "testcookie": "1",
            }
        ).encode()
        response = self._open(
            f"{self.base}/wp-login.php", data=payload, referer=f"{self.base}/wp-login.php"
        )
        body = response.read().decode("utf-8", "replace")
        if not self._logged_in():
            hint = ""
            match = re.search(r'<div id="login_error">(.*?)</div>', body, re.S)
            if match:
                hint = " — " + " ".join(re.sub(r"<[^>]+>", " ", match.group(1)).split())[:180]
            raise SystemExit(f"wp-admin login failed{hint}")

    # ---- export --------------------------------------------------------

    def export_form(self) -> tuple[list[str], str | None]:
        """Return the offered `content` values and the export nonce, if any."""
        status, body = self._get_text("/wp-admin/export.php")
        if status != 200 or any(d in body for d in DENIED):
            raise SystemExit(
                "export.php is not accessible with this account. The `export` "
                "capability belongs to Administrator; an Editor cannot use it. "
                "Either use an admin account, or take the mysqldump route "
                "(scripts/wp-dump.sh)."
            )
        contents = list(dict.fromkeys(re.findall(r'name="content"\s+value="([a-z_-]+)"', body)))
        nonce = re.search(r'name="_wpnonce"[^>]*value="([a-f0-9]+)"', body)
        return contents, (nonce.group(1) if nonce else None)

    def download(self, params: dict[str, str], destination: Path) -> int:
        """Stream one export to disk. Returns bytes written."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self.base}/wp-admin/export.php?{urlencode(params)}"
        response = self._open(url)
        status = response.status if hasattr(response, "status") else response.code
        if status != 200:
            raise SystemExit(f"export returned HTTP {status}")
        ctype = response.headers.get("Content-Type", "")

        written = 0
        with destination.open("wb") as handle:
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                handle.write(chunk)
                written += len(chunk)

        if "xml" not in ctype and written < 4096:
            head = destination.read_bytes()[:400].decode("utf-8", "replace")
            raise SystemExit(
                f"export did not return XML (content-type {ctype!r}, {written} bytes). "
                f"First bytes: {head}"
            )
        return written

    def close(self) -> None:
        self.opener.close() if hasattr(self.opener, "close") else None


# XML 1.0 forbids the C0 control characters except tab, LF and CR. WordPress
# does not strip them on export, so a single stray 0x03 pasted into a post
# years ago makes the whole year's export unparseable. In UTF-8 these bytes
# never occur as part of a multi-byte sequence, so removing them at the byte
# level cannot corrupt neighbouring characters.
ILLEGAL_XML_BYTES = frozenset(
    set(range(0x00, 0x20)) - {0x09, 0x0A, 0x0D}
)


def repair_illegal_chars(path: Path) -> dict[str, object]:
    """Strip XML-illegal control bytes in place, reporting exactly what went.

    Deliberately explicit rather than silent: the report names every byte
    removed and the text around it, so a human can confirm nothing meaningful
    was lost. These bytes carry no meaning in prose — they are paste
    artefacts — but that is a judgement worth showing rather than assuming.
    """
    data = path.read_bytes()
    offsets = [i for i, b in enumerate(data) if b in ILLEGAL_XML_BYTES]
    if not offsets:
        return {"removed": 0}

    samples = []
    for offset in offsets[:10]:
        around = data[max(0, offset - 45) : offset + 45]
        samples.append(
            {
                "offset": offset,
                "byte": f"0x{data[offset]:02x}",
                "context": around.decode("utf-8", "replace").replace("\n", " "),
            }
        )

    cleaned = bytes(b for b in data if b not in ILLEGAL_XML_BYTES)
    path.write_bytes(cleaned)
    return {
        "removed": len(offsets),
        "bytes": sorted({f"0x{data[o]:02x}" for o in offsets}),
        "samples": samples,
    }


def verify(path: Path) -> dict[str, object]:
    """Confirm the WXR parses, and count what it actually contains.

    A truncated export — the usual failure on shared hosting, where PHP is
    killed mid-stream — still *looks* like a large plausible file. Parsing is
    the only way to know, so it is not optional.
    """
    result: dict[str, object] = {"file": path.name, "bytes": path.stat().st_size}
    try:
        tree = ElementTree.parse(path)
    except ElementTree.ParseError as exc:
        result["parses"] = False
        result["error"] = f"{exc} — the export is almost certainly truncated"
        return result

    root = tree.getroot()
    items = [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "item"]
    result["parses"] = True
    result["items"] = len(items)

    def local(el: ElementTree.Element, name: str) -> str | None:
        for child in el:
            if child.tag.rsplit("}", 1)[-1] == name:
                return child.text
        return None

    types: dict[str, int] = {}
    with_meta = 0
    raw_content = 0
    for item in items:
        post_type = local(item, "post_type") or "?"
        types[post_type] = types.get(post_type, 0) + 1
        tags = {child.tag.rsplit("}", 1)[-1] for child in item}
        if "postmeta" in tags:
            with_meta += 1
        if "encoded" in tags:
            raw_content += 1

    result["by_post_type"] = dict(sorted(types.items(), key=lambda kv: -kv[1]))
    result["items_with_postmeta"] = with_meta
    result["items_with_content"] = raw_content
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", required=True, help="site slug; output goes to <slug>/db/dumps/wxr")
    parser.add_argument("--base-url", default=None, help="overrides WP_BASE_URL_<SLUG>")
    parser.add_argument(
        "--content",
        default="all",
        help="comma-separated export sets, or 'all' (default). Use 'discover' to just list them.",
    )
    parser.add_argument(
        "--chunk-years",
        action="store_true",
        help="export posts one year at a time — use when a full export times out",
    )
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    slug = args.site
    if not re.match(r"^[a-z][a-z0-9-]*$", slug):
        return int(bool(sys.stderr.write(f"invalid site slug: {slug!r}\n"))) or 2

    base = args.base_url or env_base_url(slug)
    if not base:
        key = "WP_BASE_URL_" + slug.upper().replace("-", "_")
        print(f"error: no base URL — pass --base-url or set {key}", file=sys.stderr)
        return 2

    user = os.environ.get("WP_ADMIN_USER")
    password = os.environ.get("WP_ADMIN_PASSWORD")
    if not user or not password:
        print("error: set WP_ADMIN_USER and WP_ADMIN_PASSWORD in the environment", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir) if args.out_dir else repo_root() / slug / "db" / "dumps" / "wxr"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    print(f"==> {slug}: logging in to {base}/wp-admin/")
    session = AdminSession(base, user, password)
    try:
        offered, nonce = session.export_form()
        print(f"==> exportable sets: {', '.join(offered) or '(none parsed)'}")
        print(f"==> nonce: {'present' if nonce else 'not required'}")
        if args.content == "discover":
            return 0

        wanted = [c.strip() for c in args.content.split(",") if c.strip()]
        unknown = [c for c in wanted if offered and c not in offered]
        if unknown:
            print(f"warning: not offered by this site: {', '.join(unknown)}", file=sys.stderr)

        jobs: list[tuple[str, dict[str, str], Path]] = []
        for content in wanted:
            if content == "posts" and args.chunk_years:
                # WordPress accepts YYYY-MM bounds on the posts export. One
                # year per request keeps each response inside PHP's time and
                # memory limits, which a 4,000-post single export will not be.
                this_year = datetime.now(UTC).year
                for year in range(2010, this_year + 1):
                    # post_status must be EMPTY for "any status". export.php
                    # passes the value straight into
                    # `AND post_status = %s`, so "all" is matched literally
                    # and returns nothing at all. cat/post_author use 0 for
                    # "any" because export.php tests them for truthiness.
                    params = {
                        "download": "true",
                        "content": "posts",
                        "cat": "0",
                        "post_author": "0",
                        "post_start_date": f"{year}-01",
                        "post_end_date": f"{year}-12",
                        "post_status": "",
                    }
                    if nonce:
                        params["_wpnonce"] = nonce
                    jobs.append((f"posts-{year}", params, out_dir / f"{slug}-posts-{year}-{stamp}.xml"))
            else:
                params = {"download": "true", "content": content}
                if content == "posts":
                    params |= {"cat": "0", "post_author": "0", "post_status": ""}
                if nonce:
                    params["_wpnonce"] = nonce
                jobs.append((content, params, out_dir / f"{slug}-{content}-{stamp}.xml"))

        manifest: list[dict[str, object]] = []
        for label, params, dest in jobs:
            print(f"==> {slug}: exporting {label} ...", flush=True)
            try:
                written = session.download(params, dest)
            except SystemExit as exc:
                print(f"    FAILED: {exc}", file=sys.stderr)
                manifest.append({"set": label, "error": str(exc)})
                continue
            report = verify(dest)
            if report.get("parses") is False:
                # Most likely a stray control byte, not a truncated download.
                # Try the targeted repair before calling the export a failure.
                repair = repair_illegal_chars(dest)
                if repair["removed"]:
                    print(
                        f"    repaired: stripped {repair['removed']} XML-illegal "
                        f"byte(s) {', '.join(repair['bytes'])}"
                    )
                    for sample in repair["samples"][:3]:
                        print(f"      at {sample['offset']}: …{sample['context'].strip()}…")
                    report = verify(dest)
                    report["repair"] = repair
            report["set"] = label
            manifest.append(report)
            if report.get("parses"):
                print(
                    f"    {written / 2**20:,.1f} MB, {report['items']:,} items, "
                    f"{report['items_with_postmeta']:,} with postmeta"
                )
            else:
                print(f"    {written / 2**20:,.1f} MB but INVALID XML: {report.get('error')}", file=sys.stderr)

        empty = [m for m in manifest if m.get("items") == 0 and "error" not in m]
        for m in empty:
            print(f"note: {m['set']} exported 0 items (nothing in that range)", file=sys.stderr)

        # A single empty year is ordinary. *Every* export coming back empty is
        # a bad request being served as a valid, well-formed, useless file —
        # which is what `post_status=all` did, silently, until it was caught.
        total_items = sum(int(m.get("items", 0)) for m in manifest if "error" not in m)
        if manifest and total_items == 0:
            print(
                "\nERROR: every export returned 0 items. That is a malformed query,"
                "\nnot an empty site — check the export parameters before trusting"
                "\nany file written by this run.",
                file=sys.stderr,
            )
            return 1

        mpath = out_dir / f"{slug}-wxr-manifest-{stamp}.json"
        mpath.write_text(
            json.dumps(
                {
                    "site": slug,
                    "base_url": base,
                    "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "offered_sets": offered,
                    "exports": manifest,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"==> manifest: {mpath}")

        bad = [m for m in manifest if "error" in m or m.get("parses") is False]
        if bad:
            print(f"\n{len(bad)} of {len(manifest)} exports failed — see the manifest.", file=sys.stderr)
            print("If they timed out, retry with --chunk-years.", file=sys.stderr)
            return 1
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
