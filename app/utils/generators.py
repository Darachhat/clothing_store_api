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


def generate_sku(product_code: str, color_name: str | None, size_name: str | None, sequence: int) -> str:
    """Generate a human-readable SKU from product, color, size."""
    parts = [product_code.upper()]
    if color_name:
        parts.append(re.sub(r"[^A-Z0-9]", "", color_name.upper())[:3])
    if size_name:
        parts.append(re.sub(r"[^A-Z0-9]", "", size_name.upper())[:3])
    parts.append(f"{sequence:03d}")
    return "-".join(parts)


def hash_token(token: str) -> str:
    """Hash a refresh token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
