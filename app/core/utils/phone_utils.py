"""Phone number normalization and validation utilities (E.164 standard)."""
from __future__ import annotations

import re

E164_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")


def normalize_phone_number(
    raw: str | None,
    *,
    default_country_code: str = "855",
) -> str | None:
    """Normalize a phone number to canonical E.164 format.

    Examples (for Cambodia +855):
        "+855069382165" -> "+85569382165"
        "+855 69 382 165" -> "+85569382165"
        "069382165" -> "+85569382165"
        "855069382165" -> "+85569382165"
        "85569382165" -> "+85569382165"
    """
    if raw is None:
        return None

    cleaned = raw.strip()
    if not cleaned:
        return None

    # Reject usernames, handles, or alphabetic strings masquerading as phone numbers
    if "@" in cleaned or any(ch.isalpha() for ch in cleaned):
        raise ValueError("Invalid phone number: must not contain letters or '@' handles")

    # Strip formatting characters (spaces, hyphens, parentheses, dots)
    compact = re.sub(r"[\s\-\(\)\.]", "", cleaned)

    # Convert international 00 prefix to +
    if compact.startswith("00"):
        compact = "+" + compact[2:]

    cc = default_country_code.lstrip("+")

    if compact.startswith("+"):
        # Strip trunk '0' immediately following the default country code (e.g. +855069382165 -> +85569382165)
        if compact.startswith(f"+{cc}0"):
            compact = f"+{cc}{compact[len(cc) + 2:]}"
    elif compact.startswith(f"{cc}0") and len(compact) >= len(cc) + 9:
        # e.g. 855069382165 -> +85569382165
        compact = f"+{cc}{compact[len(cc) + 1:]}"
    elif compact.startswith(cc) and len(compact) >= len(cc) + 8:
        # e.g. 85569382165 -> +85569382165
        compact = f"+{compact}"
    elif compact.startswith("0") and 8 <= len(compact) <= 11:
        # Local format with leading trunk 0 (e.g. 069382165 -> +85569382165)
        compact = f"+{cc}{compact.lstrip('0')}"
    elif compact.isdigit() and 8 <= len(compact) <= 10:
        # Local subscriber digits without leading 0
        compact = f"+{cc}{compact}"

    if not E164_REGEX.match(compact):
        raise ValueError(f"Invalid phone number format: '{raw}'")

    return compact


def get_equivalent_phone_formats(
    raw: str,
    *,
    default_country_code: str = "855",
) -> list[str]:
    """Return canonical E.164 and common equivalent representations for lookup."""
    normalized = normalize_phone_number(raw, default_country_code=default_country_code)
    if not normalized:
        return []

    cc = default_country_code.lstrip("+")
    variants: list[str] = [normalized]

    if normalized.startswith(f"+{cc}"):
        national = normalized[len(cc) + 1 :]
        for candidate in (
            f"+{cc}0{national}",
            f"0{national}",
            f"{cc}{national}",
            f"{cc}0{national}",
        ):
            if candidate not in variants:
                variants.append(candidate)

    raw_trimmed = raw.strip()
    if raw_trimmed and raw_trimmed not in variants:
        variants.append(raw_trimmed)

    return variants

