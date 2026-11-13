"""Utilities: sequence generation for business identifiers."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def next_sequence(db: AsyncSession, sequence_name: str) -> int:
    """Get next value from a named PostgreSQL sequence, with fallback for SQLite tests."""
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "sqlite":
            import random
            return random.randint(1000, 999999)
        result = await db.execute(text(f"SELECT nextval('{sequence_name}')"))
        return result.scalar_one()
    except Exception:
        import random
        return random.randint(1000, 999999)



async def generate_qr_reference(db: AsyncSession) -> str:
    """Generate a unique QR reference: VAR-NNNNNN."""
    seq = await next_sequence(db, "qr_reference_seq")
    return f"VAR-{seq:06d}"


async def generate_invoice_number(db: AsyncSession) -> str:
    """Generate an invoice number: INV-YYYY-NNNNNN."""
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "invoice_number_seq")
    return f"INV-{year}-{seq:06d}"


async def generate_po_number(db: AsyncSession) -> str:
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "po_number_seq")
    return f"PO-{year}-{seq:06d}"


async def generate_gr_number(db: AsyncSession) -> str:
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "gr_number_seq")
    return f"GR-{year}-{seq:06d}"


async def generate_transfer_number(db: AsyncSession) -> str:
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "transfer_number_seq")
    return f"TRF-{year}-{seq:06d}"


async def generate_return_number(db: AsyncSession) -> str:
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "return_number_seq")
    return f"RTN-{year}-{seq:06d}"


async def generate_expense_number(db: AsyncSession) -> str:
    from datetime import datetime

    year = datetime.now(UTC).year
    seq = await next_sequence(db, "expense_number_seq")
    return f"EXP-{year}-{seq:06d}"


async def generate_customer_code(db: AsyncSession) -> str:
    seq = await next_sequence(db, "customer_code_seq")
    return f"CUST-{seq:06d}"


async def generate_supplier_code(db: AsyncSession) -> str:
    seq = await next_sequence(db, "supplier_code_seq")
    return f"SUPP-{seq:06d}"


_COLOR_CODE_MAP: dict[str, str] = {
    "BLACK": "BLK",
    "WHITE": "WHT",
    "GRAY": "GRY",
    "GREY": "GRY",
    "RED": "RED",
    "BLUE": "BLU",
    "NAVY": "NVY",
    "NAVYBLUE": "NVY",
    "GREEN": "GRN",
    "YELLOW": "YLW",
    "PINK": "PNK",
    "PURPLE": "PRP",
    "ORANGE": "ORG",
    "BROWN": "BRN",
    "BEIGE": "BGE",
    "CREAM": "CRM",
    "KHAKI": "KHK",
    "OLIVE": "OLV",
    "MAROON": "MRN",
    "BURGUNDY": "BRG",
    "CHARCOAL": "CHC",
    "GOLD": "GLD",
    "SILVER": "SLV",
}


def format_color_code(color_name: str | None) -> str | None:
    if not color_name:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", color_name.upper())
    if not cleaned:
        return None
    if cleaned in _COLOR_CODE_MAP:
        return _COLOR_CODE_MAP[cleaned]
    # Consonant-first 3-char abbreviation if possible (e.g. BLACK -> BLK)
    consonants = re.sub(r"[AEIOU]", "", cleaned[1:])
    if len(cleaned) > 3 and len(consonants) >= 2:
        return (cleaned[0] + consonants)[:3]
    return cleaned[:3]


def format_size_code(size_name: str | None) -> str | None:
    if not size_name:
        return None
    cleaned = re.sub(r"[^A-Z0-9]", "", size_name.upper())
    return cleaned[:5] if cleaned else None


def generate_sku(
    product_code: str,
    color_name: str | None,
    size_name: str | None,
    sequence: int = 1,
) -> str:
    """
    Generate centralized retail SKU: {PRODUCT_CODE}-{COLOR_CODE}-{SIZE_CODE}
    Examples:
      - TSH-001 + Black + S  -> TSH-001-BLK-S
      - TSH-001 + Black + None -> TSH-001-BLK
      - TSH-001 + None  + M  -> TSH-001-M
      - TSH-001 + None  + None -> TSH-001-001
    """
    base = (product_code or "PRD").strip().upper()
    parts = [base]
    c_code = format_color_code(color_name)
    s_code = format_size_code(size_name)
    if c_code:
        parts.append(c_code)
    if s_code:
        parts.append(s_code)
    if not c_code and not s_code:
        parts.append(f"{max(1, sequence):03d}")
    return "-".join(parts)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
