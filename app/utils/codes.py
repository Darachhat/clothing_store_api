"""Utilities for normalizing scanned barcode/QR strings and generating compact barcodes."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urlparse


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\ufeff]+")
_PRODUCT_PATH_RE = re.compile(r"(?:^|/+)p/([^/?#&\s]+)", re.IGNORECASE)


def normalize_scanned_code(raw: str | None) -> str:
    """
    Normalize any raw scanned input (1D barcode, 2D QR URL, SKU, QR reference, or Product code)
    into a canonical lookup token.
    """
    if not raw:
        return ""

    cleaned = _CONTROL_CHARS_RE.sub("", str(raw)).strip()
    if not cleaned:
        return ""

    # Unquote percent-encoded characters if present
    if "%" in cleaned:
        try:
            cleaned = unquote(cleaned).strip()
        except Exception:
            pass

    # Handle keyboard-wedge damaged URLs where ':' was sent as ';' (e.g. https;//domain/p/VAR-000001)
    normalized_url_candidate = re.sub(r"^(https?);(//)", r"\1:\2", cleaned, flags=re.IGNORECASE)

    # Check if input contains /p/<reference> path (used by 2D QR stickers)
    path_match = _PRODUCT_PATH_RE.search(normalized_url_candidate)
    if path_match:
        token = path_match.group(1).strip()
        if token:
            return token

    # Check if input is a URL with query parameters (?code=..., ?barcode=..., ?sku=..., ?qr=...)
    if (
        normalized_url_candidate.lower().startswith(("http://", "https://"))
        or "?" in normalized_url_candidate
    ):
        try:
            parsed = urlparse(
                normalized_url_candidate
                if "://" in normalized_url_candidate
                else f"https://placeholder.local/{normalized_url_candidate.lstrip('/')}"
            )
            qs = parse_qs(parsed.query)
            for key in ("code", "barcode", "sku", "qr", "ref", "reference"):
                if key in qs and qs[key]:
                    val = qs[key][0].strip()
                    if val:
                        return val
            # Fallback to last non-empty path segment if it looks like a code
            segments = [seg.strip() for seg in parsed.path.split("/") if seg.strip()]
            if segments and parsed.scheme in ("http", "https") and len(segments) >= 1:
                last_seg = segments[-1]
                if last_seg.lower() not in ("p", "products", "scan", "pos"):
                    return last_seg
        except Exception:
            pass

    return cleaned


def generate_compact_barcode(product_code: str, variant_seq: int = 1) -> str:
    """
    Generate a compact 10-digit numeric barcode (Code-128C double-density compatible).
    Format: 885 + 5-digit product number + 2-digit variant sequence (e.g. '8850002401').
    Because it has an even number of digits (10), Code-128 encodes it in Subset C
    (2 digits per symbol), making thermal sticker bars half as wide and ultra-scannable.
    """
    digits = re.sub(r"\D", "", product_code or "")
    prod_num = int(digits) if digits else 1
    seq_num = max(1, int(variant_seq))
    if seq_num < 100:
        return f"885{prod_num:05d}{seq_num:02d}"
    return f"885{prod_num:05d}{seq_num:04d}"

