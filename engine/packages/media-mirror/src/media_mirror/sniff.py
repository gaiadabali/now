from __future__ import annotations

# Magic-byte sniffing so a soft-404 (an HTML/JSON error page served with
# HTTP 200 and an image extension — a documented, common failure mode) is
# caught even though the status line looks like success.

_SIGNATURES: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
    (b"GIF87a", "image/gif", "gif"),
    (b"GIF89a", "image/gif", "gif"),
    (b"BM", "image/bmp", "bmp"),
    (b"II*\x00", "image/tiff", "tiff"),
    (b"MM\x00*", "image/tiff", "tiff"),
]


def sniff_image(data: bytes) -> tuple[str, str] | None:
    """Return (mime, extension) if `data` is a real image by magic bytes."""
    if not data:
        return None
    for sig, mime, ext in _SIGNATURES:
        if data.startswith(sig):
            return mime, ext
    if len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", "webp"
    head = data[:512].lstrip()
    # Strip a UTF-8 BOM / leading XML declaration before checking for <svg.
    if head.startswith(b"\xef\xbb\xbf"):
        head = head[3:].lstrip()
    lowered = head.lower()
    if lowered.startswith(b"<?xml"):
        nl = lowered.find(b">")
        if nl != -1:
            lowered = lowered[nl + 1 :].lstrip()
    if lowered.startswith(b"<svg") or b"<svg" in data[:2048].lower():
        return "image/svg+xml", "svg"
    return None


def looks_like_error_page(data: bytes) -> bool:
    """Cheap heuristic: an HTML/JSON body where an image was expected."""
    head = data[:256].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html", b"{", b"["))
